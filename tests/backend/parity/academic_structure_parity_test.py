"""Story K.2 — dual-entrypoint parity for academic-structure CRUD.

Same seed + same actor (owner) through the new service-backed REST routes
(POST/PATCH/DELETE /api/settings/classes, POST/PATCH/DELETE /api/activities/houses)
and the AI tools (`create_class`/`update_class`/`delete_class`,
`create_house`/`update_house`/`delete_house`) → `classes` + `houses` +
`audit_logs` byte-identical except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "entity_id", "record_id", "class_id", "house_id",
             "created_at", "updated_at", "timestamp"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask_one(d):
    return {k: v for k, v in d.items() if k not in _VOLATILE}


def _mask_changes(ch):
    return {k: (_mask_one(v) if isinstance(v, dict) else v) for k, v in ch.items()}


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


def _snapshot(fake_db, entity_types):
    return {
        "classes": _mask(copy.deepcopy(fake_db.classes.docs)),
        "houses": _mask(copy.deepcopy(fake_db.houses.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("entity_type") in entity_types]),
    }


_TOUCHED = ("classes", "houses", "audit_logs")


def _clear(fake_db):
    for col in _TOUCHED:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    # `fake_db` is a shared session-level singleton with SEEDED collections
    # (classes has the `class-1` row student-create FK-validates against). Save &
    # restore the originals so emptying them for our len-assertions never leaks.
    saved = {col: copy.deepcopy(getattr(fake_db, col).docs) for col in _TOUCHED}
    _clear(fake_db)
    yield
    for col, docs in saved.items():
        getattr(fake_db, col).docs[:] = docs


# ───────────────────────────── Classes ─────────────────────────────────────


def _class_payload():
    return {"name": "Class 9", "section": "A", "room_number": "R-201"}


async def test_create_class_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    resp = client.post("/api/settings/classes", headers=auth_headers, json=_class_payload())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db, {"class"})

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_class(_class_payload(), OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db, {"class"})

    assert ai_state == rest_state
    assert len(rest_state["classes"]) == 1
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "class_create"]) == 1


async def test_update_class_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/settings/classes", headers=auth_headers, json=_class_payload())
    cid = created.json()["data"]["id"]
    resp = client.patch(f"/api/settings/classes/{cid}", headers=auth_headers, json={"room_number": "R-999"})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db, {"class"})

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_class(_class_payload(), OWNER_USER, None)
    cid2 = fake_db.classes.docs[0]["id"]
    out = await tool_functions_v2.tool_update_class({"class_id": cid2, "room_number": "R-999"}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db, {"class"})
    assert ai_state == rest_state


async def test_delete_class_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/settings/classes", headers=auth_headers, json=_class_payload())
    cid = created.json()["data"]["id"]
    resp = client.delete(f"/api/settings/classes/{cid}", headers=auth_headers)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db, {"class"})

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_class(_class_payload(), OWNER_USER, None)
    cid2 = fake_db.classes.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_class({"class_id": cid2}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db, {"class"})

    assert ai_state == rest_state
    assert len(rest_state["classes"]) == 0
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "class_delete"]) == 1


# ────────────────────────────── Houses ─────────────────────────────────────


def _house_payload():
    return {"name": "Phoenix", "colour": "Orange"}


async def test_create_house_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    resp = client.post("/api/activities/houses", headers=auth_headers, json=_house_payload())
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db, {"house"})

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_house(_house_payload(), OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db, {"house"})

    assert ai_state == rest_state
    assert len(rest_state["houses"]) == 1
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "house_create"]) == 1


async def test_update_house_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/activities/houses", headers=auth_headers, json=_house_payload())
    hid = created.json()["data"]["id"]
    resp = client.patch(f"/api/activities/houses/{hid}", headers=auth_headers, json={"colour": "Crimson"})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db, {"house"})

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_house(_house_payload(), OWNER_USER, None)
    hid2 = fake_db.houses.docs[0]["id"]
    out = await tool_functions_v2.tool_update_house({"house_id": hid2, "colour": "Crimson"}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db, {"house"})
    assert ai_state == rest_state


async def test_delete_house_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    created = client.post("/api/activities/houses", headers=auth_headers, json=_house_payload())
    hid = created.json()["data"]["id"]
    resp = client.delete(f"/api/activities/houses/{hid}", headers=auth_headers)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db, {"house"})

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_create_house(_house_payload(), OWNER_USER, None)
    hid2 = fake_db.houses.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_house({"house_id": hid2}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db, {"house"})

    assert ai_state == rest_state
    assert len(rest_state["houses"]) == 0
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "house_delete"]) == 1
