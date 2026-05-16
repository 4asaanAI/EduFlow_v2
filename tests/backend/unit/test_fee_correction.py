from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.factories import make_fee_transaction

pytestmark = pytest.mark.asyncio


def _accountant_headers(user_id="acct-1"):
    t = create_jwt({"user_id": user_id, "role": "admin", "name": "Acct", "sub_category": "accounts"})
    return {"Authorization": f"Bearer {t}"}


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def test_accountant_can_correct_own_transaction(client, fake_db):
    """Accountant can correct a transaction they created."""
    txn = make_fee_transaction(id="txn-c1", created_by="acct-1", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    resp = client.patch(
        "/api/fees/transactions/txn-c1/correct",
        json={"amount": 4500, "reason": "Data entry error"},
        headers=_accountant_headers("acct-1"),
    )
    assert resp.status_code == 200


def test_accountant_cannot_correct_other_transaction(client, fake_db):
    """Accountant cannot correct a transaction created by someone else."""
    txn = make_fee_transaction(id="txn-c2", created_by="other-user", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    resp = client.patch(
        "/api/fees/transactions/txn-c2/correct",
        json={"amount": 4000, "reason": "Error"},
        headers=_accountant_headers("acct-1"),
    )
    assert resp.status_code == 403


def test_owner_can_correct_any_transaction(client, fake_db):
    """Owner can correct any transaction regardless of created_by."""
    txn = make_fee_transaction(id="txn-c3", created_by="someone-else", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    resp = client.patch(
        "/api/fees/transactions/txn-c3/correct",
        json={"amount": 4800, "reason": "Correction by owner"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 200


def test_correct_returns_404_for_missing_transaction(client, fake_db):
    """Returns 404 when transaction does not exist."""
    fake_db.fee_transactions.docs = []
    resp = client.patch(
        "/api/fees/transactions/nonexistent/correct",
        json={"amount": 100, "reason": "test"},
        headers=_owner_headers(),
    )
    assert resp.status_code == 404


def test_original_snapshot_preserved_on_first_correction(client, fake_db):
    """original_snapshot is set on first correction and captures the pre-correction state."""
    txn = make_fee_transaction(id="txn-c4", created_by="own-1", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    # First correction — reason is required by the endpoint
    client.patch(
        "/api/fees/transactions/txn-c4/correct",
        json={"amount": 4500, "reason": "Data entry error"},
        headers=_owner_headers(),
    )
    updated = next((t for t in fake_db.fee_transactions.docs if t.get("id") == "txn-c4"), None)
    if updated:
        assert updated.get("original_snapshot", {}).get("amount") == 5000


def test_original_snapshot_not_overwritten_on_second_correction(client, fake_db):
    """original_snapshot is not overwritten on a second correction."""
    txn = make_fee_transaction(id="txn-c5", created_by="own-1", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    # First correction
    client.patch(
        "/api/fees/transactions/txn-c5/correct",
        json={"amount": 4500, "reason": "First correction"},
        headers=_owner_headers(),
    )
    # Second correction
    client.patch(
        "/api/fees/transactions/txn-c5/correct",
        json={"amount": 4000, "reason": "Second correction"},
        headers=_owner_headers(),
    )
    updated = next((t for t in fake_db.fee_transactions.docs if t.get("id") == "txn-c5"), None)
    if updated:
        # original_snapshot should still reflect the very first amount (5000)
        assert updated.get("original_snapshot", {}).get("amount") == 5000


def test_correction_count_increments(client, fake_db):
    """correction_count increments on each correction."""
    txn = make_fee_transaction(id="txn-c6", created_by="own-1", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    client.patch(
        "/api/fees/transactions/txn-c6/correct",
        json={"amount": 4500, "reason": "Count test"},
        headers=_owner_headers(),
    )
    updated = next((t for t in fake_db.fee_transactions.docs if t.get("id") == "txn-c6"), None)
    if updated:
        assert updated.get("correction_count", 0) >= 1


def test_correction_count_increments_twice(client, fake_db):
    """correction_count reaches 2 after two corrections."""
    txn = make_fee_transaction(id="txn-c7", created_by="own-1", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    client.patch(
        "/api/fees/transactions/txn-c7/correct",
        json={"amount": 4500, "reason": "First count"},
        headers=_owner_headers(),
    )
    client.patch(
        "/api/fees/transactions/txn-c7/correct",
        json={"amount": 4000, "reason": "Second count"},
        headers=_owner_headers(),
    )
    updated = next((t for t in fake_db.fee_transactions.docs if t.get("id") == "txn-c7"), None)
    if updated:
        assert updated.get("correction_count", 0) >= 2


def test_corrected_flag_is_set(client, fake_db):
    """corrected flag is set to True after correction."""
    txn = make_fee_transaction(id="txn-c8", created_by="own-1", amount=5000)
    fake_db.fee_transactions.docs = [txn]
    client.patch(
        "/api/fees/transactions/txn-c8/correct",
        json={"amount": 4500, "reason": "Correction"},
        headers=_owner_headers(),
    )
    updated = next((t for t in fake_db.fee_transactions.docs if t.get("id") == "txn-c8"), None)
    if updated:
        assert updated.get("corrected") is True
