"""The timetable generator, as the school reaches it.

WHO IT IS FOR. Adesh, the principal, writes the school's timetables himself, so this
is his tool (Abhimanyu, 2026-08-12). Aman holds it too, because the owner is never
shut out of his own school, and every use writes an audit row - that is how Aman sees
the tool being used on the school's live data.

THE TWO THINGS THAT MUST NOT SLIP:

  1. **Generating never saves.** It returns a proposal. The saved timetable is what
     the substitution plan reads when a teacher is away, so a timetable that appeared
     on its own is one nobody has checked.

  2. **A generated week is possible in real life.** The solver is told what every
     OTHER class has already booked, so it cannot put one teacher in two classrooms at
     once. Applying re-checks the same thing against the database, because the
     school's timetables may have moved on since the proposal was worked out.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt

GENERATE = "/api/academics/timetable/generate"
APPLY = "/api/academics/timetable/apply"


def _bearer(claims: dict) -> dict:
    return {"Authorization": "Bearer " + create_jwt({"schoolId": "aaryans-joya", **claims})}


def _owner():
    return _bearer({"user_id": "own-1", "role": "owner", "name": "Aman"})


def _principal():
    return _bearer({"user_id": "adesh-1", "role": "admin", "sub_category": "principal",
                    "branch_id": "branch-a", "name": "Adesh"})


def _management():
    return _bearer({"user_id": "lalit-1", "role": "admin", "sub_category": "management",
                    "branch_id": "branch-a", "name": "Lalit"})


def _teacher():
    return _bearer({"user_id": "t-1", "role": "teacher", "branch_id": "branch-a", "name": "Teacher"})


@pytest.fixture(autouse=True)
def _school(fake_db):
    """One class, three subjects with a teacher each, and three teachers."""
    saved = {c: list(getattr(fake_db, c).docs)
             for c in ("classes", "subjects", "staff", "timetable_slots", "audit_logs")}

    fake_db.classes.docs[:] = [
        {"id": "cls-5a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "5th", "section": "A"},
        {"id": "cls-6b", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "6th", "section": "B"},
    ]
    fake_db.subjects.docs[:] = [
        {"id": "sub-maths", "schoolId": "aaryans-joya", "class_id": "cls-5a",
         "name": "Mathematics", "teacher_id": "stf-sharma"},
        {"id": "sub-eng", "schoolId": "aaryans-joya", "class_id": "cls-5a",
         "name": "English", "teacher_id": "stf-patel"},
        {"id": "sub-hindi", "schoolId": "aaryans-joya", "class_id": "cls-5a",
         "name": "Hindi", "teacher_id": "stf-verma"},
    ]
    fake_db.staff.docs[:] = [
        {"id": "stf-sharma", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Sharma", "staff_type": "teacher", "is_active": True},
        {"id": "stf-patel", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Patel", "staff_type": "teacher", "is_active": True},
        {"id": "stf-verma", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "name": "Verma", "staff_type": "teacher", "is_active": True},
    ]
    fake_db.timetable_slots.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    yield
    for name, docs in saved.items():
        getattr(fake_db, name).docs[:] = docs


def _ask(periods=None, **over):
    body = {
        "class_id": "cls-5a",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "periods_per_day": 6,
        "periods_per_week": periods or {"sub-maths": 6, "sub-eng": 5, "sub-hindi": 4},
        "seed": 7,
    }
    body.update(over)
    return body


# ── Who may use it ───────────────────────────────────────────────────────────

def test_generating_needs_a_login(client):
    assert client.post(GENERATE, json=_ask()).status_code == 401


def test_applying_needs_a_login(client):
    assert client.post(APPLY, json={"class_id": "cls-5a", "slots": [{}]}).status_code == 401


def test_the_principal_may_generate(client):
    """Adesh writes the school's timetables. This is his tool."""
    resp = client.post(GENERATE, json=_ask(), headers=_principal())
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["solved"] is True


def test_the_owner_may_generate(client):
    """Aman is never shut out of his own school."""
    assert client.post(GENERATE, json=_ask(), headers=_owner()).status_code == 200


def test_the_management_head_may_not_generate(client):
    """Lalit keeps the timetable SCREEN he has today and can still hand-edit it.
    Working a whole week out is a different, larger thing, and it was given to Adesh
    by name."""
    assert client.post(GENERATE, json=_ask(), headers=_management()).status_code == 403


def test_a_teacher_may_not_generate(client):
    assert client.post(GENERATE, json=_ask(), headers=_teacher()).status_code == 403


def test_a_teacher_may_not_apply(client):
    resp = client.post(APPLY, json={"class_id": "cls-5a", "slots": [{}]}, headers=_teacher())
    assert resp.status_code == 403


# ── Generating proposes; it never saves ──────────────────────────────────────

def test_generating_writes_nothing_to_the_timetable(client, fake_db):
    """The saved timetable is what the substitution plan reads. A week that appeared
    on its own is one nobody has checked."""
    before = len(fake_db.timetable_slots.docs)

    resp = client.post(GENERATE, json=_ask(), headers=_principal())

    assert resp.status_code == 200
    assert len(resp.json()["data"]["slots"]) == 15
    assert len(fake_db.timetable_slots.docs) == before


def test_the_proposal_carries_names_not_only_ids(client):
    """Somebody has to read this and decide. A grid of identifiers is not readable."""
    slots = client.post(GENERATE, json=_ask(), headers=_principal()).json()["data"]["slots"]
    assert all(s["subject_name"] for s in slots)
    assert all(s["teacher_name"] for s in slots)
    assert {s["subject_name"] for s in slots} == {"Mathematics", "English", "Hindi"}


def test_every_generation_is_recorded_so_the_owner_can_see_the_tool_being_used(client, fake_db):
    client.post(GENERATE, json=_ask(), headers=_principal())

    rows = [a for a in fake_db.audit_logs.docs if a["entity_type"] == "timetable"]
    assert len(rows) == 1
    assert rows[0]["action"] == "timetable_generated"
    assert rows[0]["changed_by"] == "adesh-1"
    # The log must not read as though the school's timetable changed, because it did not.
    assert rows[0]["changes"]["saved"] is False


def test_a_refused_generation_is_recorded_too(client, fake_db):
    """A tool that only leaves a trace when it works tells the owner half a story."""
    client.post(GENERATE, json=_ask(periods={"sub-maths": 99}), headers=_principal())

    rows = [a for a in fake_db.audit_logs.docs if a["entity_type"] == "timetable"]
    assert rows[0]["action"] == "timetable_generate_failed"


# ── It knows what the rest of the school is doing ────────────────────────────

def test_a_teacher_busy_with_another_class_is_not_booked_again(client, fake_db):
    """Sharma teaches 6B all Monday. Mathematics cannot land on a Monday in 5A."""
    fake_db.timetable_slots.docs[:] = [
        {"id": f"slot-{p}", "schoolId": "aaryans-joya", "class_id": "cls-6b",
         "teacher_id": "stf-sharma", "subject_id": "sub-x", "day_of_week": 0,
         "period_number": p}
        for p in range(1, 7)
    ]

    resp = client.post(GENERATE, json=_ask(), headers=_principal())

    assert resp.status_code == 200, resp.text
    slots = resp.json()["data"]["slots"]
    assert slots, resp.json()["data"]["problems"]
    monday_maths = [s for s in slots if s["day_of_week"] == 0 and s["subject_id"] == "sub-maths"]
    assert monday_maths == []


def test_an_impossible_request_says_what_to_change(client):
    resp = client.post(GENERATE, json=_ask(periods={"sub-maths": 99}), headers=_principal())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["solved"] is False
    assert data["slots"] == []
    assert "99 periods" in " ".join(data["problems"])


def test_a_class_with_no_subjects_says_so_rather_than_failing_oddly(client, fake_db):
    fake_db.subjects.docs[:] = []
    resp = client.post(GENERATE, json=_ask(), headers=_principal())
    assert resp.status_code == 400
    assert "no subjects" in resp.json()["detail"].lower()


def test_an_unknown_class_is_a_404(client):
    resp = client.post(GENERATE, json=_ask(class_id="no-such-class"), headers=_principal())
    assert resp.status_code == 404


# ── Applying replaces the week, and re-checks it ─────────────────────────────

def _generated(client):
    return client.post(GENERATE, json=_ask(), headers=_principal()).json()["data"]["slots"]


def test_applying_saves_the_whole_week(client, fake_db):
    slots = _generated(client)

    resp = client.post(APPLY, json={"class_id": "cls-5a", "slots": slots}, headers=_principal())

    assert resp.status_code == 200, resp.text
    assert resp.json()["meta"]["count"] == 15
    saved = [s for s in fake_db.timetable_slots.docs if s["class_id"] == "cls-5a"]
    assert len(saved) == 15


def test_applying_replaces_the_old_week_rather_than_mixing_the_two(client, fake_db):
    """Leaving yesterday's periods behind wherever the new week has a gap produces a
    timetable that is half one plan and half another, with nothing to say which."""
    fake_db.timetable_slots.docs[:] = [
        {"id": "old-1", "schoolId": "aaryans-joya", "class_id": "cls-5a",
         "teacher_id": "stf-patel", "subject_id": "sub-old", "day_of_week": 4,
         "period_number": 6},
    ]
    slots = _generated(client)

    resp = client.post(APPLY, json={"class_id": "cls-5a", "slots": slots}, headers=_principal())

    assert resp.status_code == 200
    assert resp.json()["meta"]["replaced"] == 1
    kept = [s for s in fake_db.timetable_slots.docs if s.get("subject_id") == "sub-old"]
    assert kept == []


def test_applying_refuses_if_another_class_took_the_teacher_meanwhile(client, fake_db):
    """The proposal was worked out against the school as it was. If somebody else has
    since booked that teacher, saving it anyway would put one person in two rooms."""
    slots = _generated(client)
    clash = slots[0]
    fake_db.timetable_slots.docs.append({
        "id": "meanwhile", "schoolId": "aaryans-joya", "class_id": "cls-6b",
        "teacher_id": clash["teacher_id"], "subject_id": "sub-x",
        "day_of_week": clash["day_of_week"], "period_number": clash["period_number"],
    })

    resp = client.post(APPLY, json={"class_id": "cls-5a", "slots": slots}, headers=_principal())

    assert resp.status_code == 409
    assert "already teaching another class" in resp.json()["detail"]


def test_applying_nothing_is_refused_rather_than_wiping_the_week(client, fake_db):
    """An empty list must never be read as "clear this class's timetable"."""
    fake_db.timetable_slots.docs[:] = [
        {"id": "keep", "schoolId": "aaryans-joya", "class_id": "cls-5a",
         "teacher_id": "stf-patel", "subject_id": "sub-old", "day_of_week": 1,
         "period_number": 2},
    ]

    resp = client.post(APPLY, json={"class_id": "cls-5a", "slots": []}, headers=_principal())

    assert resp.status_code == 400
    assert len(fake_db.timetable_slots.docs) == 1


def test_applying_is_recorded_with_how_much_it_replaced(client, fake_db):
    slots = _generated(client)
    fake_db.audit_logs.docs[:] = []

    client.post(APPLY, json={"class_id": "cls-5a", "slots": slots}, headers=_principal())

    rows = [a for a in fake_db.audit_logs.docs if a["action"] == "timetable_applied"]
    assert len(rows) == 1
    assert rows[0]["changes"]["periods_saved"] == 15
