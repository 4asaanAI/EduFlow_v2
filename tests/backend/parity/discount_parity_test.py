"""Story B.2 — dual-entrypoint parity + approval-gate guard for fee discounts.

Below-threshold discounts apply identically through REST and the AI tool; above-threshold
discounts park in `pending_discount_approvals` on BOTH paths (closing the AI bypass).
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

# "changes" is masked: the audit row embeds the applied doc (volatile id/applied_at).
_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "applied_at", "entity_id", "record_id", "changes"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _mask(docs):
    out = [{k: v for k, v in d.items() if k not in _VOLATILE} for d in docs]
    out.sort(key=lambda d: (d.get("student_id", ""), d.get("action", "")))
    return out


def _clear(fake_db):
    for col in ("fee_discounts", "fee_discount_types", "pending_discount_approvals", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _seed_dtype(fake_db, value):
    fake_db.fee_discount_types.docs.append({
        "id": "dt-1", "schoolId": "aaryans-joya", "name": "Sibling",
        "value": value, "value_type": "flat", "is_active": True,
    })


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_below_threshold_discount_parity(client, fake_db, monkeypatch):
    _seed_dtype(fake_db, 2000)  # < 10000 threshold → applies immediately
    body = {"student_id": "stu-1", "discount_type_id": "dt-1",
            "original_amount": 5000, "effective_from": "2026-06-01"}
    resp = client.post("/api/fees/discounts/apply", json=body, headers=_owner_headers())
    assert resp.status_code == 200
    rest_discounts = _mask(copy.deepcopy(fake_db.fee_discounts.docs))
    rest_audit = _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == "discount_apply"])

    _clear(fake_db)
    _seed_dtype(fake_db, 2000)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_apply_discount(
        {"student_id": "stu-1", "discount_type_id": "dt-1",
         "original_amount": 5000, "effective_from": "2026-06-01"},
        OWNER_USER, None,
    )
    assert out["success"] is True
    ai_discounts = _mask(copy.deepcopy(fake_db.fee_discounts.docs))
    ai_audit = _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == "discount_apply"])

    assert ai_discounts == rest_discounts
    assert ai_audit == rest_audit
    assert len(rest_discounts) == 1


async def test_above_threshold_ai_discount_routes_to_approval(client, fake_db, monkeypatch):
    """B.2 regression guard: an AI discount above threshold must NOT apply directly."""
    _seed_dtype(fake_db, 15000)  # > 10000 → owner approval
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_apply_discount(
        {"student_id": "stu-1", "discount_type_id": "dt-1",
         "original_amount": 50000, "effective_from": "2026-06-01"},
        OWNER_USER, None,
    )
    assert out["success"] is True
    assert out.get("pending_approval") is True
    # Bypass closed: nothing applied directly, one pending approval created.
    assert len(fake_db.fee_discounts.docs) == 0
    assert len(fake_db.pending_discount_approvals.docs) == 1
    assert fake_db.pending_discount_approvals.docs[0]["status"] == "pending"

    # REST parity: same input also parks in pending approvals (HTTP 202).
    fake_db.pending_discount_approvals.docs[:] = []
    resp = client.post("/api/fees/discounts/apply",
                      json={"student_id": "stu-1", "discount_type_id": "dt-1",
                            "original_amount": 50000, "effective_from": "2026-06-01"},
                      headers=_owner_headers())
    assert resp.status_code == 202
    assert len(fake_db.pending_discount_approvals.docs) == 1
