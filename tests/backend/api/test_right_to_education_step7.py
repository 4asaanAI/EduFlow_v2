"""Release 2 step 7: a child on a Right to Education place is never billed a school fee.

Not discounted to nothing. Never charged. A 100% discount would interact with the
concession rules and could be edited away by anyone who may edit a discount, and the fee
would still be sitting on the family's record looking owed.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_class, make_student


def _owner_h():
    token = create_jwt({"user_id": "owner-rte", "role": "owner", "name": "Owner",
                        "branch_id": "branch-a"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("fee_structures", "fee_structure_revisions", "fee_transactions",
             "students", "classes", "audit_logs")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _seed(fake_db):
    fake_db.classes.docs.append(make_class(id="cls-3rd", branch_id="branch-a"))
    paying = make_student(id="paying", class_id="cls-3rd", branch_id="branch-a", name="Paying")
    paying["admission_number"] = "adm-paying"
    free = make_student(id="rte", class_id="cls-3rd", branch_id="branch-a", name="RTE child")
    free["admission_number"] = "adm-rte"
    free["rte_place"] = True
    free["uses_transport"] = True
    fake_db.students.docs.extend([paying, free])
    fake_db.fee_structures.docs.append({
        "id": "str-3rd", "schoolId": "aaryans-joya", "name": "3rd fees",
        "class_id": "cls-3rd", "academic_year": "2026-2027", "version": 1,
        "status": "active", "fee_heads": [],
        "installments": [{
            "code": "q1", "label": "Composite Fee 1st Quarter", "due_date": "2026-04-15",
            "fee_heads": [{"name": "Composite Fee", "amount": 8850}],
        }],
    })


def test_the_child_is_not_billed_and_is_named_rather_than_silently_missing(client, fake_db):
    _seed(fake_db)
    data = client.post("/api/fees/structures/str-3rd/charges/preview", json={},
                       headers=_owner_h()).json()["data"]

    assert [row["student_id"] for row in data["rows"]] == ["paying"]
    assert data["meta"]["right_to_education_count"] == 1
    assert data["right_to_education_not_billed"] == [
        {"student_id": "rte", "admission_number": "adm-rte"}
    ]


def test_generating_charges_raises_nothing_at_all_for_that_child(client, fake_db):
    _seed(fake_db)
    client.post("/api/fees/structures/str-3rd/charges/generate", json={}, headers=_owner_h())

    billed = {doc["student_id"] for doc in fake_db.fee_transactions.docs}
    assert billed == {"paying"}


def test_it_is_not_recorded_as_a_hundred_percent_discount(client, fake_db):
    # The difference matters: a zero-rupee charge still reads as a bill the family owes
    # nothing on, and a discount can be edited away by anyone who may edit discounts.
    _seed(fake_db)
    client.post("/api/fees/structures/str-3rd/charges/generate", json={}, headers=_owner_h())

    for doc in fake_db.fee_transactions.docs:
        assert doc["student_id"] != "rte"
    # No discount row for this child either. Scoped to this child on purpose: the shared
    # test database carries other tests' discount rows, and asserting the whole
    # collection is empty passes or fails on test order rather than on the behaviour.
    discounts = getattr(fake_db, "fee_discounts", None)
    if discounts is not None:
        assert [d for d in discounts.docs if d.get("student_id") == "rte"] == []


def test_the_bus_is_untouched_by_the_mark(client, fake_db):
    # Their school fee does not apply; the bus does, and a late bus payment is fined on
    # the ordinary schedule. Step 7 must not quietly take the bus off them too.
    _seed(fake_db)
    child = [doc for doc in fake_db.students.docs if doc["id"] == "rte"][0]
    client.post("/api/fees/structures/str-3rd/charges/generate", json={}, headers=_owner_h())
    assert child["uses_transport"] is True
