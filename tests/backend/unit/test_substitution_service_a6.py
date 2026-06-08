"""Story A.6 — substitution service: canonical doc + audit + notification, and the
AI-path corrections (status, upsert-dedup, audit action, dropped period_id)."""

from __future__ import annotations

import pytest

from services.actor_context import actor_ctx_from_user
from services.substitution_service import initiate_substitution
from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

OWNER = {"id": "admin-1", "role": "owner", "name": "Admin User"}
RESOLVED = {
    "date": "2026-05-12",
    "absent_teacher_id": "teacher-1",
    "substitute_teacher_id": "teacher-2",
    "class_id": "class-1",
    "subject_id": "subject-1",
    "period_number": 2,
}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in ("substitutions", "audit_logs", "notifications", "staff", "timetable_slots"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("substitutions", "audit_logs", "notifications", "staff", "timetable_slots"):
        getattr(fake_db, col).docs[:] = []


def _ctx():
    return actor_ctx_from_user(OWNER, school_id="aaryans-joya")


def _seed_substitute(fake_db):
    fake_db.staff.docs.append({"id": "teacher-2", "schoolId": "aaryans-joya", "user_id": "tu-2", "name": "Sub"})


async def test_service_writes_assigned_status_and_audit_and_notifies(fake_db):
    _seed_substitute(fake_db)
    result = await initiate_substitution(fake_db, _ctx(), dict(RESOLVED))
    sub = fake_db.substitutions.docs[0]
    assert sub["status"] == "assigned"
    assert sub["period_number"] == 2
    assert "period_id" not in sub  # canonical doc drops the AI's extra field
    audit = next(a for a in fake_db.audit_logs.docs if a.get("action") == "assign")
    assert audit["entity_type"] == "substitution"
    notif = next(n for n in fake_db.notifications.docs if n.get("user_id") == "tu-2")
    assert notif["type"] == "substitution_assigned"


async def test_service_upsert_dedups(fake_db):
    _seed_substitute(fake_db)
    await initiate_substitution(fake_db, _ctx(), dict(RESOLVED))
    await initiate_substitution(fake_db, _ctx(), dict(RESOLVED))
    # Same (date, absent_teacher, class, period) → one row.
    assert len(fake_db.substitutions.docs) == 1


async def test_ai_tool_now_writes_assigned_status_and_assign_audit(fake_db, monkeypatch):
    """Regression: the old AI tool omitted status, plain-inserted, and audited
    'initiate_substitution'. It now writes status='assigned' + 'assign' audit."""
    _seed_substitute(fake_db)
    fake_db.timetable_slots.docs.append({"id": "slot-1", "subject_id": "subject-1", "period_number": 2})
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_initiate_substitution(
        {"absent_staff_id": "teacher-1", "substitute_staff_id": "teacher-2",
         "class_id": "class-1", "period_id": "slot-1", "date": "2026-05-12"},
        OWNER, None,
    )
    assert out["success"] is True
    assert out["data"]["status"] == "assigned"
    assert "period_id" not in out["data"]
    assert any(a.get("action") == "assign" for a in fake_db.audit_logs.docs)
    assert not any(a.get("action") == "initiate_substitution" for a in fake_db.audit_logs.docs)
