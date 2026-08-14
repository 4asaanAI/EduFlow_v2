from __future__ import annotations

import pytest

from middleware.auth import create_jwt

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
    assert client.post("/api/commercial/crm/leads", headers=teacher, json={}).status_code == 403


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
    # Eight campus-retail paths were listed here until 2026-08-14 and are gone with the
    # feature. They are now covered by the 404 test below, which is a stronger statement:
    # not merely refused to a teacher, but no longer a route at all.
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
    # A group entity is a holding record and nothing may be booked to it. Proven on a CRM
    # lead since 2026-08-14; it used to be proven on a till shift, and the rule is the
    # entity's, not the till's.
    assert client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": group.json()["data"]["id"], "student_name": "Test Child",
        "guardian_name": "Test Guardian", "guardian_phone": "9000000001",
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


def test_entity_accounting_period_and_consolidation_access(client, fake_db):
    owner = _headers("owner-1", "owner")
    accountant = _headers("accountant-1", "admin", "accountant")
    entity = _entity(client, owner)
    fake_db.accounting_periods.docs.append({
        "id": "period-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "entity_id": entity["id"], "name": "August", "start_date": "2026-08-01",
        "end_date": "2026-08-31", "status": "closed",
    })
    # The closed-period rule used to be proven here by refusing a till sale. Campus
    # retail is gone (2026-08-14), so it is proven on an expense instead. The rule belongs
    # to the accounting period, not to the till, and expenses, fees and campus operations
    # all still go through `assert_posting_allowed`.
    blocked = client.post("/api/ops/expenses", headers=owner, json={
        "category": "stationery", "amount": 500, "description": "Books",
        "date": "2026-08-05",
    })
    assert blocked.status_code == 400, blocked.text
    assert "period" in blocked.text.lower()

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


@pytest.mark.parametrize(("method", "path"), [
    ("get", "/api/commercial/products"),
    ("post", "/api/commercial/products"),
    ("delete", "/api/commercial/products/product-1"),
    ("get", "/api/commercial/pos/shifts"),
    ("post", "/api/commercial/pos/shifts"),
    ("patch", "/api/commercial/pos/shifts/shift-1/close"),
    ("get", "/api/commercial/pos/sales"),
    ("post", "/api/commercial/pos/sales"),
    ("post", "/api/commercial/pos/sales/sale-1/returns"),
])
def test_campus_retail_routes_no_longer_exist(client, method, path):
    """The eight shop routes are GONE, not merely refused.

    Abhimanyu, 2026-08-14: The Aaryans runs no shop. The canteen is an outside vendor
    renting space and running its own business, so the school has a tenant there rather
    than a counter of its own.

    A 404 rather than a 403 is the point. A refused route still exists and can be widened
    back by a permission change somebody makes for another reason; a route that is not
    there cannot. This is asserted rather than left to the old tests simply being deleted,
    because a feature that quietly returns is exactly the kind of thing nobody notices
    until real money is typed into it.
    """
    response = client.request(method.upper(), path, headers=_headers("owner-1", "owner"), json={})
    assert response.status_code == 404, (
        f"{method.upper()} {path} answered {response.status_code}; campus retail should be gone"
    )
