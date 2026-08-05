from __future__ import annotations

from datetime import date

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_staff

def _headers(user_id: str, role: str, sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": "branch-a"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "accounting_periods", "salary_disbursements", "salary_disbursement_corrections",
        "salary_structures", "staff", "audit_logs",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _current_period():
    today = date.today()
    return {
        "name": today.strftime("%B %Y"),
        "start_date": today.replace(day=1).isoformat(),
        "end_date": today.replace(day=28).isoformat() if today.day <= 28 else today.isoformat(),
    }


def test_closed_accounting_period_blocks_new_payroll_posting(client, fake_db):
    owner = _headers("owner-1", "owner")
    fake_db.staff.docs.extend([
        make_staff(id="staff-a", branch_id="branch-a"), make_staff(id="staff-b", branch_id="branch-a"),
    ])
    period = client.post("/api/accounting/periods", headers=owner, json=_current_period())
    assert period.status_code == 200
    month = date.today().strftime("%Y-%m")
    first = client.post("/api/payroll/disburse", headers=owner, json={
        "staff_id": "staff-a", "month": month, "base_salary": 30000,
    })
    assert first.status_code == 200
    period_id = period.json()["data"]["id"]
    assert client.patch(
        f"/api/accounting/periods/{period_id}/status", headers=owner,
        json={"status": "closed"},
    ).status_code == 200
    blocked = client.post("/api/payroll/disburse", headers=owner, json={
        "staff_id": "staff-b", "month": month, "base_salary": 25000,
    })
    assert blocked.status_code == 409
    assert len(fake_db.salary_disbursements.docs) == 1


def test_payroll_payslip_self_access_and_versioned_correction(client, fake_db):
    owner = _headers("owner-1", "owner")
    teacher = _headers("teacher-user", "teacher")
    fake_db.staff.docs.append(make_staff(
        id="staff-a", user_id="teacher-user", name="Teacher A", branch_id="branch-a",
        employee_id="EMP-1", department="Academics",
    ))
    month = date.today().strftime("%Y-%m")
    created = client.post("/api/payroll/disburse", headers=owner, json={
        "staff_id": "staff-a", "month": month, "base_salary": 30000,
        "deductions": 1000, "reference": "BANK-1",
    })
    assert created.status_code == 200
    disbursement_id = created.json()["data"]["id"]
    payslip = client.get(
        f"/api/payroll/disbursements/{disbursement_id}/payslip", headers=teacher
    )
    assert payslip.status_code == 200
    assert payslip.json()["data"]["staff"]["name"] == "Teacher A"
    assert payslip.json()["data"]["net_amount"] == 29000

    corrected = client.patch(
        f"/api/payroll/disbursements/{disbursement_id}/correct", headers=owner,
        json={"changes": {"deductions": 500}, "reason": "Approved deduction correction"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["data"]["net_amount"] == 29500
    assert corrected.json()["data"]["revision"] == 1
    history = client.get(
        f"/api/payroll/disbursements/{disbursement_id}/corrections", headers=owner
    )
    assert history.status_code == 200
    assert history.json()["meta"]["count"] == 1
    assert history.json()["data"][0]["before"]["deductions"] == 1000


def test_payslip_rejects_unrelated_staff_and_periods_cannot_overlap(client, fake_db):
    owner = _headers("owner-1", "owner")
    fake_db.staff.docs.append(make_staff(id="staff-a", user_id="teacher-a", branch_id="branch-a"))
    fake_db.salary_disbursements.docs.append({
        "id": "pay-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "staff_id": "staff-a", "month": "2026-08", "base_salary": 100,
        "allowances": 0, "deductions": 0, "net_amount": 100,
    })
    assert client.get(
        "/api/payroll/disbursements/pay-1/payslip", headers=_headers("teacher-b", "teacher")
    ).status_code == 403
    assert client.post("/api/accounting/periods", headers=owner, json={
        "name": "August", "start_date": "2026-08-01", "end_date": "2026-08-31",
    }).status_code == 200
    assert client.post("/api/accounting/periods", headers=owner, json={
        "name": "Overlap", "start_date": "2026-08-15", "end_date": "2026-09-15",
    }).status_code == 400


@pytest.mark.parametrize("path", ["/api/accounting/periods", "/api/payroll/disbursements/pay-1/payslip"])
def test_finance_controls_require_authentication(client, path):
    assert client.get(path).status_code == 401
