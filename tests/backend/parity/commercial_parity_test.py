from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"
BRANCH = "branch-a"
OWNER = {"id": "owner-1", "role": "owner", "name": "Owner", "branch_id": BRANCH}
VOLATILE = {
    "_id", "id", "created_at", "updated_at", "changed_at", "entity_id",
    "record_id", "timestamp", "shift_id", "sale_id", "return_id", "product_id",
    "reference_id", "opened_at", "closed_at", "posted_at",
}


def _headers():
    token = create_jwt({"user_id": OWNER["id"], "role": "owner", "name": "Owner", "branch_id": BRANCH})
    return {"Authorization": f"Bearer {token}"}


def _scrub(value):
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _state(fake_db):
    return {
        "enquiries": _scrub(copy.deepcopy(fake_db.enquiries.docs)),
        "audit": _scrub([
            copy.deepcopy(row) for row in fake_db.audit_logs.docs
            if str(row.get("action") or "").startswith("crm_")
        ]),
    }


def _commercial_state(fake_db):
    names = (
        "legal_entities", "commercial_products", "pos_shifts", "retail_sales",
        "retail_returns", "inventory_items", "stock_movements",
    )
    return {name: _scrub(copy.deepcopy(getattr(fake_db, name).docs)) for name in names}


def _seed_entity(fake_db):
    fake_db.legal_entities.docs[:] = [{
        "_id": "entity-1", "id": "entity-1", "schoolId": SCHOOL, "branch_id": BRANCH,
        "name": "The Aaryans", "code": "TAS", "entity_type": "school",
        "is_default": True, "owns_legacy_records": True, "is_active": True,
    }]


@pytest.fixture(autouse=True)
def _setup(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    originals = {name: list(getattr(fake_db, name).docs) for name in (
        "legal_entities", "enquiries", "audit_logs", "crm_contact_keys",
        "commercial_products", "pos_shifts", "retail_sales", "retail_returns",
        "inventory_items", "stock_movements", "retail_idempotency",
        "retail_return_idempotency", "commercial_sequences",
    )}
    fake_db.enquiries.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    fake_db.crm_contact_keys.docs[:] = []
    _seed_entity(fake_db)
    yield
    for name, rows in originals.items():
        getattr(fake_db, name).docs[:] = rows


async def test_create_crm_lead_ai_and_rest_have_same_state(client, fake_db):
    payload = {
        "entity_id": "entity-1", "student_name": "Aarav Singh", "parent_name": "Neha Singh",
        "phone": "9999999999", "email": "neha@example.com", "class_applying": "5",
        "source": "school_event", "next_follow_up": "2026-08-20", "estimated_value": 48000,
    }
    response = client.post("/api/commercial/crm/leads", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    fake_db.enquiries.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    fake_db.crm_contact_keys.docs[:] = []
    output = await tool_functions_v2.tool_create_crm_lead(dict(payload), OWNER, None)
    assert output["success"] is True
    assert _state(fake_db) == rest


async def test_update_crm_lead_ai_and_rest_have_same_state(client, fake_db):
    seed = {
        "_id": "lead-1", "id": "lead-1", "schoolId": SCHOOL, "branch_id": BRANCH,
        "entity_id": "entity-1", "student_name": "Aarav Singh", "status": "new",
        "source": "walk_in", "created_at": "2026-08-01T00:00:00+00:00",
    }
    payload = {"status": "contacted", "next_follow_up": "2026-08-22", "probability": 25}
    fake_db.enquiries.docs[:] = [copy.deepcopy(seed)]
    response = client.patch("/api/commercial/crm/leads/lead-1", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    fake_db.enquiries.docs[:] = [copy.deepcopy(seed)]
    fake_db.audit_logs.docs[:] = []
    output = await tool_functions_v2.tool_update_crm_lead(
        {"enquiry_id": "lead-1", **payload}, OWNER, None
    )
    assert output["success"] is True
    assert _state(fake_db) == rest
