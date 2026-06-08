"""Fee-payment domain service — the single shared write path for recording a fee
payment (AI Layer Hardening, AD7 / Epic B, Story B.1).

Both `POST /api/fees/transactions` (REST) and the AI `record_fee_payment` tool call
`record_payment(...)`, so an AI payment is byte-identical to a panel payment: the same
partial-payment status detection, the same idempotency guard (one transaction per
`student_id|fee_period|fee_head` key), the same audit row, and the same SSE update.

**Parity decision (case-by-case, canonical = REST):** the old AI `tool_record_fee_payment`
had NO idempotency guard (a confirm retry double-charged — found defect B.1), ignored
partial payments, and emitted no SSE. All three are corrected to match the REST route.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

import uuid
from datetime import timedelta
from typing import Awaitable, Callable, Optional

from models.schemas import FeeTransaction
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter


class FeeValidationError(Exception):
    """Invalid input (missing required field) → HTTP 400."""


def normalize_fee_key(student_id: Optional[str], fee_period: Optional[str], fee_head: Optional[str]) -> str:
    """Canonical idempotency key — identical to the REST route's `_normalize_fee_key`."""
    return f"{student_id}|{fee_period}|{(fee_head or '').strip().lower()}"


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


async def record_payment(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    publish_fn: Optional[Callable[..., Awaitable]] = None,
) -> dict:
    """Record a fee payment idempotently.

    params: ``{student_id, amount, payment_mode, fee_period, fee_head, paid_amount?,
               due_date?, transaction_ref?, status?}``
    returns: ``{"data": <txn doc>, "idempotent": bool, "fee_period": str}``
    """
    school_id = actor_ctx.school_id
    fee_period = params.get("fee_period")
    fee_head = params.get("fee_head") or params.get("fee_type")
    expected_key = normalize_fee_key(params.get("student_id"), fee_period, fee_head)

    now = actor_ctx.now()
    existing = await db.fee_idempotency_keys.find_one(
        scoped_filter({"key": expected_key}, school_id), {"_id": 0}, **_session_kwargs(session)
    )
    expires_at = None
    if existing and existing.get("expires_at"):
        try:
            from datetime import datetime as _dt

            expires_at = _dt.fromisoformat(str(existing["expires_at"]))
        except ValueError:
            expires_at = None
    if existing and (expires_at is None or expires_at > now):
        txn = await db.fee_transactions.find_one(
            scoped_filter({"id": existing["transaction_id"]}, school_id), {"_id": 0}, **_session_kwargs(session)
        )
        if txn:
            return {"data": txn, "idempotent": True, "fee_period": fee_period}

    for field in ("student_id", "amount", "payment_mode", "fee_period"):
        if params.get(field) in (None, ""):
            raise FeeValidationError(f"{field} is required")

    receipt = f"RCP{now.strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    # D-review fix: non-numeric amount/paid_amount must be a 400 (domain error), not an
    # uncaught ValueError → opaque 500. Also handles whitespace-only paid_amount.
    try:
        amount = float(params["amount"])
        _paid_raw = params.get("paid_amount")
        paid_amount = float(_paid_raw) if (_paid_raw is not None and str(_paid_raw).strip() != "") else amount
    except (TypeError, ValueError):
        raise FeeValidationError("amount and paid_amount must be numeric")
    if params.get("status"):
        status = params["status"]
    elif paid_amount < amount:
        status = "partial"
    else:
        status = "paid"
    is_paid = status in ("paid", "partial")
    txn = FeeTransaction(
        student_id=params["student_id"],
        fee_type=fee_head,
        amount=amount,
        status=status,
        due_date=params.get("due_date"),
        paid_date=now.strftime("%Y-%m-%d") if is_paid else None,
        payment_mode=params["payment_mode"],
        receipt_number=receipt,
        transaction_ref=params.get("transaction_ref"),
    )
    doc = {
        **_serialize(txn),
        "_id": txn.id,
        "schoolId": school_id,
        "fee_period": fee_period,
        "fee_head": fee_head,
        "paid_amount": paid_amount,
    }
    await db.fee_transactions.insert_one(doc, **_session_kwargs(session))
    await db.fee_idempotency_keys.insert_one(
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "key": expected_key,
            "transaction_id": txn.id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=24)).isoformat(),
        },
        **_session_kwargs(session),
    )
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "fee_transaction",
            "entity_id": txn.id,
            "action": "create",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"created": {k: v for k, v in doc.items() if k != "_id"}},
            "reason": None,
            "created_at": now.isoformat(),
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )
    data = {k: v for k, v in doc.items() if k != "_id"}
    if publish_fn is not None:
        await publish_fn(db, "fee_payment_recorded", data, fee_period)
    return {"data": data, "idempotent": False, "fee_period": fee_period}
