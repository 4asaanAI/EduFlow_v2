from __future__ import annotations

import pytest

from ai.fee_metrics import fee_totals_from_txns
from middleware.auth import create_jwt
from tests.backend.factories import make_fee_transaction, make_student

pytestmark = pytest.mark.asyncio


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


OWNER = _bearer({"user_id": "owner-fees", "role": "owner", "name": "Owner"})
STUDENT = _bearer({"user_id": "fee-student-user", "role": "student", "name": "Student", "branch_id": "branch-a"})


@pytest.fixture
def mixed_fee_ledger(fake_db):
    original_students = list(fake_db.students.docs)
    original_txns = list(fake_db.fee_transactions.docs)
    student = make_student(
        id="fee-student",
        user_id="fee-student-user",
        class_id="class-1",
        name="Fee Student",
    )
    fake_db.students.docs.append(student)
    fake_db.fee_transactions.docs.extend([
        make_fee_transaction(id="paid", student_id=student["id"], amount=100, status="paid", paid_date="2026-08-01"),
        make_fee_transaction(id="pending", student_id=student["id"], amount=80, status="pending"),
        make_fee_transaction(id="overdue", student_id=student["id"], amount=60, status="overdue"),
        make_fee_transaction(id="unpaid", student_id=student["id"], amount=40, status="unpaid"),
        make_fee_transaction(id="partial", student_id=student["id"], amount=100, paid_amount=30, status="partial", paid_date="2026-08-02"),
        make_fee_transaction(id="deleted", student_id=student["id"], amount=999, status="overdue", deleted=True),
    ])
    yield student
    fake_db.students.docs[:] = original_students
    fake_db.fee_transactions.docs[:] = original_txns


async def test_overall_class_and_student_summaries_use_same_fee_math(
    client, mixed_fee_ledger
):
    overall = client.get("/api/fees/summary", headers=OWNER)
    by_class = client.get("/api/fees/class-summary", headers=OWNER)
    mine = client.get("/api/fees/my", headers=STUDENT)

    assert overall.status_code == by_class.status_code == mine.status_code == 200
    assert overall.json()["data"]["total_collected"] == 130
    assert overall.json()["data"]["total_outstanding"] == 250

    class_row = next(row for row in by_class.json()["data"] if row["class_id"] == "class-1")
    assert class_row["paid"] == 130
    assert class_row["pending"] == 250
    assert class_row["total"] == 380

    student_summary = mine.json()["summary"]
    assert student_summary["total_paid"] == 130
    assert student_summary["total_pending"] == 80
    assert student_summary["outstanding_balance"] == 250
    assert {txn["id"] for txn in mine.json()["data"]} == {
        "paid", "pending", "overdue", "unpaid", "partial"
    }


async def test_partial_overpayment_never_creates_negative_outstanding():
    totals = fee_totals_from_txns([
        {"status": "partial", "amount": 100, "paid_amount": 120},
        {"status": "overdue", "amount": 50, "deleted": True},
    ])

    assert totals == {"collected": 120.0, "outstanding": 0.0, "collection_rate": 100.0}
