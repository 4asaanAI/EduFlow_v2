"""Visitor-log domain service — single shared write path (AD7).

Both the REST routes (`POST /api/ops/visitors`, `PATCH .../checkout`,
`DELETE /api/ops/visitors/{id}`) and the AI tools call these functions:
same same-day duplicate guard, same force-override rate limit (EC-11.1),
same field set.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import re
import uuid

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_query

MAX_FORCE_OVERRIDES = 3


class VisitorValidationError(Exception):
    """Invalid input → HTTP 400."""


class VisitorNotFoundError(Exception):
    """Unknown visitor id within the caller's scope → HTTP 404."""


class VisitorDuplicateError(Exception):
    """Same visitor already checked in today (pass force=True) → HTTP 409."""

    def __init__(self, existing_id: str):
        super().__init__("Visitor already checked in today. Pass force:true to override.")
        self.existing_id = existing_id


class VisitorRateLimitError(Exception):
    """Force-override limit reached (EC-11.1) → HTTP 429."""


async def log_visitor(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Check a visitor in. params: {visitor_name, phone?, purpose?, whom_to_meet?, id_type?, force?}"""
    bid = actor_ctx.branch_id
    visitor_name = (params.get("visitor_name") or "").strip()
    force = bool(params.get("force", False))
    today_prefix = actor_ctx.now().strftime("%Y-%m-%d")
    if visitor_name:
        norm_name = re.escape(visitor_name)
        duplicate = await db.visitor_log.find_one(
            scoped_query({
                "visitor_name": {"$regex": norm_name, "$options": "i"},
                "time_in": {"$regex": f"^{today_prefix}"},
                "time_out": None,
            }, branch_id=bid),
            {"_id": 0},
        )
        if duplicate:
            if not force:
                raise VisitorDuplicateError(duplicate.get("id"))
            force_count = await db.visitor_log.count_documents(
                scoped_query({
                    "visitor_name": {"$regex": norm_name, "$options": "i"},
                    "time_in": {"$regex": f"^{today_prefix}"},
                    "force_override": True,
                }, branch_id=bid)
            )
            if force_count >= MAX_FORCE_OVERRIDES:
                raise VisitorRateLimitError(
                    f"Maximum {MAX_FORCE_OVERRIDES} forced check-ins per visitor per day exceeded"
                )
    visitor = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "visitor_name": visitor_name,
        "phone": params.get("phone", ""),
        "purpose": params.get("purpose"),
        "whom_to_meet": params.get("whom_to_meet", ""),
        "id_type": params.get("id_type", ""),
        "time_in": actor_ctx.now_iso(),
        "time_out": None,
        "force_override": force,
    }
    await db.visitor_log.insert_one({**visitor, "_id": visitor["id"]})
    return {"visitor": visitor}


async def checkout_visitor(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Check a visitor out. params: {visitor_id}"""
    visitor_id = params.get("visitor_id")
    if not visitor_id:
        raise VisitorValidationError("visitor_id is required")
    existing = await db.visitor_log.find_one(
        scoped_query({"id": visitor_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not existing:
        raise VisitorNotFoundError(visitor_id)
    time_out = actor_ctx.now_iso()
    await db.visitor_log.update_one(
        scoped_query({"id": visitor_id}, branch_id=actor_ctx.branch_id),
        {"$set": {"time_out": time_out}},
    )
    return {"visitor_id": visitor_id, "time_out": time_out}


async def delete_visitor(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Delete a visitor-log entry (hard delete, matching the panel). params: {visitor_id}"""
    visitor_id = params.get("visitor_id")
    if not visitor_id:
        raise VisitorValidationError("visitor_id is required")
    existing = await db.visitor_log.find_one(
        scoped_query({"id": visitor_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not existing:
        raise VisitorNotFoundError(visitor_id)
    await db.visitor_log.delete_one(scoped_query({"id": visitor_id}, branch_id=actor_ctx.branch_id))
    # F.10: actor-tagged deletion audit — who deleted what, when.
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "visitor_log",
            "entity_id": visitor_id,
            "action": "delete",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"deleted": existing},
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )
    return {"deleted": True, "visitor": existing}
