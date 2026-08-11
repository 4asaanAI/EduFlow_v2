"""Sonu gets access to salary data. Abhimanyu, 2026-08-11, relaying Aman's and Adesh's
instruction: the accountant head already knows and handles everyone's salary, and the
platform should reflect that.

**What was already true, and untouched here.** The accountant head has run payroll in
full since this project began: `salary_structures`, `salary_disbursements`, corrections
and payslips are all his (`_require_owner_or_accountant` in `routes/payroll.py`, and
`upsert_salary_structure` / `disburse_salary` were already open to him in the Flo
registry). He can also already READ the base salary figure on a colleague's staff
record when he opens it (decision 9, `SALARY_READERS` in `routes/staff.py`).

**What was missing, and is fixed here.** He could not WRITE that one field. The code
already had a half-built exception for it - `_is_accounts(actor_ctx) and not
_is_owner(actor_ctx): allowed |= {"salary"}` in `staff_service.update_staff` - and it
did nothing, because three lines later the `OWNER_ONLY_FIELDS` strip removed `salary`
from the update unconditionally, undoing the grant it had just made. Nothing had ever
driven a real write through that path, so nothing caught it.

**Scoped deliberately narrow.** An accountant caller of `update_staff` may change ONLY
`salary`. A name, phone or department correction stays with Lalit and Adesh (decisions
2 and 4) - this instruction was about salary, not general staff editing, and widening
it further would be assuming something nobody asked for.
"""

from __future__ import annotations

import pytest

from ai.tool_functions_v2 import TOOL_REGISTRY
from middleware.auth import create_jwt
from routes.chat import _is_tool_authorized
from services.actor_context import actor_ctx_from_user
from services.staff_service import (
    StaffAuthorizationError,
    StaffValidationError,
    update_staff as svc_update_staff,
)

SCHOOL = "aaryans-joya"

OWNER = {"id": "u-owner", "role": "owner", "name": "Aman"}
PRINCIPAL = {"id": "u-principal", "role": "admin", "sub_category": "principal", "name": "Adesh"}
ACCOUNTANT = {"id": "u-accountant", "role": "admin", "sub_category": "accountant", "name": "Sonu"}
MANAGEMENT = {"id": "u-management", "role": "admin", "sub_category": "management", "name": "Lalit"}
TEACHER = {"id": "u-teacher", "role": "teacher", "name": "T"}


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _actor(user):
    return actor_ctx_from_user(user, school_id=SCHOOL)


@pytest.fixture(autouse=True)
def _a_colleague(fake_db):
    before = list(fake_db.staff.docs)
    fake_db.staff.docs.append({
        "id": "stf-sal-1", "schoolId": SCHOOL, "name": "Ramesh Kumar",
        "staff_type": "teacher", "phone": "9990001111", "department": "Science",
        "salary": 40000, "is_active": True,
    })
    yield
    fake_db.staff.docs[:] = before


# ── The service layer: the actual grant, and its limit ──────────────────────

async def test_the_accountant_head_can_now_set_a_salary(fake_db):
    result = await svc_update_staff(
        fake_db, _actor(ACCOUNTANT), {"staff_id": "stf-sal-1", "salary": 55000}
    )
    assert result["staff"]["salary"] == 55000


async def test_the_accountant_head_can_change_salary_and_nothing_else_in_one_call(fake_db):
    # One request mixing an allowed field with two that are not. Only salary may land;
    # phone and department are silently dropped, not written and not errored on.
    result = await svc_update_staff(
        fake_db, _actor(ACCOUNTANT),
        {"staff_id": "stf-sal-1", "salary": 60000, "phone": "8880002222",
         "department": "Mathematics"},
    )
    staff = result["staff"]
    assert staff["salary"] == 60000
    assert staff["phone"] == "9990001111", "the accountant edited a field beyond salary"
    assert staff["department"] == "Science", "the accountant edited a field beyond salary"


async def test_the_accountant_head_cannot_edit_a_colleagues_other_details(fake_db):
    # General staff editing is Lalit's and Adesh's, not his. A field he may not touch,
    # with nothing else in the request, leaves nothing to write - the same "No
    # updatable fields" answer anyone gets for a request naming no field of theirs.
    with pytest.raises(StaffValidationError):
        await svc_update_staff(
            fake_db, _actor(ACCOUNTANT), {"staff_id": "stf-sal-1", "phone": "7770003333"}
        )
    staff = await fake_db.staff.find_one({"id": "stf-sal-1"}, {"_id": 0})
    assert staff["phone"] == "9990001111"


async def test_the_principal_still_cannot_write_salary(fake_db):
    # Unchanged and unaffected by this instruction - only Sonu was named.
    result = await svc_update_staff(
        fake_db, _actor(PRINCIPAL), {"staff_id": "stf-sal-1", "salary": 99999}
    )
    assert result["staff"]["salary"] == 40000


async def test_the_management_head_still_cannot_write_salary(fake_db):
    result = await svc_update_staff(
        fake_db, _actor(MANAGEMENT), {"staff_id": "stf-sal-1", "salary": 99999}
    )
    assert result["staff"]["salary"] == 40000


async def test_the_accountant_head_still_cannot_grant_owner_authority(fake_db):
    # The escalation guard runs before the field-scoping and must still catch this,
    # widened salary access notwithstanding.
    with pytest.raises(StaffAuthorizationError):
        await svc_update_staff(
            fake_db, _actor(ACCOUNTANT), {"staff_id": "stf-sal-1", "role": "owner"}
        )


async def test_the_accountant_head_still_cannot_touch_leave_balances(fake_db):
    # Decision 2: attendance and leave are his to READ, not to change.
    with pytest.raises(StaffAuthorizationError):
        await svc_update_staff(
            fake_db, _actor(ACCOUNTANT),
            {"staff_id": "stf-sal-1", "casual_leave_balance": 99},
        )


async def test_the_owner_can_still_change_anything(fake_db):
    result = await svc_update_staff(
        fake_db, _actor(OWNER),
        {"staff_id": "stf-sal-1", "salary": 70000, "phone": "6660004444"},
    )
    assert result["staff"]["salary"] == 70000
    assert result["staff"]["phone"] == "6660004444"


# ── The REST route: PATCH /api/staff/{id} ────────────────────────────────────

def test_the_accountant_head_can_set_salary_through_the_screen(client, fake_db):
    resp = client.patch(
        "/api/staff/stf-sal-1", json={"salary": 65000}, headers=_bearer(ACCOUNTANT)
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["salary"] == 65000


def test_the_route_silently_ignores_other_fields_from_the_accountant(client, fake_db):
    resp = client.patch(
        "/api/staff/stf-sal-1",
        json={"salary": 66000, "department": "Commerce"},
        headers=_bearer(ACCOUNTANT),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["department"] == "Science"


# ── Reading: single record already worked (decision 9); the list view now matches ──

def test_the_accountant_head_sees_salary_in_the_staff_list_now(client, fake_db):
    resp = client.get("/api/staff/", headers=_bearer(ACCOUNTANT))
    assert resp.status_code == 200
    row = next(r for r in resp.json()["data"] if r["id"] == "stf-sal-1")
    assert "salary" in row, (
        "the accountant head could already open one colleague's record and see their "
        "pay, but the list view still hid it - the same field, two different answers"
    )


def test_the_management_head_still_does_not_see_salary_in_the_list(client, fake_db):
    resp = client.get("/api/staff/", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 200
    row = next(r for r in resp.json()["data"] if r["id"] == "stf-sal-1")
    assert "salary" not in row


# ── Flo: the tool must actually be reachable, or the fix is a dead door ─────

def test_flo_lets_the_accountant_head_call_update_staff():
    tool_def = TOOL_REGISTRY["update_staff"]
    assert _is_tool_authorized(ACCOUNTANT, tool_def) is True


def test_flo_still_lets_management_edit_general_staff_details():
    # Unaffected by this change and correct on its own terms: general staff editing
    # (name, phone, department) is Lalit's job (decisions 2 and 4), unlike salary.
    tool_def = TOOL_REGISTRY["update_staff"]
    assert _is_tool_authorized(MANAGEMENT, tool_def) is True


def test_flo_still_refuses_a_teacher():
    tool_def = TOOL_REGISTRY["update_staff"]
    assert _is_tool_authorized(TEACHER, tool_def) is False


async def test_flo_and_the_screen_give_the_same_answer(fake_db):
    # AD7: one shared write path. Calling the Flo tool function directly must land the
    # same narrow result as the REST route above.
    from ai.tool_functions_v2 import tool_update_staff

    result = await tool_update_staff(
        {"staff_id": "stf-sal-1", "salary": 61000, "phone": "5550005555"}, ACCOUNTANT
    )
    assert result["success"] is True
    assert result["data"]["salary"] == 61000
    assert result["data"]["phone"] == "9990001111"
