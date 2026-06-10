"""Announcement moderation service — the single source of truth for the
announcement approval gate (AI Layer Hardening, AD7 / Epic A, Story A.4).

Both `POST /api/ops/announcements` (REST) and the AI `create_announcement` tool
call `decide_announcement_status(...)`, so the moderation decision is identical
regardless of entrypoint. This removes the gate logic that was duplicated inline
in `tool_create_announcement` (project-context.md previously noted the duplication
existed "due to circular import risk" — this service resolves that).

**Parity decision (case-by-case, canonical = REST, per Story A.4 "exactly as the
route does"):** the REST route exempts owner & principal (EC-9.1 — they ARE the
approvers, so self-moderation is a pointless round-trip; documented behavior). The
old AI tool applied the content gate to *everyone*, so an owner's AI announcement was
needlessly held for approval — divergent from the panel. The AI now honors the same
role exemption. (The 5 `test_announcement_moderation.py` tests assert the pre-EC-9.1
"moderate owner too" policy and remain pinned-failing — they pre-date EC-9.1.)

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

from typing import List, Optional

from services.actor_context import ActorContext

# Roles a principal may address (everything except owner). Mirrors the route's
# Story 7-47 / EC-9.1 PRINCIPAL_ALLOWED_AUDIENCES.
PRINCIPAL_ALLOWED_AUDIENCES = {"teacher", "student", "admin", "all", "parent"}


class AnnouncementValidationError(Exception):
    """Audience guard violation (principal targeting owner) → HTTP 422."""


def decide_announcement_status(
    actor_ctx: ActorContext,
    audience_type: Optional[str],
    target_roles: Optional[List[str]],
    *,
    raw_audience_roles: Optional[List[str]] = None,
) -> str:
    """Return ``"active"`` or ``"pending_approval"`` for a new announcement.

    EC-9.1: owner and principal broadcast directly (they are the approvers).
    Story 7-47: for every other role, an announcement addressed to all/class or to
    teachers/students is held for approval.

    Raises ``AnnouncementValidationError`` when a principal targets the owner role.
    """
    role = actor_ctx.role
    if role == "admin" and actor_ctx.sub_category == "principal":
        audience_set = set(raw_audience_roles if raw_audience_roles is not None else (target_roles or []))
        if not audience_set.issubset(PRINCIPAL_ALLOWED_AUDIENCES):
            raise AnnouncementValidationError("Principal cannot target owner role")
        return "active"
    if role == "owner":
        return "active"
    requires_approval = audience_type in ("all", "class") or any(
        r in ("teacher", "student") for r in (target_roles or [])
    )
    return "pending_approval" if requires_approval else "active"


class AnnouncementNotFoundError(Exception):
    """Unknown announcement id → HTTP 404."""


class AnnouncementStateError(Exception):
    """Announcement not in pending_approval state → HTTP 400."""


async def decide_announcement(db, actor_ctx, params: dict) -> dict:
    """Approve or reject a pending announcement (shared write path — REST
    PATCH /announcements/{id}/approve|reject + AI `decide_announcement`).

    params: {announcement_id, decision: approve|reject, reason (reject only)}
    """
    import uuid as _uuid

    from services.audit_service import write_audit_doc
    from services.notification_service import create_notification
    from tenant import scoped_filter

    ann_id = params.get("announcement_id")
    if not ann_id:
        raise AnnouncementValidationError("announcement_id is required")
    decision = params.get("decision")
    if decision not in ("approve", "reject"):
        raise AnnouncementValidationError("decision must be approve or reject")
    reason = (params.get("reason") or "").strip()
    if decision == "reject" and not reason:
        raise AnnouncementValidationError("rejection reason is required")

    school_id = actor_ctx.school_id
    ann = await db.announcements.find_one(scoped_filter({"id": ann_id}, school_id))
    if not ann:
        raise AnnouncementNotFoundError(ann_id)
    if ann.get("status") != "pending_approval":
        raise AnnouncementStateError(
            f"Cannot {decision} announcement in status '{ann.get('status', 'unknown')}'"
        )

    now = actor_ctx.now_iso()
    if decision == "approve":
        update = {
            "status": "active",
            "approved_by": actor_ctx.user_id,
            "approved_by_name": actor_ctx.actor_name,
            "approved_at": now,
        }
        audit_action = "announcement_approved"
        new_status = "active"
    else:
        update = {
            "status": "rejected",
            "rejected_by": actor_ctx.user_id,
            "rejected_by_name": actor_ctx.actor_name,
            "rejected_at": now,
            "rejection_reason": reason,
        }
        audit_action = "announcement_rejected"
        new_status = "rejected"

    await db.announcements.update_one(scoped_filter({"id": ann_id}, school_id), {"$set": update})
    await write_audit_doc(
        db,
        {
            "_id": str(_uuid.uuid4()),
            "id": str(_uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "announcement",
            "entity_id": ann_id,
            "action": audit_action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {
                "status": {"from": "pending_approval", "to": new_status},
                "target_roles": ann.get("target_roles") or ann.get("audience_roles"),
            },
            "reason": reason or None,
            "created_at": now,
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )
    if decision == "reject" and ann.get("created_by"):
        await create_notification(
            db,
            user_id=ann["created_by"],
            notification_type="announcement_rejected",
            title="Announcement rejected",
            message=f"Your announcement '{ann.get('title', '')}' was rejected: {reason}",
            source_id=ann_id,
            source_type="announcement",
        )
    if decision == "approve":
        return {"id": ann_id, "status": "active", "approved_at": now}
    return {"id": ann_id, "status": "rejected", "rejected_at": now, "reason": reason}


async def delete_announcement(db, actor_ctx, params: dict) -> dict:
    """Delete an announcement (shared write path — REST DELETE /announcements/{id}
    + AI `delete_announcement`). Hard delete, matching the panel, + F.10 audit."""
    import uuid as _uuid

    from services.audit_service import write_audit_doc
    from tenant import scoped_filter

    ann_id = params.get("announcement_id")
    if not ann_id:
        raise AnnouncementValidationError("announcement_id is required")
    school_id = actor_ctx.school_id
    existing = await db.announcements.find_one(scoped_filter({"id": ann_id}, school_id), {"_id": 0})
    if not existing:
        raise AnnouncementNotFoundError(ann_id)
    await db.announcements.delete_one(scoped_filter({"id": ann_id}, school_id))
    # F.10: actor-tagged deletion audit — who deleted what, when.
    await write_audit_doc(
        db,
        {
            "_id": str(_uuid.uuid4()),
            "id": str(_uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "announcement",
            "entity_id": ann_id,
            "action": "delete",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"deleted": existing},
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )
    return {"deleted": True, "announcement": existing}
