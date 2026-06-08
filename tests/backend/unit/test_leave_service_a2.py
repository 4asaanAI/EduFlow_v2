"""Story A.2 — leave-decision service: domain behavior + closed-gap regression guards.

The 5 existing REST tests in test_leave_approval.py are the REST characterization
safety net (they stay green). These tests pin the SERVICE behavior and prove the
AI path no longer silently diverges (it now notifies + audits + guards).
"""

from __future__ import annotations

import pytest

from services.actor_context import actor_ctx_from_user
from services.leave_service import (
    decide_leave,
    LeaveValidationError,
    LeaveNotFoundError,
    LeaveConflictError,
)
from ai import tool_functions

pytestmark = pytest.mark.asyncio

PRINCIPAL = {"id": "prin-1", "role": "admin", "sub_category": "principal", "name": "Principal"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in ("leave_requests", "notifications", "audit_logs", "staff"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("leave_requests", "notifications", "audit_logs", "staff"):
        getattr(fake_db, col).docs[:] = []


def _ctx():
    return actor_ctx_from_user(PRINCIPAL, school_id="aaryans-joya")


def _seed_pending(fake_db, leave_id="lr-1", **extra):
    fake_db.leave_requests.docs.append({
        "id": leave_id, "schoolId": "aaryans-joya", "status": "pending",
        "staff_id": "s1", "user_id": "u1",
        "start_date": "2026-06-01", "end_date": "2026-06-03", **extra,
    })


# ─── domain validation ────────────────────────────────────────────────────────

async def test_missing_leave_id_raises_validation(fake_db):
    with pytest.raises(LeaveValidationError):
        await decide_leave(fake_db, _ctx(), {"status": "approved"})


async def test_bad_status_raises_validation(fake_db):
    _seed_pending(fake_db)
    with pytest.raises(LeaveValidationError):
        await decide_leave(fake_db, _ctx(), {"leave_id": "lr-1", "status": "maybe"})


async def test_reject_without_reason_raises_validation(fake_db):
    _seed_pending(fake_db)
    with pytest.raises(LeaveValidationError):
        await decide_leave(fake_db, _ctx(), {"leave_id": "lr-1", "status": "rejected"})


async def test_missing_leave_raises_not_found(fake_db):
    with pytest.raises(LeaveNotFoundError):
        await decide_leave(fake_db, _ctx(), {"leave_id": "ghost", "status": "approved"})


async def test_already_decided_raises_conflict(fake_db):
    _seed_pending(fake_db, status="approved")
    with pytest.raises(LeaveConflictError):
        await decide_leave(fake_db, _ctx(), {"leave_id": "lr-1", "status": "approved"})


# ─── fan-out (notification + audit) ───────────────────────────────────────────

async def test_approve_notifies_and_audits(fake_db):
    _seed_pending(fake_db)
    result = await decide_leave(fake_db, _ctx(), {"leave_id": "lr-1", "status": "approved"})
    assert result["status"] == "approved"
    assert fake_db.leave_requests.docs[0]["status"] == "approved"
    assert fake_db.leave_requests.docs[0]["approved_by"] == "prin-1"
    assert fake_db.leave_requests.docs[0]["approved_at"].endswith("+00:00")  # UTC, canonical
    notif = next(n for n in fake_db.notifications.docs if n.get("user_id") == "u1")
    assert "approved" in notif["message"].lower()
    audit = next(a for a in fake_db.audit_logs.docs if a.get("action") == "leave_approved")
    assert audit["changes"] == {"status": "approved", "approved_by": "prin-1"}


# ─── AI-path closed-gap regression guards (defects this story fixes) ──────────

async def test_ai_approve_now_notifies_and_audits(fake_db, monkeypatch):
    """Regression: the old AI tool_approve_leave wrote NO notification and NO audit."""
    _seed_pending(fake_db, leave_id="lr-9")
    monkeypatch.setattr(tool_functions, "get_db", lambda: fake_db)
    out = await tool_functions.tool_approve_leave({"leave_id": "lr-9", "action": "approve"}, PRINCIPAL, None)
    assert out["success"] is True
    assert any(n.get("user_id") == "u1" for n in fake_db.notifications.docs)
    assert any(a.get("action") == "leave_approved" for a in fake_db.audit_logs.docs)


async def test_ai_double_approve_now_guarded(fake_db, monkeypatch):
    """Regression: the old AI tool had no pending-only guard (could re-decide)."""
    _seed_pending(fake_db, leave_id="lr-8", status="approved")
    monkeypatch.setattr(tool_functions, "get_db", lambda: fake_db)
    out = await tool_functions.tool_approve_leave({"leave_id": "lr-8", "action": "approve"}, PRINCIPAL, None)
    assert out["success"] is False
    assert "already" in out["error"].lower()
