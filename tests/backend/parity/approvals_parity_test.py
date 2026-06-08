"""Story A.3 — dual-entrypoint parity for approval decisions.

Same seed + same actor (owner) through REST PATCH .../decide and the AI
`decide_approval_request` tool → approval doc + audit row + notification are
byte-identical except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "decided_at"}

OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask(docs):
    out = []
    for d in docs:
        m = {k: v for k, v in d.items() if k not in _VOLATILE}
        if isinstance(m.get("changes"), dict):
            m["changes"] = {k: v for k, v in m["changes"].items() if k not in _VOLATILE}
        out.append(m)
    out.sort(key=lambda d: (d.get("entity_id", ""), d.get("user_id", ""), d.get("action", ""), d.get("status", "")))
    return out


def _snapshot(fake_db):
    return {
        "approval_requests": _mask(copy.deepcopy(fake_db.approval_requests.docs)),
        "notifications": _mask(copy.deepcopy(fake_db.notifications.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == "approval_decide"]),
    }


def _clear(fake_db):
    for col in ("approval_requests", "notifications", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _seed(fake_db):
    fake_db.approval_requests.docs.append({
        "id": "ap-x", "schoolId": "aaryans-joya", "status": "pending",
        "title": "Schedule change", "routing": "owner_only", "submitted_by": "sub-1",
    })


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_ai_and_rest_approval_decision_identical(client, auth_headers, fake_db, monkeypatch):
    # --- REST entrypoint (auth_headers = owner admin-1) ---
    _seed(fake_db)
    resp = client.patch(
        "/api/operations/approval-requests/ap-x/decide",
        json={"status": "approved", "reason": "ok"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI entrypoint (same owner, same seed) ---
    _clear(fake_db)
    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_decide_approval_request(
        {"request_id": "ap-x", "decision": "approve", "reason": "ok"}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state["approval_requests"] == rest_state["approval_requests"]
    assert ai_state["notifications"] == rest_state["notifications"]
    assert ai_state["audit_logs"] == rest_state["audit_logs"]
    assert rest_state["approval_requests"][0]["status"] == "approved"
    assert len(rest_state["audit_logs"]) == 1
    assert len(rest_state["notifications"]) == 1
