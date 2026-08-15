"""Leave-decision domain service - the single shared write path for approving or
rejecting a staff leave request (AI Layer Hardening, AD7 / Epic A, Story A.2).

`PATCH /api/staff/leaves/{id}` (REST), the AI `approve_leave` tool and the shared
approvals queue all call `decide_leave_request(...)`, so a decision taken in chat, on
the staff screen or in the approvals queue is the same decision: the same pending-only
guard, the same staff notification, the same audit row, and the same record of the
person being away.

**Parity decision (case-by-case, canonical = REST):** the old AI `tool_approve_leave`
silently diverged - it wrote no notification, no audit, no pending-only guard, did
not require a rejection reason, and stamped a local (not UTC) `approved_at`. All of
those are corrected to match the REST route, which is the complete/correct path.

Services raise domain exceptions, never `HTTPException`. The REST adapter maps them
to 400/404/409; the AI adapter maps them to `{success: False, error}`.

── THE TWO PATHS ARE NOW ONE (2026-08-15) ────────────────────────────────────────

There used to be two decision paths on `leave_requests` and they did different things.
`decide_leave` wrote `approved_by` and nothing else. The function below also marks the
person unavailable in `staff_availability`, and **without that row a colleague who has
been given leave still reads as available on every screen that asks** - so the staff
screen could approve somebody's leave and the school would carry on rostering them.

They are merged, and the one that marks the person away is the one that survives, by
Abhimanyu's instruction of 2026-08-15. `decide_leave` is gone; every caller was
repointed here rather than left to choose.

**What was carried across from the deleted one, because losing it would have been a
silent regression rather than a merge:**

* the pending-only guard, so a second decision on the same request raises rather than
  quietly overwriting the first one and sending the person a second notification
* the old field names are STILL WRITTEN alongside the new ones (`approved_by` beside
  `decided_by`, `rejection_reason` beside `decision_reason`). Screens, exports and the
  approvals card all read the old names on rows written before today, and a merge that
  stopped writing them would have made every future row look undecided to them
* a reason is required to REFUSE and not to approve, which is the gentler of the two
  rules and the one every other kind of approval on this platform uses
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

from typing import Optional

from services.actor_context import ActorContext
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
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


async def decide_leave_request(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Approve or reject a staff leave request, and record the person as away.

    The ONE decision path on `leave_requests`, called by the staff screen, by Flo's
    `approve_leave` tool and by the shared approvals queue alike. See the merge note in
    the module docstring for what was folded in and why.

    params: ``{"leave_id": str, "status": "approved"|"rejected",
    "reason"|"rejection_reason"?: str}``

    Raises the domain errors above; the caller maps them to HTTP. Authorization is the
    CALLER's job and has not moved: every entrance is owner-or-principal exactly as it
    was before the merge.
    """
    import uuid as _uuid

    from services.audit_service import write_audit_doc
    from tenant import get_school_id, scoped_filter

    leave_id = params.get("leave_id")
    status = params.get("status")
    # Both names are accepted. The staff screen and Flo have always said
    # `rejection_reason`; the approvals queue says `reason`. Making one of them the only
    # spelling would have silently dropped the other caller's reason on the floor, and a
    # refusal with no reason is the one thing every kind of approval here forbids.
    reason = params.get("reason") or params.get("rejection_reason") or ""
    if not leave_id:
        raise LeaveValidationError("leave_id is required")
    if status not in ("approved", "rejected"):
        raise LeaveValidationError("status must be approved or rejected")
    if status == "rejected" and not reason:
        raise LeaveValidationError("rejection_reason is required when rejecting leave")

    school_id = actor_ctx.school_id or get_school_id()

    now = actor_ctx.now_iso()
    update = {
        "status": status,
        "decision_reason": reason,
        "decided_by": actor_ctx.user_id,
        "decided_at": now,
        # The names the deleted path wrote. Still written, because screens, exports and
        # the approvals card read them on every row recorded before today; dropping them
        # would make each new decision look undecided to all of those.
        "approved_by": actor_ctx.user_id,
        "approved_at": actor_ctx.now_utc_iso(),
    }
    if reason:
        update["rejection_reason"] = reason

    # Pending-only guard, carried across from the deleted path. Without it a second
    # decision quietly overwrites the first and sends the person a second notification
    # saying the opposite of the first.
    # Branch-scoped, exactly as the deleted path was. This is NOT belt-and-braces on a
    # unique id: it is what stops one branch's principal deciding another branch's leave,
    # and there is a test that proves it. The surviving path filtered on the school only,
    # so merging without this would have quietly dropped that isolation.
    result = await db.leave_requests.update_one(
        scoped_query({"id": leave_id, "status": "pending"}, branch_id=actor_ctx.branch_id),
        {"$set": update},
        **_session_kwargs(session),
    )
    if getattr(result, "matched_count", 0) == 0:
        existing = await db.leave_requests.find_one(
            scoped_query({"id": leave_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
        )
        if existing and existing.get("status") != "pending":
            raise LeaveConflictError(f"Leave already {existing['status']}")
        raise LeaveNotFoundError("Leave request not found")

    leave = await db.leave_requests.find_one(
        scoped_query({"id": leave_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    ) or {}
    if status == "approved":
        await db.staff_availability.update_one(
            # branch-scope: intentional - scoped to one named person's own record.
            scoped_filter(
                {"staff_id": leave.get("staff_id"), "leave_request_id": leave_id}, school_id
            ),
            {"$set": {
                "staff_id": leave.get("staff_id"),
                "leave_request_id": leave_id,
                "status": "on_leave",
                "date_range": leave.get("date_range"),
                "schoolId": school_id,
                "updated_at": now,
            }},
            upsert=True,
            **_session_kwargs(session),
        )

    await write_audit_doc(
        db,
        {
            "_id": str(_uuid.uuid4()),
            "id": str(_uuid.uuid4()),
            "schoolId": school_id,
            "entity_type": "leave_request",
            "entity_id": leave_id,
            # `leave_approved` / `leave_rejected`, which is the deleted path's name and
            # the more useful of the two: the surviving path wrote `leave_decide`, so
            # the action log could not tell an approval from a refusal without opening
            # the row. Nothing read `leave_decide`; checked before changing it.
            "action": f"leave_{status}",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": update,
            "reason": reason,
            "created_at": now,
        },
        school_id=school_id,
        branch_id=actor_ctx.branch_id,
    )
    # Guarded, and worded with the dates in it. Both carried across from the deleted
    # path: a notification addressed to nobody used to be written on a request with no
    # user on it, and "Leave request approved" with no dates makes somebody go and look
    # the request up to find out which one it was.
    if leave.get("user_id"):
        await create_notification(
            db,
            user_id=leave["user_id"],
            notification_type="leave_decision",
            title=f"Leave request {status}",
            message=(
                f"Your leave from {leave.get('start_date')} to {leave.get('end_date')} "
                f"has been {status}."
                if leave.get("start_date") else f"Your leave request was {status}."
            ),
            source_id=leave_id,
            source_type="leave_request",
        )
    updated = await db.leave_requests.find_one(
        scoped_query({"id": leave_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    return {"leave": updated, "status": status, "leave_id": leave_id}
