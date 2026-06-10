"""Query/support-ticket domain service — single shared write path (AD7).

Both the REST routes in `routes/queries.py` and the AI tools
(`create_query_ticket`, `resolve_query_ticket`, `reopen_query_ticket`,
`assign_query_ticket`, `delete_query_ticket`) call these functions.

The REST create is multipart (optional image attachment); the route handles the
upload bytes and passes them in — the doc construction is identical either way.
Authorization (IT-tech/owner gates) stays in the adapters: REST keeps its route
checks, the AI side is gated by the tool registry + Phase-1 lockdown.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter

ALLOWED_PRIORITIES = ("low", "medium", "high", "urgent")


class TicketValidationError(Exception):
    """Invalid input → HTTP 400."""


class TicketNotFoundError(Exception):
    """Unknown ticket id within the caller's scope → HTTP 404."""


async def _get(db, actor_ctx: ActorContext, ticket_id: str) -> dict:
    ticket = await db.queries.find_one(
        # branch-scope: intentional — query tickets are school-wide (matches routes/queries.py)
        scoped_filter({"id": ticket_id}, actor_ctx.school_id), {"_id": 0}
    )
    if not ticket:
        raise TicketNotFoundError(ticket_id)
    return ticket


async def create_ticket(db, actor_ctx: ActorContext, params: dict, *, attachment: dict | None = None) -> dict:
    """Create a ticket. params: {title, description, priority, category?, assigned_to?}

    attachment (REST only): {"data": bytes, "type": "png|jpg|jpeg"}
    """
    title = (params.get("title") or "").strip()
    description = (params.get("description") or "").strip()
    priority = params.get("priority")
    if not title or len(title) > 200:
        raise TicketValidationError("Title must be 1–200 characters")
    if not description or len(description) > 2000:
        raise TicketValidationError("Description must be 1–2000 characters")
    if priority not in ALLOWED_PRIORITIES:
        raise TicketValidationError(f"Priority must be one of: {', '.join(ALLOWED_PRIORITIES)}")

    ticket_id = str(uuid.uuid4())
    ticket = {
        "schoolId": actor_ctx.school_id,
        "id": ticket_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "category": params.get("category") or "general",
        "assigned_to": params.get("assigned_to"),
        "created_by": actor_ctx.user_id,
        "created_by_name": actor_ctx.actor_name,
        "created_by_role": actor_ctx.role or "",
        "attachment_url": f"/api/queries/{ticket_id}/attachment" if attachment else None,
        "attachment_type": attachment["type"] if attachment else None,
        "created_at": actor_ctx.now_iso(),
        "resolved_at": None,
        "resolved_by": None,
        "resolved_by_name": None,
    }
    db_record = {**ticket, "_id": ticket_id}
    if attachment:
        db_record["attachment_data"] = attachment["data"]
    await db.queries.insert_one(db_record)
    return {"ticket": ticket}


async def resolve_ticket(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Mark a ticket resolved. params: {ticket_id}"""
    ticket_id = params.get("ticket_id")
    if not ticket_id:
        raise TicketValidationError("ticket_id is required")
    await _get(db, actor_ctx, ticket_id)
    now = actor_ctx.now_iso()
    await db.queries.update_one(
        # branch-scope: intentional — query tickets are school-wide (matches routes/queries.py)
        scoped_filter({"id": ticket_id}, actor_ctx.school_id),
        {"$set": {
            "status": "resolved",
            "resolved_at": now,
            "resolved_by": actor_ctx.user_id,
            "resolved_by_name": actor_ctx.actor_name,
        }},
    )
    return {"ticket_id": ticket_id, "status": "resolved", "resolved_at": now}


async def reopen_ticket(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Reopen a resolved ticket. params: {ticket_id}"""
    ticket_id = params.get("ticket_id")
    if not ticket_id:
        raise TicketValidationError("ticket_id is required")
    await _get(db, actor_ctx, ticket_id)
    await db.queries.update_one(
        # branch-scope: intentional — query tickets are school-wide (matches routes/queries.py)
        scoped_filter({"id": ticket_id}, actor_ctx.school_id),
        {"$set": {"status": "open", "resolved_at": None, "resolved_by": None, "resolved_by_name": None}},
    )
    return {"ticket_id": ticket_id, "status": "open"}


async def assign_ticket(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Assign a ticket. params: {ticket_id, assigned_to, status?}"""
    ticket_id = params.get("ticket_id")
    if not ticket_id:
        raise TicketValidationError("ticket_id is required")
    assigned_to = params.get("assigned_to")
    if not assigned_to:
        raise TicketValidationError("assigned_to is required")
    await _get(db, actor_ctx, ticket_id)
    update = {
        "assigned_to": assigned_to,
        "status": params.get("status", "in_progress"),
        "updated_at": actor_ctx.now_iso(),
    }
    await db.queries.update_one(
        # branch-scope: intentional — query tickets are school-wide (matches routes/queries.py)
        scoped_filter({"id": ticket_id}, actor_ctx.school_id), {"$set": update}
    )
    updated = await db.queries.find_one(
        # branch-scope: intentional — query tickets are school-wide (matches routes/queries.py)
        scoped_filter({"id": ticket_id}, actor_ctx.school_id),
        {"_id": 0, "attachment_data": 0},
    )
    return {"ticket": updated}


async def delete_ticket(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Delete a ticket (hard delete, matching the panel). params: {ticket_id}"""
    ticket_id = params.get("ticket_id")
    if not ticket_id:
        raise TicketValidationError("ticket_id is required")
    existing = await _get(db, actor_ctx, ticket_id)
    await db.queries.delete_one(
        # branch-scope: intentional — query tickets are school-wide (matches routes/queries.py)
        scoped_filter({"id": ticket_id}, actor_ctx.school_id)
    )
    existing.pop("attachment_data", None)
    # F.10: actor-tagged deletion audit — who deleted what, when.
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "query_ticket",
            "entity_id": ticket_id,
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
    return {"deleted": True, "ticket": existing}
