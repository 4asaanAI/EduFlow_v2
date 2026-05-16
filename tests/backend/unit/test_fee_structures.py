from __future__ import annotations

import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def _accountant_h():
    t = create_jwt({"user_id": "a1", "role": "admin", "name": "A", "sub_category": "accounts"})
    return {"Authorization": f"Bearer {t}"}


def _principal_h():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "P", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def test_owner_can_create_fee_structure(client):
    resp = client.post(
        "/api/fees/structures",
        json={
            "name": "Annual 2026-27",
            "class_id": "cls-1",
            "fee_heads": [{"name": "Tuition", "amount": 12000}],
            "academic_year": "2026-27",
        },
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["name"] == "Annual 2026-27"


def test_accountant_cannot_create_fee_structure(client):
    resp = client.post(
        "/api/fees/structures",
        json={"name": "Test"},
        headers=_accountant_h(),
    )
    assert resp.status_code == 403


def test_principal_cannot_create_fee_structure(client):
    resp = client.post(
        "/api/fees/structures",
        json={"name": "Test"},
        headers=_principal_h(),
    )
    assert resp.status_code == 403


def test_accountant_can_read_fee_structures(client):
    resp = client.get("/api/fees/structures", headers=_accountant_h())
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_owner_can_read_fee_structures(client):
    resp = client.get("/api/fees/structures", headers=_owner_h())
    assert resp.status_code == 200


def test_owner_can_update_fee_structure(client, fake_db):
    # Seed a structure to patch
    fake_db.fee_structures.docs = [
        {"id": "fs-1", "schoolId": "aaryans-joya", "name": "Old Name", "class_id": "cls-1"}
    ]
    resp = client.patch(
        "/api/fees/structures/fs-1",
        json={"name": "Updated Name"},
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_accountant_cannot_update_fee_structure(client, fake_db):
    fake_db.fee_structures.docs = [
        {"id": "fs-2", "schoolId": "aaryans-joya", "name": "Old Name"}
    ]
    resp = client.patch(
        "/api/fees/structures/fs-2",
        json={"name": "Hacked"},
        headers=_accountant_h(),
    )
    assert resp.status_code == 403
