"""Story K.1 — dual-entrypoint parity for fee-config CRUD.

Same seed + same actor (owner) through the REST routes
(POST/PATCH /api/fees/structures, POST/PATCH/DELETE /api/fees/discount-types) and
the AI tools (`create_fee_structure`, `update_fee_structure`, `create_discount_type`,
`update_discount_type`, `delete_discount_type`) → `fee_structures` +
`fee_discount_types` + `audit_logs` byte-identical except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "entity_id", "record_id", "structure_id",
             "discount_type_id", "created_at", "updated_at", "timestamp"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask_one(d):
    return {k: v for k, v in d.items() if k not in _VOLATILE}


def _mask_changes(ch):
    out = {}
    for k, v in ch.items():
        out[k] = _mask_one(v) if isinstance(v, dict) else v
    return out


def _mask(docs):
    out = []
    for d in docs:
        m = _mask_one(d)
        ch = m.get("changes")
        if isinstance(ch, dict):
            m = {**m, "changes": _mask_changes(ch)}
        out.append(m)
    out.sort(key=lambda d: (str(d.get("action", "")), str(d.get("name", ""))))
    return out


def _snapshot(fake_db):
    return {
        "fee_structures": _mask(copy.deepcopy(fake_db.fee_structures.docs)),
        "fee_discount_types": _mask(copy.deepcopy(fake_db.fee_discount_types.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("entity_type") == "fee_transaction"]),
    }


def _clear(fake_db):
    for col in ("fee_structures", "fee_discount_types", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


def _structure_payload():
    return {
        "name": "Class 1 Tuition", "class_id": "class-1",
        "fee_heads": [{"name": "Tuition", "amount": 1000, "frequency": "monthly"}],
        "academic_year": "2026-27",
    }


def _discount_payload():
    return {
        "name": "Sibling", "value": 10, "value_type": "percentage",
        "recurrence": "recurring", "reason_note": "Sibling concession",
    }


async def test_create_fee_structure_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    resp = client.post("/api/fees/structures", headers=auth_headers, json=_structure_payload())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_fee_structure(_structure_payload(), OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["fee_structures"]) == 1
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "fee_structure_create"]) == 1


async def test_update_fee_structure_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/fees/structures", headers=auth_headers, json=_structure_payload())
    sid = created.json()["data"]["id"]
    resp = client.patch(f"/api/fees/structures/{sid}", headers=auth_headers, json={"name": "Renamed"})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_fee_structure(_structure_payload(), OWNER_USER, None)
    sid2 = fake_db.fee_structures.docs[0]["id"]
    out = await tool_functions_v2.tool_update_fee_structure(
        {"structure_id": sid2, "name": "Renamed"}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state


async def test_create_discount_type_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    resp = client.post("/api/fees/discount-types", headers=auth_headers, json=_discount_payload())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_discount_type(_discount_payload(), OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["fee_discount_types"]) == 1
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "discount_type_create"]) == 1


async def test_update_discount_type_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/fees/discount-types", headers=auth_headers, json=_discount_payload())
    did = created.json()["data"]["id"]
    resp = client.patch(f"/api/fees/discount-types/{did}", headers=auth_headers,
                        json={"name": "Sibling-2", "is_active": False})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_discount_type(_discount_payload(), OWNER_USER, None)
    did2 = fake_db.fee_discount_types.docs[0]["id"]
    out = await tool_functions_v2.tool_update_discount_type(
        {"discount_type_id": did2, "name": "Sibling-2", "is_active": False}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state


async def test_delete_discount_type_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/fees/discount-types", headers=auth_headers, json=_discount_payload())
    did = created.json()["data"]["id"]
    resp = client.delete(f"/api/fees/discount-types/{did}", headers=auth_headers)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_discount_type(_discount_payload(), OWNER_USER, None)
    did2 = fake_db.fee_discount_types.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_discount_type(
        {"discount_type_id": did2}, OWNER_USER, None
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["fee_discount_types"]) == 0
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "discount_type_delete"]) == 1


def test_delete_discount_type_is_registered_destructive():
    # F.10/FR42: the only K.1 delete tool must carry the destructive flag so the
    # chat layer enforces the two-step confirm + actor-tagged deletion audit.
    tdef = tool_functions_v2.TOOL_REGISTRY["delete_discount_type"]
    assert tdef.get("destructive") is True
