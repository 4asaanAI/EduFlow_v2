"""UI Sweep Epic 4, Story 4.2 — a zero means zero.

The school has ONE fee transaction for 1,802 students and no attendance marked on a
typical morning. Once the double envelope was fixed and real figures started flowing,
"0%" attendance and "₹0" collected would have been indistinguishable from the broken
zeros this epic set out to remove — so the numbers themselves have to be honest, not
just the cards that render them.

These assert the tool output, because the assistant reads the same fields as the
screens. Fixing the number once fixes both surfaces.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

TOOL_URL = "/api/tools/{}/execute"


def _owner():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'e4h-owner', 'role': 'owner', 'name': 'Owner'})}"}


# Snapshot/restore, not a blanket wipe — the FakeDb is a session-wide singleton and
# other test files seed rows into these same collections.
_TOUCHED = ("students", "staff", "student_attendance", "staff_attendance",
            "fee_transactions", "leave_requests", "classes")


@pytest.fixture(autouse=True)
def _clean(fake_db):
    saved = {name: list(getattr(fake_db, name).docs) for name in _TOUCHED}
    for name in _TOUCHED:
        getattr(fake_db, name).docs[:] = []
    yield
    for name in _TOUCHED:
        getattr(fake_db, name).docs[:] = saved[name]


def _seed_students(fake_db, n=3):
    for i in range(n):
        fake_db.students.docs.append({
            "id": f"s{i}", "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "name": f"Student {i}", "is_active": True,
        })


# ── Attendance: nothing marked is not nought present ─────────────────────────

def test_unmarked_attendance_does_not_report_zero_percent(client, fake_db):
    """A principal opening the report on a Monday and reading "0%" has been told the
    school is empty. Nought marked is not nought present."""
    _seed_students(fake_db)

    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())
    summary = resp.json()["data"]["summary"]

    assert summary["attendance_rate"] != "0%"
    assert summary["attendance_rate"] == "not marked yet"
    assert summary["attendance_marked_today"] is False
    assert summary["attendance_records_today"] == 0


def test_marked_attendance_still_reports_a_real_percentage(client, fake_db):
    """The honesty fix must not swallow a genuine figure."""
    from datetime import date

    _seed_students(fake_db, 2)
    today = date.today().strftime("%Y-%m-%d")
    fake_db.student_attendance.docs.extend([
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "student_id": "s0", "date": today, "status": "present"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "student_id": "s1", "date": today, "status": "absent"},
    ])

    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())
    summary = resp.json()["data"]["summary"]

    assert summary["attendance_rate"] == "50.0%"
    assert summary["attendance_marked_today"] is True


def test_a_genuine_zero_percent_is_still_reported(client, fake_db):
    """Everyone marked absent IS 0% — and must not be hidden by the honesty fix."""
    from datetime import date

    _seed_students(fake_db, 2)
    today = date.today().strftime("%Y-%m-%d")
    fake_db.student_attendance.docs.extend([
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "student_id": "s0", "date": today, "status": "absent"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "student_id": "s1", "date": today, "status": "absent"},
    ])

    resp = client.post(TOOL_URL.format("get_school_pulse"), json={"params": {}}, headers=_owner())
    summary = resp.json()["data"]["summary"]

    assert summary["attendance_rate"] == "0.0%"
    assert summary["attendance_marked_today"] is True


def test_no_attendance_in_the_window_is_not_an_average_of_zero(client, fake_db):
    """Saying "0%" over 30 days would report a school nobody attended."""
    _seed_students(fake_db)

    resp = client.post(
        TOOL_URL.format("get_attendance_overview"), json={"params": {"days": 30}}, headers=_owner()
    )
    data = resp.json()["data"]

    assert data["avg_attendance_rate"] == "not recorded"
    assert data["has_attendance_records"] is False


def test_attendance_average_is_reported_when_records_exist(client, fake_db):
    from datetime import date

    _seed_students(fake_db, 2)
    today = date.today().strftime("%Y-%m-%d")
    fake_db.student_attendance.docs.extend([
        {"id": "a1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "student_id": "s0", "date": today, "status": "present"},
        {"id": "a2", "schoolId": "aaryans-joya", "branch_id": "branch-a",
         "student_id": "s1", "date": today, "status": "present"},
    ])

    resp = client.post(
        TOOL_URL.format("get_attendance_overview"), json={"params": {"days": 30}}, headers=_owner()
    )
    data = resp.json()["data"]

    assert data["avg_attendance_rate"] == "100.0%"
    assert data["has_attendance_records"] is True


# ── Fees: a real ₹0 must be able to say why ──────────────────────────────────

def test_fee_summary_reports_how_many_records_exist(client, fake_db):
    """The school's ₹0 is TRUE — one transaction for 1,802 students. Without this
    count the screen cannot tell him a real zero from a failed request."""
    resp = client.post(TOOL_URL.format("get_fee_summary"), json={"params": {}}, headers=_owner())
    stats = resp.json()["data"]["stats"]

    assert stats["transactions_on_file"] == 0
    assert stats["total_collected"] == "₹0"


# ── Class strength: "Other" was hiding "never recorded" ──────────────────────

def test_unrecorded_gender_is_counted_separately_from_other(client, fake_db):
    """Reported by the owner, 2026-07-22: "not sure why there are 2 columns i.e.
    other and total giving the same number".

    "Other" used to mean everything that was not male or female, which lumped a
    student recorded as another gender together with a student whose gender was
    never captured. Gender is empty for all 1,802 students, so Other == Total on
    every row. They are different facts and are now counted separately.
    """
    from routes.students import classify_gender

    # A student whose gender was never captured is NOT "other".
    assert classify_gender(None) == "not_recorded"
    assert classify_gender("") == "not_recorded"
    assert classify_gender("   ") == "not_recorded"

    # A recorded gender of other IS "other" — a real, different answer.
    assert classify_gender("other") == "other"
    assert classify_gender("Transgender") == "other"

    for male in ("male", "Male", "M", " boy "):
        assert classify_gender(male) == "boys", male
    for female in ("female", "FEMALE", "f", "Girl"):
        assert classify_gender(female) == "girls", female

    # The school's actual data: every student unrecorded. Under the old rule all
    # 1,802 landed in "other", so Other == Total on every row — the exact symptom
    # the owner reported. Under the new rule none of them do.
    school_as_it_stands = [classify_gender(g) for g in [None] * 50]
    assert set(school_as_it_stands) == {"not_recorded"}
    assert "other" not in school_as_it_stands


def test_strength_endpoint_reports_the_not_recorded_bucket(client, fake_db):
    """The endpoint must expose the fourth count, or the screen cannot draw it.

    NOTE: the in-memory test double cannot evaluate `$cond`/`$toLower`/`$trim`, so
    the *arithmetic* of the aggregation is not asserted here — that would be
    measuring the fake rather than the code. The rule itself is covered
    exhaustively by `classify_gender` above, and the pipeline mirrors it.
    """
    resp = client.get("/api/students/strength", headers=_owner())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    for row in body["data"]:
        assert "not_recorded" in row, "the screen needs this to stop showing Other == Total"
        assert "other" in row


def test_strength_pipeline_counts_unrecorded_separately():
    """The aggregation must not fold 'never captured' back into 'other'."""
    import inspect

    from routes import students as students_module

    src = inspect.getsource(students_module.class_strength_stats)
    assert '"not_recorded"' in src
    # `other` is total minus the three known buckets, INCLUDING not_recorded —
    # if not_recorded is dropped from that subtraction the old defect returns.
    assert '"$not_recorded"' in src


def test_fee_record_count_reflects_stored_transactions(client, fake_db):
    fake_db.fee_transactions.docs.append({
        "id": "f1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_id": "s0", "amount": 5000, "status": "paid",
    })
    resp = client.post(TOOL_URL.format("get_fee_summary"), json={"params": {}}, headers=_owner())
    stats = resp.json()["data"]["stats"]

    assert stats["transactions_on_file"] == 1
