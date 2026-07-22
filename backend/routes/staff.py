from __future__ import annotations

from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import get_current_user, require_owner_or_principal, require_role
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from services.actor_context import actor_ctx_from_user
from services.leave_service import (
    decide_leave,
    LeaveValidationError,
    LeaveNotFoundError,
    LeaveConflictError,
)
from services.staff_service import (
    create_staff as create_staff_service,
    update_staff as update_staff_service,
    StaffFieldValidationError,
    StaffValidationError,
    StaffNotFoundError,
    StaffAuthorizationError,
    LinkedUserNotFoundError,
)
from tenant import get_school_id, scoped_filter, scoped_query
from services.auth_tokens import revoke_user_refresh_tokens


router = APIRouter(prefix="/api/staff", tags=["staff"])

ADMIN_ROLES = {"owner", "admin"}
SORT_FIELDS = {
    "name": ("name", 1),
    "staff_type": ("staff_type", 1),
    "department": ("department", 1),
    "created_at": ("created_at", -1),
}
PROFILE_FIELDS = {
    "name",
    "staff_type",
    "employee_id",
    "phone",
    "email",
    "photo_url",
    "qualification",
    "specialization",
    "department",
    "join_date",
    "salary",
    "role",
    "sub_category",
}
LEAVE_BALANCE_FIELDS = {"casual_leave_balance", "medical_leave_balance", "earned_leave_balance"}
# UI-Sweep Story 1.3 — the ONLY fields a person may change on their own record.
# An allow-list, never a deny-list: a deny-list silently admits every field
# someone adds to the schema later.
# Story 1.3, REVISED by the owner 2026-07-22: nobody edits their own record.
#
# The first version let a person correct their own name, phone and email
# directly. The owner reversed that: a person changing their own name or phone
# is itself a way to misuse the account, so a correction must be approved by an
# administrator before it takes effect. The approval flow is planned work
# (Epic 8) and does not exist yet, so the interim state is simply: no
# self-service writes at all. Name, phone and email are changed by the Owner or
# Principal on the staff screen, which they could already do.
#
# This set is deliberately EMPTY rather than deleted — it is the hook the
# approval flow will fill, and its emptiness is asserted by a test so the
# read-only state cannot be lost by accident.
SELF_SERVICE_FIELDS: set = set()

# Epic 8 — what a person may ASK to have corrected. Deliberately the same three
# fields the first version of Story 1.3 let them write directly: the difference
# is that asking changes nothing until an administrator approves it. Anything
# wider here would make the request route a side door around the rule.
REQUESTABLE_FIELDS = {"name", "phone", "email"}


def get_user(req: Request):
    return get_current_user(req)


def _staff_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


def _can_manage(user: dict) -> bool:
    return user.get("role") in ADMIN_ROLES


def _public_staff(staff: dict) -> dict:
    staff = {k: v for k, v in staff.items() if k != "_id"}
    return staff


def _own_profile(staff: dict) -> dict:
    """The self-service view. Salary is dropped here rather than relying on the
    query projection alone — a privacy guarantee should not depend on a database
    option that a caller could later change without noticing what it protected."""
    return {k: v for k, v in _public_staff(staff).items() if k != "salary"}


def _human_list(items) -> str:
    """"name, phone and email" — for a message a person reads, not a log line."""
    items = list(items)
    if len(items) <= 1:
        return items[0] if items else ""
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


async def _notify_reviewers(db, *, message: str, source_id: str) -> None:
    """Tell whoever can decide — the Owner and any Principal — that one is waiting.

    Best-effort by design: a notification that fails to send must not lose the
    request itself. The queue on the staff screen is the source of truth; the
    notification is a nudge towards it.
    """
    try:
        # branch-scope: intentional — a request must reach whoever can decide it,
        # and the Owner and Principal are school-wide rather than per-branch.
        reviewers = await db.staff.find(
            _staff_query({"$or": [{"role": "owner"}, {"sub_category": "principal"}]}),
            {"_id": 0, "salary": 0},
        ).to_list(20)
        seen = set()
        for reviewer in reviewers:
            reviewer_user_id = reviewer.get("user_id")
            if not reviewer_user_id or reviewer_user_id in seen:
                continue
            seen.add(reviewer_user_id)
            await create_notification(
                db,
                user_id=reviewer_user_id,
                notification_type="profile_change_request",
                title="A correction needs your approval",
                message=message,
                source_id=source_id,
                source_type="profile_change_request",
                school_id=get_school_id(),
            )
    except Exception:  # noqa: BLE001 — never lose the request over a notification
        import logging
        logging.getLogger(__name__).warning("profile change request notify failed", exc_info=True)


async def _audit(db, *, action: str, staff_id: str, user: dict, changes: dict | None = None):
    await write_audit_doc(db, {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "entity_type": "staff",
        "entity_id": staff_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_role": user.get("role"),
        "changes": changes or {},
        "created_at": datetime.now().isoformat(),
    }, school_id=get_school_id(), branch_id=user.get("branch_id"))


@router.get("/")
async def list_staff(request: Request, page: int = 1, limit: int = 20, sort: str = "name", include_inactive: bool = False):
    db = get_db()
    user = get_user(request)
    if not _can_manage(user):
        raise HTTPException(403, "Forbidden")

    page = max(1, page)
    per_page = max(1, min(limit, 500))
    query = {} if include_inactive else {"is_active": True}
    sort_field, sort_dir = SORT_FIELDS.get(sort, SORT_FIELDS["name"])
    scoped = _staff_query(query)
    staff = await db.staff.find(scoped, {"_id": 0, "salary": 0}).sort(sort_field, sort_dir).skip((page - 1) * per_page).limit(per_page).to_list(per_page)
    total = await db.staff.count_documents(scoped)
    return {"success": True, "data": staff, "meta": {"page": page, "per_page": per_page, "total": total, "sort": sort}}


@router.post("/")
async def create_staff(request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_manage(user):
        raise HTTPException(403, "Forbidden")

    # Thin adapter over services.staff_service.create_staff — the SAME write path
    # as the AI `create_staff` tool (Story J.2 / AD7). Privileged-field gating and
    # the credential-issued audit live in the service.
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await create_staff_service(db, actor_ctx, body)
    # Story 1.2: the subclass must be caught FIRST or the 400 handler below
    # swallows it and the 422 never fires.
    except StaffFieldValidationError as e:
        raise HTTPException(422, str(e))
    except StaffValidationError as e:
        raise HTTPException(400, str(e))
    except StaffAuthorizationError as e:
        raise HTTPException(403, str(e))
    except LinkedUserNotFoundError as e:
        raise HTTPException(404, str(e))
    data = _public_staff(result["staff"])
    if result.get("temporary_password"):
        data["temporary_password"] = result["temporary_password"]
    return {"success": True, "data": data}


# ── Own profile, read-only (Story 1.3, revised) ──────────────────────────────
# Declared BEFORE "/{staff_id}" — FastAPI matches routes in declaration order,
# so a path parameter registered first would swallow "/me" and a request about
# your own profile would instead ask for the staff member whose id is literally
# "me".


@router.get("/me")
async def get_my_staff_profile(request: Request):
    """The signed-in person's own staff record. No role gate — everyone has a self."""
    db = get_db()
    user = get_user(request)
    staff = await db.staff.find_one(_staff_query({"user_id": user["id"]}), {"_id": 0, "salary": 0})
    if not staff:
        raise HTTPException(404, "No staff record is linked to this account")
    return {"success": True, "data": _own_profile(staff)}


@router.patch("/me")
async def update_my_staff_profile(request: Request):
    """Nobody changes their own record. Refused for everyone, including the Owner.

    Owner's decision, 2026-07-22: a person altering their own name or phone
    number is itself a way to misuse an account, so a correction has to be
    approved by an administrator before it takes effect.

    This route exists rather than being deleted for two reasons. It refuses
    *explicitly* — without it, `PATCH /api/staff/me` would fall through to the
    `/{staff_id}` handler and refuse only as a side effect of there being no
    staff member whose id is "me", which is an accident that a future routing
    change could undo silently. And it is where the approval flow (Epic 8) will
    attach: this handler becomes "record a requested change", not "apply it".
    """
    get_user(request)  # 401 for an unauthenticated caller before anything else
    raise HTTPException(
        403,
        "You cannot change your own details. Ask the Owner or the Principal to "
        "update them for you, or send a request from your profile.",
    )


# ── Epic 8: ask for a correction, an administrator decides ───────────────────
# Also declared before "/{staff_id}" — see the routing note above.


@router.post("/me/change-requests")
async def request_my_profile_change(request: Request):
    """Ask for your own name, phone or email to be corrected. Changes nothing.

    This route must enforce the SAME field rule as the direct edit it replaces.
    If it accepted a wider set, it would be a side door around the very rule it
    exists to serve — a person could not change their own role, but could ask
    for it and have a busy reviewer wave it through.
    """
    db = get_db()
    user = get_user(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Expected a JSON object")

    rejected = sorted(set(body) - REQUESTABLE_FIELDS)
    if rejected:
        raise HTTPException(
            403,
            "You cannot ask to change: %s. Only your name, phone and email can be "
            "corrected this way." % ", ".join(rejected),
        )

    requested = {}
    for field in sorted(set(body) & REQUESTABLE_FIELDS):
        value = body[field]
        if value is not None and not isinstance(value, str):
            raise HTTPException(422, f"{field} must be text")
        value = (value or "").strip()
        if field == "name" and not value:
            raise HTTPException(422, "name cannot be empty")
        requested[field] = value
    if not requested:
        raise HTTPException(400, "Say what you would like corrected")

    staff = await db.staff.find_one(_staff_query({"user_id": user["id"]}), {"_id": 0})
    if not staff:
        raise HTTPException(404, "No staff record is linked to this account")

    changed = {k: v for k, v in requested.items() if (staff.get(k) or "") != v}
    if not changed:
        raise HTTPException(400, "Those are already your recorded details")

    pending = await db.profile_change_requests.find_one(
        _staff_query({"staff_id": staff["id"], "status": "pending"}), {"_id": 0}
    )
    if pending:
        raise HTTPException(
            409,
            "You already have a request waiting to be looked at. It has to be "
            "settled before you can send another.",
        )

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "branch_id": user.get("branch_id"),
        "staff_id": staff["id"],
        "user_id": user["id"],
        "requested_by_name": staff.get("name"),
        # Both sides are stored so a reviewer sees what it is changing FROM
        # without a second lookup, and so the audit trail survives later edits.
        "current": {k: staff.get(k) for k in changed},
        "requested": changed,
        "status": "pending",
        "created_at": now,
    }
    await db.profile_change_requests.insert_one({**doc, "_id": doc["id"]})
    await _audit(db, action="profile_change_requested", staff_id=staff["id"], user=user,
                 changes={k: {"previous": staff.get(k), "new": v} for k, v in changed.items()})
    await _notify_reviewers(
        db,
        message="%s has asked to correct their %s."
                % (staff.get("name") or "A member of staff", _human_list(sorted(changed))),
        source_id=doc["id"],
    )
    return {"success": True, "data": doc}


@router.get("/me/change-requests")
async def get_my_profile_change_requests(request: Request):
    """What I have asked for, and what happened to it."""
    db = get_db()
    user = get_user(request)
    staff = await db.staff.find_one(_staff_query({"user_id": user["id"]}), {"_id": 0})
    if not staff:
        return {"success": True, "data": [], "meta": {"count": 0}}
    items = await db.profile_change_requests.find(
        _staff_query({"staff_id": staff["id"]}), {"_id": 0}
    ).sort("created_at", -1).to_list(20)
    return {"success": True, "data": items, "meta": {"count": len(items)}}


@router.get("/change-requests")
async def list_profile_change_requests(
    request: Request, status: str = "pending", user: dict = Depends(require_owner_or_principal),
):
    """Owner or Principal only — the queue of corrections waiting on a decision."""
    db = get_db()
    if status not in ("pending", "approved", "rejected", "all"):
        raise HTTPException(422, "status must be pending, approved, rejected or all")
    query = {} if status == "all" else {"status": status}
    # branch-scope: intentional — Owner and Principal are school-wide roles and
    # review every branch's requests, exactly as they do pending leaves.
    items = await db.profile_change_requests.find(
        _staff_query(query), {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"success": True, "data": items, "meta": {"count": len(items)}}


@router.patch("/change-requests/{request_id}")
async def decide_profile_change_request(
    request_id: str, request: Request, user: dict = Depends(require_owner_or_principal),
):
    """Approve or reject a requested correction. Only here does anything change."""
    db = get_db()
    body = await request.json()
    decision = (body.get("status") or "").strip().lower()
    if decision not in ("approved", "rejected"):
        raise HTTPException(422, "status must be 'approved' or 'rejected'")

    req = await db.profile_change_requests.find_one(_staff_query({"id": request_id}), {"_id": 0})
    if not req:
        raise HTTPException(404, "Request not found")
    if req.get("status") != "pending":
        raise HTTPException(409, "That request has already been %s" % req.get("status"))

    # A Principal is an administrator, so without this they could raise a
    # request and wave it through themselves — which is precisely the
    # self-editing this whole feature exists to prevent. The Owner decides theirs.
    if req.get("user_id") == user.get("id"):
        raise HTTPException(
            403,
            "You cannot decide your own request. The Owner will look at it.",
        )

    now = datetime.now(timezone.utc).isoformat()
    settled = {
        "status": decision,
        "decided_by": user.get("id"),
        "decided_by_role": user.get("role"),
        "decided_at": now,
        "rejection_reason": (body.get("rejection_reason") or "").strip() or None,
    }

    if decision == "approved":
        staff = await db.staff.find_one(_staff_query({"id": req["staff_id"]}), {"_id": 0})
        if not staff:
            raise HTTPException(404, "That member of staff no longer has a record")
        update = dict(req.get("requested") or {})
        await db.staff.update_one(
            _staff_query({"id": staff["id"]}), {"$set": {**update, "updated_at": now}}
        )
        # The login record carries the name and phone the sign-in token is built
        # from, so an approved correction that skipped it would vanish at the
        # next sign-in.
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
        _staff_query({"id": request_id}), {"$set": settled}
    )
    await _audit(
        db, action=f"profile_change_{decision}", staff_id=req["staff_id"], user=user,
        changes={"request_id": request_id, "requested": req.get("requested")},
    )
    await create_notification(
        db,
        user_id=req.get("user_id"),
        notification_type="profile_change_decision",
        title="Your requested correction was %s" % decision,
        message=("Your details have been updated." if decision == "approved"
                 else "Your requested correction was not approved."
                      + (" Reason: %s" % settled["rejection_reason"] if settled["rejection_reason"] else "")),
        source_id=request_id,
        source_type="profile_change_request",
        school_id=get_school_id(),
    )
    return {"success": True, "data": {**req, **settled}}


@router.get("/{staff_id}")
async def get_staff(staff_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    staff = await db.staff.find_one(_staff_query({"id": staff_id}), {"_id": 0})
    if not staff:
        raise HTTPException(404, "Staff not found")
    if not _can_manage(user) and staff.get("user_id") != user.get("id"):
        raise HTTPException(403, "Forbidden")
    return {"success": True, "data": _public_staff(staff)}


@router.patch("/{staff_id}")
async def update_staff(staff_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_manage(user):
        raise HTTPException(403, "Forbidden")
    # Thin adapter over services.staff_service.update_staff — the SAME write path
    # as the AI `update_staff` tool (Story J.2 / AD7). OWNER_ONLY_FIELDS silent-strip,
    # leave-balance/accounts authority, and the auth_users user_info sync live there.
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await update_staff_service(db, actor_ctx, {**body, "staff_id": staff_id})
    except StaffNotFoundError as e:
        raise HTTPException(404, str(e))
    except StaffAuthorizationError as e:
        raise HTTPException(403, str(e))
    except StaffFieldValidationError as e:
        raise HTTPException(422, str(e))
    except StaffValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": _public_staff(result["staff"])}


@router.delete("/{staff_id}")
async def delete_staff(staff_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_manage(user):
        raise HTTPException(403, "Forbidden")
    staff = await db.staff.find_one(_staff_query({"id": staff_id}), {"_id": 0})
    if not staff:
        raise HTTPException(404, "Staff not found")

    update = {"is_active": False, "deactivated_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}
    await db.staff.update_one(_staff_query({"id": staff_id}), {"$set": update})
    if staff.get("user_id"):
        await db.auth_users.update_one({"id": staff["user_id"]}, {"$set": {"is_active": False}})
        await revoke_user_refresh_tokens(db, staff["user_id"], reason="staff_deactivated")
        # R6.4 (XM5, DPDP §12): when a staff account is retired, erase the AI's
        # learned memories AND skills for that user — the assistant must not retain
        # what it learned about a person who has left. Best-effort, audited inside.
        try:
            from services.memory.store import erase_owner_memories
            from services.memory.skills_store import erase_owner_skills
            from services.memory.feedback_store import erase_owner_feedback

            await erase_owner_memories(
                db, school_id=get_school_id(), user_id=staff["user_id"], changed_by=user.get("id", "system")
            )
            await erase_owner_skills(
                db, school_id=get_school_id(), user_id=staff["user_id"], changed_by=user.get("id", "system")
            )
            # R10.2 AC4: feedback is DPDP-erasable and joins the lifecycle-end path.
            await erase_owner_feedback(
                db, school_id=get_school_id(), user_id=staff["user_id"], changed_by=user.get("id", "system")
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning("ai_memory/skill/feedback erase on staff delete failed", exc_info=True)
    await _audit(db, action="deactivate", staff_id=staff_id, user=user, changes={"is_active": {"previous": staff.get("is_active"), "new": False}})
    return {"success": True}


@router.get("/{staff_id}/leave-requests")
async def get_leave_requests(staff_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    leaves = await db.leave_requests.find(scoped_filter({"staff_id": staff_id}, get_school_id()), {"_id": 0}).to_list(50)
    return {"success": True, "data": leaves}


@router.get("/leaves/my")
async def get_my_leaves(request: Request):
    db = get_db()
    user = get_user(request)
    leaves = await db.leave_requests.find(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0}).sort("applied_at", -1).to_list(20)
    if not leaves:
        staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
        if staff:
            leaves = await db.leave_requests.find(scoped_filter({"staff_id": staff["id"]}, get_school_id()), {"_id": 0}).sort("applied_at", -1).to_list(20)
    return {"success": True, "data": leaves}


@router.get("/leaves/pending")
async def get_pending_leaves(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    leaves = await db.leave_requests.find(scoped_filter({"status": "pending"}, get_school_id()), {"_id": 0}).to_list(50)
    s_ids = list({lr["staff_id"] for lr in leaves if lr.get("staff_id")})
    staff_list = await db.staff.find(scoped_filter({"id": {"$in": s_ids}}, get_school_id()), {"_id": 0, "salary": 0}).to_list(len(s_ids)) if s_ids else []
    staff_map = {s["id"]: s for s in staff_list}
    enriched = [{**lr, "staff": staff_map.get(lr["staff_id"])} for lr in leaves]
    return {"success": True, "data": enriched}


@router.patch("/leaves/{leave_id}")
async def update_leave(leave_id: str, request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    params = {
        "leave_id": leave_id,
        "status": body.get("status"),
        "rejection_reason": body.get("rejection_reason"),
    }
    try:
        result = await decide_leave(db, actor_ctx, params)
    except LeaveValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LeaveConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except LeaveNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"success": True, "status": result["status"]}
