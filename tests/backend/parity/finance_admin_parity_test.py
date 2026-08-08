"""Dual-entrypoint parity for payroll and accounting-period administration."""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt


SCHOOL = "aaryans-joya"
BRANCH = "branch-a"
OWNER = {"id": "owner-1", "role": "owner", "name": "Owner", "branch_id": BRANCH}
VOLATILE = {
    "_id", "id", "entity_id", "record_id", "created_at", "updated_at",
    "paid_at", "closed_at", "corrected_at", "correction_id", "timestamp", "at",
}


def _headers():
    token = create_jwt({
        "user_id": OWNER["id"], "role": "owner", "name": "Owner", "branch_id": BRANCH,
    })
    return {"Authorization": f"Bearer {token}"}


def _scrub(value):
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _state(fake_db):
    return _scrub({
        name: copy.deepcopy(getattr(fake_db, name).docs)
        for name in (
            "salary_structures", "salary_disbursements",
            "salary_disbursement_corrections", "accounting_periods",
            "accounting_period_locks", "audit_logs",
        )
    })


def _clear(fake_db):
    for name in (
        "salary_structures", "salary_disbursements", "salary_disbursement_corrections",
        "accounting_periods", "accounting_period_locks", "audit_logs",
    ):
        getattr(fake_db, name).docs[:] = []


def _seed_staff(fake_db):
    fake_db.staff.docs[:] = [{
        "_id": "staff-1", "id": "staff-1", "schoolId": SCHOOL,
        "branch_id": BRANCH, "name": "Teacher One", "is_active": True,
    }]


def _disbursement():
    return {
        "_id": "pay-1", "id": "pay-1", "schoolId": SCHOOL, "branch_id": BRANCH,
        "staff_id": "staff-1", "month": "2026-07", "base_salary": 30000.0,
        "allowances": 0.0, "deductions": 0.0, "net_amount": 30000.0,
        "status": "paid", "paid_by": OWNER["id"], "revision": 0,
    }


def _period():
    return {
        "_id": "period-1", "id": "period-1", "schoolId": SCHOOL, "branch_id": BRANCH,
        "name": "FY 2026", "start_date": "2026-04-01", "end_date": "2027-03-31",
        "status": "open", "created_by": OWNER["id"],
    }


@pytest.fixture(autouse=True)
def _setup(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db)
    _seed_staff(fake_db)
    yield
    _clear(fake_db)


async def test_salary_structure_ai_and_rest_have_same_state(client, fake_db):
    payload = {"staff_id": "staff-1", "base_salary": 30000, "allowances": {"hra": 3000}}
    response = client.post("/api/payroll/structures", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    result = await tool_functions_v2.tool_upsert_salary_structure(payload, OWNER, None)
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_salary_disbursement_ai_and_rest_have_same_state(client, fake_db):
    payload = {"staff_id": "staff-1", "month": "2026-07", "base_salary": 30000}
    response = client.post("/api/payroll/disburse", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    result = await tool_functions_v2.tool_disburse_salary(payload, OWNER, None)
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_salary_correction_ai_and_rest_have_same_state(client, fake_db):
    payload = {"changes": {"deductions": 1000}, "reason": "Late deduction"}
    fake_db.salary_disbursements.docs[:] = [_disbursement()]
    response = client.patch(
        "/api/payroll/disbursements/pay-1/correct", json=payload, headers=_headers()
    )
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    fake_db.salary_disbursements.docs[:] = [_disbursement()]
    result = await tool_functions_v2.tool_correct_salary_disbursement(
        {"disbursement_id": "pay-1", **payload}, OWNER, None
    )
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_accounting_period_create_ai_and_rest_have_same_state(client, fake_db):
    payload = {"name": "FY 2026", "start_date": "2026-04-01", "end_date": "2027-03-31"}
    response = client.post("/api/accounting/periods", json=payload, headers=_headers())
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    result = await tool_functions_v2.tool_create_accounting_period(payload, OWNER, None)
    assert result["success"] is True
    assert _state(fake_db) == rest


async def test_accounting_period_status_ai_and_rest_have_same_state(client, fake_db):
    payload = {"status": "closed"}
    fake_db.accounting_periods.docs[:] = [_period()]
    response = client.patch(
        "/api/accounting/periods/period-1/status", json=payload, headers=_headers()
    )
    assert response.status_code == 200, response.text
    rest = _state(fake_db)

    _clear(fake_db)
    fake_db.accounting_periods.docs[:] = [_period()]
    result = await tool_functions_v2.tool_change_accounting_period_status(
        {"period_id": "period-1", **payload}, OWNER, None
    )
    assert result["success"] is True
    assert _state(fake_db) == rest
