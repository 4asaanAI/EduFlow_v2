"""Story A.5 — fee contact-log service: write + canonical audit + AI mapping."""

from __future__ import annotations

import pytest

from services.actor_context import actor_ctx_from_user
from services.contact_log_service import log_contact_event, ContactLogValidationError
from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

OWNER = {"id": "admin-1", "role": "owner", "name": "Admin User"}
FULL = {
    "student_id": "student-1",
    "fee_transaction_id": "fee-1",
    "date": "2026-05-12",
    "contact_type": "call",
    "outcome": "Parent promised payment",
    "notes": "Called guardian",
}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in ("fee_contact_logs", "audit_logs", "fee_transactions"):
        getattr(fake_db, col).docs[:] = []
    yield
    for col in ("fee_contact_logs", "audit_logs", "fee_transactions"):
        getattr(fake_db, col).docs[:] = []


def _ctx():
    return actor_ctx_from_user(OWNER, school_id="aaryans-joya")


def _seed_txn(fake_db, txn_id="fee-1"):
    fake_db.fee_transactions.docs.append({
        "id": txn_id, "schoolId": "aaryans-joya", "student_id": "student-1",
        "fee_head": "tuition", "amount": 1000, "status": "overdue",
        "created_at": "2026-05-01T00:00:00",
    })


async def test_missing_field_raises_validation(fake_db):
    with pytest.raises(ContactLogValidationError):
        await log_contact_event(fake_db, _ctx(), {**FULL, "notes": ""})


async def test_writes_record_and_canonical_audit(fake_db):
    result = await log_contact_event(fake_db, _ctx(), dict(FULL))
    assert "_id" not in result["record"]
    rec = fake_db.fee_contact_logs.docs[0]
    assert rec["contact_type"] == "call"
    assert rec["fee_transaction_id"] == "fee-1"
    assert rec["created_by"] == "admin-1"
    audit = next(a for a in fake_db.audit_logs.docs if a.get("action") == "contact_log")
    assert audit["entity_type"] == "fee_transaction"
    assert audit["entity_id"] == "fee-1"


async def test_ai_tool_maps_note_and_writes_canonical_audit(fake_db, monkeypatch):
    """Regression: the old AI tool wrote audit action 'log_contact_event'/'fee_transactions';
    it now writes the canonical 'contact_log'/'fee_transaction'."""
    _seed_txn(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_log_contact_event(
        {"student_id": "student-1", "fee_transaction_id": "fee-1", "date": "2026-05-12",
         "contact_type": "call", "outcome": "ok", "note": "Called guardian"},
        OWNER, None,
    )
    assert out["success"] is True
    assert fake_db.fee_contact_logs.docs[0]["notes"] == "Called guardian"  # note → notes
    assert any(a.get("action") == "contact_log" and a.get("entity_type") == "fee_transaction"
               for a in fake_db.audit_logs.docs)


async def test_ai_tool_resolves_latest_txn_when_id_absent(fake_db, monkeypatch):
    _seed_txn(fake_db, "fee-latest")
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_log_contact_event(
        {"student_id": "student-1", "contact_type": "call", "outcome": "ok", "note": "n"},
        OWNER, None,
    )
    assert out["success"] is True
    assert fake_db.fee_contact_logs.docs[0]["fee_transaction_id"] == "fee-latest"
