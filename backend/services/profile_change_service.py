"""Deciding a staff member's requested correction to their own details.

Approvals workflow, 2026-08-15. The whole of this lived in the body of
`PATCH /api/staff/change-requests/{id}`. It moved here so the shared approvals queue
decides a profile change through exactly this code rather than a second copy of it,
which is the only way the screen and the queue can be guaranteed to do the same thing.

**Nothing about who may decide has moved.** Both entrances are owner-or-principal, and
the one rule that lives with the record rather than with the route - that nobody may
wave through their own request - is enforced here, so it now covers both.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from tenant import get_school_id, scoped_filter


class ProfileChangeError(Exception):
    """Base class for profile-change decision errors."""


class ProfileChangeValidationError(ProfileChangeError):
    """Bad decision value -> HTTP 422."""


class ProfileChangeNotFoundError(ProfileChangeError):
    """No such request, or the colleague is gone -> HTTP 404."""


class ProfileChangeConflictError(ProfileChangeError):
    """Already decided -> HTTP 409."""


class ProfileChangeAuthorizationError(ProfileChangeError):
    """Deciding your own request -> HTTP 403."""


def _query(school_id: str, extra: dict | None = None) -> dict:
    # branch-scope: intentional - owner and principal are school-wide roles and review
    # every branch's requests, exactly as they do pending leaves.
    return scoped_filter(extra or {}, school_id)


async def decide_profile_change(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Approve or reject a requested correction. Only here does anything change.

    params: ``{"request_id": str, "status": "approved"|"rejected",
               "rejection_reason"?: str}``
    """
    request_id = params.get("request_id")
    decision = (params.get("status") or "").strip().lower()
    if decision not in ("approved", "rejected"):
        raise ProfileChangeValidationError("status must be 'approved' or 'rejected'")

    school_id = actor_ctx.school_id or get_school_id()
    req = await db.profile_change_requests.find_one(
        _query(school_id, {"id": request_id}), {"_id": 0}
    )
    if not req:
        raise ProfileChangeNotFoundError("Request not found")
    if req.get("status") != "pending":
        raise ProfileChangeConflictError(
            "That request has already been %s" % req.get("status")
        )

    # A principal is an administrator, so without this they could raise a request and
    # wave it through themselves - which is precisely the self-editing this whole
    # feature exists to prevent. The owner decides theirs.
    if req.get("user_id") == actor_ctx.user_id:
        raise ProfileChangeAuthorizationError(
            "You cannot decide your own request. The Owner will look at it."
        )

    now = datetime.now(timezone.utc).isoformat()
    settled = {
        "status": decision,
        "decided_by": actor_ctx.user_id,
        "decided_by_role": actor_ctx.role,
        "decided_at": now,
        "rejection_reason": (params.get("rejection_reason") or "").strip() or None,
    }

    if decision == "approved":
        staff = await db.staff.find_one(_query(school_id, {"id": req["staff_id"]}), {"_id": 0})
        if not staff:
            raise ProfileChangeNotFoundError("That member of staff no longer has a record")
        update = dict(req.get("requested") or {})
        await db.staff.update_one(
            _query(school_id, {"id": staff["id"]}), {"$set": {**update, "updated_at": now}}
        )
        # The login record carries the name and phone the sign-in token is built from,
        # so an approved correction that skipped it would vanish at the next sign-in.
        if staff.get("user_id") and ({"name", "phone"} & set(update)):
            auth_user = await db.auth_users.find_one({"id": staff["user_id"]}, {"_id": 0})
            if auth_user:
                user_info = {**(auth_user.get("user_info") or {}), "id": staff["user_id"]}
                for field in ("name", "phone"):
                    if field in update:
                        user_info[field] = update[field]
                await db.auth_users.update_one(
                    {"id": staff["user_id"]}, {"$set": {"user_info": user_info}}
                )

    await db.profile_change_requests.update_one(
        _query(school_id, {"id": request_id}), {"$set": settled}
    )
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "staff",
            "entity_id": req["staff_id"],
            "action": f"profile_change_{decision}",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"request_id": request_id, "requested": req.get("requested")},
            "created_at": datetime.now().isoformat(),
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )
    await create_notification(
        db,
        user_id=req.get("user_id"),
        notification_type="profile_change_decision",
        title="Your requested correction was %s" % decision,
        message=("Your details have been updated." if decision == "approved"
                 else "Your requested correction was not approved."
                      + (" Reason: %s" % settled["rejection_reason"]
                         if settled["rejection_reason"] else "")),
        source_id=request_id,
        source_type="profile_change_request",
        school_id=school_id,
    )
    return {**req, **settled}
