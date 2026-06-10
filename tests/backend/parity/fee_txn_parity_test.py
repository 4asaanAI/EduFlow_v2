"""Dual-entrypoint parity — fee transaction correction, soft-delete, and fee sync.

Same seed through the REST routes (`PATCH /api/fees/transactions/{id}/correct`,
`DELETE /api/fees/transactions/{id}`, `POST /api/fees/sync/trigger`) and the AI
tools (`correct_fee_transaction`, `delete_fee_transaction`, `trigger_fee_sync`)
→ identical DB state via services/fees_service.py + fee_sync_service.py (AD7).
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

import routes.fees as fees_routes
from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id",
             "corrected_at", "deleted_at", "started_at", "completed_at", "failed_at"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}
SCHOOL = "aaryans-joya"


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _scrub(value):
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _mask(docs):
    out = [_scrub(d) for d in copy.deepcopy(docs)]
    return sorted(out, key=lambda d: str(sorted(d.items())))


def _clear(fake_db):
    for col in ("fee_transactions", "fee_transaction_corrections", "fee_sync_jobs", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _ai_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db)
    yield
    _clear(fake_db)


def _seed_txn(fake_db):
    fake_db.fee_transactions.docs[:] = [{
        "_id": "txn-1", "id": "txn-1", "schoolId": SCHOOL, "student_id": "stu-1",
        "fee_period": "2026-06", "fee_head": "tuition", "fee_type": "tuition",
        "amount": 5000.0, "status": "paid", "payment_mode": "cash",
        "paid_date": "2026-06-01", "created_by": "own-1",
        "created_at": "2026-06-01T00:00:00",
    }]


def _txn_state(fake_db):
    return {
        "fee_transactions": _mask(fake_db.fee_transactions.docs),
        "corrections": _mask(fake_db.fee_transaction_corrections.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("entity_type") == "fee_transaction"]),
    }


async def test_correct_fee_transaction_parity(client, fake_db):
    _seed_txn(fake_db)
    resp = client.patch("/api/fees/transactions/txn-1/correct",
                        json={"amount": 4500, "reason": "typo in amount"},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _txn_state(fake_db)

    _clear(fake_db)
    _seed_txn(fake_db)
    out = await tool_functions_v2.tool_correct_fee_transaction(
        {"transaction_id": "txn-1", "amount": 4500, "reason": "typo in amount"}, OWNER_USER, None)
    assert out["success"] is True
    assert _txn_state(fake_db) == rest_state
    txn = rest_state["fee_transactions"][0]
    assert txn["amount"] == 4500
    assert txn["corrected"] is True
    assert txn["correction_count"] == 1
    assert txn["original_snapshot"]["amount"] == 5000.0
    assert len(rest_state["corrections"]) == 1


async def test_delete_fee_transaction_parity_is_soft(client, fake_db):
    _seed_txn(fake_db)
    resp = client.delete("/api/fees/transactions/txn-1", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _txn_state(fake_db)

    _clear(fake_db)
    _seed_txn(fake_db)
    out = await tool_functions_v2.tool_delete_fee_transaction(
        {"transaction_id": "txn-1", "reason": "duplicate entry"}, OWNER_USER, None)
    assert out["success"] is True
    ai_state = _txn_state(fake_db)
    # The AI path records the optional reason on the audit row; REST has no body.
    for state in (ai_state, rest_state):
        for row in state["audit"]:
            row.pop("reason", None)
    assert ai_state == rest_state
    txn = rest_state["fee_transactions"][0]
    assert txn["deleted"] is True              # soft delete — financial trail kept
    assert len(rest_state["audit"]) == 1       # F.10 actor-tagged deletion audit


async def test_deleted_transaction_cannot_be_deleted_again(client, fake_db):
    _seed_txn(fake_db)
    fake_db.fee_transactions.docs[0]["deleted"] = True
    resp = client.delete("/api/fees/transactions/txn-1", headers=_owner_headers())
    assert resp.status_code == 404
    out = await tool_functions_v2.tool_delete_fee_transaction(
        {"transaction_id": "txn-1"}, OWNER_USER, None)
    assert out["success"] is False


# ─── Fee sync ────────────────────────────────────────────────────────────────

_EXTERNAL = [
    {"student_id": "stu-9", "fee_period": "2026-06", "fee_head": "tuition",
     "amount": 3000, "status": "pending", "due_date": "2026-06-15"},
]


def _sync_state(fake_db):
    return {
        "fee_transactions": _mask(fake_db.fee_transactions.docs),
        "jobs": _mask(fake_db.fee_sync_jobs.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("entity_type") == "fee_sync_job"]),
    }


async def test_trigger_fee_sync_parity(client, fake_db, monkeypatch):
    async def _fake_fetch():
        return copy.deepcopy(_EXTERNAL)

    monkeypatch.setattr(fees_routes, "_fetch_external_fee_records", _fake_fetch)

    resp = client.post("/api/fees/sync/trigger", headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "completed"
    rest_state = _sync_state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_trigger_fee_sync({}, OWNER_USER, None)
    assert out["success"] is True
    assert _sync_state(fake_db) == rest_state
    assert rest_state["jobs"][0]["synced_count"] == 1
    assert rest_state["fee_transactions"][0]["source"] == "fee_api_sync"


async def test_get_fee_sync_status_reports_latest(fake_db):
    fake_db.fee_sync_jobs.docs[:] = [{
        "_id": "job-1", "id": "job-1", "schoolId": SCHOOL, "status": "completed",
        "started_at": "2026-06-10T08:00:00", "synced_count": 4, "conflict_count": 0,
        "conflicts": [], "triggered_by": "own-1", "created_at": "2026-06-10T08:00:00",
    }]
    out = await tool_functions_v2.tool_get_fee_sync_status({}, OWNER_USER, None)
    assert out["success"] is True
    assert out["data"]["latest"]["synced_count"] == 4
