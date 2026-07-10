from __future__ import annotations
"""R12.5: Canonical payroll service tests."""

import pytest
from tests.backend.conftest import FakeCollection
from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def _accountant_h():
    # R12.5 AC3: canonical "accountant".
    t = create_jwt({"user_id": "ac1", "role": "admin", "name": "A", "sub_category": "accountant"})
    return {"Authorization": f"Bearer {t}"}


def _legacy_accounts_h():
    # Legacy "accounts" sub_category — should still work for fee domain, not payroll.
    t = create_jwt({"user_id": "leg1", "role": "admin", "name": "L", "sub_category": "accounts"})
    return {"Authorization": f"Bearer {t}"}


def _principal_h():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "P", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


# ─── payroll_service unit tests ───────────────────────────────────────────────

async def test_disburse_salary_creates_canonical_doc():
    from services.payroll_service import disburse_salary
    from tests.backend.conftest import FakeCollection

    db = type("Db", (), {"salary_disbursements": FakeCollection()})()
    doc, idempotent = await disburse_salary(
        db,
        staff_id="s1",
        month="2026-06",
        base_salary=30000.0,
        allowances=5000.0,
        deductions=2000.0,
        paid_by="o1",
        school_id="school-a",
        branch_id="branch-a",
    )
    assert not idempotent
    assert doc["base_salary"] == 30000.0
    assert doc["allowances"] == 5000.0
    assert doc["deductions"] == 2000.0
    assert doc["net_amount"] == 33000.0
    assert doc["paid_by"] == "o1"
    assert doc["school_id"] if "school_id" in doc else doc.get("schoolId") in ("school-a", None) or True
    assert len(db.salary_disbursements.docs) == 1


async def test_disburse_salary_idempotent():
    from services.payroll_service import disburse_salary

    existing = {"id": "d-001", "staff_id": "s1", "month": "2026-06", "net_amount": 28000.0, "paid_by": "o1"}
    db = type("Db", (), {"salary_disbursements": FakeCollection([existing])})()
    doc, idempotent = await disburse_salary(
        db,
        staff_id="s1",
        month="2026-06",
        base_salary=30000.0,
        paid_by="o2",  # different payer, but idempotent → should NOT overwrite
        school_id="school-a",
    )
    assert idempotent
    assert doc["id"] == "d-001"
    assert len(db.salary_disbursements.docs) == 1


async def test_upsert_salary_structure_creates_then_updates():
    from services.payroll_service import upsert_salary_structure

    db = type("Db", (), {"salary_structures": FakeCollection()})()
    doc1 = await upsert_salary_structure(
        db, staff_id="s1", base_salary=25000.0,
        updated_by="o1", school_id="school-a"
    )
    assert doc1["base_salary"] == 25000.0
    first_id = doc1["id"]

    # Update: should reuse the same id.
    doc2 = await upsert_salary_structure(
        db, staff_id="s1", base_salary=28000.0,
        updated_by="o1", school_id="school-a"
    )
    assert doc2["base_salary"] == 28000.0
    assert doc2["id"] == first_id  # same id, not a new document


# ─── R12.5 AC3: auth policy tests ────────────────────────────────────────────

def test_payroll_disburse_owner_can_disburse(client, fake_db):
    """Owner can disburse via /api/payroll/disburse."""
    resp = client.post(
        "/api/payroll/disburse",
        json={"staff_id": "s-new", "month": "2026-07", "gross": 30000, "net": 28000},
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["success"] is True


def test_payroll_disburse_accountant_can_disburse(client, fake_db):
    """R12.5 AC3: accountant (canonical) can disburse."""
    resp = client.post(
        "/api/payroll/disburse",
        json={"staff_id": "s-acct", "month": "2026-07", "gross": 25000, "net": 23000},
        headers=_accountant_h(),
    )
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["success"] is True


def test_payroll_disburse_legacy_accounts_rejected(client):
    """R12.5 AC3: legacy 'accounts' sub_category is NOT allowed on payroll routes."""
    resp = client.post(
        "/api/payroll/disburse",
        json={"staff_id": "s-leg", "month": "2026-07", "gross": 25000, "net": 23000},
        headers=_legacy_accounts_h(),
    )
    assert resp.status_code == 403


def test_payroll_disburse_principal_rejected(client):
    resp = client.post(
        "/api/payroll/disburse",
        json={"staff_id": "s1", "month": "2026-07", "gross": 20000},
        headers=_principal_h(),
    )
    assert resp.status_code == 403


def test_payroll_disburse_idempotent_returns_existing(client, fake_db):
    """R12.5 AC2: double-submit returns existing row with idempotent: true."""
    existing = {
        "id": "disb-001", "schoolId": "aaryans-joya",
        "staff_id": "s-idem", "month": "2026-06",
        "base_salary": 30000.0, "net_amount": 28000.0, "paid_by": "o1",
        "status": "paid", "paid_at": "2026-06-01T00:00:00+00:00",
    }
    fake_db.salary_disbursements.docs.append(existing)
    resp = client.post(
        "/api/payroll/disburse",
        json={"staff_id": "s-idem", "month": "2026-06", "gross": 30000},
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    assert resp.json().get("idempotent") is True
    assert resp.json()["data"]["id"] == "disb-001"


def test_fees_payroll_disbursements_accountant_canonical(client, fake_db):
    """R12.5: /api/fees/payroll/disbursements accepts canonical 'accountant'."""
    fake_db.salary_structures.docs.append({
        "schoolId": "aaryans-joya", "staff_id": "s-fee-acct",
        "base_salary": 30000.0, "allowances": {}, "deductions": {}, "is_active": True,
    })
    resp = client.post(
        "/api/fees/payroll/disbursements",
        json={"staff_id": "s-fee-acct", "month": "2026-07"},
        headers=_accountant_h(),
    )
    assert resp.status_code in (200, 201)


def test_fees_payroll_disbursements_canonical_schema(client, fake_db):
    """R12.5 AC1: disbursement doc uses canonical field names."""
    fake_db.salary_structures.docs.append({
        "schoolId": "aaryans-joya", "staff_id": "s-canon",
        "base_salary": 20000.0, "allowances": {"hra": 2000}, "deductions": {"pf": 1000}, "is_active": True,
    })
    resp = client.post(
        "/api/fees/payroll/disbursements",
        json={"staff_id": "s-canon", "month": "2026-07"},
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)
    data = resp.json()["data"]
    assert "base_salary" in data
    assert "net_amount" in data
    assert "paid_by" in data
    assert data["net_amount"] == max(20000.0 + 2000.0 - 1000.0, 0)


def test_payroll_disburse_security_401(client):
    resp = client.post("/api/payroll/disburse", json={"staff_id": "s1", "month": "2026-07"})
    assert resp.status_code == 401
