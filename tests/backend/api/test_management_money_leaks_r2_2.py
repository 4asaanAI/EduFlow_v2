from __future__ import annotations

"""R2-2 - the management head never sees a rupee figure.

Lalit Thomas keeps the school's day-to-day data current. He is not in the money side
of the school at all, and decision 1 of 2026-08-10 is explicit: he sees whether a
child's fees are paid or unpaid, as a visible flag, and he never sees an amount
anywhere.

The 2026-08-10 audit listed nine places where he could. This file is the route half of
the proof. It walks each one as Lalit and asserts he is refused, or that the payload
that does come back carries no money in it.

Asserted BY KEY NAME, never by searching the response for a rupee sign. A test that
greps for a currency symbol passes happily the day an amount comes back as a bare
number, which is exactly how a money leak survives a green suite.
"""

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = {"user_id": "own-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
PRINCIPAL = {"user_id": "prn-1", "role": "admin", "sub_category": "principal", "name": "Adesh Singh"}
ACCOUNTANT = {"user_id": "acc-1", "role": "admin", "sub_category": "accountant", "name": "Sonu Ruhal"}
MANAGEMENT = {"user_id": "mgt-1", "role": "admin", "sub_category": "management", "name": "Lalit Thomas"}

# The same four people as the shape a request handler sees them in, where the key is
# `role` rather than a JWT claim set.
OWNER_USER = {"id": "own-1", "role": "owner", "sub_category": "owner"}
PRINCIPAL_USER = {"id": "prn-1", "role": "admin", "sub_category": "principal"}
ACCOUNTANT_USER = {"id": "acc-1", "role": "admin", "sub_category": "accountant"}
MANAGEMENT_USER = {"id": "mgt-1", "role": "admin", "sub_category": "management"}

# Every key any of these payloads could carry an amount in. Kept in one place so that
# a new money field has to be added here consciously.
MONEY_KEYS = {
    "amount", "amount_paid", "amount_due", "balance", "total", "total_amount",
    "total_collected", "total_due", "total_fees", "total_outstanding", "collected",
    "outstanding", "overdue_amount", "paid_amount", "pending_amount", "due_amount",
    "fee_amount", "salary", "gross_salary", "net_salary", "basic_salary",
    "discount_amount", "fine", "late_fine", "concession",
}


def _money_keys_in(payload) -> set:
    """Every money key anywhere inside a nested response, by name."""
    found = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in MONEY_KEYS:
                found.add(key)
            found |= _money_keys_in(value)
    elif isinstance(payload, list):
        for item in payload:
            found |= _money_keys_in(item)
    return found


# ─── The routes he must be refused outright ─────────────────────────────────────

def test_class_fee_summary_is_refused_to_the_management_head(client):
    """Per-class fee collection totals, in rupees, for the whole school."""
    resp = client.get("/api/fees/class-summary", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 403, resp.text


def test_class_fee_summary_still_reaches_the_people_who_need_it(client):
    for who in (OWNER, PRINCIPAL, ACCOUNTANT):
        resp = client.get("/api/fees/class-summary", headers=_bearer(who))
        assert resp.status_code != 403, f"{who['name']} was refused: {resp.text}"


def test_student_discounts_are_refused_to_the_management_head(client):
    resp = client.get("/api/fees/discounts/student-1", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 403, resp.text


def test_accounting_periods_are_refused_to_the_management_head(client):
    """The posting lock. He could open and close the school's books."""
    resp = client.get("/api/accounting/periods", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 403, resp.text


def test_opening_or_closing_the_posting_lock_is_refused_to_the_management_head(client):
    resp = client.patch(
        "/api/accounting/periods/period-1/status",
        json={"status": "open"},
        headers=_bearer(MANAGEMENT),
    )
    assert resp.status_code == 403, resp.text


def test_editing_an_expense_is_refused_to_the_management_head(client):
    resp = client.patch(
        "/api/ops/expenses/expense-1",
        json={"amount": 1},
        headers=_bearer(MANAGEMENT),
    )
    assert resp.status_code == 403, resp.text


# ─── The one he keeps, with the money taken out ────────────────────────────────

def test_a_staff_record_carries_no_salary_for_the_management_head(client, fake_db):
    """The staff LIST strips salary with a projection. The single record did not.

    Lalit maintains the staff directory, so he opens these records all day. Every one
    of them was handing him that person's pay.
    """
    fake_db.staff.docs[:] = [{
        "id": "staff-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "A Teacher", "designation": "TGT", "phone": "9000000000",
        "salary": 42000, "user_id": "someone-else",
    }]
    resp = client.get("/api/staff/staff-1", headers=_bearer(MANAGEMENT))

    assert resp.status_code == 200, resp.text
    record = resp.json()["data"]
    assert "salary" not in record, "the management head was handed a salary"
    # ...and the record is still useful to him, or we have broken his job instead of
    # protecting the teacher's pay.
    assert record["name"] == "A Teacher"
    assert record["designation"] == "TGT"


def test_a_staff_record_still_carries_salary_for_the_three_who_may_see_it(client, fake_db):
    """Decision 9, 2026-08-10: the owner AND the principal both see every salary."""
    fake_db.staff.docs[:] = [{
        "id": "staff-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "A Teacher", "salary": 42000, "user_id": "someone-else",
    }]
    for who in (OWNER, PRINCIPAL, ACCOUNTANT):
        resp = client.get("/api/staff/staff-1", headers=_bearer(who))
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"].get("salary") == 42000, (
            f"{who['name']} can no longer see a salary they are entitled to"
        )


def test_a_person_can_still_see_their_own_salary(client, fake_db):
    """Whatever else changes, nobody loses sight of their own pay."""
    fake_db.staff.docs[:] = [{
        "id": "staff-9", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "Themself", "salary": 31000, "user_id": MANAGEMENT["user_id"],
    }]
    resp = client.get("/api/staff/staff-9", headers=_bearer(MANAGEMENT))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"].get("salary") == 31000


# ─── Fee status: he gets the flag, not the figure ──────────────────────────────

def test_fee_status_gives_the_management_head_a_flag_and_no_amounts(client, fake_db):
    """Decision 1: a paid-or-unpaid flag, as a visible field, and no rupee figure.

    He needs to know a child is a defaulter - that is why families are chased - but
    not by how much.
    """
    fake_db.fee_transactions.docs[:] = [{
        "id": "txn-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "student_id": "student-1", "status": "overdue", "amount": 12500,
        "due_date": "2026-07-01",
    }]
    resp = client.get("/api/fees/status/student-1", headers=_bearer(MANAGEMENT))

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    # The flag is present and tells him what he needs.
    assert data.get("status") in {"paid", "unpaid", "overdue"}
    assert data["status"] != "paid"
    # And nothing in the payload is an amount, checked by key name.
    leaked = _money_keys_in(data)
    assert leaked == set(), f"the management head was handed money keys: {sorted(leaked)}"


# ─── The one money figure everyone may see: the published rate card ───────────

def test_the_fee_rate_card_is_public_to_every_staff_profile():
    """Abhimanyu, 2026-08-10.

    What a class is charged per year is on the school's own fee sheet and any parent
    may ask for it. It is the school's price list, not the school's money, so it is
    the single exception to "the management head never sees a rupee figure".

    `get_fee_structures` returns class group, the named components, their amounts and
    the annual total. No child, no arrears, no payment history.
    """
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    tool = TOOL_REGISTRY["get_fee_structures"]
    for sub_category in (
        "principal", "accountant", "management", "transport_head",
        "receptionist", "it_tech", "maintenance", "support_staff",
    ):
        user = {"role": "admin", "sub_category": sub_category}
        assert is_tool_authorized(user, tool) is True, sub_category
    assert is_tool_authorized({"role": "owner"}, tool) is True


def test_everything_that_is_actually_the_schools_money_stays_shut():
    """The rate card being public must not drag the ledger along with it.

    Collections, arrears, individual payments and the finance report are a different
    thing entirely, and so is CHANGING the rate card.
    """
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    STILL_FINANCE_ONLY = [
        "get_fee_summary",        # what has been collected
        "get_fee_defaulters",     # who is behind
        "get_fee_transactions",   # individual payments
        "get_financial_report",
        "create_fee_structure",   # writing the rate card is not reading it
        "update_fee_structure",
        "delete_fee_structure",
    ]
    for tool_name in STILL_FINANCE_ONLY:
        tool = TOOL_REGISTRY[tool_name]
        assert is_tool_authorized(MANAGEMENT_USER, tool) is False, tool_name
        for sub_category in ("transport_head", "receptionist", "it_tech", "maintenance", "support_staff"):
            assert is_tool_authorized(
                {"role": "admin", "sub_category": sub_category}, tool
            ) is False, f"{sub_category} / {tool_name}"


def test_the_action_log_stays_with_the_school_owner_and_the_principal():
    """Owner request 10, 2026-08-06, reconfirmed by Abhimanyu 2026-08-10.

    Aman asked that only he and the Principal read the record of who changed what.
    Nobody below them, including the accountant and management heads.
    """
    from ai.tool_access import is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY

    tool = TOOL_REGISTRY["query_audit_log"]
    assert is_tool_authorized({"role": "owner"}, tool) is True
    assert is_tool_authorized(PRINCIPAL_USER, tool) is True
    for sub_category in (
        "accountant", "management", "transport_head", "receptionist",
        "it_tech", "maintenance", "support_staff",
    ):
        assert is_tool_authorized(
            {"role": "admin", "sub_category": sub_category}, tool
        ) is False, sub_category


# ─── Smart Alerts: the fee rows never leave the server for him ─────────────────

def test_smart_alerts_drops_the_fee_rows_for_the_management_head():
    """Filtered on the server, not in the browser.

    An alert filtered in the screen has still been sent, and the same tool answers Flo
    in chat, where there is no screen to filter it.
    """
    from ai.tool_functions import _may_see_money

    assert _may_see_money(MANAGEMENT_USER) is False
    for who in (OWNER_USER, PRINCIPAL_USER, ACCOUNTANT_USER):
        assert _may_see_money(who) is True, who


def test_smart_alerts_money_rule_reads_the_one_grant_table():
    """It must not become a second hand-written list of profiles.

    If somebody adds a profile to the matrix with the finance domain, this answer has
    to follow automatically - that is the whole reason the matrix exists.
    """
    from ai.tool_functions import _may_see_money
    from services.profile_matrix import FINANCE, PROFILE_MATRIX

    for name, entry in PROFILE_MATRIX.items():
        user = (
            {"role": "owner"} if name == "owner"
            else {"role": "admin", "sub_category": name}
        )
        assert _may_see_money(user) is (FINANCE in entry["tool_domains"]), name

    # Nobody outside the table is shown money by this rule.
    assert _may_see_money({"role": "teacher"}) is False
    assert _may_see_money({"role": "student"}) is False
    assert _may_see_money({}) is False


def test_fee_status_reads_the_same_for_everyone_who_may_call_it(client, fake_db):
    """This route was already flag-only, for every caller.

    Worth pinning: the reason it is safe to open to the management head is that it
    returns `{student_id, status}` and nothing else. Nobody loses anything by his
    being added, because there was never an amount in here to lose. The day somebody
    adds one, the test above starts failing for him - which is the intended alarm.
    """
    fake_db.fee_transactions.docs[:] = [{
        "id": "txn-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "student_id": "student-1", "status": "overdue", "amount": 12500,
        "due_date": "2026-07-01",
    }]
    payloads = []
    for who in (OWNER, PRINCIPAL, ACCOUNTANT, MANAGEMENT):
        resp = client.get("/api/fees/status/student-1", headers=_bearer(who))
        assert resp.status_code == 200, f"{who['name']}: {resp.text}"
        payloads.append(resp.json()["data"])
    assert all(p == payloads[0] for p in payloads)
    assert _money_keys_in(payloads[0]) == set()
