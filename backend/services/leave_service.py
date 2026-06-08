"""Leave-decision domain service — the single shared write path for approving or
rejecting a staff leave request (AI Layer Hardening, AD7 / Epic A, Story A.2).

Both `PATCH /api/staff/leaves/{id}` (REST) and the AI `approve_leave` tool call
`decide_leave(...)`, so an AI decision is byte-identical to a panel decision:
the same pending-only idempotency guard, the same staff notification, and the
same audit row.

**Parity decision (case-by-case, canonical = REST):** the old AI `tool_approve_leave`
silently diverged — it wrote no notification, no audit, no pending-only guard, did
not require a rejection reason, and stamped a local (not UTC) `approved_at`. All of
those are corrected to match the REST route, which is the complete/correct path.

Services raise domain exceptions, never `HTTPException`. The REST adapter maps them
to 400/404/409; the AI adapter maps them to `{success: False, error}`.
"""

from __future__ import annotations

from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit
from services.notification_service import create_notification
from tenant import scoped_query


class LeaveError(Exception):
    """Base class for leave-decision domain errors."""


class LeaveValidationError(LeaveError):
    """Invalid input (bad status, missing rejection reason) → HTTP 400."""


class LeaveNotFoundError(LeaveError):
    """Leave request does not exist (in tenant scope) → HTTP 404."""


class LeaveConflictError(LeaveError):
    """Leave already decided (not pending) → HTTP 409."""


def _session_kwargs(session) -> dict:
    return {"session": session} if session is not None else {}


async def decide_leave(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Approve or reject a pending leave request.

    params: ``{"leave_id": str, "status": "approved"|"rejected", "rejection_reason"?: str}``
    returns: ``{"leave": <updated doc>, "status": str, "leave_id": str}``
    """
    leave_id = params.get("leave_id")
    new_status = params.get("status")
    if not leave_id:
        raise LeaveValidationError("leave_id is required")
    if new_status not in {"approved", "rejected"}:
        raise LeaveValidationError("status must be approved or rejected")
    rejection_reason = params.get("rejection_reason")
    if new_status == "rejected" and not rejection_reason:
        raise LeaveValidationError("rejection_reason is required when rejecting leave")

    set_fields: dict = {
        "status": new_status,
        "approved_by": actor_ctx.user_id,
        "approved_at": actor_ctx.now_utc_iso(),
    }
    if rejection_reason:
        set_fields["rejection_reason"] = rejection_reason

    # Idempotency guard — only transition a still-pending request (prevents a
    # double-decision creating duplicate notifications/audit entries).
    result = await db.leave_requests.update_one(
        scoped_query({"id": leave_id, "status": "pending"}, branch_id=actor_ctx.branch_id),
        {"$set": set_fields},
        **_session_kwargs(session),
    )

    if result.matched_count == 0:
        existing = await db.leave_requests.find_one(
            scoped_query({"id": leave_id}, branch_id=actor_ctx.branch_id)
        )
        if existing and existing.get("status") != "pending":
            raise LeaveConflictError(f"Leave already {existing['status']}")
        raise LeaveNotFoundError("Leave request not found")

    leave = await db.leave_requests.find_one(
        scoped_query({"id": leave_id}, branch_id=actor_ctx.branch_id)
    )

    if leave and leave.get("user_id"):
        action_word = "approved" if new_status == "approved" else "rejected"
        await create_notification(
            db=db,
            user_id=leave["user_id"],
            notification_type="leave_decision",
            title=f"Leave Request {action_word.title()}",
            message=f"Your leave from {leave.get('start_date')} to {leave.get('end_date')} has been {action_word}.",
        )

    await write_audit(
        db=db,
        action=f"leave_{new_status}",
        entity_id=leave_id,
        collection="leave_requests",
        changed_by=actor_ctx.user_id,
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes={"status": new_status, "approved_by": actor_ctx.user_id},
    )

    return {"leave": leave, "status": new_status, "leave_id": leave_id}
