"""Story B.1 — dual-entrypoint parity + idempotency for fee payments.

Same seed through both write entrypoints (REST POST /api/fees/transactions via
TestClient, and the AI `record_fee_payment` tool via its real dispatch fn) → the
fee_transactions doc + idempotency key + audit row are byte-identical except a
volatile allowlist. Also pins the B.1 double-charge regression guard.
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

# "changes" is masked: the audit row embeds the full txn doc (volatile id/receipt/dates).
_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "receipt_number",
             "transaction_id", "expires_at", "paid_date", "entity_id", "record_id", "changes"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: (d.get("student_id", ""), d.get("action", ""), d.get("key", "")))
    return out


def _snapshot(fake_db):
    return {
        "fee_transactions": _mask(copy.deepcopy(fake_db.fee_transactions.docs)),
        "fee_idempotency_keys": _mask(copy.deepcopy(fake_db.fee_idempotency_keys.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs)
                             if a.get("entity_type") == "fee_transaction"]),
    }


def _clear(fake_db):
    for col in ("fee_transactions", "fee_idempotency_keys", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


_BODY = {
    "student_id": "stu-1",
    "amount": 5000,
    "payment_mode": "cash",
    "fee_period": "2026-06",
    "fee_head": "tuition",
}
_IDEM_KEY = "stu-1|2026-06|tuition"


async def test_ai_and_rest_fee_payment_identical(client, fake_db, monkeypatch):
    # --- REST entrypoint ---
    resp = client.post("/api/fees/transactions", json=_BODY,
                       headers={**_owner_headers(), "Idempotency-Key": _IDEM_KEY})
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI entrypoint (same actor, same seed) ---
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_record_fee_payment(
        {"student_id": "stu-1", "amount": 5000, "mode": "cash",
         "fee_period": "2026-06", "fee_head": "tuition"},
        OWNER_USER, None,
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state
    assert rest_state["fee_transactions"][0]["status"] == "paid"
    assert len(rest_state["audit_logs"]) == 1


async def test_ai_partial_payment_matches_rest(client, fake_db, monkeypatch):
    body = {**_BODY, "paid_amount": 2000}
    resp = client.post("/api/fees/transactions", json=body,
                       headers={**_owner_headers(), "Idempotency-Key": _IDEM_KEY})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "partial"

    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_record_fee_payment(
        {"student_id": "stu-1", "amount": 5000, "mode": "cash",
         "fee_period": "2026-06", "fee_head": "tuition", "paid_amount": 2000},
        OWNER_USER, None,
    )
    assert out["success"] is True
    assert out["data"]["status"] == "partial"


async def test_ai_fee_payment_idempotent_no_double_charge(fake_db, monkeypatch):
    """B.1 regression guard: a confirm retry with the same key produces ONE transaction."""
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    p = {"student_id": "stu-1", "amount": 5000, "mode": "cash",
         "fee_period": "2026-06", "fee_head": "tuition"}
    out1 = await tool_functions_v2.tool_record_fee_payment(p, OWNER_USER, None)
    out2 = await tool_functions_v2.tool_record_fee_payment(p, OWNER_USER, None)
    assert out1["success"] is True and out2["success"] is True
    assert len(fake_db.fee_transactions.docs) == 1
    # Both confirmations resolve to the same transaction id.
    assert out1["data"]["id"] == out2["data"]["id"]
