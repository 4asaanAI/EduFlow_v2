"""Tenant-scoped login account administration shared by REST and Flo."""

from __future__ import annotations

import re
import uuid
from typing import Optional

from middleware.auth import hash_password
from pymongo.errors import DuplicateKeyError
from services.actor_context import ActorContext
from services.audit_service import write_audit
from services.txn_context import session_kwargs
from tenant import scoped_filter


class AccountValidationError(Exception):
    """The requested account change is invalid."""


class AccountNotFoundError(Exception):
    """The requested student or login does not exist in this school."""


class AccountConflictError(Exception):
    """The requested username or linked login is already in use."""


class AccountAuthorizationError(Exception):
    """The actor may not administer the requested account."""


def _is_leadership(actor: ActorContext) -> bool:
    return actor.role == "owner" or (
        actor.role == "admin" and actor.sub_category == "principal"
    )


def _is_management(actor: ActorContext) -> bool:
    return actor.role == "admin" and actor.sub_category == "management"


def _normalise_username(value: object) -> str:
    username = str(value or "").strip().lower()
    if not 2 <= len(username) <= 100:
        raise AccountValidationError("Username must be 2-100 characters")
    if not re.fullmatch(r"[a-z0-9._-]+", username):
        raise AccountValidationError(
            "Username may contain only letters, numbers, dots, underscores, and hyphens"
        )
    return username


def _student_username(params: dict, student: dict, student_id: str) -> str:
    if params.get("username"):
        return _normalise_username(params["username"])
    source = str(student.get("admission_number") or f"student.{student_id}").lower()
    derived = re.sub(r"[^a-z0-9._-]+", ".", source).strip(".")[:100]
    return _normalise_username(derived)


def _password_hash(params: dict) -> str:
    prehashed = params.get("new_password_hash") or params.get("password_hash")
    if prehashed:
        if not isinstance(prehashed, str) or not prehashed.startswith(("$2a$", "$2b$", "$2y$")):
            raise AccountValidationError("Protected password value is invalid")
        return prehashed
    password = params.get("new_password") or params.get("password")
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise AccountValidationError("Password must be 8-128 characters")
    return hash_password(password)


def _auth_filter(*, user_id: Optional[str] = None, username: Optional[str] = None) -> dict:
    if user_id:
        return {
            "$or": [
                {"id": user_id},
                {"user_id": user_id},
                {"user_info.id": user_id},
            ]
        }
    if username:
        return {"username_lower": _normalise_username(username)}
    raise AccountValidationError("user_id or username is required")


async def create_student_login(
    db,
    actor: ActorContext,
    params: dict,
    *,
    session=None,
) -> dict:
    """Create and link a login for an existing student record."""
    if not (_is_leadership(actor) or _is_management(actor)):
        raise AccountAuthorizationError("Only owner, principal, or management can create student logins")
    student_id = str(params.get("student_id") or "").strip()
    if not student_id:
        raise AccountValidationError("student_id is required")

    student = await db.students.find_one(
        scoped_filter({"id": student_id}, actor.school_id), {"_id": 0}
    )
    if not student:
        raise AccountNotFoundError("Student not found")
    if student.get("user_id"):
        linked = await db.auth_users.find_one(
            scoped_filter({"id": student["user_id"]}, actor.school_id), {"_id": 0}
        )
        if linked:
            raise AccountConflictError("This student already has a login profile")

    username = _student_username(params, student, student_id)
    collision = await db.auth_users.find_one(
        scoped_filter({"username_lower": username}, actor.school_id), {"_id": 0}
    )
    if collision:
        raise AccountConflictError("That username is already in use")

    user_id = str(uuid.uuid4())
    now = actor.now_iso()
    branch_id = student.get("branch_id") or actor.branch_id
    auth_doc = {
        "_id": user_id,
        "id": user_id,
        "schoolId": actor.school_id,
        "username": username,
        "username_lower": username,
        "password_hash": _password_hash(params),
        "role": "student",
        "is_active": True,
        "must_change_password": False,
        "user_info": {
            "id": user_id,
            "name": student.get("name", ""),
            "role": "student",
            "sub_category": "student",
            "branch_id": branch_id,
            "is_active": True,
        },
        "created_by": actor.user_id,
        "created_at": now,
    }
    kwargs = session_kwargs(session)
    try:
        await db.auth_users.insert_one(auth_doc, **kwargs)
    except DuplicateKeyError as exc:
        raise AccountConflictError("That username is already in use") from exc

    previous_user_id = student.get("user_id")
    link_filter = {"id": student_id}
    if previous_user_id:
        link_filter["user_id"] = previous_user_id
    else:
        link_filter["$or"] = [
            {"user_id": {"$exists": False}}, {"user_id": None}, {"user_id": ""}
        ]
    link_result = await db.students.update_one(
        scoped_filter(link_filter, actor.school_id),
        {"$set": {"user_id": user_id, "updated_at": now}},
        **kwargs,
    )
    if getattr(link_result, "modified_count", 0) != 1:
        await db.auth_users.delete_one(
            scoped_filter({"id": user_id}, actor.school_id), **kwargs
        )
        raise AccountConflictError("This student already has a login profile")

    await db.users.update_one(
        scoped_filter({"id": user_id}, actor.school_id),
        {
            "$set": {
                "schoolId": actor.school_id,
                "name": student.get("name", ""),
                "role": "student",
                "sub_category": "student",
                "branch_id": branch_id,
                "is_active": True,
                "updated_at": now,
            },
            "$setOnInsert": {"_id": user_id, "id": user_id, "created_at": now},
        },
        upsert=True,
        **kwargs,
    )
    await write_audit(
        db,
        action="student_login_created",
        entity_id=user_id,
        collection="auth_users",
        changed_by=actor.user_id or "",
        changed_by_role=actor.role or "",
        school_id=actor.school_id,
        branch_id=branch_id or "",
        changes={
            "student_id": student_id,
            "username": username,
            "role": "student",
            "must_change_password": False,
        },
    )
    return {
        "account": {
            "user_id": user_id,
            "student_id": student_id,
            "username": username,
            "role": "student",
            "must_change_password": False,
        }
    }


async def set_profile_password(
    db,
    actor: ActorContext,
    params: dict,
    *,
    session=None,
    must_change_password: bool = False,
) -> dict:
    """Replace a login credential and revoke every existing refresh session."""
    if not (_is_leadership(actor) or _is_management(actor)):
        raise AccountAuthorizationError("Only owner, principal, or management can change profile passwords")

    query = scoped_filter(
        _auth_filter(user_id=params.get("user_id"), username=params.get("username")),
        actor.school_id,
    )
    target = await db.auth_users.find_one(query, {"_id": 0})
    if not target:
        raise AccountNotFoundError("User profile not found")
    info = target.get("user_info") or {}
    target_id = info.get("id") or target.get("id") or target.get("user_id")
    target_role = info.get("role") or target.get("role") or ""

    if _is_management(actor) and target_role != "student":
        raise AccountAuthorizationError("Management can change passwords only for student profiles")
    if actor.role != "owner" and target_role == "owner":
        raise AccountAuthorizationError("Only the owner can change an owner password")

    now = actor.now_iso()
    kwargs = session_kwargs(session)
    await db.auth_users.update_one(
        query,
        {
            "$set": {
                "password_hash": _password_hash(params),
                "must_change_password": bool(must_change_password),
                "password_reset_by": actor.user_id,
                "password_reset_at": now,
            }
        },
        **kwargs,
    )
    await db.refresh_tokens.update_many(
        {"user_id": target_id, "revoked_at": None},
        {"$set": {"revoked_at": actor.now(), "revoked_reason": "admin_password_reset"}},
        **kwargs,
    )
    await write_audit(
        db,
        action="admin_password_reset",
        entity_id=target_id,
        collection="auth_users",
        changed_by=actor.user_id or "",
        changed_by_role=actor.role or "",
        school_id=actor.school_id,
        branch_id=actor.branch_id or "",
        changes={
            "reset_for_role": target_role,
            "must_change_password": bool(must_change_password),
            "sessions_revoked": True,
        },
    )
    return {
        "account": {
            "user_id": target_id,
            "username": target.get("username") or target.get("username_lower"),
            "role": target_role,
            "must_change_password": bool(must_change_password),
        }
    }
