"""Release 2 step 5: the concession rules are what the family is actually billed.

These drive the real charge-generation path rather than asserting against hand-built
rows, because the defect this initiative keeps finding is a rule that exists, reads as
authoritative, and never reaches the database.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_class, make_student


def _owner_h():
    token = create_jwt({"user_id": "owner-conc", "role": "owner", "name": "Owner",
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


def _seed(fake_db, *, concessions_by_student=None):
    """One 6th-class structure at the school's real band, 9,750 a quarter."""
    marks = concessions_by_student or {}
    fake_db.classes.docs.append(make_class(id="cls-6th", branch_id="branch-a"))
    for sid, name in (("plain", "Full fee child"), ("marked", "Concession child")):
        student = make_student(id=sid, class_id="cls-6th", branch_id="branch-a", name=name)
        student["admission_number"] = f"adm-{sid}"
        if sid in marks:
            student["concessions"] = marks[sid]
        fake_db.students.docs.append(student)
    fake_db.fee_structures.docs.append({
        "id": "str-6th", "schoolId": "aaryans-joya", "name": "6th fees",
        "class_id": "cls-6th", "academic_year": "2026-2027", "version": 1,
        "status": "active", "fee_heads": [],
        "installments": [{
            "code": "q1", "label": "Composite Fee 1st Quarter", "due_date": "2026-04-15",
            "fee_heads": [{"name": "Composite Fee", "amount": 9750}],
        }],
    })


def _preview(client):
    return client.post("/api/fees/structures/str-6th/charges/preview", json={},
                       headers=_owner_h())


def test_a_school_with_no_concession_marks_bills_exactly_what_it_did_before(client, fake_db):
    # Every child on the platform today. Step 5 must change nobody's bill until the
    # marks are loaded.
    _seed(fake_db)
    rows = _preview(client).json()["data"]["rows"]
    assert [row["amount"] for row in rows] == [9750.0, 9750.0]
    assert all(row["concession_total"] == 0.0 for row in rows)


def test_the_sibling_concession_comes_off_the_bill_and_says_why(client, fake_db):
    _seed(fake_db, concessions_by_student={"marked": {"sibling": True}})
    rows = {row["student_id"]: row for row in _preview(client).json()["data"]["rows"]}
    assert rows["plain"]["amount"] == 9750.0
    assert rows["marked"]["amount"] == 7950.0        # 9,750 less the 1,800 band value
    assert rows["marked"]["gross_amount"] == 9750.0
    assert rows["marked"]["concession_lines"][0]["rule"] == "sibling"


def test_an_employee_child_who_is_also_a_sibling_gets_the_employee_one_only(client, fake_db):
    _seed(fake_db, concessions_by_student={
        "marked": {"employee_child": True, "sibling": True},
    })
    rows = {row["student_id"]: row for row in _preview(client).json()["data"]["rows"]}
    # Half of 9,750. Not 9,750 - 4,875 - 1,800, which is what stacking would bill.
    assert rows["marked"]["amount"] == 4875.0


def test_the_generated_charge_carries_the_net_figure_and_its_reasons(client, fake_db):
    _seed(fake_db, concessions_by_student={"marked": {"employee_child": True}})
    made = client.post("/api/fees/structures/str-6th/charges/generate", json={},
                       headers=_owner_h())
    assert made.status_code == 200
    charged = {doc["student_id"]: doc for doc in fake_db.fee_transactions.docs}
    assert charged["marked"]["amount"] == 4875.0
    assert charged["marked"]["gross_amount"] == 9750.0
    assert charged["marked"]["concession_total"] == 4875.0
    assert charged["plain"]["amount"] == 9750.0


def test_a_one_time_admission_concession_is_consumed_and_cannot_repeat(client, fake_db):
    _seed(fake_db, concessions_by_student={"marked": {"admission_discount": {
        "amount": 6000, "authorised_by": "Aman Litt", "authorised_on": "2026-04-02",
    }}})
    client.post("/api/fees/structures/str-6th/charges/generate", json={},
                headers=_owner_h())
    charged = {doc["student_id"]: doc for doc in fake_db.fee_transactions.docs}
    assert charged["marked"]["amount"] == 3750.0     # 9,750 less the authorised 6,000

    # The child's record now records which instalment consumed it.
    student = [doc for doc in fake_db.students.docs if doc["id"] == "marked"][0]
    assert student["concessions"]["admission_discount"]["applied_to"] == "q1"

    # A later quarter charges the full fee. The 6,000 is not given twice.
    fake_db.fee_structures.docs[0]["installments"].append({
        "code": "q2", "label": "Composite Fee 2nd Quarter", "due_date": "2026-07-15",
        "fee_heads": [{"name": "Composite Fee", "amount": 9750}],
    })
    rows = {(row["student_id"], row["installment_code"]): row
            for row in _preview(client).json()["data"]["rows"]}
    assert rows[("marked", "q2")]["amount"] == 9750.0


def test_a_band_the_school_has_no_sibling_value_for_refuses_the_whole_preview(client, fake_db):
    # Better to bill nobody and say why than to bill one child a figure nobody agreed.
    _seed(fake_db, concessions_by_student={"marked": {"sibling": True}})
    fake_db.fee_structures.docs[0]["installments"][0]["fee_heads"][0]["amount"] = 4321
    out = _preview(client)
    assert out.status_code == 400
    assert "adm-marked" in out.json()["detail"]
    assert fake_db.fee_transactions.docs == []
