"""Work out a timetable that satisfies the school's constraints, and score it.

WHERE THIS CAME FROM. Ported from the standalone "AI Timetable Builder" Abhimanyu
supplied on 2026-08-12 (a Next.js/TypeScript/Supabase app). The valuable half of that
app is this solver; the app around it was a second product with its own database, its
own logins and no permission model, so it is not what was brought over. The timetable
SCREEN, the storage, the permission rules and the substitution plan stay as they are -
this only produces a proposal to put into them.

THE ALGORITHM, unchanged in substance:
  backtracking search over (day, period) slots, placing one required period at a time,
  most-frequent subject first, preferring teachers with the fewest periods so far, then
  a local-search pass that swaps pairs of lessons and keeps a swap when the score does
  not fall. Four soft scores out of 100 each, evenly weighted: how evenly a subject is
  spread across the week, how often teachers get their preferred periods, whether
  subjects flagged for the morning land in the morning, and whether the same subject
  sits back to back.

THE ONE THING THAT HAD TO CHANGE, and it is not cosmetic.

  The original checks teacher clashes WITHIN the one timetable it is building. Its own
  comment says so: "In a single-section schedule this is trivially false." That is safe
  for a standalone tool that knows about one class at a time.

  This school has 48 classes and its teachers are shared across them. Generating 5A's
  timetable without looking at what Mr Sharma is already teaching in 6B produces a
  timetable that is impossible in real life - and, worse, the substitution plan reads
  these rows to work out who is free when a teacher is away, so it would then be
  offering a cover teacher who is already standing in another classroom.

  So the solver takes `busy_teacher_slots`: every (day, period) a teacher is already
  committed to in ANOTHER class's saved timetable. Those are treated exactly like a
  teacher being unavailable. A generated timetable is therefore correct against the
  whole school, not just against itself.

WHAT THIS MODULE IS NOT: it does not read the database, decide who may generate, or
save anything. It takes a description and returns a proposal. The caller owns all
three - see `routes/academics.py`.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

# How long one generation may run before it gives up and says so.
#
# A refusal that names the reason is worth far more than a timetable that quietly
# leaves periods empty: an empty period in a school day is a class of children with
# nobody in front of them. The original used 8 seconds; this keeps that, because the
# work happens inside a web request the person is waiting on.
TIMEOUT_SECONDS = 8.0

# Periods counted as "the morning" for a subject flagged to prefer it.
MORNING_PERIODS = (0, 1, 2)

# Each soft score is out of 100 and they are weighted evenly, as in the original.
SCORE_WEIGHTS = {
    "distribution": 25,
    "teacher_preference": 25,
    "morning_preference": 25,
    "consecutive_avoidance": 25,
}


@dataclass
class Subject:
    id: str
    name: str
    periods_per_week: int
    prefer_morning: bool = False


@dataclass
class Teacher:
    id: str
    name: str
    subject_ids: List[str] = field(default_factory=list)
    # (day, period) pairs this teacher can take. Empty means "any" - the school does
    # not record teacher availability today, so this is almost always empty, and the
    # busy-slots set below is what actually constrains them.
    available: Optional[Set[Tuple[str, int]]] = None
    preferred: Set[Tuple[str, int]] = field(default_factory=set)

    def can_teach(self, subject_id: str) -> bool:
        return subject_id in self.subject_ids

    def is_free(self, day: str, period: int) -> bool:
        if not self.available:
            return True
        return (day, period) in self.available


@dataclass
class TimetableRequest:
    days: List[str]
    periods_per_day: int
    subjects: List[Subject]
    teachers: List[Teacher]
    # (day, period) pairs that are not lessons: assembly, lunch, games.
    breaks: Set[Tuple[str, int]] = field(default_factory=set)
    break_labels: Dict[Tuple[str, int], str] = field(default_factory=dict)
    # teacher_id -> {(day, period)} already taken in ANOTHER class. See the module note.
    busy_teacher_slots: Dict[str, Set[Tuple[str, int]]] = field(default_factory=dict)

    def teaching_slots(self) -> List[Tuple[str, int]]:
        return [
            (day, period)
            for day in self.days
            for period in range(self.periods_per_day)
            if (day, period) not in self.breaks
        ]


def check_feasibility(request: TimetableRequest) -> List[str]:
    """Reasons this cannot be solved, in words the office can act on.

    Checked BEFORE searching, because "no teacher is assigned to Hindi" is an answer a
    person can fix in a minute, whereas eight seconds of searching followed by "could
    not find a timetable" tells them nothing about what to change.
    """
    errors: List[str] = []

    if not request.days:
        errors.append("No days were chosen for the timetable.")
    if not request.subjects:
        errors.append("No subjects were chosen, so there is nothing to place.")
    if not request.teachers:
        errors.append("No teachers were chosen, so nobody can take these lessons.")
    if errors:
        return errors

    available = len(request.teaching_slots())
    required = sum(s.periods_per_week for s in request.subjects)
    if required > available:
        errors.append(
            f"These subjects need {required} periods a week but there are only "
            f"{available} teaching periods available. Either remove "
            f"{required - available} periods, add a day, or add periods to the day."
        )

    for subject in request.subjects:
        capable = [t for t in request.teachers if t.can_teach(subject.id)]
        if not capable:
            errors.append(
                f"Nobody is set up to teach {subject.name}. Assign a teacher to it first."
            )
            continue

        # How many periods this subject could actually go in, given who can teach it
        # and what those teachers are already committed to elsewhere.
        openings = 0
        for day, period in request.teaching_slots():
            if any(_teacher_open(request, t, day, period) for t in capable):
                openings += 1
        if openings < subject.periods_per_week:
            errors.append(
                f"{subject.name} needs {subject.periods_per_week} periods a week, but "
                f"its teachers are only free for {openings} of them. They are teaching "
                "other classes at the rest."
            )

    return errors


def _teacher_open(request: TimetableRequest, teacher: Teacher, day: str, period: int) -> bool:
    """Free in their own diary AND not already teaching another class then."""
    if not teacher.is_free(day, period):
        return False
    return (day, period) not in request.busy_teacher_slots.get(teacher.id, set())


class _Search:
    """One backtracking search. Held in a class only to keep the recursion readable."""

    def __init__(self, request: TimetableRequest, rng: random.Random):
        self.request = request
        self.rng = rng
        self.slots = request.teaching_slots()
        self.rng.shuffle(self.slots)
        self.iterations = 0
        self.deadline = time.monotonic() + TIMEOUT_SECONDS
        # (day, period) -> {"subject_id", "teacher_id"}
        self.grid: Dict[Tuple[str, int], Dict[str, str]] = {}
        # teacher_id -> {(day, period)} used by THIS timetable, on top of what the
        # request says they are already committed to elsewhere.
        self.used: Dict[str, Set[Tuple[str, int]]] = {t.id: set() for t in request.teachers}

    def run(self) -> Optional[Dict[Tuple[str, int], Dict[str, str]]]:
        placements: List[str] = []
        # Hardest first: a subject wanting six periods a week has far less room to move
        # than one wanting two, so placing it late is how a search wastes its time.
        for subject in sorted(self.request.subjects, key=lambda s: -s.periods_per_week):
            placements.extend([subject.id] * subject.periods_per_week)

        if self._place(placements, 0):
            return self.grid
        return None

    def _place(self, placements: List[str], index: int) -> bool:
        if time.monotonic() > self.deadline:
            return False
        if index == len(placements):
            return True

        self.iterations += 1
        subject_id = placements[index]
        subject = next((s for s in self.request.subjects if s.id == subject_id), None)

        empty = [s for s in self.slots if s not in self.grid]
        # A subject asked for in the morning tries morning periods first.
        prefer_morning = bool(subject and subject.prefer_morning)
        empty.sort(key=lambda sl: (-10 if prefer_morning and sl[1] in MORNING_PERIODS else sl[1]))

        for day, period in empty:
            teacher = self._pick_teacher(subject_id, day, period)
            if teacher is None:
                continue

            self.grid[(day, period)] = {"subject_id": subject_id, "teacher_id": teacher.id}
            self.used[teacher.id].add((day, period))

            if self._place(placements, index + 1):
                return True

            del self.grid[(day, period)]
            self.used[teacher.id].discard((day, period))

        return False

    def _pick_teacher(self, subject_id: str, day: str, period: int) -> Optional[Teacher]:
        candidates = [
            t for t in self.request.teachers
            if t.can_teach(subject_id)
            and _teacher_open(self.request, t, day, period)
            and (day, period) not in self.used[t.id]
        ]
        if not candidates:
            return None
        # Spread the load: whoever has the fewest periods so far goes first.
        candidates.sort(key=lambda t: len(self.used[t.id]))
        return candidates[0]


# ── Scoring ──────────────────────────────────────────────────────────────────


def score_timetable(grid: Dict[Tuple[str, int], Dict[str, str]],
                    request: TimetableRequest) -> Dict[str, int]:
    """Four marks out of 100 and an evenly weighted total. Ported unchanged."""
    parts = {
        "distribution": _score_distribution(grid, request),
        "teacher_preference": _score_teacher_preference(grid, request),
        "morning_preference": _score_morning_preference(grid, request),
        "consecutive_avoidance": _score_consecutive(grid, request),
    }
    total = sum(parts[k] * SCORE_WEIGHTS[k] for k in parts) / 100
    result = {k: int(round(v)) for k, v in parts.items()}
    result["total"] = int(round(total))
    return result


def _score_distribution(grid, request: TimetableRequest) -> float:
    """A subject spread evenly across the week rather than piled onto one day."""
    if not request.subjects:
        return 100.0
    penalty = 0.0
    worst = 0.0
    for subject in request.subjects:
        per_day = [
            sum(1 for d, p in grid if d == day and grid[(d, p)]["subject_id"] == subject.id)
            for day in request.days
        ]
        if not per_day:
            continue
        penalty += (max(per_day) - min(per_day)) * subject.periods_per_week
        worst += subject.periods_per_week ** 2
    if worst == 0:
        return 100.0
    return max(0.0, 100.0 - (penalty / worst) * 100.0)


def _score_teacher_preference(grid, request: TimetableRequest) -> float:
    with_prefs = [t for t in request.teachers if t.preferred]
    if not with_prefs:
        return 100.0
    matched = total = 0
    for teacher in with_prefs:
        for (day, period), cell in grid.items():
            if cell["teacher_id"] != teacher.id:
                continue
            total += 1
            if (day, period) in teacher.preferred:
                matched += 1
    return 100.0 if total == 0 else (matched / total) * 100.0


def _score_morning_preference(grid, request: TimetableRequest) -> float:
    wanted = {s.id for s in request.subjects if s.prefer_morning}
    if not wanted:
        return 100.0
    matched = total = 0
    for (_day, period), cell in grid.items():
        if cell["subject_id"] not in wanted:
            continue
        total += 1
        if period in MORNING_PERIODS:
            matched += 1
    return 100.0 if total == 0 else (matched / total) * 100.0


def _score_consecutive(grid, request: TimetableRequest) -> float:
    """The same subject twice in a row is tiring for a class and is avoided."""
    clashes = comparisons = 0
    for day in request.days:
        for period in range(request.periods_per_day - 1):
            here = grid.get((day, period))
            after = grid.get((day, period + 1))
            if not here or not after:
                continue
            comparisons += 1
            if here["subject_id"] == after["subject_id"]:
                clashes += 1
    return 100.0 if comparisons == 0 else max(0.0, 100.0 - (clashes / comparisons) * 100.0)


def _improve(grid, request: TimetableRequest, rng: random.Random, rounds: int = 800):
    """Swap two lessons at random, keep the swap unless the score falls.

    A swap is only tried when BOTH teachers could really take the other's slot, which
    now includes not already teaching another class at that time. Without that check
    the polish pass would quietly undo the very thing the search was careful about.
    """
    best = dict(grid)
    best_score = score_timetable(best, request)["total"]
    filled = list(best.keys())
    if len(filled) < 2:
        return best

    teachers = {t.id: t for t in request.teachers}
    for _ in range(rounds):
        a, b = rng.sample(filled, 2)
        cell_a, cell_b = best[a], best[b]
        teacher_a = teachers.get(cell_a["teacher_id"])
        teacher_b = teachers.get(cell_b["teacher_id"])
        if not teacher_a or not teacher_b:
            continue
        if not _teacher_open(request, teacher_a, b[0], b[1]):
            continue
        if not _teacher_open(request, teacher_b, a[0], a[1]):
            continue

        best[a], best[b] = cell_b, cell_a
        new_score = score_timetable(best, request)["total"]
        if new_score >= best_score:
            best_score = new_score
        else:
            best[a], best[b] = cell_a, cell_b
    return best


# ── The one entry point ──────────────────────────────────────────────────────


def generate(request: TimetableRequest, seed: Optional[int] = None) -> Dict[str, Any]:
    """Propose a timetable, or say plainly why there is not one.

    Returns a dict carrying `solved`, the `slots` proposed, the `score`, the `problems`
    that make it impossible, and how long it took. **It never saves anything**: a
    generated timetable is a suggestion until a person looks at it and applies it, and
    the substitution plan reads the saved one.
    """
    started = time.monotonic()
    problems = check_feasibility(request)
    if problems:
        return {
            "solved": False,
            "slots": [],
            "score": None,
            "problems": problems,
            "seconds": round(time.monotonic() - started, 2),
            "iterations": 0,
        }

    rng = random.Random(seed)
    search = _Search(request, rng)
    grid = search.run()

    if grid is None:
        return {
            "solved": False,
            "slots": [],
            "score": None,
            "problems": [
                "No timetable fits all of these at once. The usual causes are one "
                "teacher being asked for too many periods, or a subject whose only "
                "teacher is busy with other classes. Try freeing a period, or sharing "
                "a subject between two teachers."
            ],
            "seconds": round(time.monotonic() - started, 2),
            "iterations": search.iterations,
        }

    grid = _improve(grid, request, rng)

    # `day` is the NAME, not a number, and `period_number` counts from 1 as the rest of
    # the platform does. Turning a day name into the stored `day_of_week` is the
    # caller's job: this module has no opinion about which day the school's week starts
    # on, and guessing one here is how a timetable ends up a day out.
    slots = [
        {
            "day": day,
            "period_number": period + 1,
            "subject_id": cell["subject_id"],
            "teacher_id": cell["teacher_id"],
        }
        for (day, period), cell in sorted(
            grid.items(), key=lambda kv: (request.days.index(kv[0][0]), kv[0][1])
        )
    ]

    return {
        "solved": True,
        "slots": slots,
        "score": score_timetable(grid, request),
        "problems": [],
        "seconds": round(time.monotonic() - started, 2),
        "iterations": search.iterations,
    }
