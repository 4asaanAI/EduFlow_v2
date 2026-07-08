"""Epic R2 — /confirm dispatch surfaces true outcomes (API tier, FakeDb).

Failure matrix at the HTTP boundary: a confirmed step that returns a failure
envelope aborts with a 422 that names the failed step, and the audit row records
the same failure (reply == audit). A transaction that cannot be started outside
development fails loud with a 503 — never a silent non-transactional write.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest

from services.confirm_tokens import compute_plan_hash

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean(fake_db):
    cols = ("confirm_tokens", "ai_dispatch_audit_log", "ai_write_idempotency",
            "ai_rate_limit_counters", "ai_rate_limit_overrides", "messages")
    for col in cols:
        getattr(fake_db, col).docs[:] = []
    yield
    for col in cols:
        getattr(fake_db, col).docs[:] = []


def _login_owner(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _seed_plan_token(db, *, user_id, session_id, plan, school_id=None, branch_id=None):
    token = str(_uuid.uuid4())
    exp = datetime.now(timezone.utc) + timedelta(minutes=5)
    db.confirm_tokens.docs.append({
        "_id": token, "token": token, "action": "plan", "params": {},
        "user_id": user_id, "session_id": session_id,
        "school_id": school_id, "branch_id": branch_id,
        "plan": plan, "plan_hash": compute_plan_hash(plan, school_id=school_id, branch_id=branch_id),
        "schema_version": 1, "expires_at": exp, "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    return token


def _audit_row(db, token):
    for d in db.ai_dispatch_audit_log.docs:
        if d.get("id") == f"ai-dispatch-{token}":
            return d
    return None


async def test_multistep_step_failure_aborts_with_422_and_audit_agrees(client, fake_db, monkeypatch):
    from routes import chat

    ran = []

    async def _ok(params, user, scope=None):
        ran.append("approve_leave")
        return {"success": True, "message": "approved"}

    async def _fail(params, user, scope=None):
        ran.append("create_announcement")
        return {"success": False, "message": "announcement title already exists"}

    monkeypatch.setitem(chat.TOOL_REGISTRY["approve_leave"], "fn", _ok)
    monkeypatch.setitem(chat.TOOL_REGISTRY["create_announcement"], "fn", _fail)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    plan = [
        {"idx": 0, "tool": "approve_leave", "kind": "write",
         "params": {"leave_id": "lv-1", "action": "approve"}},
        {"idx": 1, "tool": "create_announcement", "kind": "write",
         "params": {"title": "Closed", "content": "x"}},
    ]
    plan_token = _seed_plan_token(fake_db, user_id="admin-1", session_id="sess-F", plan=plan)

    resp = client.post("/api/chat/confirm", headers=headers, json={
        "token": plan_token, "session_id": "sess-F", "confirmed": True, "decision": "confirm",
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "step_failed"
    assert detail["failed_tool"] == "create_announcement"
    assert "No changes were applied" in detail["message"]

    # The audit row records the failure — the user reply and the audit agree.
    row = _audit_row(fake_db, plan_token)
    assert row is not None
    assert row["success"] is False
    assert row["status"] == "failure"


async def test_single_action_failure_reply_from_actual_result(client, fake_db, monkeypatch):
    from routes import chat

    async def _fail(params, user, scope=None):
        return {"success": False, "message": "student already inactive"}

    monkeypatch.setitem(chat.TOOL_REGISTRY["set_student_status"], "fn", _fail)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    # Legacy single-action token (no `plan`) — the classic single confirmed write.
    tok = str(_uuid.uuid4())
    fake_db.confirm_tokens.docs.append({
        "_id": tok, "token": tok, "action": "set_student_status",
        "params": {"student_id": "stu-1", "status": "inactive"},
        "user_id": "admin-1", "session_id": "sess-S",
        "school_id": None, "branch_id": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "used": False, "created_at": datetime.now(timezone.utc),
    })

    resp = client.post("/api/chat/confirm", headers=headers, json={
        "token": tok, "session_id": "sess-S", "confirmed": True, "decision": "confirm",
    })
    assert resp.status_code == 422, resp.text
    detail = resp.json()["detail"]
    assert detail["code"] == "step_failed"
    # The reply is composed from the tool's own failure message.
    assert "student already inactive" in detail["message"]
    row = _audit_row(fake_db, tok)
    assert row is not None and row["success"] is False


async def test_post_commit_metric_failure_still_returns_success(client, fake_db, monkeypatch):
    """XM9: a committed plan must never become a user-facing 500 because a
    post-commit metric/audit write failed."""
    from routes import chat

    async def _ok(params, user, scope=None):
        return {"success": True, "message": "leave approved"}

    monkeypatch.setitem(chat.TOOL_REGISTRY["approve_leave"], "fn", _ok)

    async def _boom_metric(*args, **kwargs):
        raise RuntimeError("metrics backend down")

    monkeypatch.setattr(chat, "record_ai_metric", _boom_metric)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    plan = [{"idx": 0, "tool": "approve_leave", "kind": "write",
             "params": {"leave_id": "lv-1", "action": "approve"}}]
    plan_token = _seed_plan_token(fake_db, user_id="admin-1", session_id="sess-M", plan=plan)

    resp = client.post("/api/chat/confirm", headers=headers, json={
        "token": plan_token, "session_id": "sess-M", "confirmed": True, "decision": "confirm",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["success"] is True


async def test_txn_unavailable_returns_503(client, fake_db, monkeypatch):
    from routes import chat
    from ai import plan_executor
    from database import TransactionUnavailableError

    async def _ok(params, user, scope=None):
        return {"success": True, "message": "ok"}

    monkeypatch.setitem(chat.TOOL_REGISTRY["approve_leave"], "fn", _ok)

    async def _boom():
        raise TransactionUnavailableError("no txn")

    # Force the executor's session factory to fail as it would outside development
    # when start_session() is unavailable.
    monkeypatch.setattr(plan_executor, "get_txn_session", _boom)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    plan = [{"idx": 0, "tool": "approve_leave", "kind": "write",
             "params": {"leave_id": "lv-1", "action": "approve"}}]
    plan_token = _seed_plan_token(fake_db, user_id="admin-1", session_id="sess-T", plan=plan)

    resp = client.post("/api/chat/confirm", headers=headers, json={
        "token": plan_token, "session_id": "sess-T", "confirmed": True, "decision": "confirm",
    })
    assert resp.status_code == 503, resp.text
    assert resp.json()["detail"]["code"] == "txn_unavailable"
