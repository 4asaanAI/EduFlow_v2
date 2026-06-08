"""Staff CRUD service — the single shared write path for staff records
(AI Layer Hardening, AD7 / AD15 / Epic J, Story J.2).

Both the REST routes (`POST /api/staff/`, `PATCH /api/staff/{id}`) and the new AI
tools (`create_staff`, `update_staff`) call into the functions here, so an
AI-created/edited staff member is byte-identical to the panel result. The
`OWNER_ONLY_FIELDS` protection and privileged-account-creation gate are enforced
here (off `actor_ctx.role`) so both entrypoints apply them identically.

Staff hard-delete (`DELETE /staff/{id}`, a soft-deactivate that revokes sessions)
is NOT in this service's AI-reachable surface in Phase 1 — any destructive staff
op routes through F.10 (two-step confirm + deletion audit). Epic J ships create/edit only.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from middleware.auth import hash_password
from models.schemas import Staff
from services.actor_context import ActorContext
from services.audit_service import write_audit, write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter

# Field whitelists — the SAME sets the REST route enforces (keep in lockstep).
PROFILE_FIELDS = {
    "name", "staff_type", "employee_id", "phone", "email", "photo_url",
    "qualification", "specialization", "department", "join_date", "salary",
    "role", "sub_category",
}
LEAVE_BALANCE_FIELDS = {"casual_leave_balance", "medical_leave_balance", "earned_leave_balance"}
OWNER_ONLY_FIELDS = {"role", "sub_category", "salary", "is_active"}


class StaffValidationError(Exception):
    """Bad/empty input → HTTP 400."""


class StaffNotFoundError(Exception):
    """Staff id not found in tenant → HTTP 404."""


class StaffAuthorizationError(Exception):
    """Caller lacks authority for a privileged field/op → HTTP 403."""


class LinkedUserNotFoundError(Exception):
    """Provided user_id has no auth_users account → HTTP 404."""


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _is_owner(actor_ctx: ActorContext) -> bool:
    return actor_ctx.role == "owner"


def _is_owner_or_principal(actor_ctx: ActorContext) -> bool:
    return actor_ctx.role == "owner" or (
        actor_ctx.role == "admin" and (actor_ctx.sub_category or "principal") == "principal"
    )


def _is_accounts(actor_ctx: ActorContext) -> bool:
    return actor_ctx.role == "admin" and actor_ctx.sub_category in ("accounts", "accountant")


def _default_username(body: dict) -> str:
    source = body.get("username") or body.get("email") or body.get("phone") or body.get("employee_id") or body.get("name", "staff")
    return re.sub(r"[^a-zA-Z0-9._-]+", ".", source.lower()).strip(".")[:48] or f"staff.{uuid.uuid4().hex[:8]}"


async def _write_staff_audit(
    db, actor_ctx: ActorContext, *, action: str, staff_id: str,
    changes: Optional[dict] = None, session=None,
) -> None:
    await write_audit_doc(db, {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "entity_type": "staff",
        "entity_id": staff_id,
        "action": action,
        "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role,
        "changes": changes or {},
        "created_at": actor_ctx.now_iso(),
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id)


async def _create_or_link_user(db, actor_ctx: ActorContext, body: dict, *, session=None) -> tuple:
    if body.get("user_id"):
        existing = await db.auth_users.find_one({"id": body["user_id"]}, {"_id": 0})
        if not existing:
            raise LinkedUserNotFoundError("Linked user account not found")
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
        "schoolId": actor_ctx.school_id,
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
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }, **_session_kwargs(session))
    return user_id, temp_password


async def create_staff(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Create a staff member (+ link/create auth user) identically to `POST /api/staff/`.

    params: ``{name, staff_type, role?, sub_category?, employee_id?, phone?, email?,
    qualification?, specialization?, department?, join_date?, salary?, user_id?,
    password?, casual_leave_balance?, medical_leave_balance?, earned_leave_balance?}``
    returns: ``{"staff": <staff_doc>, "temporary_password": <str|None>}``
    """
    if not params.get("name") or not params.get("staff_type"):
        raise StaffValidationError("name and staff_type are required")
    requested_role = params.get("role") or ("teacher" if params.get("staff_type") == "teacher" else "admin")
    requested_sub = params.get("sub_category")
    if not _is_owner(actor_ctx) and (requested_role in {"owner", "admin"} or requested_sub):
        raise StaffAuthorizationError("Only owner can create privileged staff accounts")

    user_id, temp_password = await _create_or_link_user(db, actor_ctx, params, session=session)
    staff = Staff(
        user_id=user_id,
        name=params["name"],
        staff_type=params["staff_type"],
        employee_id=params.get("employee_id"),
        phone=params.get("phone"),
        email=params.get("email"),
        qualification=params.get("qualification"),
        specialization=params.get("specialization"),
        department=params.get("department"),
        join_date=params.get("join_date"),
        salary=params.get("salary"),
        casual_leave_balance=params.get("casual_leave_balance", 12),
        medical_leave_balance=params.get("medical_leave_balance", 10),
        earned_leave_balance=params.get("earned_leave_balance", 15),
    )
    staff_doc = {**_serialize(staff), "role": requested_role, "sub_category": requested_sub}
    await db.staff.insert_one({**staff_doc, "_id": staff.id}, **_session_kwargs(session))
    await _write_staff_audit(
        db, actor_ctx, action="create", staff_id=staff.id,
        changes={"created": staff_doc}, session=session,
    )
    if temp_password:
        # security: intentional — first-time credential delivery, no other channel.
        await write_audit(
            db=db,
            action="credential_issued",
            entity_id=staff.id,
            collection="staff",
            changed_by=actor_ctx.user_id,
            changed_by_role=actor_ctx.role or "",
            school_id=actor_ctx.school_id,
            branch_id=actor_ctx.branch_id or "",
            changes={"credential_type": "temporary_password", "issued_to_staff_id": staff.id},
        )
    return {"staff": staff_doc, "temporary_password": temp_password}


async def update_staff(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Update a staff member identically to `PATCH /api/staff/{id}`.

    Preserves OWNER_ONLY_FIELDS (silent strip for non-owners), leave-balance
    authority, accounts-salary, and the auth_users user_info sync.

    params: ``{staff_id, <fields>}``
    returns: ``{"staff": <updated_doc>, "noop": bool}``
    """
    school_id = actor_ctx.school_id
    staff_id = params.get("staff_id")
    if not staff_id:
        raise StaffValidationError("staff_id is required")
    existing = await db.staff.find_one(scoped_filter({"id": staff_id}, school_id), {"_id": 0})
    if not existing:
        raise StaffNotFoundError("Staff not found")

    body = {k: v for k, v in params.items() if k != "staff_id"}

    allowed = set(PROFILE_FIELDS)
    if not _is_owner(actor_ctx):
        allowed -= {"role", "sub_category", "salary"}
    if _is_owner_or_principal(actor_ctx):
        allowed |= LEAVE_BALANCE_FIELDS
    if _is_accounts(actor_ctx) and not _is_owner(actor_ctx):
        allowed |= {"salary"}
    if not _is_owner_or_principal(actor_ctx) and any(f in body for f in LEAVE_BALANCE_FIELDS):
        raise StaffAuthorizationError("Forbidden")

    update = {k: v for k, v in body.items() if k in allowed}

    # EC-9.4: OWNER_ONLY_FIELDS — non-owners cannot change role/sub_category/salary/is_active.
    body_had_owner_only = any(f in body for f in OWNER_ONLY_FIELDS)
    if not _is_owner(actor_ctx):
        for field in OWNER_ONLY_FIELDS:
            update.pop(field, None)  # silent strip — EC-9.4

    if not update:
        if body_had_owner_only and not _is_owner(actor_ctx):
            return {"staff": existing, "noop": True}
        raise StaffValidationError("No updatable fields provided")

    update["updated_at"] = actor_ctx.now_iso()
    changes = {k: {"previous": existing.get(k), "new": v} for k, v in update.items()
               if k != "updated_at" and existing.get(k) != v}
    if not changes:
        return {"staff": existing, "noop": True}

    await db.staff.update_one(
        scoped_filter({"id": staff_id}, school_id), {"$set": update}, **_session_kwargs(session)
    )
    if existing.get("user_id") and any(k in update for k in {"name", "phone", "role", "sub_category"}):
        user_info = {
            **(await db.auth_users.find_one({"id": existing["user_id"]}, {"_id": 0}) or {}).get("user_info", {}),
            "id": existing["user_id"],
            "name": update.get("name", existing.get("name")),
            "phone": update.get("phone", existing.get("phone")),
            "role": update.get("role", existing.get("role")),
            "sub_category": update.get("sub_category", existing.get("sub_category")),
        }
        await db.auth_users.update_one(
            {"id": existing["user_id"]}, {"$set": {"user_info": user_info}}, **_session_kwargs(session)
        )
    await _write_staff_audit(db, actor_ctx, action="update", staff_id=staff_id, changes=changes, session=session)
    updated = await db.staff.find_one(scoped_filter({"id": staff_id}, school_id), {"_id": 0})
    return {"staff": updated, "noop": False}
