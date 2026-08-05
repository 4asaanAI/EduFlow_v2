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


async def test_commercial_entity_catalog_shift_sale_return_suite_has_ai_rest_parity(client, fake_db):
    def seed():
        fake_db.legal_entities.docs[:] = []
        fake_db.commercial_products.docs[:] = []
        fake_db.pos_shifts.docs[:] = []
        fake_db.retail_sales.docs[:] = []
        fake_db.retail_returns.docs[:] = []
        fake_db.stock_movements.docs[:] = []
        fake_db.retail_idempotency.docs[:] = []
        fake_db.retail_return_idempotency.docs[:] = []
        fake_db.commercial_sequences.docs[:] = []
        fake_db.audit_logs.docs[:] = []
        fake_db.inventory_items.docs[:] = [{
            "_id": "item-1", "id": "item-1", "schoolId": SCHOOL, "branch_id": BRANCH,
            "sku": "NOTE", "name": "Notebook", "quantity": 10, "on_hand": 10,
            "reorder_level": 2, "is_active": True,
        }]

    seed()
    first = client.post("/api/commercial/entities", headers=_headers(), json={
        "name": "Aaryans School", "code": "TAS", "entity_type": "school",
    }).json()["data"]
    second = client.post("/api/commercial/entities", headers=_headers(), json={
        "name": "Campus Store", "code": "STORE", "entity_type": "company",
    }).json()["data"]
    assert client.patch(f"/api/commercial/entities/{second['id']}/default", headers=_headers(), json={}).status_code == 200
    product = client.post("/api/commercial/products", headers=_headers(), json={
        "entity_id": first["id"], "inventory_item_id": "item-1", "sku": "NOTE",
        "name": "Notebook", "unit_price": 10,
    }).json()["data"]
    shift = client.post("/api/commercial/pos/shifts", headers=_headers(), json={
        "entity_id": first["id"], "register_name": "Counter", "opening_cash": 100,
    }).json()["data"]
    sale_payload = {"entity_id": first["id"], "shift_id": shift["id"],
                    "lines": [{"product_id": product["id"], "quantity": 1}],
                    "payments": [{"mode": "cash", "amount": 10}]}
    sale = client.post("/api/commercial/pos/sales", headers={**_headers(), "Idempotency-Key": "parity-sale"}, json=sale_payload).json()["data"]
    return_payload = {"entity_id": first["id"], "shift_id": shift["id"], "reason": "Unused",
                      "lines": [{"product_id": product["id"], "quantity": 1}]}
    assert client.post(f"/api/commercial/pos/sales/{sale['id']}/returns",
                       headers={**_headers(), "Idempotency-Key": "parity-return"}, json=return_payload).status_code == 200
    assert client.patch(f"/api/commercial/pos/shifts/{shift['id']}/close", headers=_headers(),
                        json={"counted_cash": 100}).status_code == 200
    rest = _commercial_state(fake_db)

    seed()
    ai_first = (await tool_functions_v2.tool_create_legal_entity(
        {"name": "Aaryans School", "code": "TAS", "entity_type": "school"}, OWNER, None
    ))["data"]
    ai_second = (await tool_functions_v2.tool_create_legal_entity(
        {"name": "Campus Store", "code": "STORE", "entity_type": "company"}, OWNER, None
    ))["data"]
    assert ai_first
    await tool_functions_v2.tool_set_default_legal_entity({"entity_id": ai_second["id"]}, OWNER, None)
    ai_product = (await tool_functions_v2.tool_create_retail_product({
        "entity_id": ai_first["id"], "inventory_item_id": "item-1", "sku": "NOTE",
        "name": "Notebook", "unit_price": 10,
    }, OWNER, None))["data"]
    ai_shift = (await tool_functions_v2.tool_open_pos_shift({
        "entity_id": ai_first["id"], "register_name": "Counter", "opening_cash": 100,
    }, OWNER, None))["data"]
    ai_sale = (await tool_functions_v2.tool_post_pos_sale({
        "entity_id": ai_first["id"], "shift_id": ai_shift["id"],
        "lines": [{"product_id": ai_product["id"], "quantity": 1}],
        "payments": [{"mode": "cash", "amount": 10}], "idempotency_key": "parity-sale",
    }, OWNER, None))["data"]
    await tool_functions_v2.tool_post_pos_return({
        "sale_id": ai_sale["id"], "entity_id": ai_first["id"], "shift_id": ai_shift["id"],
        "reason": "Unused", "lines": [{"product_id": ai_product["id"], "quantity": 1}],
        "idempotency_key": "parity-return",
    }, OWNER, None)
    await tool_functions_v2.tool_close_pos_shift(
        {"shift_id": ai_shift["id"], "counted_cash": 100}, OWNER, None
    )
    assert _commercial_state(fake_db) == rest
