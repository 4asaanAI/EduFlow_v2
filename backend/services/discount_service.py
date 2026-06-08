"""Fee-discount domain service — the single shared write path for applying a fee
discount (AI Layer Hardening, AD7 / Epic B, Story B.2).

Both `POST /api/fees/discounts/apply` (REST) and the AI `apply_discount` tool call
`apply_discount(...)`, so an AI discount honours owner authority identically to the
panel: a discount **above** `DISCOUNT_APPROVAL_THRESHOLD` is parked in
`pending_discount_approvals` (never applied directly); a discount **below** applies
immediately.

**Parity decision (case-by-case, canonical = REST):** the old AI `tool_apply_discount`
applied every discount directly, bypassing owner approval on children's fees (found
defect B.2 — a live authority hole). The threshold gate is now centralized here and
enforced for the AI path too.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter


def _approval_threshold() -> Decimal:
    return Decimal(os.environ.get("DISCOUNT_APPROVAL_THRESHOLD", "10000"))


class DiscountValidationError(Exception):
    """Invalid input (missing required field) → HTTP 400."""


class DiscountNotFoundError(Exception):
    """Discount type does not exist (in scope) → HTTP 404."""


def _session_kwargs(session) -> dict:
    return {"session": session} if session is not None else {}


async def apply_discount(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Apply a fee discount, routing large discounts to owner approval.

    params: ``{student_id, discount_type_id, original_amount?, effective_from?, note?}``
    returns: ``{"status": "pending"|"applied", "data": <doc>, "message": str}``
    """
    school_id = actor_ctx.school_id
    student_id = params.get("student_id")
    discount_type_id = params.get("discount_type_id")
    note = params.get("note", "")

    if not student_id or not discount_type_id:
        raise DiscountValidationError("student_id and discount_type_id are required")

    dtype = await db.fee_discount_types.find_one(
        scoped_filter({"id": discount_type_id}, school_id), {"_id": 0}, **_session_kwargs(session)
    )
    if not dtype:
        raise DiscountNotFoundError("Discount type not found")

    discount_amount = Decimal(str(dtype.get("value", 0)))
    threshold = _approval_threshold()

    # Above threshold → owner approval (EXCLUSIVE upper bound), never applied directly.
    if discount_amount > threshold:
        pending = {
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "student_id": student_id,
            "discount_type_id": discount_type_id,
            "discount_amount": float(discount_amount),
            "requested_by": actor_ctx.user_id,
            "note": note,
            "status": "pending",
            "created_at": actor_ctx.now_utc_iso(),
        }
        await db.pending_discount_approvals.insert_one({**pending, "_id": pending["id"]}, **_session_kwargs(session))
        return {
            "status": "pending",
            "data": pending,
            "message": (
                f"Discount of ₹{discount_amount} requires owner approval "
                f"(threshold: ₹{threshold})"
            ),
        }

    # Below threshold — apply immediately.
    original_amount = params.get("original_amount")
    effective_from = params.get("effective_from")
    if original_amount is None or effective_from is None:
        raise DiscountValidationError(
            "original_amount and effective_from are required for immediate discount application"
        )
    application = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": school_id,
        "student_id": student_id,
        "discount_type_id": dtype["id"],
        "original_amount": float(original_amount),
        "effective_from": effective_from,
        "applied_by": actor_ctx.user_id,
        "applied_at": actor_ctx.now().isoformat(),
        "note": note,
    }
    await db.fee_discounts.insert_one(application, **_session_kwargs(session))
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "fee_transaction",
            "entity_id": application["id"],
            "action": "discount_apply",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"applied": {k: v for k, v in application.items() if k != "_id"}},
            "reason": note,
            "created_at": actor_ctx.now().isoformat(),
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )
    return {
        "status": "applied",
        "data": {k: v for k, v in application.items() if k != "_id"},
        "message": "Discount applied.",
    }
