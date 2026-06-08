"""Story A.7 — attendance-correction service: snapshot + status update + audit,
and the AI-path corrections (audit action, school-wide scoping)."""

from __future__ import annotations

import pytest

from services.actor_context import actor_ctx_from_user
from services.attendance_correction_service import (
    correct_attendance,
    AttendanceCorrectionValidationError,
    AttendanceCorrectionNotFoundError,
)
from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

OWNER = {"id": "admin-1", "role": "owner", "name": "Admin User"}
PRINCIPAL = {"id": "p1", "role": "admin", "sub_category": "principal", "name": "Principal", "branch_id": "branch-a"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in ("student_attendance", "attendance_corrections", "audit_logs"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("student_attendance", "attendance_corrections", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _ctx(user=OWNER):
    return actor_ctx_from_user(user, school_id="aaryans-joya")


def _seed_att(fake_db, att_id="att-1"):
    fake_db.student_attendance.docs.append({
        "id": att_id, "schoolId": "aaryans-joya", "student_id": "student-1",
        "class_id": "class-1", "date": "2026-05-12", "status": "present", "source": "manual",
    })


async def test_missing_reason_raises_validation(fake_db):
    _seed_att(fake_db)
    with pytest.raises(AttendanceCorrectionValidationError):
        await correct_attendance(fake_db, _ctx(), {"attendance_id": "att-1", "correction_type": "absent"})


async def test_missing_record_raises_not_found(fake_db):
    with pytest.raises(AttendanceCorrectionNotFoundError):
        await correct_attendance(fake_db, _ctx(), {"attendance_id": "ghost", "correction_type": "absent", "reason": "x"})


async def test_writes_snapshot_status_and_audit(fake_db):
    _seed_att(fake_db)
    result = await correct_attendance(fake_db, _ctx(), {"attendance_id": "att-1", "correction_type": "absent", "reason": "signed note"})
    assert result["correction"]["previous_status"] == "present"
    assert result["correction"]["new_status"] == "absent"
    assert result["correction"]["original_record"]["status"] == "present"
    updated = next(r for r in fake_db.student_attendance.docs if r["id"] == "att-1")
    assert updated["status"] == "absent" and updated["corrected"] is True
    audit = next(a for a in fake_db.audit_logs.docs if a.get("action") == "correct")
    assert audit["entity_type"] == "student_attendance"
    assert audit["changes"] == {"status": {"previous": "present", "new": "absent"}}


async def test_ai_tool_writes_canonical_correct_audit(fake_db, monkeypatch):
    """Regression: the old AI tool wrote audit action 'correct_attendance'; now 'correct'."""
    _seed_att(fake_db, "att-9")
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_correct_attendance(
        {"record_id": "att-9", "correction_type": "absent", "reason": "note"}, OWNER, None
    )
    assert out["success"] is True
    assert any(a.get("action") == "correct" for a in fake_db.audit_logs.docs)
    assert not any(a.get("action") == "correct_attendance" for a in fake_db.audit_logs.docs)


async def test_ai_principal_can_correct_school_wide_record(fake_db, monkeypatch):
    """Regression: the old AI tool scoped the find by branch_id; since attendance docs
    carry no branch_id, a branch-scoped principal could never find the record. School-wide
    scoping fixes it."""
    _seed_att(fake_db, "att-7")  # no branch_id on the attendance doc
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_correct_attendance(
        {"record_id": "att-7", "correction_type": "absent", "reason": "note"}, PRINCIPAL, None
    )
    assert out["success"] is True
    assert next(r for r in fake_db.student_attendance.docs if r["id"] == "att-7")["status"] == "absent"
