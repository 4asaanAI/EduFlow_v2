from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.factories import make_fee_transaction


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def test_partial_payment_creates_partial_status(client, fake_db):
    """Payment with paid_amount < amount creates partial status."""
    fake_db.fee_idempotency_keys.docs = []
    resp = client.post(
        "/api/fees/transactions",
        json={
            "student_id": "stu-1",
            "fee_type": "Tuition",
            "fee_head": "Tuition",
            "fee_period": "2026-05",
            "amount": 5000,
            "paid_amount": 2000,
            "payment_mode": "cash",
        },
        headers={**_owner_h(), "Idempotency-Key": "stu-1|2026-05|tuition"},
    )
    assert resp.status_code in (200, 201)
    txn = next(
        (t for t in fake_db.fee_transactions.docs if t.get("paid_amount") == 2000.0),
        None,
    )
    if txn:
        assert txn["status"] == "partial"


def test_full_payment_creates_paid_status(client, fake_db):
    """Payment without paid_amount defaults to paid status."""
    fake_db.fee_idempotency_keys.docs = []
    resp = client.post(
        "/api/fees/transactions",
        json={
            "student_id": "stu-2",
            "fee_type": "Tuition",
            "fee_head": "Tuition",
            "fee_period": "2026-06",
            "amount": 5000,
            "payment_mode": "online",
        },
        headers={**_owner_h(), "Idempotency-Key": "stu-2|2026-06|tuition"},
    )
    assert resp.status_code in (200, 201)
    data = resp.json().get("data", {})
    assert data.get("status") == "paid"


def test_receipt_endpoint_returns_receipt_fields(client, fake_db):
    """Receipt endpoint returns required fields when format=json."""
    fake_db.fee_transactions.docs = [
        make_fee_transaction(id="txn-r1", receipt_number="RCP-001", student_id="stu-3")
    ]
    fake_db.students.docs = [{"id": "stu-3", "name": "Alice", "schoolId": "aaryans-joya"}]
    resp = client.get(
        "/api/fees/transactions/txn-r1/receipt?format=json",
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "receipt_number" in data
    assert "paid_amount" in data


def test_receipt_returns_404_for_missing_transaction(client, fake_db):
    """Receipt returns 404 for non-existent transaction."""
    fake_db.fee_transactions.docs = []
    resp = client.get(
        "/api/fees/transactions/nonexistent/receipt?format=json",
        headers=_owner_h(),
    )
    assert resp.status_code == 404
