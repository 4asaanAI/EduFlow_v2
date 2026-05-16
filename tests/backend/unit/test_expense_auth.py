from __future__ import annotations

import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _accountant_h():
    t = create_jwt({"user_id": "a1", "role": "admin", "name": "A", "sub_category": "accounts"})
    return {"Authorization": f"Bearer {t}"}


def _principal_h():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "P", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def test_accountant_can_list_expenses(client):
    resp = client.get("/api/ops/expenses", headers=_accountant_h())
    assert resp.status_code == 200


def test_principal_cannot_list_expenses(client):
    resp = client.get("/api/ops/expenses", headers=_principal_h())
    assert resp.status_code == 403


def test_owner_can_list_expenses(client):
    resp = client.get("/api/ops/expenses", headers=_owner_h())
    assert resp.status_code == 200


def test_owner_can_create_expense(client):
    resp = client.post(
        "/api/ops/expenses",
        json={"category": "Utilities", "amount": 500, "description": "Electricity", "date": "2026-05-16"},
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)


def test_accountant_can_create_expense(client):
    resp = client.post(
        "/api/ops/expenses",
        json={"category": "Supplies", "amount": 200, "description": "Stationery", "date": "2026-05-16"},
        headers=_accountant_h(),
    )
    assert resp.status_code in (200, 201)


def test_principal_cannot_create_expense(client):
    resp = client.post(
        "/api/ops/expenses",
        json={"category": "Utilities", "amount": 100},
        headers=_principal_h(),
    )
    assert resp.status_code == 403


def test_expense_summary_returns_data(client):
    resp = client.get("/api/ops/expenses/summary", headers=_accountant_h())
    assert resp.status_code == 200
    assert "monthly" in resp.json()["data"]
    assert "ytd" in resp.json()["data"]


def test_expense_summary_owner_allowed(client):
    resp = client.get("/api/ops/expenses/summary", headers=_owner_h())
    assert resp.status_code == 200


def test_expense_summary_principal_forbidden(client):
    resp = client.get("/api/ops/expenses/summary", headers=_principal_h())
    assert resp.status_code == 403
