"""Story A.4 — dual-entrypoint parity for the announcement moderation gate.

For the same actor + equivalent audience, the resulting announcement `status` is
identical whether created via REST `POST /api/ops/announcements` (TestClient) or the
AI `create_announcement` tool — for BOTH an exempt actor (owner → active) and a
non-exempt actor (reception → pending_approval).
"""

from __future__ import annotations

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}
RECEPTION_USER = {"id": "rec-1", "role": "admin", "sub_category": "reception", "name": "Reception"}


def _headers(user):
    t = create_jwt({"user_id": user["id"], "role": user["role"], "name": user["name"],
                    **({"sub_category": user["sub_category"]} if user.get("sub_category") else {})})
    return {"Authorization": f"Bearer {t}"}


def _clear(fake_db):
    fake_db.announcements.docs[:] = []
    fake_db.audit_logs.docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def _rest_status(client, fake_db, user):
    _clear(fake_db)
    resp = client.post(
        "/api/ops/announcements",
        headers=_headers(user),
        json={"title": "T", "content": "C", "audience_type": "all"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["status"]


async def _ai_status(fake_db, monkeypatch, user):
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_announcement(
        {"title": "T", "content": "C", "audience_type": "all"}, user, None
    )
    assert out["success"] is True
    return out["data"]["status"]


async def test_owner_all_audience_parity_active(client, fake_db, monkeypatch):
    rest = await _rest_status(client, fake_db, OWNER_USER)
    ai = await _ai_status(fake_db, monkeypatch, OWNER_USER)
    assert rest == ai == "active"


async def test_reception_all_audience_parity_pending(client, fake_db, monkeypatch):
    rest = await _rest_status(client, fake_db, RECEPTION_USER)
    ai = await _ai_status(fake_db, monkeypatch, RECEPTION_USER)
    assert rest == ai == "pending_approval"
