"""Approval-request decision service — the single shared write path for deciding
an approval request (AI Layer Hardening, AD7 / Epic A, Story A.3).

Both `PATCH /api/operations/approval-requests/{id}/decide` (REST) and the AI
`decide_approval_request` tool call `decide_approval_request(...)`.

**Parity decision (case-by-case, canonical = REST):**
- The REST route's authorization is *record-level and routing-dependent*: it uses
  `Depends(get_current_user)` (no static role gate) and decides authz from the loaded
  record — owner may decide ANY request; a principal may decide ONLY `owner_and_principal`
  routings; anyone else is forbidden. The old AI tool **dropped this check** (a P6 comment
  claimed the registry gate covers it, but `_is_tool_authorized` can't see `approval.routing`,
  so an admin-accountant or a principal could decide an `owner_only` request via chat — a real
  hole). The check is centralized here so BOTH entrypoints enforce it identically. (Static
  role/sub_category authz still lives in the adapters per architecture P2; this is the
  dynamic, record-dependent gate that was already a route body check.)
- Audit is canonicalized to the REST shape: action `approval_decide`, entity_type
  `approval_request` (the AI tool wrote `decide_approval_request`/`approval_requests`).
- `approval_requests` are intentionally school-wide (routed to owner/principal); the AI tool's
  branch-narrowing `scoped_query` is corrected to the route's school-wide `scoped_filter`.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from tenant import scoped_filter


class ApprovalError(Exception):
    """Base class for approval-decision domain errors."""


class ApprovalValidationError(ApprovalError):
    """Invalid input (bad status / missing reason) → HTTP 400."""


class ApprovalNotFoundError(ApprovalError):
    """Approval request not found → HTTP 404."""


class ApprovalAuthorizationError(ApprovalError):
    """Actor not permitted to decide this routing → HTTP 403."""


def _session_kwargs(session) -> dict:
    return {"session": session} if session is not None else {}


async def decide_approval_request(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Approve or reject a routed approval request.

    params: ``{"approval_id": str, "status": "approved"|"rejected", "reason": str}``
    returns: ``{"approval": <updated doc>, "status": str, "approval_id": str}``
    """
    approval_id = params.get("approval_id")
    status = params.get("status")
    reason = params.get("reason")

    # Validation order mirrors the REST route exactly (400 before 404 before 403).
    if status not in ("approved", "rejected") or not reason:
        raise ApprovalValidationError("status approved/rejected and reason are required")
    if not approval_id:
        raise ApprovalValidationError("approval_id is required")

    # branch-scope: intentional — approval_requests are school-wide (routed to owner/principal).
    approval = await db.approval_requests.find_one(
        scoped_filter({"id": approval_id}, actor_ctx.school_id), {"_id": 0}
    )
    if not approval:
        raise ApprovalNotFoundError("Approval request not found")

    # Record-level (routing-dependent) authorization — identical for both entrypoints.
    is_principal = actor_ctx.role == "admin" and actor_ctx.sub_category == "principal"
    if actor_ctx.role != "owner" and not (is_principal and approval.get("routing") == "owner_and_principal"):
        raise ApprovalAuthorizationError("Forbidden")

    update = {
        "status": status,
        "decision_reason": reason,
        "decided_by": actor_ctx.user_id,
        "decided_at": actor_ctx.now_iso(),
        "unread_for": [],
    }
    await db.approval_requests.update_one(
        # branch-scope: intentional — approval_requests are school-wide (routed to owner/principal).
        scoped_filter({"id": approval_id}, actor_ctx.school_id),
        {"$set": update},
        **_session_kwargs(session),
    )

    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "approval_request",
            "entity_id": approval_id,
            "action": "approval_decide",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": update,
            "reason": reason,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )

    await create_notification(
        db,
        user_id=approval.get("submitted_by"),
        notification_type="approval_decision",
        title="Approval decision",
        message=f"{approval.get('title', 'Approval request')} {status}",
        source_id=approval_id,
        source_type="approval_request",
    )

    # branch-scope: intentional — approval_requests are school-wide (routed to owner/principal).
    updated = await db.approval_requests.find_one(
        scoped_filter({"id": approval_id}, actor_ctx.school_id), {"_id": 0}
    )
    return {"approval": updated, "status": status, "approval_id": approval_id}
