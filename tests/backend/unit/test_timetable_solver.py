"""Working a timetable out: it must be possible in real life, or refused in words.

Ported on 2026-08-12 from the standalone timetable builder Abhimanyu supplied. The
tests that matter most are not "does it produce a grid" - almost anything produces a
grid. They are:

  1. **A teacher is never in two classrooms at once.** The original solver only
     checked clashes inside the one timetable it was building, which is safe for a
     tool that knows about one class. This school shares its teachers across 48
     classes, and the substitution plan reads these rows to work out who is free when
     somebody is away. A timetable that double-books a teacher is not merely untidy:
     it sends a cover teacher to a room where they are already teaching.

  2. **An impossible request is refused in words the office can act on**, before eight
     seconds of searching. "Nobody is set up to teach Hindi" can be fixed in a minute.
     "Could not find a timetable" cannot.

  3. **Nothing is ever half-placed.** A timetable with a quietly empty period is a
     class of children with nobody in front of them, and it is this release's defining
     fault in the place it does the most harm.
"""

from __future__ import annotations

import pytest

from services import timetable_solver as solver

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def _subject(sid, name, per_week, morning=False):
    return solver.Subject(id=sid, name=name, periods_per_week=per_week, prefer_morning=morning)


def _teacher(tid, name, subject_ids, preferred=None):
    return solver.Teacher(id=tid, name=name, subject_ids=list(subject_ids),
                          preferred=set(preferred or []))


def _request(**over):
    base = dict(
        days=list(DAYS),
        periods_per_day=6,
        subjects=[
            _subject("maths", "Mathematics", 6),
            _subject("english", "English", 5),
            _subject("hindi", "Hindi", 4),
            _subject("science", "Science", 5),
        ],
        teachers=[
            _teacher("t-maths", "Sharma", ["maths"]),
            _teacher("t-eng", "Patel", ["english"]),
            _teacher("t-hindi", "Verma", ["hindi"]),
            _teacher("t-sci", "Khan", ["science"]),
        ],
    )
    base.update(over)
    return solver.TimetableRequest(**base)


# ── It produces a week that adds up ──────────────────────────────────────────

def test_every_period_asked_for_is_placed_exactly_that_many_times():
    result = solver.generate(_request(), seed=1)

    assert result["solved"] is True
    counts = {}
    for slot in result["slots"]:
        counts[slot["subject_id"]] = counts.get(slot["subject_id"], 0) + 1
    # Not "roughly". A subject short of a period is a lesson the class never gets.
    assert counts == {"maths": 6, "english": 5, "hindi": 4, "science": 5}


def test_a_class_never_has_two_subjects_in_one_period():
    result = solver.generate(_request(), seed=2)
    seen = [(s["day"], s["period_number"]) for s in result["slots"]]
    assert len(seen) == len(set(seen))


def test_periods_are_numbered_from_one_like_the_rest_of_the_platform():
    result = solver.generate(_request(), seed=3)
    numbers = {s["period_number"] for s in result["slots"]}
    assert min(numbers) == 1
    assert max(numbers) <= 6


def test_a_break_is_left_empty():
    breaks = {(day, 3) for day in DAYS}  # the fourth period every day
    result = solver.generate(_request(breaks=breaks), seed=4)

    assert result["solved"] is True
    assert all(s["period_number"] != 4 for s in result["slots"])


# ── A teacher is never in two classrooms at once ─────────────────────────────

def test_a_teacher_already_teaching_another_class_is_not_booked_again():
    """THE CHANGE THAT HAD TO BE MADE for this to work in a real school.

    Sharma is teaching another class every Monday. The generated timetable must not
    put Mathematics on a Monday, because there is nobody else to teach it.
    """
    busy = {"t-maths": {("Monday", p) for p in range(6)}}
    result = solver.generate(_request(busy_teacher_slots=busy), seed=5)

    assert result["solved"] is True
    monday_maths = [s for s in result["slots"] if s["day"] == "Monday" and s["subject_id"] == "maths"]
    assert monday_maths == []


def test_the_polish_pass_cannot_undo_that():
    """The local search swaps pairs of lessons to improve the score. If it forgot to
    re-check who is busy elsewhere, it would quietly put back the very clash the
    search was careful to avoid - and nothing downstream would notice until a cover
    teacher was sent to the wrong room."""
    busy = {"t-maths": {("Monday", p) for p in range(6)}}
    for seed in range(6):
        result = solver.generate(_request(busy_teacher_slots=busy), seed=seed)
        assert result["solved"] is True
        for slot in result["slots"]:
            assert (slot["day"], slot["period_number"] - 1) not in busy.get(slot["teacher_id"], set())


def test_one_teacher_covering_two_subjects_is_not_double_booked_with_themselves():
    request = _request(
        subjects=[_subject("maths", "Mathematics", 5), _subject("science", "Science", 5)],
        teachers=[_teacher("t-both", "Sharma", ["maths", "science"])],
    )
    result = solver.generate(request, seed=7)

    assert result["solved"] is True
    booked = [(s["day"], s["period_number"]) for s in result["slots"]]
    assert len(booked) == len(set(booked))


# ── An impossible request is refused, in words ───────────────────────────────

def test_a_subject_with_no_teacher_says_which_subject():
    request = _request(teachers=[_teacher("t-maths", "Sharma", ["maths"])])
    result = solver.generate(request, seed=8)

    assert result["solved"] is False
    assert result["slots"] == []
    joined = " ".join(result["problems"])
    assert "English" in joined
    # It has to say what to do, not only that something is wrong.
    assert "Assign a teacher" in joined


def test_asking_for_more_periods_than_the_week_holds_says_by_how_many():
    request = _request(
        periods_per_day=2,  # 5 days x 2 = 10 periods, but 20 are asked for
    )
    result = solver.generate(request, seed=9)

    assert result["solved"] is False
    joined = " ".join(result["problems"])
    assert "20 periods" in joined and "10 teaching periods" in joined
    assert "remove 10" in joined.lower()


def test_a_teacher_busy_everywhere_else_is_reported_as_the_reason():
    """The most confusing failure to hit without an explanation: everything looks set
    up correctly, and it still cannot be done, because the one Hindi teacher is
    already teaching every period of the week somewhere else."""
    busy = {"t-hindi": {(day, p) for day in DAYS for p in range(6)}}
    result = solver.generate(_request(busy_teacher_slots=busy), seed=10)

    assert result["solved"] is False
    joined = " ".join(result["problems"])
    assert "Hindi" in joined
    assert "teaching other classes" in joined


def test_no_subjects_and_no_teachers_are_each_said_plainly():
    assert "No subjects" in " ".join(solver.generate(_request(subjects=[]), seed=11)["problems"])
    assert "No teachers" in " ".join(solver.generate(_request(teachers=[]), seed=12)["problems"])


def test_a_refusal_never_returns_a_half_timetable():
    """Half a week is worse than none: it looks like a timetable, and the empty
    periods are classes with nobody in front of them."""
    result = solver.generate(_request(teachers=[_teacher("t-maths", "Sharma", ["maths"])]), seed=13)
    assert result["slots"] == []
    assert result["score"] is None


# ── The four marks out of 100 ────────────────────────────────────────────────

def test_a_solved_timetable_carries_a_score_out_of_a_hundred():
    result = solver.generate(_request(), seed=14)
    score = result["score"]
    assert set(score) == {
        "distribution", "teacher_preference", "morning_preference",
        "consecutive_avoidance", "total",
    }
    assert 0 <= score["total"] <= 100


def test_a_subject_asked_for_in_the_morning_mostly_lands_in_the_morning():
    request = _request(subjects=[
        _subject("maths", "Mathematics", 5, morning=True),
        _subject("english", "English", 5),
        _subject("hindi", "Hindi", 5),
    ])
    result = solver.generate(request, seed=15)

    assert result["solved"] is True
    assert result["score"]["morning_preference"] >= 60


def test_the_same_subject_twice_running_scores_worse_than_a_spread_one():
    spread = {("Monday", 0): {"subject_id": "a", "teacher_id": "t"},
              ("Monday", 2): {"subject_id": "a", "teacher_id": "t"}}
    back_to_back = {("Monday", 0): {"subject_id": "a", "teacher_id": "t"},
                    ("Monday", 1): {"subject_id": "a", "teacher_id": "t"}}
    request = _request(subjects=[_subject("a", "A", 2)], teachers=[_teacher("t", "T", ["a"])])

    assert (solver.score_timetable(spread, request)["consecutive_avoidance"]
            > solver.score_timetable(back_to_back, request)["consecutive_avoidance"])


# ── Same input, same answer ──────────────────────────────────────────────────

def test_the_same_seed_gives_the_same_timetable():
    """Not a nicety. Without it a person cannot regenerate what they were looking at,
    and a failing test could never be reproduced."""
    first = solver.generate(_request(), seed=99)["slots"]
    second = solver.generate(_request(), seed=99)["slots"]
    assert first == second
