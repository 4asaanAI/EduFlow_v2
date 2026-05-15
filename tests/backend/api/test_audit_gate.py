"""Part 4 Story 4.2: Audit write-ahead gate — fail-open tests.

Ensures that a failure in the pre-write audit insert does NOT block AI
responses. The request must still succeed (200) and a warning must be logged
with "audit" in the message.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone


def _login_owner(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _seed_confirm_token(db, *, user_id, session_id, action="approve_leave", params=None):
    """Seed a valid confirm token into the fake DB."""
    import uuid as _uuid
    token = str(_uuid.uuid4())
    db.confirm_tokens.docs.append({
        "_id": token,
        "token": token,
        "action": action,
        "params": params or {"leave_id": "leave-1", "action": "approve", "reason": "ok"},
        "user_id": user_id,
        "session_id": session_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    return token


@pytest.fixture(autouse=True)
def _clean_collections(fake_db):
    """Reset relevant collections between tests."""
    fake_db.ai_dispatch_audit_log.docs[:] = []
    fake_db.confirm_tokens.docs[:] = []
    fake_db.ai_rate_limit_counters.docs[:] = []
    fake_db.ai_rate_limit_overrides.docs[:] = []
    yield
    fake_db.ai_dispatch_audit_log.docs[:] = []
    fake_db.confirm_tokens.docs[:] = []
    fake_db.ai_rate_limit_counters.docs[:] = []
    fake_db.ai_rate_limit_overrides.docs[:] = []


def test_ai_chat_succeeds_when_audit_write_fails(client, fake_db, monkeypatch):
    """When audit_ai_dispatch_pending raises, the endpoint must still return 200."""
    import routes.chat as chat_routes

    async def _raise_on_audit_write(**kwargs):
        raise Exception("Simulated MongoDB audit write failure")

    monkeypatch.setattr(chat_routes, "audit_ai_dispatch_pending", _raise_on_audit_write)

    # Also mock the tool function to avoid real DB side-effects
    original_registry = chat_routes.TOOL_REGISTRY.copy()

    async def _noop_tool(params, user, *args, **kwargs):
        return {"success": True, "message": "ok"}

    # Patch a write tool's fn directly in TOOL_REGISTRY
    from ai.tool_functions_v2 import TOOL_REGISTRY
    original_fn = TOOL_REGISTRY["approve_leave"]["fn"]
    TOOL_REGISTRY["approve_leave"]["fn"] = _noop_tool

    try:
        token = _login_owner(client)
        headers = {"Authorization": f"Bearer {token}"}
        confirm_token = _seed_confirm_token(
            fake_db, user_id="admin-1", session_id="sess-audit-gate"
        )

        resp = client.post(
            "/api/chat/confirm",
            headers=headers,
            json={
                "token": confirm_token,
                "session_id": "sess-audit-gate",
                "confirmed": True,
                "decision": "confirm",
            },
        )
        # Must succeed even though audit write failed
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    finally:
        TOOL_REGISTRY["approve_leave"]["fn"] = original_fn


def test_audit_write_failure_logs_warning(client, fake_db, monkeypatch, caplog):
    """When audit_ai_dispatch_pending raises, a warning containing 'audit' must be logged."""
    import logging
    import routes.chat as chat_routes

    async def _raise_on_audit_write(**kwargs):
        raise Exception("Simulated MongoDB audit write failure")

    monkeypatch.setattr(chat_routes, "audit_ai_dispatch_pending", _raise_on_audit_write)

    from ai.tool_functions_v2 import TOOL_REGISTRY

    async def _noop_tool(params, user, *args, **kwargs):
        return {"success": True, "message": "ok"}

    original_fn = TOOL_REGISTRY["approve_leave"]["fn"]
    TOOL_REGISTRY["approve_leave"]["fn"] = _noop_tool

    try:
        token = _login_owner(client)
        headers = {"Authorization": f"Bearer {token}"}
        confirm_token = _seed_confirm_token(
            fake_db, user_id="admin-1", session_id="sess-audit-log-warn"
        )

        with caplog.at_level(logging.WARNING, logger="routes.chat"):
            client.post(
                "/api/chat/confirm",
                headers=headers,
                json={
                    "token": confirm_token,
                    "session_id": "sess-audit-log-warn",
                    "confirmed": True,
                    "decision": "confirm",
                },
            )

        # At least one warning should mention "audit"
        audit_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and "audit" in r.message.lower()
        ]
        assert audit_warnings, (
            "Expected a WARNING log containing 'audit' but none found. "
            f"All warnings: {[r.message for r in caplog.records if r.levelno >= logging.WARNING]}"
        )
    finally:
        TOOL_REGISTRY["approve_leave"]["fn"] = original_fn
