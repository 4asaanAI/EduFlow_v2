"""The registration and admission fee raised when a child joins.

Abhimanyu, 2026-08-12: raise these automatically.

This is the most dangerous thing on the platform to automate, because the difference
between "a child joined today" and "a child was typed into the platform today" is
invisible to the database and worth 13,000 to a family. 1,842 children already on the roll
were typed in during a bulk load; had this existed then, every one of those families would
have been billed for joining years ago.

So most of what follows is about what must NOT be charged.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from services.actor_context import actor_ctx_from_user
from services.admission_charge_service import raise_joining_charges
from tests.backend.factories import make_class


def _ctx():
    return actor_ctx_from_user(
        {"id": "owner-j", "role": "owner", "branch_id": "branch-a"},
        school_id="aaryans-joya",
    )


def _owner_h():
    return {"Authorization": "Bearer " + create_jwt(
        {"user_id": "owner-j", "role": "owner", "name": "Owner", "branch_id": "branch-a",
         "schoolId": "aaryans-joya"}
    )}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("students", "guardians", "classes", "fee_structures", "fee_transactions",
             "audit_logs")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _seed(fake_db, *, charges={"registration_fee": 1500, "admission_fee": 16500}):
    fake_db.classes.docs.append(make_class(id="cls-9th", branch_id="branch-a"))
    fake_db.fee_structures.docs.append({
        "_id": "str-9", "id": "str-9", "schoolId": "aaryans-joya", "name": "9th fees",
        "class_id": "cls-9th", "status": "active", "quarterly_amount": 12000,
        "new_student_charges": charges,
        "installments": [{"code": "q1", "label": "Q1", "due_date": "2026-04-15",
                          "fee_heads": [{"name": "Composite Fee", "amount": 12000}]}],
    })


def _admit(client, name="A New Child", **extra):
    return client.post("/api/students/", headers=_owner_h(),
                       json={"name": name, "class_id": "cls-9th", **extra})


def _bills(fake_db):
    return {(c["fee_head"], c["amount"]) for c in fake_db.fee_transactions.docs}


def test_a_child_who_joins_is_charged_the_schools_two_joining_fees(client, fake_db):
    _seed(fake_db)
    out = _admit(client)
    assert out.status_code == 200

    assert _bills(fake_db) == {("Registration Fee", 1500.0), ("Admission Fee", 16500.0)}
    raised = out.json()["joining_charges"]["raised"]
    assert {row["fee_head"] for row in raised} == {"Registration Fee", "Admission Fee"}


async def test_the_charges_are_not_raised_twice_if_the_same_child_is_created_again(
        client, fake_db):
    _seed(fake_db)
    _admit(client, admission_number="A-1")
    # The guard that matters is the charge key: re-running the raise for the same child
    # adds nothing, so a repeated create cannot bill a family twice.
    assert len(fake_db.fee_transactions.docs) == 2
    await raise_joining_charges(fake_db, _ctx(), fake_db.students.docs[0])
    assert len(fake_db.fee_transactions.docs) == 2


def test_a_bulk_load_of_existing_children_charges_nobody(client, fake_db):
    # THE one that matters. A data load says so and no family is billed for joining
    # years ago.
    _seed(fake_db)
    out = _admit(client, raise_joining_charges=False)
    assert out.status_code == 200
    assert fake_db.fee_transactions.docs == []


def test_the_spreadsheet_import_does_not_go_through_this_path_at_all(client, fake_db):
    # `routes/import_data.py` inserts students directly rather than through the student
    # service, so the joining charges cannot reach it even by accident. Pinned here
    # because the day somebody refactors that to use the service is the day 1,842
    # families could be billed.
    import inspect

    from routes import import_data

    source = inspect.getsource(import_data)
    assert "create_student" not in source
    assert "raise_joining_charges" not in source


async def test_a_right_to_education_child_is_charged_nothing_to_join(client, fake_db):
    _seed(fake_db)
    _admit(client)
    fake_db.fee_transactions.docs[:] = []
    fake_db.students.docs[0]["rte_place"] = True

    result = await raise_joining_charges(fake_db, _ctx(), fake_db.students.docs[0])
    assert result["raised"] == []
    assert "Right to Education" in result["skipped_because"]
    assert fake_db.fee_transactions.docs == []


def test_a_class_with_no_joining_charges_raises_none_and_says_so(client, fake_db):
    # 10th and 12th carry none: nobody joins the school at those classes.
    _seed(fake_db, charges={})
    out = _admit(client)
    assert out.status_code == 200
    assert fake_db.fee_transactions.docs == []
    assert "records no joining charges" in out.json()["joining_charges"]["skipped_because"]


def test_a_class_with_no_fee_structure_still_admits_the_child(client, fake_db):
    # A fee problem must never be the thing that keeps a child off the roll.
    fake_db.classes.docs.append(make_class(id="cls-9th", branch_id="branch-a"))
    out = _admit(client)
    assert out.status_code == 200
    assert len(fake_db.students.docs) == 1
    assert "no fee structure" in out.json()["joining_charges"]["skipped_because"]


def test_the_charges_are_written_into_the_audit_trail(client, fake_db):
    _seed(fake_db)
    _admit(client)
    assert "joining_charges_raised" in [a.get("action") for a in fake_db.audit_logs.docs]
