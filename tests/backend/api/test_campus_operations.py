from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_student

def _headers(user_id: str, role: str, sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": "branch-a"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "resources", "resource_bookings", "assets", "asset_custody",
        "inventory_items", "stock_movements", "purchase_requisitions", "purchase_orders",
        "library_titles", "library_loans", "students", "guardians", "staff",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def test_resource_calendar_rejects_overlapping_booking(client, fake_db):
    principal = _headers("principal-1", "admin", "principal")
    teacher = _headers("teacher-1", "teacher")
    created = client.post("/api/campus/resources", headers=principal, json={
        "name": "Science Lab", "resource_type": "lab", "capacity": 30,
    })
    assert created.status_code == 200
    resource_id = created.json()["data"]["id"]
    start = datetime.now(timezone.utc) + timedelta(days=1)
    end = start + timedelta(hours=1)
    body = {"resource_id": resource_id, "purpose": "Chemistry practical", "start_at": start.isoformat(), "end_at": end.isoformat(), "attendees": 25}
    first = client.post("/api/campus/resource-bookings", headers=teacher, json=body)
    assert first.status_code == 200
    assert client.post("/api/campus/resource-bookings", headers=teacher, json=body).status_code == 409
    cancelled = client.patch(
        f"/api/campus/resource-bookings/{first.json()['data']['id']}/cancel", headers=teacher
    )
    assert cancelled.status_code == 200
    assert client.post("/api/campus/resource-bookings", headers=teacher, json=body).status_code == 200


def test_asset_custody_checkout_and_return(client, fake_db):
    fake_db.assets.docs.append({
        "id": "asset-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "name": "Projector", "quantity": 1, "status": "active",
    })
    owner = _headers("owner-1", "owner")
    checkout = client.post("/api/campus/assets/asset-1/checkout", headers=owner, json={
        "holder_type": "staff", "holder_id": "teacher-1", "condition": "good",
    })
    assert checkout.status_code == 200
    custody_id = checkout.json()["data"]["id"]
    assert fake_db.assets.docs[0]["current_holder"] == "teacher-1"
    assert client.post(
        "/api/campus/assets/asset-1/checkout", headers=owner,
        json={"holder_type": "staff", "holder_id": "teacher-2"},
    ).status_code == 409
    returned = client.patch(
        f"/api/campus/asset-custody/{custody_id}/return", headers=owner,
        json={"condition": "good"},
    )
    assert returned.status_code == 200
    assert fake_db.assets.docs[0]["custody_status"] == "available"


def test_procurement_receipt_updates_inventory_once(client, fake_db):
    maintenance = _headers("maintenance-1", "admin", "maintenance")
    owner = _headers("owner-1", "owner")
    item_response = client.post("/api/campus/inventory/items", headers=maintenance, json={
        "sku": "PAPER-A4", "name": "A4 paper ream", "opening_quantity": 2,
        "reorder_level": 3, "unit": "ream",
    })
    assert item_response.status_code == 200
    item_id = item_response.json()["data"]["id"]
    requisition = client.post("/api/campus/procurement/requisitions", headers=maintenance, json={
        "purpose": "Monthly stationery", "lines": [{
            "item_id": item_id, "description": "A4 paper ream", "quantity": 5,
            "estimated_unit_cost": 250,
        }],
    })
    requisition_id = requisition.json()["data"]["id"]
    assert client.patch(
        f"/api/campus/procurement/requisitions/{requisition_id}/decision",
        headers=owner, json={"decision": "approve"},
    ).status_code == 200
    order = client.post(
        f"/api/campus/procurement/requisitions/{requisition_id}/order",
        headers=owner, json={"supplier": "Local Stationers"},
    )
    assert order.status_code == 200
    order_id = order.json()["data"]["id"]
    assert client.patch(
        f"/api/campus/procurement/orders/{order_id}/receive", headers=maintenance
    ).status_code == 200
    assert fake_db.inventory_items.docs[0]["on_hand"] == 7
    repeated = client.patch(
        f"/api/campus/procurement/orders/{order_id}/receive", headers=maintenance
    )
    assert repeated.status_code == 200
    assert fake_db.inventory_items.docs[0]["on_hand"] == 7


def test_library_circulation_preserves_copies_and_student_scope(client, fake_db):
    owner = _headers("owner-1", "owner")
    student_headers = _headers("student-user", "student")
    fake_db.students.docs.extend([
        make_student(id="student-a", user_id="student-user", branch_id="branch-a"),
        make_student(id="student-b", user_id="other-student", branch_id="branch-a"),
    ])
    title = client.post("/api/campus/library/titles", headers=owner, json={
        "accession_number": "LIB-001", "title": "The Blue Umbrella",
        "author": "Ruskin Bond", "copies": 1,
    })
    assert title.status_code == 200
    title_id = title.json()["data"]["id"]
    due = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    issued = client.post(f"/api/campus/library/titles/{title_id}/issue", headers=owner, json={
        "borrower_type": "student", "borrower_id": "student-a", "due_at": due,
    })
    assert issued.status_code == 200
    loan_id = issued.json()["data"]["id"]
    assert fake_db.library_titles.docs[0]["copies_available"] == 0
    assert client.post(f"/api/campus/library/titles/{title_id}/issue", headers=owner, json={
        "borrower_type": "student", "borrower_id": "student-b", "due_at": due,
    }).status_code == 409
    own_loans = client.get("/api/campus/library/loans", headers=student_headers)
    assert own_loans.status_code == 200
    assert [row["borrower_id"] for row in own_loans.json()["data"]] == ["student-a"]
    assert client.patch(
        f"/api/campus/library/loans/{loan_id}/return", headers=owner, json={"daily_fine": 1},
    ).status_code == 200
    assert fake_db.library_titles.docs[0]["copies_available"] == 1


def test_library_search_treats_regex_characters_as_literal_text(client, fake_db):
    owner = _headers("owner-1", "owner")
    fake_db.library_titles.docs.extend([
        {
            "id": "literal", "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "title": "C++ Fundamentals", "author": "A. Teacher",
            "accession_number": "LIB-C++", "is_active": True,
        },
        {
            "id": "unrelated", "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "title": "Chemistry", "author": "B. Teacher",
            "accession_number": "LIB-002", "is_active": True,
        },
    ])

    response = client.get("/api/campus/library/titles", params={"search": "C++"}, headers=owner)

    assert response.status_code == 200
    assert [row["id"] for row in response.json()["data"]] == ["literal"]


@pytest.mark.parametrize("path", [
    "/api/campus/resources", "/api/campus/inventory/items",
    "/api/campus/procurement/requisitions", "/api/campus/library/titles",
])
def test_campus_surfaces_require_authentication(client, path):
    assert client.get(path).status_code == 401
