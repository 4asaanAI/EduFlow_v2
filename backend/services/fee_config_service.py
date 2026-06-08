"""Fee-configuration domain service — the single shared write path for fee
structures and discount types (AI Layer Hardening, AD7 / Epic K, Story K.1).

Both the REST routes (`POST/PATCH /api/fees/structures`,
`POST/PATCH/DELETE /api/fees/discount-types`) and the matching Owner/Principal AI
tools call these functions, so an AI fee-config change is byte-identical to the
panel (proven by the dual-entrypoint parity test).

Services raise domain exceptions, never `HTTPException`. The adapters map them.

**Characterization note (Story K.1):** the doc shapes here pin the pre-extraction
REST behavior exactly (so existing `test_fees*` stay green). The AC additionally
requires fee-structure create/update to be *audited*; that audit row is added to
BOTH entrypoints (it flows through the same service), so parity still holds.
Role/authority gating stays in the route `Depends(...)` and chat `_is_tool_authorized`
(P2) — never in the service.
"""

from __future__ import annotations

import uuid
from datetime import timezone
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import add_school_id, scoped_filter, scoped_query


class FeeConfigValidationError(Exception):
    """Invalid input (missing/invalid required field) → HTTP 400."""


class FeeConfigNotFoundError(Exception):
    """Target structure / discount type does not exist (in scope) → HTTP 404."""


# Discount-type fields the update path may change (mirrors the pre-extraction
# REST whitelist in routes/fees.py:update_discount_type).
DISCOUNT_TYPE_UPDATABLE_FIELDS = {"name", "is_active", "reason_note"}

# Keys that must never be overwritten by a caller-supplied update body — guards
# the fee-structure $set against tenant/identity escape.
_IMMUTABLE_KEYS = {"_id", "id", "schoolId"}


def _session_kwargs(session) -> dict:
    # Resolve the ambient transaction session when the caller passes none, so a
    # service invoked inside the plan executor's txn auto-enlists (AD6/D.2).
    return _txn_session_kwargs(session)


async def _audit_fee_config(
    db,
    actor_ctx: ActorContext,
    *,
    action: str,
    entity_id: str,
    changes: dict,
    reason: Optional[str] = None,
    session=None,
) -> None:
    """Audit row identical in shape to the pre-extraction REST `_audit` helper
    (entity_type ``fee_transaction``, naive-local ``created_at``)."""
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "fee_transaction",
            "entity_id": entity_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": changes,
            "reason": reason,
            "created_at": actor_ctx.now().isoformat(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


# ───────────────────────── Fee structures ──────────────────────────────────


async def create_fee_structure(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create a fee structure for a class.

    params: ``{name, class_id, fee_heads?, academic_year?}``
    returns: ``{"structure": <doc>}``
    """
    school_id = actor_ctx.school_id
    structure = {
        "id": str(uuid.uuid4()),
        "name": params.get("name", ""),
        "class_id": params.get("class_id", ""),
        "fee_heads": params.get("fee_heads", []),
        "academic_year": params.get("academic_year", ""),
        "created_by": actor_ctx.user_id,
        # REST used datetime.now(timezone.utc).isoformat() — mirror it.
        "created_at": actor_ctx.now_utc().isoformat(),
    }
    doc = add_school_id(structure, school_id)
    await db.fee_structures.insert_one({**doc, "_id": doc["id"]}, **_session_kwargs(session))
    await _audit_fee_config(
        db, actor_ctx,
        action="fee_structure_create",
        entity_id=doc["id"],
        changes={"created": {k: v for k, v in doc.items()}},
        session=session,
    )
    return {"structure": doc}


async def update_fee_structure(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update a fee structure.

    params: ``{structure_id, **fields}`` — any field except immutable identity keys.
    returns: ``{"structure_id": <id>}``  (REST returned only ``{"success": True}``)
    raises: ``FeeConfigNotFoundError`` when the structure is not in scope.
    """
    school_id = actor_ctx.school_id
    structure_id = params.get("structure_id")
    if not structure_id:
        raise FeeConfigValidationError("structure_id is required")
    changes = {k: v for k, v in params.items() if k not in _IMMUTABLE_KEYS and k != "structure_id"}
    result = await db.fee_structures.update_one(
        scoped_query({"id": structure_id}, branch_id=actor_ctx.branch_id),
        {"$set": changes},
        **_session_kwargs(session),
    )
    if result.matched_count == 0:
        raise FeeConfigNotFoundError("Fee structure not found")
    await _audit_fee_config(
        db, actor_ctx,
        action="fee_structure_update",
        entity_id=structure_id,
        changes=changes,
        session=session,
    )
    return {"structure_id": structure_id}


# ───────────────────────── Discount types ──────────────────────────────────


async def create_discount_type(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Create a fee discount type.

    params: ``{name, value, value_type, recurrence, reason_note}`` (all required)
    returns: ``{"discount_type": <doc without _id>}``
    """
    required = ("name", "value", "value_type", "recurrence", "reason_note")
    if any(params.get(field) in (None, "") for field in required):
        raise FeeConfigValidationError(
            "name, value, value_type, recurrence, and reason_note are required"
        )
    if params["value_type"] not in ("flat", "percentage"):
        raise FeeConfigValidationError("value_type must be flat or percentage")
    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "name": params["name"],
        "value": float(params["value"]),
        "value_type": params["value_type"],
        "recurrence": params["recurrence"],
        "reason_note": params["reason_note"],
        "is_active": True,
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now().isoformat(),
    }
    await db.fee_discount_types.insert_one(doc, **_session_kwargs(session))
    public = {k: v for k, v in doc.items() if k != "_id"}
    await _audit_fee_config(
        db, actor_ctx,
        action="discount_type_create",
        entity_id=doc["id"],
        changes={"created": public},
        session=session,
    )
    return {"discount_type": public}


async def update_discount_type(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Update a discount type (name / is_active / reason_note only).

    params: ``{discount_type_id, name?, is_active?, reason_note?}``
    returns: ``{"discount_type": <updated doc>}``
    raises: ``FeeConfigValidationError`` (no editable fields), ``FeeConfigNotFoundError``.
    """
    school_id = actor_ctx.school_id
    discount_type_id = params.get("discount_type_id")
    if not discount_type_id:
        raise FeeConfigValidationError("discount_type_id is required")
    changes = {k: v for k, v in params.items() if k in DISCOUNT_TYPE_UPDATABLE_FIELDS}
    if not changes:
        raise FeeConfigValidationError("No editable fields supplied")
    existing = await db.fee_discount_types.find_one(
        scoped_filter({"id": discount_type_id}, school_id), {"_id": 0}, **_session_kwargs(session)
    )
    if not existing:
        raise FeeConfigNotFoundError("Discount type not found")
    await db.fee_discount_types.update_one(
        scoped_filter({"id": discount_type_id}, school_id),
        {"$set": {**changes, "updated_at": actor_ctx.now().isoformat()}},
        **_session_kwargs(session),
    )
    await _audit_fee_config(
        db, actor_ctx,
        action="discount_type_update",
        entity_id=discount_type_id,
        changes=changes,
        reason=params.get("reason_note"),
        session=session,
    )
    updated = await db.fee_discount_types.find_one(
        scoped_filter({"id": discount_type_id}, school_id), {"_id": 0}, **_session_kwargs(session)
    )
    return {"discount_type": updated}


async def delete_discount_type(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Hard-delete a discount type (destructive — routed through F.10 two-step
    confirm + actor-tagged deletion audit at the dispatch layer).

    params: ``{discount_type_id}``
    returns: ``{"deleted": True, "discount_type_id": <id>}``
    raises: ``FeeConfigNotFoundError`` when not in scope.
    """
    school_id = actor_ctx.school_id
    discount_type_id = params.get("discount_type_id")
    if not discount_type_id:
        raise FeeConfigValidationError("discount_type_id is required")
    existing = await db.fee_discount_types.find_one(
        scoped_filter({"id": discount_type_id}, school_id), {"_id": 0}, **_session_kwargs(session)
    )
    if not existing:
        raise FeeConfigNotFoundError("Discount type not found")
    await db.fee_discount_types.delete_one(
        scoped_filter({"id": discount_type_id}, school_id), **_session_kwargs(session)
    )
    await _audit_fee_config(
        db, actor_ctx,
        action="discount_type_delete",
        entity_id=discount_type_id,
        changes={"deleted": existing},
        session=session,
    )
    return {"deleted": True, "discount_type_id": discount_type_id}
