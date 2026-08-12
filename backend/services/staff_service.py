"""Staff CRUD service - the single shared write path for staff records
(AI Layer Hardening, AD7 / AD15 / Epic J, Story J.2).

Both the REST routes (`POST /api/staff/`, `PATCH /api/staff/{id}`) and the new AI
tools (`create_staff`, `update_staff`) call into the functions here, so an
AI-created/edited staff member is byte-identical to the panel result. The
`OWNER_ONLY_FIELDS` protection and privileged-account-creation gate are enforced
here (off `actor_ctx.role`) so both entrypoints apply them identically.

Staff hard-delete (`DELETE /staff/{id}`, a soft-deactivate that revokes sessions)
is NOT in this service's AI-reachable surface in Phase 1 - any destructive staff
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

# Field whitelists - the SAME sets the REST route enforces (keep in lockstep).
PROFILE_FIELDS = {
    "name", "staff_type", "employee_id", "phone", "email", "photo_url",
    "qualification", "specialization", "department", "join_date", "salary",
    # Owner request 11 (2026-08-06) - where this person lives.
    "address",
    "role", "sub_category",
}
LEAVE_BALANCE_FIELDS = {"casual_leave_balance", "medical_leave_balance", "earned_leave_balance"}
OWNER_ONLY_FIELDS = {"role", "sub_category", "salary", "is_active"}

# UI-Sweep Story 1.1 - owner authority is not grantable through this API by
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
    except Exception:  # noqa: BLE001 - audit must never mask the denial
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
    be re-granted here either - demoting the last owner would leave the school
    with no owner and no in-app way to appoint one.
    """
    existing_role = _norm((existing or {}).get("role"))
    existing_sub = _norm((existing or {}).get("sub_category"))

    for field, existing_value in (("role", existing_role), ("sub_category", existing_sub)):
        if field not in params:
            continue
        requested = _norm(params.get(field))
        if requested == existing_value:
            continue  # unchanged - nothing to police
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
            "Owner access cannot be granted through this API - it is assigned out of band"
            if granting else
            "Owner access cannot be removed through this API - it is managed out of band"
        )


def _validate_role_and_sub_category(params: dict, *, existing: Optional[dict] = None) -> None:
    """Reject role/sub_category values the permission system does not recognize (Story 1.2).

    Validates only what is being WRITTEN. Values already stored are left alone -
    some of the 88 live records may hold a legacy spelling, and an admin fixing a
    phone number on such a record must not be handed an error they cannot clear.
    A field resent with the value it already holds counts as stored, not written:
    the staff form posts every field back, so the owner's own record legitimately
    resends `role: "owner"` - a value this function would otherwise reject.
    """
    existing_role = _norm((existing or {}).get("role"))
    existing_sub = _norm((existing or {}).get("sub_category"))
    role_changing = "role" in params and _norm(params["role"]) != existing_role
    sub_changing = "sub_category" in params and _norm(params["sub_category"]) != existing_sub
    if not (role_changing or sub_changing):
        return

    # Judge the record as it will END UP, not the shape of the request. Moving a
    # class_teacher to role "admin" without sending a sub_category leaves
    # `class_teacher` attached to an admin - the very pairing that matches no
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
    changes: Optional[dict] = None, reason: Optional[str] = None, session=None,
) -> None:
    doc = {
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
    }
    if reason:
        doc["reason"] = reason
    await write_audit_doc(db, doc, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id)


async def _assert_login_is_linkable(db, actor_ctx: ActorContext, login: dict) -> None:
    """Refuse to attach a staff record to a login that isn't free to claim (D-12).

    Two ways in: a caller-supplied `user_id`, or a name/email/phone whose derived
    username collides with an existing account. Either would let a staff manager
    point a new staff record at the OWNER's login - and deactivating that staff
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
    # branch-scope: intentional - a login already claimed by a staff record in
    # ANOTHER branch is still claimed. Filtering by branch here would let the
    # same login be claimed once per branch, which is the hole this closes.
    claimed = await db.staff.find_one(
        scoped_filter({"user_id": login.get("id")}, actor_ctx.school_id), {"_id": 0}
    )
    if claimed:
        # Reachable without malice: two staff with the same name and no email or
        # phone derive the same username. Previously they silently SHARED one
        # login - both signing in as the same person. Say what to do about it.
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

    temp_password = body.get("password") or (None if body.get("password_hash") else f"EduFlow-{uuid.uuid4().hex[:8]}")
    password_hash = body.get("password_hash") or hash_password(temp_password)
    role = body.get("role") or ("teacher" if body.get("staff_type") == "teacher" else "admin")
    user_id = str(uuid.uuid4())
    await db.auth_users.insert_one({
        "_id": user_id,
        "id": user_id,
        "schoolId": actor_ctx.school_id,
        "username": username,
        "username_lower": username.lower(),
        "password_hash": password_hash,
        "is_active": True,
        "must_change_password": False,
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
    if "password" in params and not 8 <= len(str(params.get("password") or "")) <= 128:
        raise StaffValidationError("password must be 8-128 characters")
    if params.get("password_hash") and not str(params["password_hash"]).startswith(("$2a$", "$2b$", "$2y$")):
        raise StaffValidationError("protected password value is invalid")
    requested_role = _norm(params.get("role")) or ("teacher" if params.get("staff_type") == "teacher" else "admin")
    requested_sub = _norm(params.get("sub_category"))
    effective = {**params, "role": requested_role}
    if "sub_category" in params:
        effective["sub_category"] = requested_sub

    # Story 1.1 - owner authority is refused for EVERY caller, the owner included,
    # and refused BEFORE any record is written. The login account is the real seat
    # of authority (`auth_users.user_info.role` is what login reads to mint the
    # JWT), so a gate placed after `_create_or_link_user` would leave a privileged
    # login behind on a request that returned 403.
    await _assert_no_owner_authority_change(db, actor_ctx, params=effective, existing=None)
    # Authority BEFORE validation, deliberately: a caller who may not set these
    # fields at all should not be handed an error message enumerating the values
    # that would have been accepted.
    if not _is_owner_or_principal(actor_ctx) and (requested_role == "admin" or requested_sub):
        raise StaffAuthorizationError("Only owner or principal can create privileged staff accounts")
    # Story 1.2 - a value the permission system does not recognize grants nothing.
    _validate_role_and_sub_category(effective, existing=None)

    user_id, temp_password = await _create_or_link_user(db, actor_ctx, effective, session=session)
    staff = Staff(
        user_id=user_id,
        name=params["name"],
        staff_type=params["staff_type"],
        employee_id=params.get("employee_id"),
        phone=params.get("phone"),
        email=params.get("email"),
        address=params.get("address"),
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
        # security: intentional - first-time credential delivery, no other channel.
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

    # Story 1.1 - a change of owner authority in either direction is a hard 403
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
    # Abhimanyu, 2026-08-11, relaying Aman's and Adesh's instruction: the accountant
    # head already runs payroll in full - salary_structures and salary_disbursements
    # have been his since this project began - and now gets the one figure that sat
    # outside that system, the base salary on a colleague's staff record.
    #
    # Scoped to ONLY that field, overwriting rather than adding to `allowed`: a name,
    # phone or department change is Lalit's and Adesh's remit (decisions 2 and 4), and
    # this instruction was about salary, not people generally. Widening it further
    # would be assuming something nobody asked for.
    if _is_accounts(actor_ctx) and not _is_owner(actor_ctx):
        allowed = {"salary"}
    if not _is_owner_or_principal(actor_ctx) and any(f in body for f in LEAVE_BALANCE_FIELDS):
        raise StaffAuthorizationError("Forbidden")

    update = {k: v for k, v in body.items() if k in allowed}

    # EC-9.4: OWNER_ONLY_FIELDS - role/sub_category/is_active stay owner-only for
    # everybody, no exceptions. `salary` is the one field that can be in `allowed` for
    # someone other than the owner (the accountant head, as of 2026-08-11), so the
    # strip below defers to `allowed` rather than repeating OWNER_ONLY_FIELDS blindly.
    #
    # Before 2026-08-11 this loop stripped `salary` unconditionally, which silently
    # undid the `allowed |= {"salary"}` line above the moment it was reached - the
    # accountant exception was written and never actually took effect. It had no test
    # driving a real write through it, so nothing caught a permission granted in one
    # line and taken back three lines later.
    body_had_owner_only = any(f in body for f in OWNER_ONLY_FIELDS)
    if not _is_owner(actor_ctx):
        for field in OWNER_ONLY_FIELDS:
            if field in allowed:
                continue
            update.pop(field, None)  # silent strip - EC-9.4

    # Story 1.2 - validate exactly what will be WRITTEN, and only that: values
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


async def set_enrolment_state(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Move a staff member or teacher between on the roll, NSO and TC issued.

    params: ``{staff_id, state, reason?}``
    returns: ``{"staff": <updated_doc>, "noop": bool, "previous_state": str}``

    THE ONE WRITER of `is_active` on a staff record outside `DELETE /api/staff/{id}`,
    and it always writes `status` in the same breath. See
    `services/enrolment_status.py` for what the three states mean.

    Owner request 10 decision 2, Abhimanyu 2026-08-06: the three states apply to
    staff and teachers exactly as they do to students, not to students only. The
    words are the school's own, so they are kept even where "TC issued" reads oddly
    for an employee - a member of staff who has formally left is in the same place
    in the product as a child who has taken their leaving certificate, and a second
    vocabulary for the same three states is how the two would drift apart.

    THE LOGIN FOLLOWS THE STATE. Someone off the roll cannot sign in, and their
    existing sessions are ended straight away; putting them back on the roll turns
    the login on again. Doing this here rather than in the route is what stops a
    person keeping a working session after the school has stopped employing them.

    What this deliberately does NOT do is erase what the assistant learned about
    them. `DELETE /api/staff/{id}` does that because it reads as a retirement, and
    permanent erasure does it because the record is being destroyed. These three
    states are reversible, and an erase you cannot undo has no place behind a button
    labelled "move to NSO".
    """
    from services import enrolment_status
    from services.auth_tokens import revoke_user_refresh_tokens

    school_id = actor_ctx.school_id
    staff_id = params.get("staff_id")
    if not staff_id:
        raise StaffValidationError("staff_id is required")

    state = str(params.get("state") or "").strip().lower()
    if state not in enrolment_status.SETTABLE_STATES:
        raise StaffValidationError(
            "state must be one of: " + ", ".join(enrolment_status.SETTABLE_STATES)
        )

    existing = await db.staff.find_one(scoped_filter({"id": staff_id}, school_id), {"_id": 0})
    if not existing:
        raise StaffNotFoundError("Staff not found")

    # Story 1.1 again: owner authority is not switched off through this API either.
    # Deactivating the owner's own staff record would lock the school out of the one
    # account that can put anything back.
    if _holds_owner_authority(existing) and state != enrolment_status.ACTIVE:
        raise StaffAuthorizationError("Forbidden")

    previous_state = enrolment_status.normalise(existing)
    update = enrolment_status.fields_for(state)
    changes = {
        key: {"previous": existing.get(key), "new": value}
        for key, value in update.items()
        if existing.get(key) != value
    }
    if not changes:
        return {"staff": existing, "noop": True, "previous_state": previous_state}

    update["updated_at"] = actor_ctx.now_iso()
    if state == enrolment_status.ACTIVE:
        update["deactivated_at"] = None
    else:
        update["deactivated_at"] = actor_ctx.now_iso()

    await db.staff.update_one(
        scoped_filter({"id": staff_id}, school_id), {"$set": update}, **_session_kwargs(session)
    )

    if existing.get("user_id"):
        on_roll = state == enrolment_status.ACTIVE
        await db.auth_users.update_one(
            {"id": existing["user_id"]}, {"$set": {"is_active": on_roll}}, **_session_kwargs(session)
        )
        if not on_roll:
            await revoke_user_refresh_tokens(db, existing["user_id"], reason=f"staff_{state}")

    await _write_staff_audit(
        db, actor_ctx,
        # A distinct action per state, so the log answers "who took this teacher off
        # the roll, and when" without anyone reading a diff to work it out.
        action=f"enrolment_{state}",
        staff_id=staff_id,
        changes={**changes, "previous_state": {"previous": previous_state, "new": state}},
        reason=(params.get("reason") or "").strip() or None,
        session=session,
    )
    updated = await db.staff.find_one(scoped_filter({"id": staff_id}, school_id), {"_id": 0})
    return {"staff": updated, "noop": False, "previous_state": previous_state}


async def delete_staff(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
) -> dict:
    """Take a colleague off the roll - the shared path behind `DELETE /api/staff/{id}`
    and the AI `delete_staff` tool.

    Owner instruction 2026-08-07 - Flo could add a staff member but had no way to
    remove one.

    Reversible, like the student equivalent: `set_enrolment_state` puts them back. It
    closes the door behind them as it goes - `set_enrolment_state` already disables the
    login and revokes any refresh token, so an open session cannot outlive the
    decision, and this adds the erasure of what the assistant had learned about them
    (R6.4 / DPDP §12). That erasure is best-effort and never blocks the deactivation.

    params: ``{staff_id, reason?}``
    returns: ``{"staff": <doc>, "noop": bool, "previous_state": str}``
    """
    from services import enrolment_status

    from services.profile_matrix import may_delete_people, user_from_actor

    staff_id = params.get("staff_id")
    if not staff_id:
        raise StaffValidationError("staff_id is required")

    # R2-4 / decision 4, 2026-08-10: the management head adds and edits colleagues; he
    # does not take them off the roll. Guarded HERE and not on the route, because the
    # route and the Flo `delete_staff` tool both come through this function.
    if not may_delete_people(user_from_actor(actor_ctx)):
        raise StaffAuthorizationError(
            "Only the school's owner or the principal can take a colleague off the roll"
        )

    result = await set_enrolment_state(
        db,
        actor_ctx,
        {
            "staff_id": staff_id,
            "state": enrolment_status.TC_ISSUED,
            "reason": params.get("reason"),
        },
        session=session,
    )
    if not result.get("noop"):
        await erase_ai_memory_of_staff(db, actor_ctx, result.get("staff") or {})
    return result


async def erase_ai_memory_of_staff(db, actor_ctx: ActorContext, staff: dict) -> None:
    """Erase what the assistant learned about a colleague who has left (R6.4, DPDP §12).

    Lifted out of `routes/staff.py:delete_staff` on 2026-08-07 so the AI tool and the
    REST route cannot drift: before this, only the route did it, so a colleague
    deactivated by any other path left their memories behind.

    Best-effort by design - the deactivation itself has already happened and must not
    be undone because a memory store was unreachable.
    """
    user_id = staff.get("user_id")
    if not user_id:
        return
    try:
        from services.memory.store import erase_owner_memories
        from services.memory.skills_store import erase_owner_skills
        from services.memory.feedback_store import erase_owner_feedback

        changed_by = actor_ctx.user_id or "system"
        await erase_owner_memories(db, school_id=actor_ctx.school_id, user_id=user_id, changed_by=changed_by)
        await erase_owner_skills(db, school_id=actor_ctx.school_id, user_id=user_id, changed_by=changed_by)
        await erase_owner_feedback(db, school_id=actor_ctx.school_id, user_id=user_id, changed_by=changed_by)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "ai_memory/skill/feedback erase on staff delete failed", exc_info=True
        )
