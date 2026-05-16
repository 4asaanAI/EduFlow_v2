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


def test_owner_can_create_salary_structure(client):
    resp = client.post("/api/payroll/structures", json={
        "staff_id": "s1", "designation": "Teacher",
        "base_salary": 25000, "allowances": {"hra": 5000}
    }, headers=_owner_h())
    assert resp.status_code in (200, 201)


def test_accountant_can_read_salary_structures(client):
    resp = client.get("/api/payroll/structures", headers=_accountant_h())
    assert resp.status_code == 200
    assert "data" in resp.json()


def test_accountant_cannot_create_salary_structure(client):
    resp = client.post("/api/payroll/structures", json={"staff_id": "s2", "base_salary": 20000}, headers=_accountant_h())
    assert resp.status_code == 403


def test_owner_can_disburse_salary(client, fake_db):
    resp = client.post("/api/payroll/disburse", json={
        "staff_id": "s3", "month": "2026-05", "gross": 30000, "net": 28000
    }, headers=_owner_h())
    assert resp.status_code in (200, 201)


def test_principal_cannot_read_payroll(client):
    resp = client.get("/api/payroll/disbursements", headers=_principal_h())
    assert resp.status_code == 403


def test_disbursements_list_accessible_to_accountant(client):
    resp = client.get("/api/payroll/disbursements", headers=_accountant_h())
    assert resp.status_code == 200
