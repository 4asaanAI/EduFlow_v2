from __future__ import annotations

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _headers(user_id: str, role: str, sub_category: str | None = None, branch_id: str = "branch-a"):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": branch_id}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "legal_entities", "commercial_sequences", "enquiries", "crm_activities", "crm_contact_keys",
        "crm_opportunities", "commercial_products", "pos_shifts", "retail_sales",
        "retail_returns", "retail_idempotency", "retail_return_idempotency",
        "inventory_items", "stock_movements", "accounting_periods", "audit_logs",
        "students", "guardians",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _entity(client, owner, *, name="The Aaryans School", code="TAS", **extra):
    response = client.post("/api/commercial/entities", headers=owner, json={
        "name": name, "code": code, "entity_type": "school", **extra,
    })
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_commercial_endpoints_require_auth_and_role(client):
    assert client.get("/api/commercial/entities").status_code == 401
    teacher = _headers("teacher-1", "teacher")
    assert client.get("/api/commercial/entities", headers=teacher).status_code == 403
    assert client.post("/api/commercial/pos/sales", headers=teacher, json={}).status_code == 403


@pytest.mark.parametrize(("method", "path"), [
    ("get", "/api/commercial/entities"),
    ("post", "/api/commercial/entities"),
    ("patch", "/api/commercial/entities/entity-1/default"),
    ("get", "/api/commercial/summary"),
    ("get", "/api/commercial/crm/leads"),
    ("post", "/api/commercial/crm/leads"),
    ("patch", "/api/commercial/crm/leads/lead-1"),
    ("get", "/api/commercial/crm/leads/lead-1/activities"),
    ("post", "/api/commercial/crm/leads/lead-1/activities"),
    ("post", "/api/commercial/crm/leads/lead-1/opportunities"),
    ("get", "/api/commercial/crm/opportunities"),
    ("patch", "/api/commercial/crm/opportunities/opportunity-1"),
    ("get", "/api/commercial/crm/pipeline"),
    ("get", "/api/commercial/products"),
    ("post", "/api/commercial/products"),
    ("get", "/api/commercial/pos/shifts"),
    ("post", "/api/commercial/pos/shifts"),
    ("patch", "/api/commercial/pos/shifts/shift-1/close"),
    ("get", "/api/commercial/pos/sales"),
    ("post", "/api/commercial/pos/sales"),
    ("post", "/api/commercial/pos/sales/sale-1/returns"),
])
def test_every_commercial_endpoint_rejects_wrong_role(client, method, path):
    response = client.request(method.upper(), path, headers=_headers("teacher-1", "teacher"), json={})
    assert response.status_code == 403


def test_legal_entity_group_rules_default_and_branch_isolation(client, fake_db):
    owner = _headers("owner-1", "owner")
    group = client.post("/api/commercial/entities", headers=owner, json={
        "name": "Aaryans Trust", "code": "AT", "entity_type": "group",
    })
    assert group.status_code == 200
    child = _entity(client, owner, parent_entity_id=group.json()["data"]["id"])
    assert child["is_default"] is True
    assert client.post("/api/commercial/pos/shifts", headers=owner, json={
        "entity_id": group.json()["data"]["id"], "register_name": "Counter 1",
    }).status_code == 400
    fake_db.legal_entities.docs.append({
        "id": "other-branch", "schoolId": "aaryans-joya", "branch_id": "branch-b",
        "name": "Hidden", "code": "HID", "entity_type": "school", "is_active": True,
    })
    fake_db.legal_entities.docs.append({
        "id": "other-school", "schoolId": "other-school", "branch_id": "branch-a",
        "name": "Other tenant", "code": "OTH", "entity_type": "school", "is_active": True,
    })
    listed = client.get("/api/commercial/entities", headers=owner)
    assert listed.status_code == 200
    assert {row["id"] for row in listed.json()["data"]} == {group.json()["data"]["id"], child["id"]}


def test_school_crm_extends_enquiry_with_activity_opportunity_and_loss_rule(client):
    owner = _headers("owner-1", "owner")
    entity = _entity(client, owner)
    lead = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity["id"], "student_name": "Aarav Singh", "parent_name": "Neha Singh",
        "phone": "9999999999", "email": "neha@example.com", "class_applying": "5",
        "source": "school_event", "next_follow_up": "2026-08-01", "estimated_value": 48000,
    })
    assert lead.status_code == 200, lead.text
    lead_id = lead.json()["data"]["id"]
    duplicate = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity["id"], "student_name": "Second", "phone": "9999999999",
    })
    assert duplicate.status_code == 409
    second = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity["id"], "student_name": "Second", "phone": "8888888888",
    })
    assert second.status_code == 200
    duplicate_update = client.patch(
        f"/api/commercial/crm/leads/{second.json()['data']['id']}", headers=owner,
        json={"phone": "9999999999"},
    )
    assert duplicate_update.status_code == 409
    enrolled_without_links = client.patch(
        f"/api/commercial/crm/leads/{lead_id}", headers=owner, json={"status": "enrolled"}
    )
    assert enrolled_without_links.status_code == 400
    activity = client.post(f"/api/commercial/crm/leads/{lead_id}/activities", headers=owner, json={
        "activity_type": "call", "subject": "Parent callback", "next_follow_up": "2026-08-10",
    })
    assert activity.status_code == 200
    opportunity = client.post(f"/api/commercial/crm/leads/{lead_id}/opportunities", headers=owner, json={
        "title": "Class 5 admission", "amount": 48000, "probability": 60,
    })
    assert opportunity.status_code == 200
    lost_without_reason = client.patch(f"/api/commercial/crm/leads/{lead_id}", headers=owner, json={
        "status": "lost",
    })
    assert lost_without_reason.status_code == 400
    lost = client.patch(f"/api/commercial/crm/leads/{lead_id}", headers=owner, json={
        "status": "lost", "lost_reason": "Family moved city",
    })
    assert lost.status_code == 200


def test_pos_sale_return_idempotency_stock_and_shift_close(client, fake_db):
    owner = _headers("owner-1", "owner")
    entity = _entity(client, owner)
    fake_db.inventory_items.docs.append({
        "id": "item-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "sku": "NOTE-A5", "name": "A5 Notebook", "is_active": True,
        "on_hand": 5, "quantity": 5,
    })
    fake_db.students.docs.append({
        "id": "student-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "name": "Aarav", "is_active": True,
    })
    product = client.post("/api/commercial/products", headers=owner, json={
        "entity_id": entity["id"], "inventory_item_id": "item-1", "sku": "NOTE-A5",
        "name": "A5 Notebook", "unit_price": 100, "tax_rate_percent": 0,
    })
    assert product.status_code == 200, product.text
    shift = client.post("/api/commercial/pos/shifts", headers=owner, json={
        "entity_id": entity["id"], "register_name": "Book Counter", "opening_cash": 10,
    })
    assert shift.status_code == 200, shift.text
    body = {
        "entity_id": entity["id"], "shift_id": shift.json()["data"]["id"],
        "customer_type": "student", "customer_id": "student-1", "customer_name": "Aarav",
        "lines": [{"product_id": product.json()["data"]["id"], "quantity": 2, "unit_price": 100}],
        "payments": [{"mode": "cash", "amount": 200}],
    }
    headers = {**owner, "Idempotency-Key": "sale-one"}
    first = client.post("/api/commercial/pos/sales", headers=headers, json=body)
    assert first.status_code == 200, first.text
    replay = client.post("/api/commercial/pos/sales", headers=headers, json=body)
    assert replay.status_code == 200
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert fake_db.inventory_items.docs[0]["on_hand"] == 3
    returned = client.post(
        f"/api/commercial/pos/sales/{first.json()['data']['id']}/returns",
        headers={**owner, "Idempotency-Key": "return-one"}, json={
            "entity_id": entity["id"], "shift_id": shift.json()["data"]["id"],
            "reason": "Unused", "lines": [{"product_id": product.json()["data"]["id"], "quantity": 1}],
        },
    )
    assert returned.status_code == 200, returned.text
    assert fake_db.inventory_items.docs[0]["on_hand"] == 4
    excessive = client.post(
        f"/api/commercial/pos/sales/{first.json()['data']['id']}/returns",
        headers={**owner, "Idempotency-Key": "return-too-many"}, json={
            "entity_id": entity["id"], "shift_id": shift.json()["data"]["id"],
            "reason": "No", "lines": [{"product_id": product.json()["data"]["id"], "quantity": 2}],
            "payments": [{"mode": "cash", "amount": 200}],
        },
    )
    assert excessive.status_code == 409
    close = client.patch(
        f"/api/commercial/pos/shifts/{shift.json()['data']['id']}/close",
        headers=owner, json={"counted_cash": 110},
    )
    assert close.status_code == 200, close.text
    assert close.json()["data"]["variance_paise"] == 0


def test_entity_accounting_period_and_consolidation_access(client, fake_db):
    owner = _headers("owner-1", "owner")
    accountant = _headers("accountant-1", "admin", "accountant")
    entity = _entity(client, owner)
    fake_db.accounting_periods.docs.append({
        "id": "period-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "entity_id": entity["id"], "name": "August", "start_date": "2026-08-01",
        "end_date": "2026-08-31", "status": "closed",
    })
    fake_db.inventory_items.docs.append({
        "id": "item-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "sku": "BOOK", "name": "Book", "is_active": True, "on_hand": 5, "quantity": 5,
    })
    product = client.post("/api/commercial/products", headers=owner, json={
        "entity_id": entity["id"], "inventory_item_id": "item-1", "sku": "BOOK",
        "name": "Book", "unit_price": 50,
    }).json()["data"]
    shift = client.post("/api/commercial/pos/shifts", headers=owner, json={
        "entity_id": entity["id"], "register_name": "Counter",
    }).json()["data"]
    blocked = client.post("/api/commercial/pos/sales", headers={**owner, "Idempotency-Key": "closed"}, json={
        "entity_id": entity["id"], "shift_id": shift["id"], "posting_date": "2026-08-05",
        "lines": [{"product_id": product["id"], "quantity": 1}],
        "payments": [{"mode": "cash", "amount": 50}],
    })
    assert blocked.status_code == 409
    assert client.get("/api/commercial/summary?consolidated=true", headers=accountant).status_code == 403
    assert client.get("/api/commercial/summary?consolidated=true", headers=owner).status_code == 200


async def test_flo_commercial_tool_is_scoped_and_consolidation_is_owner_only(fake_db):
    from ai.tool_functions_v2 import TOOL_REGISTRY

    fake_db.legal_entities.docs.append({
        "id": "entity-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "name": "The Aaryans School", "code": "TAS", "entity_type": "school",
        "is_active": True, "is_default": True, "is_group": False,
    })
    fn = TOOL_REGISTRY["get_commercial_operations"]["fn"]
    owner = {"id": "owner-1", "role": "owner", "branch_id": "branch-a"}
    accountant = {"id": "accountant-1", "role": "admin", "sub_category": "accountant", "branch_id": "branch-a"}
    overview = await fn({"domain": "overview"}, owner, {"branch_id": "branch-a"})
    assert overview["success"] is True
    assert overview["data"]["crm"]["entity"]["id"] == "entity-a"
    denied = await fn({"domain": "consolidated"}, accountant, {"branch_id": "branch-a"})
    assert denied["success"] is False
    assert denied["denied"] is True
