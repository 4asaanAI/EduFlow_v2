from __future__ import annotations
import pytest
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _owner_headers():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _accountant_headers():
    t = create_jwt({"user_id": "a1", "role": "admin", "name": "Acct", "sub_category": "accountant"})
    return {"Authorization": f"Bearer {t}"}


def _plain_admin_headers():
    t = create_jwt({"user_id": "adm1", "role": "admin", "name": "Admin"})
    return {"Authorization": f"Bearer {t}"}


def test_fee_export_returns_csv_with_receipt_column(client):
    """Fee export CSV includes Receipt No column."""
    resp = client.get("/api/export/fee-transactions", headers=_owner_headers())
    assert resp.status_code == 200
    assert "Receipt No" in resp.text or "receipt" in resp.text.lower()


def test_fee_export_includes_corrected_column(client):
    """Fee export CSV includes Corrected column."""
    resp = client.get("/api/export/fee-transactions", headers=_owner_headers())
    assert resp.status_code == 200
    assert "Corrected" in resp.text or "corrected" in resp.text.lower()


def test_fee_export_includes_class_column(client):
    """Fee export CSV includes Class column."""
    resp = client.get("/api/export/fee-transactions", headers=_owner_headers())
    assert resp.status_code == 200
    assert "Class" in resp.text or "class" in resp.text.lower()


def test_fee_export_includes_period_column(client):
    """Fee export CSV includes Period column."""
    resp = client.get("/api/export/fee-transactions", headers=_owner_headers())
    assert resp.status_code == 200
    assert "Period" in resp.text or "period" in resp.text.lower()


def test_fee_export_with_fee_period_filter(client):
    """Fee export accepts fee_period query param without error."""
    resp = client.get("/api/export/fee-transactions?fee_period=2026-April", headers=_owner_headers())
    assert resp.status_code == 200


def test_expense_export_accessible_to_accountant(client):
    """Accountant (admin + sub_category=accounts) can export expenses."""
    resp = client.get("/api/export/expenses", headers=_accountant_headers())
    assert resp.status_code == 200


def test_expense_export_blocked_for_plain_admin(client):
    """Plain admin (no accounts sub_category) cannot export expenses."""
    resp = client.get("/api/export/expenses", headers=_plain_admin_headers())
    assert resp.status_code == 403


def test_expense_export_accessible_to_owner(client):
    """Owner can always export expenses."""
    resp = client.get("/api/export/expenses", headers=_owner_headers())
    assert resp.status_code == 200
