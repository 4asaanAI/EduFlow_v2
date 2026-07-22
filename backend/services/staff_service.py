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

import logging
import re
import uuid
from typing import Optional

from middleware.auth import SUB_CATEGORIES_BY_ROLE, VALID_ROLES, hash_password
from models.schemas import Staff
from services.actor_context import ActorContext
from services.audit_service import write_audit, write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter

logger = logging.getLogger(__name__)

# Field whitelists — the SAME sets the REST route enforces (keep in lockstep).
PROFILE_FIELDS = {
    "name", "staff_type", "employee_id", "phone", "email", "photo_url",
    "qualification", "specialization", "department", "join_date", "salary",
    "role", "sub_category",
}
LEAVE_BALANCE_FIELDS = {"casual_leave_balance", "medical_leave_balance", "earned_leave_balance"}
OWNER_ONLY_FIELDS = {"role", "sub_category", "salary", "is_active"}

# UI-Sweep Story 1.1 — owner authority is not grantable through this API by
# ANYONE, the owner included. Assignment happens out of band only.
OWNER_AUTHORITY = "owner"
# Roles this API may write onto a staff record. Derived by subtraction from the
# platform's role list rather than typed out, so a role added in one place
# cannot be quietly forgotten here: `owner` is excluded because it is never
# granted through this API, `student` because a student is not staff.
ASSIGNABLE_STAFF_ROLES = VALID_ROLES - {OWNER_AUTHORITY, "student"}


class StaffValidationError(Exception):
    """Bad/empty input → HTTP 400."""


class StaffFieldValidationError(StaffValidationError):
    """A field carries a value the permission system does not recognize → HTTP 422.

    A subclass of StaffValidationError so every existing caller that catches the
    parent keeps working; callers that want the sharper status catch this first.
    """


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


def _norm(value) -> Optional[str]:
    """Lower-case and trim a role/sub_category so `" Owner "` cannot slip past a
    literal comparison. Non-strings (and None) pass through untouched."""
    return value.strip().lower() if isinstance(value, str) else value


def _holds_owner_authority(record: Optional[dict]) -> bool:
    """True if this staff/auth record carries owner authority in either field."""
    if not record:
        return False
    info = record.get("user_info") or {}
    return OWNER_AUTHORITY in {
        _norm(record.get("role")), _norm(record.get("sub_category")),
        _norm(info.get("role")), _norm(info.get("sub_category")),
    }


async def _audit_denial(db, actor_ctx: ActorContext, *, staff_id: str, attempted: dict, reason: str) -> None:
    """Record a refused privilege change (Story 1.1).

    Fail-open per ADR-002: an audit backend that is down must not convert a
    correct 403 into a 500, which would read to the caller as "the server broke"
    rather than "you may not do that".
    """
    try:
        await _write_staff_audit(
            db, actor_ctx,
            action="privilege_escalation_denied",
            staff_id=staff_id or "unassigned",
            changes={"attempted": attempted, "reason": reason},
        )
    except Exception:  # noqa: BLE001 — audit must never mask the denial
        logger.warning("privilege_escalation_denied audit write failed", exc_info=True)


async def _assert_no_owner_authority_change(
    db, actor_ctx: ActorContext, *, params: dict, existing: Optional[dict] = None,
) -> None:
    """Refuse any request that would GRANT or REMOVE owner authority (Story 1.1).

    The rule is about a *change* measured against what is stored, not about the
    string "owner" appearing in a body: the staff form posts every field back, so
    an owner editing the owner's own record legitimately resends `role: "owner"`.
    Denying that would break a real workflow while protecting nothing.

    Both directions are refused. Granting is the privilege-escalation hole this
    story exists to close (FR4/NFR-S1). Removing is refused because owner cannot
    be re-granted here either — demoting the last owner would leave the school
    with no owner and no in-app way to appoint one.
    """
    existing_role = _norm((existing or {}).get("role"))
    existing_sub = _norm((existing or {}).get("sub_category"))

    for field, existing_value in (("role", existing_role), ("sub_category", existing_sub)):
        if field not in params:
            continue
        requested = _norm(params.get(field))
        if requested == existing_value:
            continue  # unchanged — nothing to police
        if OWNER_AUTHORITY not in (requested, existing_value):
            continue  # a change, but not one that touches owner authority
        granting = requested == OWNER_AUTHORITY
        await _audit_denial(
            db, actor_ctx,
            staff_id=(existing or {}).get("id", ""),
            attempted={field: params.get(field), "previous": existing_value},
            reason="grant_owner_authority" if granting else "remove_owner_authority",
        )
        raise StaffAuthorizationError(
            "Owner access cannot be granted through this API — it is assigned out of band"
            if granting else
            "Owner access cannot be removed through this API — it is managed out of band"
        )


def _validate_role_and_sub_category(params: dict, *, existing: Optional[dict] = None) -> None:
    """Reject role/sub_category values the permission system does not recognize (Story 1.2).

    Validates only what is being WRITTEN. Values already stored are left alone —
    some of the 88 live records may hold a legacy spelling, and an admin fixing a
    phone number on such a record must not be handed an error they cannot clear.
    A field resent with the value it already holds counts as stored, not written:
    the staff form posts every field back, so the owner's own record legitimately
    resends `role: "owner"` — a value this function would otherwise reject.
    """
    existing_role = _norm((existing or {}).get("role"))
    existing_sub = _norm((existing or {}).get("sub_category"))
    role_changing = "role" in params and _norm(params["role"]) != existing_role
    sub_changing = "sub_category" in params and _norm(params["sub_category"]) != existing_sub
    if not (role_changing or sub_changing):
        return

    # Judge the record as it will END UP, not the shape of the request. Moving a
    # class_teacher to role "admin" without sending a sub_category leaves
    # `class_teacher` attached to an admin — the very pairing that matches no
    # permission rule, reached by changing the other half of the pair.
    effective_role = _norm(params["role"]) if "role" in params else existing_role
    effective_sub = _norm(params["sub_category"]) if "sub_category" in params else existing_sub

    if role_changing and effective_role not in ASSIGNABLE_STAFF_ROLES:
        raise StaffFieldValidationError(
            "role: %r is not a role that can be assigned to a staff member "
            "(expected one of: %s)" % (params.get("role"), ", ".join(sorted(ASSIGNABLE_STAFF_ROLES)))
        )

    if effective_sub in (None, ""):
        return  # no sub_category at all is a valid state; clearing one is allowed
    allowed_for_role = SUB_CATEGORIES_BY_ROLE.get(effective_role or "", frozenset())
    if effective_sub not in allowed_for_role:
        raise StaffFieldValidationError(
            "sub_category: %r is not valid for role %r (expected one of: %s)"
            % (effective_sub, effective_role, ", ".join(sorted(allowed_for_role)) or "none")
        )


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


async def _assert_login_is_linkable(db, actor_ctx: ActorContext, login: dict) -> None:
    """Refuse to attach a staff record to a login that isn't free to claim (D-12).

    Two ways in: a caller-supplied `user_id`, or a name/email/phone whose derived
    username collides with an existing account. Either would let a staff manager
    point a new staff record at the OWNER's login — and deactivating that staff
    record deactivates the linked login and revokes its sessions, locking the
    owner out of their own school.
    """
    if _holds_owner_authority(login):
        await _audit_denial(
            db, actor_ctx, staff_id="",
            attempted={"user_id": login.get("id")}, reason="link_to_owner_login",
        )
        raise StaffAuthorizationError(
            "That login belongs to an owner account and cannot be linked to a staff record"
        )
    # branch-scope: intentional — a login already claimed by a staff record in
    # ANOTHER branch is still claimed. Filtering by branch here would let the
    # same login be claimed once per branch, which is the hole this closes.
    claimed = await db.staff.find_one(
        scoped_filter({"user_id": login.get("id")}, actor_ctx.school_id), {"_id": 0}
    )
    if claimed:
        # Reachable without malice: two staff with the same name and no email or
        # phone derive the same username. Previously they silently SHARED one
        # login — both signing in as the same person. Say what to do about it.
        raise StaffAuthorizationError(
            "The login '%s' already belongs to another staff record (%s). Give this "
            "person their own email, phone or employee ID so they get their own login."
            % (login.get("username", ""), claimed.get("name", "another staff member"))
        )


async def _create_or_link_user(db, actor_ctx: ActorContext, body: dict, *, session=None) -> tuple:
    if body.get("user_id"):
        existing = await db.auth_users.find_one({"id": body["user_id"]}, {"_id": 0})
        if not existing:
            raise LinkedUserNotFoundError("Linked user account not found")
        await _assert_login_is_linkable(db, actor_ctx, existing)
        return body["user_id"], None

    username = _default_username(body)
    existing = await db.auth_users.find_one({"username_lower": username.lower()}, {"_id": 0})
    if existing:
        await _assert_login_is_linkable(db, actor_ctx, existing)
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
    requested_role = _norm(params.get("role")) or ("teacher" if params.get("staff_type") == "teacher" else "admin")
    requested_sub = _norm(params.get("sub_category"))
    effective = {**params, "role": requested_role}
    if "sub_category" in params:
        effective["sub_category"] = requested_sub

    # Story 1.1 — owner authority is refused for EVERY caller, the owner included,
    # and refused BEFORE any record is written. The login account is the real seat
    # of authority (`auth_users.user_info.role` is what login reads to mint the
    # JWT), so a gate placed after `_create_or_link_user` would leave a privileged
    # login behind on a request that returned 403.
    await _assert_no_owner_authority_change(db, actor_ctx, params=effective, existing=None)
    # Authority BEFORE validation, deliberately: a caller who may not set these
    # fields at all should not be handed an error message enumerating the values
    # that would have been accepted.
    if not _is_owner(actor_ctx) and (requested_role == "admin" or requested_sub):
        raise StaffAuthorizationError("Only owner can create privileged staff accounts")
    # Story 1.2 — a value the permission system does not recognize grants nothing.
    _validate_role_and_sub_category(effective, existing=None)

    user_id, temp_password = await _create_or_link_user(db, actor_ctx, effective, session=session)
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
    for field in ("role", "sub_category"):
        if field in body:
            body[field] = _norm(body[field])

    # Story 1.1 — a change of owner authority in either direction is a hard 403
    # for every caller, checked against what is stored. Deliberately NOT the
    # silent strip below: stripping salary tells a caller "that field isn't
    # yours"; silently stripping an escalation attempt leaves them believing it
    # worked and leaves no record that they tried.
    await _assert_no_owner_authority_change(db, actor_ctx, params=body, existing=existing)

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

    # Story 1.2 — validate exactly what will be WRITTEN, and only that: values
    # already stored are left alone, and a field the caller was not allowed to
    # write has been stripped above, so they get no error enumerating the values
    # that would have been accepted.
    _validate_role_and_sub_category(update, existing=existing)

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
