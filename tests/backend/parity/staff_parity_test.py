"""Story J.2 — dual-entrypoint parity for staff CRUD.

Same seed + same actor (owner) through the REST routes (POST /api/staff/,
PATCH /api/staff/{id}) and the AI tools (`create_staff`, `update_staff`) →
`staff` + `auth_users` + `audit_logs` byte-identical except a volatile allowlist
(ids, timestamps, password hashes).
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

# user_id / *_id are references to volatile UUIDs; password_hash is a salted hash.
_VOLATILE = {
    "id", "_id", "user_id", "entity_id", "record_id", "issued_to_staff_id",
    "created_at", "updated_at", "password_hash", "timestamp",
}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _scrub(d):
    out = {}
    for k, v in d.items():
        if k in _VOLATILE:
            continue
        if isinstance(v, dict):
            out[k] = _scrub(v)
        else:
            out[k] = v
    return out


def _mask(docs):
    out = [_scrub(d) for d in docs]
    out.sort(key=lambda d: (str(d.get("action", "")), str(d.get("name", "")),
                            str(d.get("username", "")), str(d.get("staff_type", ""))))
    return out


def _snapshot(fake_db):
    return {
        "staff": _mask(copy.deepcopy(fake_db.staff.docs)),
        "auth_users": _mask(copy.deepcopy(fake_db.auth_users.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("entity_type") == "staff" or a.get("collection") == "staff"]),
    }


def _clear(fake_db):
    fake_db.staff.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    # keep only the seeded admin login; drop any staff-created accounts
    fake_db.auth_users.docs[:] = [u for u in fake_db.auth_users.docs if u.get("id") == "admin-1"]


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


def _payload():
    return {
        "name": "Parity Teacher", "staff_type": "teacher", "department": "Math",
        "phone": "9220000001", "employee_id": "EMP-PAR", "password": "FixedPass1",
    }


async def test_create_staff_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    resp = client.post("/api/staff/", headers=auth_headers, json=_payload())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_staff(_payload(), OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["staff"]) == 1
    # one staff-account login created
    assert any(u.get("username") for u in rest_state["auth_users"] if u.get("username") != "admin")


async def test_create_staff_ai_does_not_leak_temp_password(fake_db, monkeypatch):
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_staff(
        {"name": "Secret Teacher", "staff_type": "teacher"}, OWNER_USER, None
    )
    assert out["success"] is True
    # The plaintext temporary password must never enter the chat/LLM-visible payload.
    assert "temporary_password" not in out.get("data", {})
    assert "EduFlow-" not in str(out)


async def test_update_staff_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    create = client.post("/api/staff/", headers=auth_headers, json=_payload())
    sid = create.json()["data"]["id"]
    resp = client.patch(f"/api/staff/{sid}", headers=auth_headers, json={"department": "Science", "phone": "9220000099"})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    client.post("/api/staff/", headers=auth_headers, json=_payload())
    sid2 = fake_db.staff.docs[0]["id"]
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_update_staff(
        {"staff_id": sid2, "department": "Science", "phone": "9220000099"}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state
