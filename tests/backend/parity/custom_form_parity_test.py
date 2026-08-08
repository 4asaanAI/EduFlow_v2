"""Dual-entrypoint parity for controlled school-defined schemas and rows."""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt


SCHOOL = "aaryans-joya"
BRANCH = "branch-a"
OWNER = {"id": "owner-1", "role": "owner", "name": "Owner", "branch_id": BRANCH}
VOLATILE = {
    "_id", "id", "entity_id", "record_id", "created_at", "updated_at",
    "submitted_at", "changed_at", "public_slug", "timestamp",
}


def _headers():
    token = create_jwt({
        "user_id": OWNER["id"], "role": "owner", "name": "Owner", "branch_id": BRANCH,
    })
    return {"Authorization": f"Bearer {token}"}


def _scrub(value):
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _state(fake_db):
    return _scrub({
        "forms": copy.deepcopy(fake_db.custom_forms.docs),
        "responses": copy.deepcopy(fake_db.form_responses.docs),
        "audit": [
            copy.deepcopy(row) for row in fake_db.audit_logs.docs
            if row.get("collection") in {"custom_forms", "form_responses"}
        ],
    })


def _clear(fake_db):
    fake_db.custom_forms.docs[:] = []
    fake_db.form_responses.docs[:] = []
    fake_db.audit_logs.docs[:] = []


def _form():
    return {
        "_id": "form-1", "id": "form-1", "schoolId": SCHOOL,
        "title": "Transport Requests", "schema_version": 1, "is_active": True,
        "fields": [
            {"key": "student", "label": "Student", "type": "text", "required": True},
        ],
        "created_by": OWNER["id"], "created_at": "2026-08-01T00:00:00+00:00",
        "updated_at": "2026-08-01T00:00:00+00:00",
    }


@pytest.fixture(autouse=True)
def _setup(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_create_custom_form_ai_and_rest_have_same_state(client, fake_db):
    payload = {
        "title": "Transport Requests",
        "fields": [{"key": "student", "label": "Student", "type": "text", "required": True}],
    }
    response = client.post("/api/settings/forms", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    result = await tool_functions_v2.tool_create_custom_form(payload, OWNER, None)
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_update_custom_form_ai_and_rest_have_same_state(client, fake_db):
    payload = {"title": "Transport Register"}
    fake_db.custom_forms.docs[:] = [_form()]
    response = client.patch("/api/settings/forms/form-1", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    fake_db.custom_forms.docs[:] = [_form()]
    result = await tool_functions_v2.tool_update_custom_form(
        {"form_id": "form-1", **payload}, OWNER, None
    )
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_add_custom_form_row_ai_and_rest_have_same_state(client, fake_db):
    payload = {"answers": {"student": "Riya"}}
    fake_db.custom_forms.docs[:] = [_form()]
    response = client.post(
        "/api/settings/forms/form-1/responses", json=payload, headers=_headers()
    )
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    fake_db.custom_forms.docs[:] = [_form()]
    result = await tool_functions_v2.tool_add_custom_form_row(
        {"form_id": "form-1", **payload}, OWNER, None
    )
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_delete_custom_form_ai_and_rest_have_same_state(client, fake_db):
    seed_response = {
        "_id": "row-1", "id": "row-1", "schoolId": SCHOOL,
        "form_id": "form-1", "answers": {"student": "Riya"},
    }
    fake_db.custom_forms.docs[:] = [_form()]
    fake_db.form_responses.docs[:] = [copy.deepcopy(seed_response)]
    response = client.delete("/api/settings/forms/form-1", headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    fake_db.custom_forms.docs[:] = [_form()]
    fake_db.form_responses.docs[:] = [copy.deepcopy(seed_response)]
    result = await tool_functions_v2.tool_delete_custom_form(
        {"form_id": "form-1"}, OWNER, None
    )
    assert result["success"] is True
    assert _state(fake_db) == rest
