"""Epic E.5 — plan-then-confirm-once execution end-to-end (FakeDb tier).

Drives the real `/api/chat/confirm` dispatch path with a multi-step plan token:
all steps execute through the one atomic executor, the result lists every step,
and a token that expired while the user read the plan returns the clear,
re-planable `plan_expired` 409 (not a generic 400).
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest

from services.confirm_tokens import compute_plan_hash

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in ("confirm_tokens", "ai_dispatch_audit_log", "ai_write_idempotency",
                "ai_rate_limit_counters", "ai_rate_limit_overrides"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("confirm_tokens", "ai_dispatch_audit_log", "ai_write_idempotency",
                "ai_rate_limit_counters", "ai_rate_limit_overrides"):
        getattr(fake_db, col).docs[:] = []


def _login_owner(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _seed_plan_token(db, *, user_id, session_id, plan, school_id=None, branch_id=None, expired=False):
    token = str(_uuid.uuid4())
    exp = datetime.now(timezone.utc) + (timedelta(minutes=-1) if expired else timedelta(minutes=5))
    db.confirm_tokens.docs.append({
        "_id": token, "token": token, "action": "plan", "params": {},
        "user_id": user_id, "session_id": session_id,
        "school_id": school_id, "branch_id": branch_id,
        "plan": plan, "plan_hash": compute_plan_hash(plan, school_id=school_id, branch_id=branch_id),
        "schema_version": 1, "expires_at": exp, "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    return token


_PLAN = [
    {"idx": 0, "tool": "approve_leave", "kind": "write",
     "params": {"leave_id": "lv-1", "action": "approve"}},
    {"idx": 1, "tool": "create_announcement", "kind": "write",
     "params": {"title": "Closed", "content": "School closed tomorrow"}},
]


async def test_multistep_plan_confirm_runs_all_steps(client, fake_db, monkeypatch):
    from routes import chat

    ran = []

    async def _fake_approve(params, user, scope=None):
        ran.append("approve_leave")
        return {"success": True, "message": "leave approved"}

    async def _fake_announce(params, user, scope=None):
        ran.append("create_announcement")
        return {"success": True, "message": "announced"}

    monkeypatch.setitem(chat.TOOL_REGISTRY["approve_leave"], "fn", _fake_approve)
    monkeypatch.setitem(chat.TOOL_REGISTRY["create_announcement"], "fn", _fake_announce)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    plan_token = _seed_plan_token(fake_db, user_id="admin-1", session_id="sess-P", plan=_PLAN)

    resp = client.post("/api/chat/confirm", headers=headers, json={
        "token": plan_token, "session_id": "sess-P", "confirmed": True, "decision": "confirm",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert ran == ["approve_leave", "create_announcement"]
    assert len(body["data"]["result"]["steps"]) == 2


async def test_expired_plan_token_returns_replanable_409(client, fake_db):
    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    plan_token = _seed_plan_token(
        fake_db, user_id="admin-1", session_id="sess-E", plan=_PLAN, expired=True,
    )
    resp = client.post("/api/chat/confirm", headers=headers, json={
        "token": plan_token, "session_id": "sess-E", "confirmed": True, "decision": "confirm",
    })
    assert resp.status_code == 409, resp.text
    assert resp.json()["detail"]["code"] == "plan_expired"
