"""
GET /api/fees/transactions round-trips the fields the student-profile fee history
table (frontend/src/components/ui/StudentFeePanel.js) needs for Total Fees, Fees
Paid, Created At and Last Edited. No backend change was made for that feature -
this pins the assumption the frontend relies on.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt

_TEST_STUDENT_IDS = {"student-history-1", "student-history-2"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    # fake_db is a session-wide singleton (tests/backend/conftest.py) shared with
    # every other test file. A blanket `.docs.clear()` would drop other tests'
    # fixtures out from under them, so this only purges this file's own student
    # ids - before AND after, since a left-behind record from this file skews
    # whole-school aggregates in files that run afterward (e.g. fee summaries).
    def _purge():
        fake_db.fee_transactions.docs[:] = [
            d for d in fake_db.fee_transactions.docs if d.get("student_id") not in _TEST_STUDENT_IDS
        ]
        fake_db.fee_idempotency_keys.docs[:] = [
            d for d in fake_db.fee_idempotency_keys.docs
            if str(d.get("key", "")).split("|")[0] not in _TEST_STUDENT_IDS
        ]
    _purge()
    yield
    _purge()


def _accountant_headers(user_id="acct-1"):
    token = create_jwt({"user_id": user_id, "role": "admin", "name": "Acct", "sub_category": "accountant"})
    return {"Authorization": f"Bearer {token}"}


def _payment_payload():
    return {
        "student_id": "student-history-1",
        "fee_period": "2026-05",
        "fee_head": "tuition",
        "fee_type": "tuition",
        "amount": 3000,
        "payment_mode": "upi",
        "status": "paid",
        "due_date": "2026-05-10",
    }


def test_fresh_transaction_returns_amount_paid_amount_and_created_at(client):
    headers = {**_accountant_headers(), "Idempotency-Key": "student-history-1|2026-05|tuition"}

    client.post("/api/fees/transactions", json=_payment_payload(), headers=headers)
    resp = client.get(
        "/api/fees/transactions", params={"student_id": "student-history-1"}, headers=_accountant_headers()
    )

    assert resp.status_code == 200
    txns = resp.json()["data"]
    assert len(txns) == 1
    txn = txns[0]
    assert txn["amount"] == 3000
    assert txn["paid_amount"] == 3000
    assert txn["created_at"]
    assert "updated_at" not in txn or txn["updated_at"] is None


def test_corrected_transaction_returns_updated_at(client):
    headers = {**_accountant_headers(), "Idempotency-Key": "student-history-2|2026-05|tuition"}

    created = client.post(
        "/api/fees/transactions",
        json={**_payment_payload(), "student_id": "student-history-2"},
        headers=headers,
    ).json()["data"]

    client.patch(
        f"/api/fees/transactions/{created['id']}/correct",
        json={"amount": 2500, "reason": "Bank slip amount was wrong"},
        headers=_accountant_headers(),
    )

    resp = client.get(
        "/api/fees/transactions", params={"student_id": "student-history-2"}, headers=_accountant_headers()
    )
    txn = resp.json()["data"][0]
    assert txn["amount"] == 2500
    assert txn["updated_at"]
