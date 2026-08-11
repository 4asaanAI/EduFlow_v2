"""Release 2 audit finding 7: a concession change reaches a bill already raised.

Bills are worked out when they are generated, and charge generation skips anything it has
already generated. So before this, granting a concession after the quarter had been billed
left the old figure on the bill and nothing ever went back for it. The family would have
been asked for the wrong amount and nobody would have found out until they complained.

The hard rule underneath: **a bill with money against it is never touched.** That is a
receipt of what a family was asked for and what they gave, and rewriting it would rewrite
the school's own record.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt


def _acct_h():
    return {"Authorization": "Bearer " + create_jwt(
        {"user_id": "sonu", "role": "admin", "sub_category": "accountant",
         "name": "Sonu", "schoolId": "aaryans-joya"}
    )}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = ("students", "fee_transactions", "fee_structures", "audit_logs")
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def _charge(cid, *, amount=9750, gross=None, status="pending", paid=0,
            head="Composite Fee", period="q1"):
    return {
        "_id": cid, "id": cid, "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "student_id": "stu-1", "fee_head": head, "fee_type": head,
        "installment_code": period, "fee_period": period,
        "amount": amount, "gross_amount": gross if gross is not None else amount,
        "concession_total": 0,
        "status": status, "paid_amount": paid,
    }


def _seed(fake_db, charges):
    fake_db.students.docs.append({
        "_id": "stu-1", "id": "stu-1", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "name": "A Child", "admission_number": "adm-1", "class_id": "cls-6th",
        "is_active": True,
    })
    fake_db.fee_transactions.docs.extend(charges)


def _charge_by_id(fake_db, cid):
    return [c for c in fake_db.fee_transactions.docs if c["id"] == cid][0]


def test_granting_a_concession_corrects_a_bill_that_is_still_unpaid(client, fake_db):
    _seed(fake_db, [_charge("c1")])
    out = client.post("/api/fees/concessions/set", headers=_acct_h(), json={
        "student_id": "stu-1", "concession": "sibling", "granted": True,
    })
    assert out.status_code == 200

    corrected = _charge_by_id(fake_db, "c1")
    assert corrected["amount"] == 7950.0          # 9,750 less the 1,800 band value
    assert corrected["gross_amount"] == 9750.0
    assert corrected["concession_lines"][0]["rule"] == "sibling"
    assert out.json()["data"]["bills_reworked"]["updated"] == ["c1"]


def test_taking_a_concession_away_puts_the_bill_back_up(client, fake_db):
    # The bill carries BOTH figures: 7,950 asked for, against a class fee of 9,750. That
    # is what lets the concession be taken back off without guessing at the band.
    _seed(fake_db, [_charge("c1", amount=7950, gross=9750)])
    fake_db.students.docs[0]["concessions"] = {"sibling": True}
    client.post("/api/fees/concessions/set", headers=_acct_h(), json={
        "student_id": "stu-1", "concession": "sibling", "granted": False,
    })
    assert _charge_by_id(fake_db, "c1")["amount"] == 9750.0


def test_a_bill_that_has_been_paid_is_never_touched(client, fake_db):
    # A receipt. Changing it would rewrite what the family was asked for and what they
    # actually gave.
    _seed(fake_db, [_charge("paid", status="paid", paid=9750)])
    out = client.post("/api/fees/concessions/set", headers=_acct_h(), json={
        "student_id": "stu-1", "concession": "sibling", "granted": True,
    })
    assert _charge_by_id(fake_db, "paid")["amount"] == 9750.0
    assert out.json()["data"]["bills_reworked"]["left_alone"] == ["paid"]
    assert out.json()["data"]["bills_reworked"]["updated"] == []


def test_a_part_paid_bill_is_left_alone_and_reported(client, fake_db):
    _seed(fake_db, [_charge("part", status="pending", paid=3000)])
    out = client.post("/api/fees/concessions/set", headers=_acct_h(), json={
        "student_id": "stu-1", "concession": "sibling", "granted": True,
    })
    assert _charge_by_id(fake_db, "part")["amount"] == 9750.0
    assert out.json()["data"]["bills_reworked"]["left_alone"] == ["part"]


def test_the_bus_is_never_reworked_by_a_concession(client, fake_db):
    # Transport carries no concession of any kind, so a bus charge must come out
    # untouched even for a child who has just been given one.
    _seed(fake_db, [_charge("bus", amount=650, head="Transport Fee",
                            period="transport-april")])
    client.post("/api/fees/concessions/set", headers=_acct_h(), json={
        "student_id": "stu-1", "concession": "employee_child", "granted": True,
    })
    assert _charge_by_id(fake_db, "bus")["amount"] == 650


def test_a_right_to_education_place_cancels_unpaid_school_fees_and_keeps_the_bus(
        client, fake_db):
    _seed(fake_db, [_charge("school"), _charge("bus", amount=650, head="Transport Fee")])
    out = client.post("/api/fees/concessions/right-to-education", headers=_acct_h(), json={
        "student_id": "stu-1", "holds_place": True, "reason": "government letter seen",
    })
    assert out.status_code == 200

    school = _charge_by_id(fake_db, "school")
    # Cancelled, not deleted and not set to a zero-rupee bill: a zero bill still reads as
    # something owed, and a deleted row loses the fact that it was ever raised.
    assert school["status"] == "cancelled"
    assert school["amount"] == 0
    assert "Right to Education" in school["cancelled_reason"]
    assert _charge_by_id(fake_db, "bus")["amount"] == 650


def test_a_paid_school_fee_survives_a_right_to_education_mark(client, fake_db):
    # The family did pay it. Whether they should have is a refund conversation for a
    # person, not something to erase quietly.
    _seed(fake_db, [_charge("paid", status="paid", paid=9750)])
    out = client.post("/api/fees/concessions/right-to-education", headers=_acct_h(), json={
        "student_id": "stu-1", "holds_place": True, "reason": "letter seen",
    })
    assert _charge_by_id(fake_db, "paid")["status"] == "paid"
    assert out.json()["data"]["bills_reworked"]["cancelled"] == []


def test_the_rework_is_written_into_the_audit_trail(client, fake_db):
    _seed(fake_db, [_charge("c1")])
    client.post("/api/fees/concessions/set", headers=_acct_h(), json={
        "student_id": "stu-1", "concession": "sibling", "granted": True,
    })
    actions = [a.get("action") for a in fake_db.audit_logs.docs]
    assert "fee_charges_reworked_after_concession_change" in actions
