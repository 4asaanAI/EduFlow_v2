"""Story A.3 — approval-decision service: routing-dependent authz + fan-out parity.

Pins the SERVICE behavior and proves the AI path now enforces the routing-dependent
authority gate it previously skipped (owner decides any; principal only
owner_and_principal; anyone else forbidden).
"""

from __future__ import annotations

import pytest

from services.actor_context import actor_ctx_from_user
from services.approvals_service import (
    decide_approval_request,
    ApprovalValidationError,
    ApprovalNotFoundError,
    ApprovalAuthorizationError,
)
from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

OWNER = {"id": "owner-1", "role": "owner", "name": "Owner"}
PRINCIPAL = {"id": "prin-1", "role": "admin", "sub_category": "principal", "name": "Principal"}
ACCOUNTANT = {"id": "acct-1", "role": "admin", "sub_category": "accountant", "name": "Accountant"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in ("approval_requests", "notifications", "audit_logs"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("approval_requests", "notifications", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _ctx(user):
    return actor_ctx_from_user(user, school_id="aaryans-joya")


def _seed(fake_db, approval_id="ap-1", routing="owner_only", **extra):
    fake_db.approval_requests.docs.append({
        "id": approval_id, "schoolId": "aaryans-joya", "status": "pending",
        "title": "Schedule change", "routing": routing,
        "submitted_by": "sub-1", **extra,
    })


# ─── validation / not-found ───────────────────────────────────────────────────

async def test_missing_reason_raises_validation(fake_db):
    _seed(fake_db)
    with pytest.raises(ApprovalValidationError):
        await decide_approval_request(fake_db, _ctx(OWNER), {"approval_id": "ap-1", "status": "approved"})


async def test_bad_status_raises_validation(fake_db):
    _seed(fake_db)
    with pytest.raises(ApprovalValidationError):
        await decide_approval_request(fake_db, _ctx(OWNER), {"approval_id": "ap-1", "status": "maybe", "reason": "x"})


async def test_missing_approval_raises_not_found(fake_db):
    with pytest.raises(ApprovalNotFoundError):
        await decide_approval_request(fake_db, _ctx(OWNER), {"approval_id": "ghost", "status": "approved", "reason": "x"})


# ─── routing-dependent authorization (the parity-critical gate) ───────────────

async def test_owner_can_decide_owner_only(fake_db):
    _seed(fake_db, routing="owner_only")
    result = await decide_approval_request(fake_db, _ctx(OWNER), {"approval_id": "ap-1", "status": "approved", "reason": "ok"})
    assert result["status"] == "approved"


async def test_principal_can_decide_owner_and_principal(fake_db):
    _seed(fake_db, routing="owner_and_principal")
    result = await decide_approval_request(fake_db, _ctx(PRINCIPAL), {"approval_id": "ap-1", "status": "approved", "reason": "ok"})
    assert result["status"] == "approved"


async def test_principal_cannot_decide_owner_only(fake_db):
    _seed(fake_db, routing="owner_only")
    with pytest.raises(ApprovalAuthorizationError):
        await decide_approval_request(fake_db, _ctx(PRINCIPAL), {"approval_id": "ap-1", "status": "approved", "reason": "ok"})


async def test_accountant_cannot_decide(fake_db):
    _seed(fake_db, routing="owner_and_principal")
    with pytest.raises(ApprovalAuthorizationError):
        await decide_approval_request(fake_db, _ctx(ACCOUNTANT), {"approval_id": "ap-1", "status": "approved", "reason": "ok"})


# ─── fan-out (audit + notification, canonical shape) ──────────────────────────

async def test_decision_audits_and_notifies(fake_db):
    _seed(fake_db, routing="owner_only")
    await decide_approval_request(fake_db, _ctx(OWNER), {"approval_id": "ap-1", "status": "approved", "reason": "ok"})
    audit = next(a for a in fake_db.audit_logs.docs if a.get("action") == "approval_decide")
    assert audit["entity_type"] == "approval_request"
    notif = next(n for n in fake_db.notifications.docs if n.get("user_id") == "sub-1")
    assert notif["type"] == "approval_decision"


# ─── AI-path closed-hole regression guards ────────────────────────────────────

async def test_ai_principal_cannot_decide_owner_only(fake_db, monkeypatch):
    """Regression: the old AI tool skipped the routing check — a principal could
    decide an owner_only request via chat. Now refused."""
    _seed(fake_db, approval_id="ap-9", routing="owner_only")
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_decide_approval_request(
        {"request_id": "ap-9", "decision": "approve", "reason": "x"}, PRINCIPAL, None
    )
    assert out["success"] is False
    # No decision should have been written.
    assert fake_db.approval_requests.docs[0]["status"] == "pending"


async def test_ai_owner_decision_writes_canonical_audit(fake_db, monkeypatch):
    _seed(fake_db, approval_id="ap-7", routing="owner_only")
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_decide_approval_request(
        {"request_id": "ap-7", "decision": "approve", "reason": "x"}, OWNER, None
    )
    assert out["success"] is True
    assert any(a.get("action") == "approval_decide" for a in fake_db.audit_logs.docs)
