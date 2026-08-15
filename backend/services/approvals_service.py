"""Approval-request decision service - the single shared write path for deciding
an approval request (AI Layer Hardening, AD7 / Epic A, Story A.3).

Both `PATCH /api/operations/approval-requests/{id}/decide` (REST) and the AI
`decide_approval_request` tool call `decide_approval_request(...)`.

**Parity decision (case-by-case, canonical = REST):**
- The REST route's authorization is *record-level and routing-dependent*: it uses
  `Depends(get_current_user)` (no static role gate) and decides authz from the loaded
  record - owner may decide ANY request; a principal may decide ONLY `owner_and_principal`
  routings; anyone else is forbidden. The old AI tool **dropped this check** (a P6 comment
  claimed the registry gate covers it, but `_is_tool_authorized` can't see `approval.routing`,
  so an admin-accountant or a principal could decide an `owner_only` request via chat - a real
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

from services.txn_context import session_kwargs as _txn_session_kwargs

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


# ── R3-2, 2026-08-15: an approval that actually DOES the thing ────────────────
#
# Abhimanyu's decision: the transport head may delete a route, a vehicle, a driver or a
# conductor, and it needs Aman OR Adesh to agree first. Either one, not both.
#
# The obvious cheap version is "refuse him, and raise a request for somebody else to go
# and do it by hand". That was rejected. It produces an approval card that says APPROVED
# while nothing has been deleted, and somebody has to remember to go and finish it. A
# control that reports success without acting is the exact fault this platform keeps
# finding in itself.
#
# So an approval request may CARRY the action, and approving it performs the action in the
# same call. Rejecting performs nothing. The shape follows R2-9's certificate approval,
# where the record is created pending and the decision flips it, rather than inventing a
# second approval system.
#
# Registered rather than hard-coded so that the next thing needing an approval adds one
# entry here instead of another branch inside the decision.


class PendingActionError(ApprovalError):
    """The approved action could not be carried out → HTTP 409."""


async def _do_delete_transport_route(db, actor_ctx, payload, session=None):
    from services.transport_service import delete_route as _delete_route

    return await _delete_route(
        db, actor_ctx, {"route_id": payload.get("route_id")},
        session=session, _approved=True,
    )


async def _do_delete_vehicle(db, actor_ctx, payload, session=None):
    from services.transport_service import delete_vehicle as _delete_vehicle

    return await _delete_vehicle(
        db, actor_ctx, {"vehicle_id": payload.get("vehicle_id")},
        session=session, _approved=True,
    )


async def _do_remove_staff_member(db, actor_ctx, payload, session=None):
    """Take a driver or conductor off the roll, once Aman or Adesh has agreed.

    R3-2, 2026-08-15. Goes through `staff_service.delete_staff` rather than writing
    `is_active: False` itself, and that is the whole point of it.

    A first version did write the flag directly. It looked equivalent and was not: the
    real path also closes the login, revokes any refresh token so an open session cannot
    outlive the decision, records the leaving state properly so `set_enrolment_state` can
    put them back, and erases what the assistant had learned about them (R6.4, DPDP §12).
    Writing the flag would have left a colleague who is off the roll on every screen and
    still able to use a session that was already open.

    `_approved` is how the service knows Aman or Adesh has already agreed, so it carries
    the removal out instead of asking again.
    """
    staff_id = payload.get("staff_id")
    from services.staff_service import (
        delete_staff as _delete_staff,
        StaffNotFoundError as _StaffNotFound,
    )

    try:
        result = await _delete_staff(
            db, actor_ctx, {"staff_id": staff_id, "_approved": True}, session=session,
        )
    except _StaffNotFound:
        raise PendingActionError("That colleague is no longer on the roll.")
    return {"staff_id": staff_id, "removed": not result.get("noop", False)}


async def _do_agree_a_repair_cost(db, actor_ctx, payload, session=None):
    """Agree what a vehicle repair may cost, BEFORE the money is committed.

    Abhimanyu, 2026-08-15: the transport head arranges the servicing and sees what it
    costs, and Aman or Adesh agrees the figure first. So the amount sits on the request
    as a proposal until one of them says yes, and only then becomes the approved cost.
    """
    request_id = payload.get("request_id")
    amount = payload.get("estimated_cost")
    result = await db.facility_requests.update_one(
        scoped_filter({"id": request_id}, actor_ctx.school_id),
        {"$set": {
            "estimated_cost": amount,
            "cost_approved_by": actor_ctx.user_id,
            "cost_approved_at": actor_ctx.now_iso(),
            "cost_awaiting_approval": None,
        }},
        **_txn_session_kwargs(session),
    )
    if getattr(result, "matched_count", 0) == 0:
        raise PendingActionError("That repair request no longer exists.")
    return {"request_id": request_id, "estimated_cost": amount}


# In ordinary words, what pressing Approve will actually do. Written per action rather
# than as one generic sentence, because "the route is deleted" and "the money is committed"
# are different things to be agreeing to.
_WHAT_APPROVING_DOES = {
    "delete_transport_route": (
        "Agreeing to this DELETES the bus route straight away. Nothing else has to be done."
    ),
    "delete_transport_vehicle": (
        "Agreeing to this REMOVES the vehicle from the register straight away. Nothing "
        "else has to be done."
    ),
    "remove_staff_member": (
        "Agreeing to this takes the colleague OFF the roll straight away. Their attendance "
        "and pay history are kept."
    ),
    "agree_a_repair_cost": (
        "Agreeing to this COMMITS the school to that amount for the repair. The accountant "
        "head pays it."
    ),
}

PENDING_ACTIONS = {
    "delete_transport_route": _do_delete_transport_route,
    "delete_transport_vehicle": _do_delete_vehicle,
    "remove_staff_member": _do_remove_staff_member,
    "agree_a_repair_cost": _do_agree_a_repair_cost,
}


async def create_approval_request_doc(
    db,
    actor_ctx: ActorContext,
    *,
    title: str,
    description: str,
    estimated_impact: str,
    note: str,
    routing: str = "owner_and_principal",
    pending_action: Optional[dict] = None,
    session=None,
) -> str:
    """Record a request for Aman or Adesh to decide, and return its id.

    R3-2, 2026-08-15. The REST route `POST /api/operations/approval-requests` builds this
    same record inline. This function exists so a SERVICE can raise one too, without the
    transport service growing its own idea of what an approval request looks like. The
    route keeps its own copy for now; if a third caller appears, the route should move
    onto this instead of a third copy being written.
    """
    approval_id = str(uuid.uuid4())
    record = {
        "_id": approval_id,
        "id": approval_id,
        "schoolId": actor_ctx.school_id,
        "title": title,
        "description": description,
        "estimated_impact": estimated_impact,
        "note": note,
        "routing": routing,
        "status": "pending",
        "submitted_by": actor_ctx.user_id,
        "submitted_at": actor_ctx.now_iso(),
        "unread_for": ["owner"] + (["principal"] if routing == "owner_and_principal" else []),
    }
    if pending_action:
        record["pending_action"] = pending_action
        # R3-2, 2026-08-15 (Abhimanyu). Say out loud that agreeing to this DOES the thing.
        #
        # Without it the card reads like every other request: a description and two
        # buttons. Aman would press Approve believing he was recording an opinion, and a
        # bus route would disappear. A person has to be able to tell "I agree with this"
        # from "carry this out", and the platform is the only thing that knows which one
        # the button is.
        record["approval_carries_out_the_action"] = True
        record["what_approving_does"] = _WHAT_APPROVING_DOES.get(
            pending_action.get("kind"),
            "Agreeing to this carries it out straight away.",
        )
    await db.approval_requests.insert_one(record, **_txn_session_kwargs(session))

    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "approval_request",
            "entity_id": approval_id,
            "action": "approval_submit",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"created": {k: v for k, v in record.items() if k != "_id"}},
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )

    # Both are notified, because either may decide it.
    targets = await db.users.find(
        scoped_filter({"role": "owner"}, actor_ctx.school_id), {"_id": 0, "id": 1}
    ).to_list(5)
    if routing == "owner_and_principal":
        targets += await db.users.find(
            scoped_filter({"role": "admin", "sub_category": "principal"}, actor_ctx.school_id),
            {"_id": 0, "id": 1},
        ).to_list(5)
    for target in targets:
        await create_notification(
            db,
            user_id=target.get("id"),
            notification_type="approval_submitted",
            title="Approval needed",
            message=title,
            source_id=approval_id,
            source_type="approval_request",
        )
    return approval_id


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


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

    # branch-scope: intentional - approval_requests are school-wide (routed to owner/principal).
    approval = await db.approval_requests.find_one(
        scoped_filter({"id": approval_id}, actor_ctx.school_id), {"_id": 0}
    )
    if not approval:
        raise ApprovalNotFoundError("Approval request not found")

    # Record-level (routing-dependent) authorization - identical for both entrypoints.
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

    # R3-2, 2026-08-15: a request may carry the action it is asking for, and approving it
    # CARRIES THAT ACTION OUT. See PENDING_ACTIONS above for why it works this way rather
    # than leaving somebody to go and finish the job by hand.
    #
    # Done BEFORE the request is marked approved, deliberately. If the action fails - the
    # route was already deleted, children are still assigned to it - the request stays
    # pending and the person is told why, rather than being shown APPROVED over something
    # that never happened.
    pending = approval.get("pending_action") if status == "approved" else None
    action_result = None
    if pending:
        handler = PENDING_ACTIONS.get(pending.get("kind"))
        if not handler:
            raise PendingActionError(
                f"This request asks for '{pending.get('kind')}', which this platform no "
                "longer knows how to carry out. Nothing has been changed."
            )
        action_result = await handler(db, actor_ctx, pending, session=session)
        update["pending_action_result"] = action_result
        update["pending_action_done_at"] = actor_ctx.now_iso()

    await db.approval_requests.update_one(
        # branch-scope: intentional - approval_requests are school-wide (routed to owner/principal).
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

    # branch-scope: intentional - approval_requests are school-wide (routed to owner/principal).
    updated = await db.approval_requests.find_one(
        scoped_filter({"id": approval_id}, actor_ctx.school_id), {"_id": 0}
    )
    return {"approval": updated, "status": status, "approval_id": approval_id}
