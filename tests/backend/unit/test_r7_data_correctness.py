from __future__ import annotations

import pytest
from datetime import date, timedelta

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# R7.1 — shared fee-outstanding helper (M5)
# ---------------------------------------------------------------------------

async def test_compute_fee_totals_canonical_formula():
    from ai.fee_metrics import compute_fee_totals

    db = type("FakeDb", (), {
        "fee_transactions": FakeCollection([
            {"status": "paid", "amount": 1000, "paid_amount": 1000},
            {"status": "partial", "amount": 1000, "paid_amount": 400},
            {"status": "overdue", "amount": 500},
            {"status": "pending", "amount": 300},
            {"status": "unpaid", "amount": 200},
        ]),
    })()

    totals = await compute_fee_totals(db, {})
    # collected = paid(1000) + partial paid(400) = 1400
    assert totals["collected"] == 1400
    # outstanding = overdue(500)+pending(300)+unpaid(200)+partial_remaining(600) = 1600
    assert totals["outstanding"] == 1600
    assert totals["collection_rate"] == round(1400 / 3000 * 100, 1)


async def test_student_outstanding_uses_partial_remainder():
    from ai.fee_metrics import student_outstanding_from_txns

    dues = student_outstanding_from_txns([
        {"student_id": "s1", "status": "overdue", "amount": 500, "due_date": "2026-01-01"},
        {"student_id": "s1", "status": "partial", "amount": 1000, "paid_amount": 400, "due_date": "2026-02-01"},
        {"student_id": "s2", "status": "pending", "amount": 300, "due_date": "2026-03-01"},
    ])
    # s1 owes 500 + (1000-400)=600 => 1100; oldest due retained
    assert dues["s1"]["owed"] == 1100
    assert dues["s1"]["oldest_due"] == "2026-01-01"
    assert dues["s2"]["owed"] == 300


async def test_fee_defaulters_includes_pending_not_only_overdue(monkeypatch):
    """R7.1/AC3: a student with only a 'pending' balance is a defaulter."""
    from ai.tool_functions_v2 import tool_get_fee_defaulters
    import ai.tool_functions_v2 as _mod

    db = type("FakeDb", (), {
        "fee_transactions": FakeCollection([
            {"student_id": "s1", "status": "pending", "amount": 400, "due_date": "2026-01-01",
             "schoolId": "aaryans-joya"},
        ]),
        "students": FakeCollection([
            {"id": "s1", "name": "Pending Payer", "class_id": "c1", "schoolId": "aaryans-joya"},
        ]),
        "classes": FakeCollection([
            {"id": "c1", "name": "5", "section": "A", "schoolId": "aaryans-joya"},
        ]),
    })()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_fee_defaulters({}, {"id": "u1", "role": "owner"}, scope=None)
    names = [d["name"] for d in result.get("data", [])]
    assert "Pending Payer" in names


# ---------------------------------------------------------------------------
# R7.1 — branch comparison reads student_attendance (M3)
# ---------------------------------------------------------------------------

async def test_branch_comparison_attendance_reads_student_attendance(monkeypatch):
    from ai.tool_functions_v2 import tool_get_branch_comparison
    import ai.tool_functions_v2 as _mod

    today = date.today().strftime("%Y-%m-%d")
    db = type("FakeDb", (), {
        "branches": FakeCollection([{"id": "b1", "name": "Main", "is_active": True}]),
        "students": FakeCollection([]),
        "classes": FakeCollection([
            {"id": "c1", "branch_id": "b1", "schoolId": "aaryans-joya"},
        ]),
        "student_attendance": FakeCollection([
            {"class_id": "c1", "date": today, "status": "present", "schoolId": "aaryans-joya"},
            {"class_id": "c1", "date": today, "status": "absent", "schoolId": "aaryans-joya"},
        ]),
        "fee_transactions": FakeCollection([]),
    })()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_branch_comparison({"metric": "attendance"}, {"id": "u1", "role": "owner"}, scope=None)
    br = result["data"]["branches"][0]
    assert br["attendance_rate_today"] == 50.0


# ---------------------------------------------------------------------------
# R7.3 — exam pass-rate uses actual max_marks (M7)
# ---------------------------------------------------------------------------

async def test_exam_pass_rate_uses_actual_max_marks(monkeypatch):
    from ai.tool_functions_v2 import tool_get_exam_results_summary
    import ai.tool_functions_v2 as _mod

    db = type("FakeDb", (), {
        "exams": FakeCollection([
            {"id": "e1", "name": "Unit Test", "subject": "Math", "exam_date": "2026-05-01",
             "max_marks": 50, "schoolId": "aaryans-joya"},
        ]),
        "exam_results": FakeCollection([
            # 33% of 50 = 16.5 → 16 fails, 20 passes
            {"exam_id": "e1", "student_id": "s1", "marks_obtained": 20, "max_marks": 50, "schoolId": "aaryans-joya"},
            {"exam_id": "e1", "student_id": "s2", "marks_obtained": 16, "max_marks": 50, "schoolId": "aaryans-joya"},
        ]),
    })()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_exam_results_summary({}, {"id": "u1", "role": "owner"}, scope=None)
    row = result["data"][0]
    # With max=50, threshold=16.5: 20 passes, 16 fails => 50%. (If /100 assumed, both fail => 0%.)
    assert row["pass_rate"] == "50.0%"
    assert row["average"] == "18.0/50"


# ---------------------------------------------------------------------------
# R7.3 — attendance rate can never exceed 100% (M7)
# ---------------------------------------------------------------------------

async def test_attendance_rate_never_exceeds_100(monkeypatch):
    from ai.tool_functions_v2 import tool_get_today_class_attendance
    import ai.tool_functions_v2 as _mod

    today = date.today().strftime("%Y-%m-%d")
    db = type("FakeDb", (), {
        "classes": FakeCollection([{"id": "c1", "name": "5", "section": "A", "schoolId": "aaryans-joya"}]),
        "students": FakeCollection([
            {"id": "s1", "name": "Active One", "class_id": "c1", "is_active": True, "schoolId": "aaryans-joya"},
        ]),
        # Two present records but only one active student — must not yield 200%.
        "student_attendance": FakeCollection([
            {"student_id": "s1", "class_id": "c1", "date": today, "status": "present", "schoolId": "aaryans-joya"},
            {"student_id": "ghost", "class_id": "c1", "date": today, "status": "present", "schoolId": "aaryans-joya"},
        ]),
    })()
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_today_class_attendance(
        {"class_id": "c1"}, {"id": "u1", "role": "owner"}, scope=None
    )
    rate = result["data"][0]["rate"]
    assert rate == "100.0%"


# ---------------------------------------------------------------------------
# R7.3 — detect_navigate anchors on the verb (M-misc / AC3)
# ---------------------------------------------------------------------------

def test_detect_navigate_anchors_on_command():
    from routes.chat import detect_navigate

    # Verb-led command navigates.
    assert detect_navigate("open library") == "library"
    assert detect_navigate("please open library") == "library"
    # A mere mention mid-sentence does NOT navigate.
    assert detect_navigate("why can't we open library on Sundays?") is None
    assert detect_navigate("the students love the open library concept") is None


# ---------------------------------------------------------------------------
# R7.3 — _extract_result_count counts the envelope data list (AC4)
# ---------------------------------------------------------------------------

def test_extract_result_count_counts_data_list_not_first_field():
    from routes.chat import _extract_result_count

    # No meta.count; data is the authoritative list.
    envelope = {"success": True, "data": [{"x": 1}, {"x": 2}, {"x": 3}],
                "action_buttons": [{"b": 1}]}
    assert _extract_result_count(envelope) == 3

    # meta.count still wins when present.
    assert _extract_result_count({"data": [1, 2], "meta": {"count": 9}}) == 9
