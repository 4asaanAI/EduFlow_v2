"""Story K.3 — dual-entrypoint parity for org-config CRUD.

Same seed + same actor (owner) through the REST routes
(POST/PUT/DELETE /api/settings/branches, PATCH /api/settings/school,
POST /api/settings/year-end-transition) and the AI tools (`create_branch`,
`update_branch`, `delete_branch`, `update_school_settings`, `year_end_transition`)
→ `branches` + `school_settings` + `academic_years` + `audit_logs` byte-identical
except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "entity_id", "record_id", "branch_id",
             "created_at", "updated_at", "timestamp"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask_one(d):
    return {k: v for k, v in d.items() if k not in _VOLATILE}


def _mask_changes(ch):
    # changes may be a FLAT doc (branch_upsert/school_settings embed updated_at)
    # or carry a nested doc ("deleted"/"new_year"). Drop volatile keys at both levels.
    out = {}
    for k, v in ch.items():
        if k in _VOLATILE:
            continue
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


_AUDIT_COLLECTIONS = {"branches", "school_settings", "academic_years"}


def _snapshot(fake_db):
    return {
        "branches": _mask(copy.deepcopy(fake_db.branches.docs)),
        "school_settings": _mask(copy.deepcopy(fake_db.school_settings.docs)),
        "academic_years": _mask(copy.deepcopy(fake_db.academic_years.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("collection") in _AUDIT_COLLECTIONS]),
    }


_TOUCHED = ("branches", "school_settings", "academic_years", "audit_logs")


def _clear(fake_db):
    for col in _TOUCHED:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    # `fake_db` is a shared session-level singleton with SEEDED collections
    # (academic_years). Save & restore so emptying for our assertions never leaks.
    saved = {col: copy.deepcopy(getattr(fake_db, col).docs) for col in _TOUCHED}
    _clear(fake_db)
    yield
    for col, docs in saved.items():
        getattr(fake_db, col).docs[:] = docs


# ───────────────────────────── Branches ────────────────────────────────────


async def test_create_branch_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    payload = {"name": "North Campus", "branch_code": "NC", "location": "Sector 5"}
    resp = client.post("/api/settings/branches", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_create_branch(payload, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["branches"]) == 1


async def test_update_branch_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    payload = {"name": "South Campus", "address": "Main Rd", "phone": "999"}
    resp = client.put("/api/settings/branches/br-1", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_update_branch({**payload, "branch_id": "br-1"}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state


async def test_delete_branch_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    client.put("/api/settings/branches/br-2", headers=auth_headers, json={"name": "Temp"})
    resp = client.delete("/api/settings/branches/br-2", headers=auth_headers)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    await tool_functions_v2.tool_update_branch({"branch_id": "br-2", "name": "Temp"}, OWNER_USER, None)
    out = await tool_functions_v2.tool_delete_branch({"branch_id": "br-2"}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len(rest_state["branches"]) == 0
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "branch_delete"]) == 1


# ───────────────────────── School settings ─────────────────────────────────


async def test_update_school_settings_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    payload = {"school_name": "Aaryans Intl", "board": "CBSE", "attendance_threshold": 75}
    resp = client.patch("/api/settings/school", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_update_school_settings(payload, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)
    assert ai_state == rest_state


# ──────────────────────── Year-end transition ──────────────────────────────


async def test_year_end_transition_ai_and_rest_identical(client, auth_headers, fake_db, monkeypatch):
    payload = {"new_year_name": "2027-28"}
    resp = client.post("/api/settings/year-end-transition", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_year_end_transition(payload, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert len([y for y in rest_state["academic_years"] if y.get("is_current")]) == 1
    assert len([a for a in rest_state["audit_logs"] if a["action"] == "academic_year_transition"]) == 1
