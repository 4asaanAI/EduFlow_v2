"""Story A.5 — dual-entrypoint parity for fee contact-log.

Same seed + same actor (owner) through REST POST /api/fees/contact-log and the AI
`log_contact_event` tool → fee_contact_logs record + contact_log audit byte-identical
except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "timestamp"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask(docs):
    out = []
    for d in docs:
        m = {k: v for k, v in d.items() if k not in _VOLATILE}
        ch = m.get("changes")
        if isinstance(ch, dict) and isinstance(ch.get("contact"), dict):
            m = {**m, "changes": {"contact": {k: v for k, v in ch["contact"].items() if k not in _VOLATILE}}}
        out.append(m)
    out.sort(key=lambda d: (d.get("entity_id", ""), d.get("contact_type", ""), d.get("action", "")))
    return out


def _snapshot(fake_db):
    return {
        "fee_contact_logs": _mask(copy.deepcopy(fake_db.fee_contact_logs.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == "contact_log"]),
    }


def _clear(fake_db):
    for col in ("fee_contact_logs", "audit_logs", "fee_transactions"):
        getattr(fake_db, col).docs[:] = []


def _seed_txn(fake_db):
    fake_db.fee_transactions.docs.append({
        "id": "fee-1", "schoolId": "aaryans-joya", "student_id": "student-1",
        "fee_head": "tuition", "amount": 1000, "status": "overdue", "created_at": "2026-05-01T00:00:00",
    })


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_ai_and_rest_contact_log_identical(client, auth_headers, fake_db, monkeypatch):
    payload = {
        "student_id": "student-1", "fee_transaction_id": "fee-1", "date": "2026-05-12",
        "contact_type": "call", "outcome": "Parent promised payment", "notes": "Called guardian",
    }
    # --- REST ---
    _seed_txn(fake_db)
    resp = client.post("/api/fees/contact-log", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI (note → notes; explicit fee_transaction_id) ---
    _clear(fake_db)
    _seed_txn(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_log_contact_event(
        {"student_id": "student-1", "fee_transaction_id": "fee-1", "date": "2026-05-12",
         "contact_type": "call", "outcome": "Parent promised payment", "note": "Called guardian"},
        OWNER_USER, None,
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state["fee_contact_logs"] == rest_state["fee_contact_logs"]
    assert ai_state["audit_logs"] == rest_state["audit_logs"]
    assert len(rest_state["fee_contact_logs"]) == 1
    assert len(rest_state["audit_logs"]) == 1
