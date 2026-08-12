from __future__ import annotations

"""R2-6 - a screen somebody is offered must actually work for them.

A button that answers "no" is worse than a button that is not there. The person
believes the platform is broken rather than that they are not allowed, and they ring
somebody about it.

Two were found on 2026-08-10 and both are fixed here or in R2-1:

  The principal could open the payroll screen - `_require_owner_or_accountant`
  admits him - and was then refused the moment he clicked a payslip, because the
  payslip route checked a NARROWER list that had never been updated. Decision 9 is
  explicit that Aman and Adesh both see everyone's salary.

  The management head was offered the School Settings screen, which is backed by
  `update_school_settings` - owner-only in the registry. Closed in R2-1 by leaving it
  out of his matrix entry.
"""

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "Adesh Singh"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "Sonu Ruhal"}
MANAGEMENT = {"user_id": "mgt-1", "role": "admin", "sub_category": "management", "name": "Lalit Thomas"}


def test_the_principal_can_open_a_payslip_not_just_the_payroll_screen(client, fake_db):
    """Decision 9, 2026-08-10: the owner AND the principal see everyone's salary."""
    original = list(fake_db.salary_disbursements.docs)
    fake_db.salary_disbursements.docs[:] = [{
        "id": "disb-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "staff_id": "staff-1", "net_salary": 42000, "month": "2026-07",
    }]
    try:
        for who in (OWNER, PRINCIPAL, ACCOUNTANT):
            resp = client.get("/api/payroll/disbursements/disb-1/payslip", headers=_bearer(who))
            assert resp.status_code != 403, f"{who['name']} was refused a payslip: {resp.text}"
    finally:
        fake_db.salary_disbursements.docs[:] = original


def test_the_screen_gate_and_the_payslip_gate_give_the_same_answer():
    """They disagreed, which is exactly how the dead button appeared.

    Pinned as one helper rather than two lists, so they cannot drift apart again.
    """
    from routes.payroll import _may_read_payroll

    for who in ({"role": "owner"},
                {"role": "admin", "sub_category": "principal"},
                {"role": "admin", "sub_category": "accountant"}):
        assert _may_read_payroll(who) is True, who

    for who in ({"role": "admin", "sub_category": "management"},
                {"role": "admin", "sub_category": "receptionist"},
                {"role": "teacher"},
                {"role": "student"}):
        assert _may_read_payroll(who) is False, who


def test_the_management_head_is_still_kept_out_of_payroll(client):
    """He may not see anybody's pay. Decision 1 and R2-2."""
    resp = client.get("/api/payroll/structures", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 403, resp.text


def test_a_person_can_still_open_their_own_payslip(client, fake_db):
    """The narrower check existed to let staff see their own pay. That still works."""
    original_d = list(fake_db.salary_disbursements.docs)
    original_s = list(fake_db.staff.docs)
    fake_db.salary_disbursements.docs[:] = [{
        "id": "disb-9", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "staff_id": "staff-9", "net_salary": 31000, "month": "2026-07",
    }]
    fake_db.staff.docs[:] = [{
        "id": "staff-9", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "Themself", "user_id": MANAGEMENT["user_id"],
    }]
    try:
        resp = client.get("/api/payroll/disbursements/disb-9/payslip", headers=_bearer(MANAGEMENT))
        assert resp.status_code == 200, resp.text
    finally:
        fake_db.salary_disbursements.docs[:] = original_d
        fake_db.staff.docs[:] = original_s


def test_no_profile_is_offered_a_screen_backed_by_a_tool_it_cannot_use():
    """The general rule, checked on the cases we know the backing tool for.

    There is no formal screen-to-tool map in the codebase, so this cannot be
    exhaustive. It pins the ones that have already gone wrong, and any new pair added
    here is checked for every profile at once.
    """
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY
    from services.profile_matrix import PROFILE_MATRIX, may_open_screen

    SCREEN_BACKED_BY = {
        "school-settings": "update_school_settings",
        "audit-log": "query_audit_log",
        "transport-manager": "get_transport_status",
        "financial-reports": "get_financial_report",
        "what-ive-learned": "recall_history",
    }

    dead_buttons = []
    for profile_name in PROFILE_MATRIX:
        user = (
            {"role": "owner", "sub_category": "owner"} if profile_name == "owner"
            else {"role": "admin", "sub_category": profile_name}
        )
        for screen_id, tool_name in SCREEN_BACKED_BY.items():
            offered = may_open_screen(user, screen_id)
            works = is_tool_authorized(user, TOOL_REGISTRY[tool_name])
            if offered and not works:
                dead_buttons.append(f"{profile_name} is offered {screen_id} but cannot use {tool_name}")

    assert dead_buttons == [], "; ".join(dead_buttons)
