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
# Everything else — role, sub_category, school, salary, token allowance — is
# read-only here. Authority changes happen on the staff screen (Stories
# 1.1/1.2) so there is exactly one place where a person's permissions can move.
SELF_SERVICE_FIELDS = {"name", "phone", "email"}


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


# ── Self-service profile (Story 1.3) ─────────────────────────────────────────
# Declared BEFORE "/{staff_id}" — FastAPI matches routes in declaration order,
# so a path parameter registered first would swallow "/me" and a person editing
# their own details would instead be asking for the staff member whose id is
# literally "me".


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
    """Correct your own name, phone and email — and nothing else.

    A request carrying any other field is refused OUTRIGHT rather than partially
    applied. Saving the name while quietly dropping `role` would tell the caller
    exactly where the boundary sits and leave them believing the rest went
    through; both are worse than a clear refusal.
    """
    db = get_db()
    user = get_user(request)
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "Expected a JSON object")

    rejected = sorted(set(body) - SELF_SERVICE_FIELDS)
    if rejected:
        raise HTTPException(
            403,
            "These details cannot be changed from your own profile: %s. "
            "Ask the Owner to change them from the staff screen." % ", ".join(rejected),
        )

    update = {}
    for field in sorted(set(body) & SELF_SERVICE_FIELDS):
        value = body[field]
        if value is not None and not isinstance(value, str):
            raise HTTPException(422, f"{field} must be text")
        value = value.strip() if isinstance(value, str) else value
        if field == "name" and not value:
            raise HTTPException(422, "name cannot be empty")
        update[field] = value
    if not update:
        raise HTTPException(400, "No changes provided")

    staff = await db.staff.find_one(_staff_query({"user_id": user["id"]}), {"_id": 0})
    if not staff:
        raise HTTPException(404, "No staff record is linked to this account")

    changes = {k: {"previous": staff.get(k), "new": v} for k, v in update.items() if staff.get(k) != v}
    if not changes:
        return {"success": True, "data": _own_profile(staff)}

    await db.staff.update_one(
        _staff_query({"id": staff["id"]}),
        {"$set": {**update, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )

    # The signed-in session carries the person's name and phone, and that token
    # is not reissued until the next sign-in. Write the same values onto the
    # login record so the correction survives signing out and back in.
    if staff.get("user_id") and ({"name", "phone"} & set(update)):
        auth_user = await db.auth_users.find_one({"id": staff["user_id"]}, {"_id": 0})
        if auth_user:
            user_info = {**(auth_user.get("user_info") or {}), "id": staff["user_id"]}
            for field in ("name", "phone"):
                if field in update:
                    user_info[field] = update[field]
            await db.auth_users.update_one({"id": staff["user_id"]}, {"$set": {"user_info": user_info}})

    await _audit(db, action="self_update", staff_id=staff["id"], user=user, changes=changes)
    updated = await db.staff.find_one(_staff_query({"id": staff["id"]}), {"_id": 0, "salary": 0})
    return {"success": True, "data": _own_profile(updated)}


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
