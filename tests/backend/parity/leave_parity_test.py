"""Story A.2 — dual-entrypoint parity for leave decisions.

Same seed through both write entrypoints (REST PATCH /api/staff/leaves/{id} via
TestClient, and the AI `approve_leave` tool via its real dispatch fn) → the leave
doc + staff notification + audit row are byte-identical except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "approved_at"}

# Same actor on both sides (principal). The REST JWT and the AI user dict resolve
# to the same actor_ctx: id=prin-1, role=admin, sub_category=principal, branch_id=None.
PRINCIPAL_USER = {"id": "prin-1", "role": "admin", "sub_category": "principal", "name": "Principal"}


def _principal_headers():
    t = create_jwt({"user_id": "prin-1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: (d.get("entity_id", ""), d.get("user_id", ""), d.get("action", ""), d.get("status", "")))
    return out


def _snapshot(fake_db):
    return {
        "leave_requests": _mask(copy.deepcopy(fake_db.leave_requests.docs)),
        "notifications": _mask(copy.deepcopy(fake_db.notifications.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if str(a.get("action", "")).startswith("leave_")]),
    }


def _clear(fake_db):
    for col in ("leave_requests", "notifications", "audit_logs", "staff"):
        getattr(fake_db, col).docs[:] = []


def _seed(fake_db, leave_id):
    fake_db.leave_requests.docs.append({
        "id": leave_id, "schoolId": "aaryans-joya", "status": "pending",
        "staff_id": "s1", "user_id": "u1",
        "start_date": "2026-06-01", "end_date": "2026-06-03",
    })


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_ai_and_rest_leave_decision_identical(client, fake_db, monkeypatch):
    # Same seed id on both sides → masked docs compare directly (entity_id matches).
    # --- REST entrypoint ---
    _seed(fake_db, "lr-x")
    resp = client.patch("/api/staff/leaves/lr-x", json={"status": "approved"}, headers=_principal_headers())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI entrypoint (same actor, same seed) ---
    _clear(fake_db)
    _seed(fake_db, "lr-x")
    monkeypatch.setattr(tool_functions, "get_db", lambda: fake_db)
    out = await tool_functions.tool_approve_leave({"leave_id": "lr-x", "action": "approve"}, PRINCIPAL_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state["leave_requests"] == rest_state["leave_requests"]
    assert ai_state["notifications"] == rest_state["notifications"]
    assert ai_state["audit_logs"] == rest_state["audit_logs"]
    # Sanity: non-trivial (decision + notification + audit all happened).
    assert rest_state["leave_requests"][0]["status"] == "approved"
    assert len(rest_state["notifications"]) == 1
    assert len(rest_state["audit_logs"]) == 1
