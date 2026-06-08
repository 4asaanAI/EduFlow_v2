"""Epic F dispatch-level integration — F.4 kill-switch, F.5 dry-run, F.10
two-step destructive + deletion audit, F.11 lockdown, F.2 minor-read audit.

Drives the real `/api/chat/confirm` dispatch path with seeded confirm tokens.
"""

from __future__ import annotations

import sys
import os
import uuid as _uuid
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from tests.backend.conftest import APP_AVAILABLE  # noqa: E402

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from middleware.auth import create_jwt  # noqa: E402
from services.confirm_tokens import compute_plan_hash  # noqa: E402
from services import ai_kill_switch, ai_shadow_mode  # noqa: E402

pytestmark = pytest.mark.asyncio


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "name": "Owner"}
TEACHER = {"user_id": "tch-1", "role": "teacher", "name": "Teacher"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    cols = ("confirm_tokens", "ai_dispatch_audit_log", "ai_write_idempotency",
            "ai_rate_limit_counters", "ai_rate_limit_overrides", "system_flags",
            "ai_metrics", "audit_logs")
    for c in cols:
        getattr(fake_db, c).docs[:] = []
    ai_kill_switch.reset_cache()
    ai_shadow_mode.reset_cache()
    yield
    for c in cols:
        getattr(fake_db, c).docs[:] = []
    ai_kill_switch.reset_cache()
    ai_shadow_mode.reset_cache()


def _seed_single_token(db, *, user_id, session_id, action="approve_leave", params=None):
    token = str(_uuid.uuid4())
    db.confirm_tokens.docs.append({
        "_id": token, "token": token, "action": action, "params": params or {"leave_id": "lv-1", "action": "approve"},
        "user_id": user_id, "session_id": session_id,
        "school_id": None, "branch_id": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "used": False, "created_at": datetime.now(timezone.utc),
    })
    return token


def _seed_plan_token(db, *, user_id, session_id, plan):
    token = str(_uuid.uuid4())
    db.confirm_tokens.docs.append({
        "_id": token, "token": token, "action": "plan", "params": {},
        "user_id": user_id, "session_id": session_id, "school_id": None, "branch_id": None,
        "plan": plan, "plan_hash": compute_plan_hash(plan, school_id=None, branch_id=None),
        "schema_version": 1,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "used": False, "created_at": datetime.now(timezone.utc),
    })
    return token


def _patch_tool(monkeypatch, name, fn):
    from routes import chat
    monkeypatch.setitem(chat.TOOL_REGISTRY[name], "fn", fn)


# ── F.4: kill-switch ───────────────────────────────────────────────────────
async def test_kill_switch_blocks_write(client, fake_db, monkeypatch):
    ran = []

    async def _fn(params, user, scope=None):
        ran.append(1)
        return {"success": True}

    _patch_tool(monkeypatch, "approve_leave", _fn)
    await ai_kill_switch.set_ai_writes_enabled(fake_db, enabled=False)
    tok = _seed_single_token(fake_db, user_id="own-1", session_id="s1")
    resp = client.post("/api/chat/confirm", headers=_bearer(OWNER), json={
        "token": tok, "session_id": "s1", "confirmed": True})
    assert resp.status_code == 403, resp.text
    assert resp.json()["detail"]["code"] == "ai_writes_disabled"
    assert ran == []  # tool never ran


async def test_kill_switch_on_allows_write(client, fake_db, monkeypatch):
    async def _fn(params, user, scope=None):
        return {"success": True, "message": "ok"}

    _patch_tool(monkeypatch, "approve_leave", _fn)
    tok = _seed_single_token(fake_db, user_id="own-1", session_id="s1")
    resp = client.post("/api/chat/confirm", headers=_bearer(OWNER), json={
        "token": tok, "session_id": "s1", "confirmed": True})
    assert resp.status_code == 200, resp.text


# ── F.5: dry-run ─────────────────────────────────────────────────────────────
async def test_dry_run_reports_would_change(client, fake_db, monkeypatch):
    async def _fn(params, user, scope=None):
        return {"success": True, "message": "would approve"}

    _patch_tool(monkeypatch, "approve_leave", _fn)
    await ai_shadow_mode.set_ai_dry_run(fake_db, enabled=True)
    tok = _seed_single_token(fake_db, user_id="own-1", session_id="s1")
    resp = client.post("/api/chat/confirm", headers=_bearer(OWNER), json={
        "token": tok, "session_id": "s1", "confirmed": True})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]["result"]
    assert data["dry_run"] is True
    assert "would_change" in data


# ── F.11: lockdown ───────────────────────────────────────────────────────────
async def test_teacher_write_refused_in_phase1(client, fake_db, monkeypatch):
    ran = []

    async def _fn(params, user, scope=None):
        ran.append(1)
        return {"success": True}

    _patch_tool(monkeypatch, "approve_leave", _fn)
    tok = _seed_single_token(fake_db, user_id="tch-1", session_id="s1")
    resp = client.post("/api/chat/confirm", headers=_bearer(TEACHER), json={
        "token": tok, "session_id": "s1", "confirmed": True})
    assert resp.status_code == 403, resp.text
    assert ran == []


# ── F.10: two-step destructive + deletion audit ─────────────────────────────
async def test_destructive_requires_second_ack_then_audits(client, fake_db, monkeypatch):
    async def _fn(params, user, scope=None):
        return {"success": True, "message": "deleted"}

    _patch_tool(monkeypatch, "approve_leave", _fn)  # stand-in write tool flagged destructive
    plan = [{"idx": 0, "tool": "approve_leave", "kind": "write", "destructive": True,
             "params": {"id": "obj-9", "leave_id": "lv-1", "action": "approve"}}]
    tok = _seed_plan_token(fake_db, user_id="own-1", session_id="s1", plan=plan)

    # First confirm WITHOUT ack → 409 destructive_confirmation_required
    r1 = client.post("/api/chat/confirm", headers=_bearer(OWNER), json={
        "token": tok, "session_id": "s1", "confirmed": True})
    assert r1.status_code == 409, r1.text
    assert r1.json()["detail"]["code"] == "destructive_confirmation_required"

    # Token not burned — second confirm WITH ack succeeds + writes deletion audit
    r2 = client.post("/api/chat/confirm", headers=_bearer(OWNER), json={
        "token": tok, "session_id": "s1", "confirmed": True, "destructive_ack": True})
    assert r2.status_code == 200, r2.text
    dels = [d for d in fake_db.audit_logs.docs if d.get("action") == "delete"]
    assert len(dels) == 1
    assert dels[0]["changes"]["actor"] == "own-1"
    assert dels[0]["entity_id"] == "obj-9"


async def test_forbidden_student_delete_tool_refused(client, fake_db):
    plan = [{"idx": 0, "tool": "erase_student", "kind": "write", "params": {"id": "stu-1"}}]
    tok = _seed_plan_token(fake_db, user_id="own-1", session_id="s1", plan=plan)
    resp = client.post("/api/chat/confirm", headers=_bearer(OWNER), json={
        "token": tok, "session_id": "s1", "confirmed": True, "destructive_ack": True})
    assert resp.status_code == 403, resp.text


# ── F.2: minor-read audit ───────────────────────────────────────────────────
async def test_minor_read_writes_audit(fake_db):
    from routes.chat import _audit_minor_read
    raw = {"data": [{"student_id": "stu-1", "name": "A"}, {"admission_number": "ADM-2"}]}
    await _audit_minor_read(fake_db, {"id": "own-1", "role": "owner"}, "search_students", raw)
    rows = [d for d in fake_db.audit_logs.docs if d.get("action") == "minor_record_read"]
    assert len(rows) == 1
    assert set(rows[0]["changes"]["student_refs"]) == {"stu-1", "ADM-2"}


async def test_non_minor_read_tool_not_audited(fake_db):
    from routes.chat import _audit_minor_read
    await _audit_minor_read(fake_db, {"id": "own-1", "role": "owner"}, "get_fee_summary",
                            {"student_id": "stu-1"})
    rows = [d for d in fake_db.audit_logs.docs if d.get("action") == "minor_record_read"]
    assert rows == []
