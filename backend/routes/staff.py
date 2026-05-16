from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import get_current_user, hash_password, require_owner_or_principal, require_role
from models.schemas import Staff
from services.audit_service import write_audit_doc, write_audit
from services.notification_service import create_notification
from tenant import get_school_id, scoped_filter, scoped_query


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


def get_user(req: Request):
    return get_current_user(req)


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _staff_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


def _can_manage(user: dict) -> bool:
    return user.get("role") in ADMIN_ROLES


def _is_owner(user: dict) -> bool:
    return user.get("role") == "owner"


def _is_owner_or_principal(user: dict) -> bool:
    return user.get("role") == "owner" or (user.get("role") == "admin" and user.get("sub_category", "principal") == "principal")


def _is_accounts(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") in ("accounts", "accountant")


def _can_set_privileged_fields(user: dict) -> bool:
    return _is_owner(user)


def _default_username(body: dict) -> str:
    source = body.get("username") or body.get("email") or body.get("phone") or body.get("employee_id") or body.get("name", "staff")
    return re.sub(r"[^a-zA-Z0-9._-]+", ".", source.lower()).strip(".")[:48] or f"staff.{uuid.uuid4().hex[:8]}"


def _public_staff(staff: dict) -> dict:
    staff = {k: v for k, v in staff.items() if k != "_id"}
    return staff


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


async def _create_or_link_user(db, body: dict, actor: dict) -> tuple[str, str | None]:
    if body.get("user_id"):
        existing = await db.auth_users.find_one({"id": body["user_id"]}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Linked user account not found")
        return body["user_id"], None

    username = _default_username(body)
    existing = await db.auth_users.find_one({"username_lower": username.lower()}, {"_id": 0})
    if existing:
        return existing["id"], None

    temp_password = body.get("password") or f"EduFlow-{uuid.uuid4().hex[:8]}"
    role = body.get("role") or ("teacher" if body.get("staff_type") == "teacher" else "admin")
    user_id = str(uuid.uuid4())
    await db.auth_users.insert_one({
        "_id": user_id,
        "id": user_id,
        "schoolId": get_school_id(),
        "username": username,
        "username_lower": username.lower(),
        "password_hash": hash_password(temp_password),
        "is_active": True,
        "user_info": {
            "id": user_id,
            "role": role,
            "name": body.get("name"),
            "phone": body.get("phone"),
            "sub_category": body.get("sub_category"),
        },
        "created_by": actor.get("id"),
        "created_at": datetime.now().isoformat(),
    })
    return user_id, temp_password


@router.get("/")
async def list_staff(request: Request, page: int = 1, limit: int = 20, sort: str = "name", include_inactive: bool = False):
    db = get_db()
    user = get_user(request)
    if not _can_manage(user):
        raise HTTPException(403, "Forbidden")

    page = max(1, page)
    per_page = max(1, min(limit, 20))
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

    body = await request.json()
    if not body.get("name") or not body.get("staff_type"):
        raise HTTPException(400, "name and staff_type are required")
    requested_role = body.get("role") or ("teacher" if body.get("staff_type") == "teacher" else "admin")
    requested_sub = body.get("sub_category")
    if not _can_set_privileged_fields(user) and (requested_role in {"owner", "admin"} or requested_sub):
        raise HTTPException(403, "Only owner can create privileged staff accounts")

    user_id, temp_password = await _create_or_link_user(db, body, user)
    staff = Staff(
        user_id=user_id,
        name=body["name"],
        staff_type=body["staff_type"],
        employee_id=body.get("employee_id"),
        phone=body.get("phone"),
        email=body.get("email"),
        qualification=body.get("qualification"),
        specialization=body.get("specialization"),
        department=body.get("department"),
        join_date=body.get("join_date"),
        salary=body.get("salary"),
        casual_leave_balance=body.get("casual_leave_balance", 12),
        medical_leave_balance=body.get("medical_leave_balance", 10),
        earned_leave_balance=body.get("earned_leave_balance", 15),
    )
    staff_doc = {**_serialize(staff), "role": requested_role, "sub_category": requested_sub}
    await db.staff.insert_one({**staff_doc, "_id": staff.id})
    await _audit(db, action="create", staff_id=staff.id, user=user, changes={"created": staff_doc})
    if temp_password:
        # security: intentional — first-time credential delivery, no other channel.
        # Password is returned once in plaintext so the creating admin can hand it to the
        # new staff member. It is hashed in auth_users and is never stored or logged elsewhere.
        await write_audit(
            db=db,
            action="credential_issued",
            entity_id=staff.id,
            collection="staff",
            changed_by=user.get("id"),
            changed_by_role=user.get("role", ""),
            school_id=get_school_id(),
            branch_id=user.get("branch_id", ""),
            changes={"credential_type": "temporary_password", "issued_to_staff_id": staff.id},
        )
    data = _public_staff(staff_doc)
    if temp_password:
        data["temporary_password"] = temp_password
    return {"success": True, "data": data}


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
    existing = await db.staff.find_one(_staff_query({"id": staff_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Staff not found")

    body = await request.json()
    allowed = set(PROFILE_FIELDS)
    if not _can_set_privileged_fields(user):
        allowed -= {"role", "sub_category", "salary"}
    if _is_owner_or_principal(user):
        allowed |= LEAVE_BALANCE_FIELDS
    if _is_accounts(user) and not _is_owner(user):
        allowed |= {"salary"}
    if not _is_owner_or_principal(user) and any(field in body for field in LEAVE_BALANCE_FIELDS):
        raise HTTPException(403, "Forbidden")
    # Note: role, sub_category, salary are handled by OWNER_ONLY_FIELDS silent-strip below (EC-9.4)
    # Non-owner callers who send these fields have them silently removed — no 403

    update = {k: v for k, v in body.items() if k in allowed}

    # EC-9.4: OWNER_ONLY_FIELDS — principals cannot change role, sub_category, salary, or is_active.
    # Applies to ALL updates including self-updates (staff_id == user['id'] is NOT exempt).
    OWNER_ONLY_FIELDS = {"role", "sub_category", "salary", "is_active"}
    body_had_owner_only = any(f in body for f in OWNER_ONLY_FIELDS)
    if user.get("role") != "owner":
        for field in OWNER_ONLY_FIELDS:
            update.pop(field, None)  # silent strip — EC-9.4

    if not update:
        # All submitted fields were owner-only and silently stripped — return no-op success.
        if body_had_owner_only and user.get("role") != "owner":
            return {"success": True, "data": existing}
        raise HTTPException(400, "No updatable fields provided")
    update["updated_at"] = datetime.now().isoformat()
    changes = {k: {"previous": existing.get(k), "new": v} for k, v in update.items() if k != "updated_at" and existing.get(k) != v}
    if not changes:
        return {"success": True, "data": existing}

    await db.staff.update_one(_staff_query({"id": staff_id}), {"$set": update})
    if existing.get("user_id") and any(k in update for k in {"name", "phone", "role", "sub_category"}):
        user_info = {
            **(await db.auth_users.find_one({"id": existing["user_id"]}, {"_id": 0}) or {}).get("user_info", {}),
            "id": existing["user_id"],
            "name": update.get("name", existing.get("name")),
            "phone": update.get("phone", existing.get("phone")),
            "role": update.get("role", existing.get("role")),
            "sub_category": update.get("sub_category", existing.get("sub_category")),
        }
        await db.auth_users.update_one({"id": existing["user_id"]}, {"$set": {"user_info": user_info}})
    await _audit(db, action="update", staff_id=staff_id, user=user, changes=changes)
    updated = await db.staff.find_one(_staff_query({"id": staff_id}), {"_id": 0})
    return {"success": True, "data": _public_staff(updated)}


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
        await db.refresh_tokens.update_many({"user_id": staff["user_id"], "revoked": False}, {"$set": {"revoked": True, "revoked_at": datetime.now().isoformat()}})
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
    new_status = body.get("status")
    if new_status not in {"approved", "rejected"}:
        raise HTTPException(400, "status must be approved or rejected")

    # EC-9.3: Idempotency guard — only update if still pending.
    # Prevents double-approval creating duplicate notifications and audit entries.
    set_fields: dict = {
        "status": new_status,
        "approved_by": user["id"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    if new_status == "rejected" and not body.get("rejection_reason"):
        raise HTTPException(400, "rejection_reason is required when rejecting leave")
    if body.get("rejection_reason"):
        set_fields["rejection_reason"] = body["rejection_reason"]

    result = await db.leave_requests.update_one(
        scoped_query({"id": leave_id, "status": "pending"}, branch_id=user.get("branch_id")),
        {"$set": set_fields},
    )

    if result.matched_count == 0:
        # Either already approved/rejected, or not found — distinguish the two cases.
        existing = await db.leave_requests.find_one(
            scoped_query({"id": leave_id}, branch_id=user.get("branch_id"))
        )
        if existing and existing.get("status") != "pending":
            raise HTTPException(status_code=409, detail=f"Leave already {existing['status']}")
        raise HTTPException(status_code=404, detail="Leave request not found")

    # Fetch the updated leave request for notification details.
    leave = await db.leave_requests.find_one(
        scoped_query({"id": leave_id}, branch_id=user.get("branch_id"))
    )

    # Notify the staff member.
    if leave and leave.get("user_id"):
        action_word = "approved" if new_status == "approved" else "rejected"
        await create_notification(
            db=db,
            user_id=leave["user_id"],
            notification_type="leave_decision",
            title=f"Leave Request {action_word.title()}",
            message=f"Your leave from {leave.get('start_date')} to {leave.get('end_date')} has been {action_word}.",
        )

    # Audit trail.
    await write_audit(
        db=db,
        action=f"leave_{new_status}",
        entity_id=leave_id,
        collection="leave_requests",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"status": new_status, "approved_by": user["id"]},
    )

    return {"success": True, "status": new_status}
