"""Epic R4 — One Tool Envelope + Denied ≠ Empty (behavior tier).

Covers the reliability guarantees behind the envelope migration: recall_history no
longer drops the fees/enquiries sections (C1/C3), permission failures are `denied`
(not empty success — M2), write not-found is `success: False` (L1), phones are
masked at source (H5/AC2/AC3), and get_leave_requests carries the leave id (L3).
"""

from __future__ import annotations

import pytest

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


def _db(**collections):
    class _D:
        def __getattr__(self, name):
            col = FakeCollection([])
            object.__setattr__(self, name, col)
            return col
    d = _D()
    for name, docs in collections.items():
        object.__setattr__(d, name, FakeCollection(docs))
    return d


# ── C1/C3: recall_history includes fees + enquiries sections ───────────────────

async def test_recall_history_includes_fees_and_enquiries(monkeypatch):
    import ai.tool_functions_v2 as v2
    import ai.tool_functions as v1

    student = {"id": "stu-1", "schoolId": "aaryans-joya", "name": "Rahul Sharma",
               "class_id": "c1", "is_active": True, "status": "active"}
    db = _db(
        students=[student],
        classes=[{"id": "c1", "schoolId": "aaryans-joya", "name": "5", "section": "A"}],
        fee_transactions=[{"id": "ft1", "schoolId": "aaryans-joya", "student_id": "stu-1",
                           "fee_type": "tuition", "amount": 5000, "status": "pending"}],
        enquiries=[{"id": "e1", "schoolId": "aaryans-joya", "student_name": "Rahul Sharma",
                    "parent_name": "Mr Sharma", "phone": "9876543210", "status": "new",
                    "created_at": "2026-05-01T00:00:00"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)
    monkeypatch.setattr(v1, "get_db", lambda: db)

    # Avoid the memory subsystem in this unit (covered elsewhere).
    monkeypatch.setattr(v2, "_branch_id", lambda user, scope: None, raising=False)

    result = await v2.tool_recall_history(
        {"subject": "Sharma"}, {"id": "own-1", "role": "owner", "name": "Owner"}, None,
    )
    assert result["success"] is True
    sections = result["data"]["sections"]
    # The C3 bug dropped these because v1 tools lacked success/data — now present.
    assert "fees" in sections and sections["fees"], "fees section missing (C3 regression)"
    assert "enquiries" in sections and sections["enquiries"], "enquiries section missing (C3 regression)"


# ── M2: permission denial is denied, not empty success ─────────────────────────

async def test_student_database_class_denial_is_denied(monkeypatch):
    import ai.tool_functions_v2 as v2

    db = _db(classes=[{"id": "c9", "schoolId": "aaryans-joya", "name": "9", "section": "A"}])
    monkeypatch.setattr(v2, "get_db", lambda: db)
    # Scope that restricts to a DIFFERENT class → asking for c9 is a denial.
    scope = {"branch_id": None, "class_ids": ["c1"], "can_write": True}
    monkeypatch.setattr(v2, "_scope_class_ids", lambda s: ["c1"], raising=False)

    result = await v2.tool_get_student_database({"class_name": "9"}, {"id": "t1", "role": "teacher"}, scope)
    assert result["success"] is False
    assert result["denied"] is True
    assert "access" in result["message"].lower()


# ── L1: write not-found is a failure, not empty success ────────────────────────

async def test_award_points_student_not_found_is_failure(monkeypatch):
    import ai.tool_functions_v2 as v2

    db = _db(students=[])
    monkeypatch.setattr(v2, "get_db", lambda: db)

    result = await v2.tool_award_house_points(
        {"student_name": "Ghost", "points": 5, "reason": "x"},
        {"id": "own-1", "role": "owner"}, None,
    )
    assert result["success"] is False   # was empty-success (L1)
    assert result["denied"] is False    # a failure, not a denial
    assert "not found" in result["message"].lower()


# ── H5/AC2: enquiry phone masked (canonical last-3), not first-5 exposed ───────

async def test_enquiry_phone_masked_canonically(monkeypatch):
    import ai.tool_functions as v1

    db = _db(enquiries=[{"id": "e1", "schoolId": "aaryans-joya", "student_name": "A",
                         "parent_name": "B", "phone": "9876543210", "status": "new",
                         "created_at": "2026-05-01T00:00:00"}])
    monkeypatch.setattr(v1, "get_db", lambda: db)

    result = await v1.tool_get_enquiries({}, {"id": "u1", "role": "admin"}, None)
    phone = result["data"][0]["phone"]
    assert "98765" not in phone           # first-5 no longer exposed
    assert phone.endswith("210")          # canonical: last 3 kept
    assert "X" in phone


# ── L3/AC4: get_leave_requests carries the leave id ────────────────────────────

async def test_get_leave_requests_includes_id(monkeypatch):
    import ai.tool_functions_v2 as v2

    db = _db(
        leave_requests=[{"id": "lv-7", "schoolId": "aaryans-joya", "staff_id": "st1",
                         "status": "pending", "leave_type": "sick",
                         "start_date": "2026-05-01", "end_date": "2026-05-02",
                         "created_at": "2026-04-30"}],
        staff=[{"id": "st1", "schoolId": "aaryans-joya", "name": "Mr Rao", "staff_type": "teacher"}],
    )
    monkeypatch.setattr(v2, "get_db", lambda: db)

    result = await v2.tool_get_leave_requests({"status": "pending"}, {"id": "own-1", "role": "owner"}, None)
    assert result["success"] is True
    row = result["data"][0]
    assert row["id"] == "lv-7"
    assert row["leave_id"] == "lv-7"   # approve_leave consumes this
