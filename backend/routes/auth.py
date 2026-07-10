from __future__ import annotations
from typing import Optional

"""
Auth routes — Password login and JWT token management.

Endpoints:
  POST /api/auth/login           — Username/password login (primary)
  GET  /api/auth/me              — Get current user profile from JWT
  GET  /api/auth/seed-status     — Check seed data counts (public)
"""

import re
import logging
import uuid
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, validator
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from database import get_db
from middleware.auth import (
    create_jwt,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from services.audit_service import write_audit
from services.auth_tokens import (
    clear_legacy_refresh_cookie,
    clear_refresh_cookie,
    consume_refresh_token,
    get_refresh_cookie,
    issue_refresh_token,
    revoke_refresh_token,
    set_refresh_cookie,
    revoke_user_refresh_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Maximum login attempts before temporary lockout
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


# ─── Request models ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str
    school_id: Optional[str] = None  # For multi-school login disambiguation

    @validator("username")
    def validate_username(cls, v):
        v = v.strip()
        if not v or len(v) < 2 or len(v) > 100:
            raise ValueError("Username must be 2-100 characters")
        # Block regex/NoSQL injection characters
        if any(c in v for c in ["$", "{", "}", "(", ")"]):
            raise ValueError("Invalid characters in username")
        return v

    @validator("password")
    def validate_password(cls, v):
        v = v.strip()
        if not v or len(v) < 4 or len(v) > 128:
            raise ValueError("Password must be 4-128 characters")
        return v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v or "") < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be 8-128 characters")
        return v


class SetPasswordRequest(BaseModel):
    new_password: str

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v or "") < 6:
            raise ValueError("Password must be at least 6 characters")
        if len(v) > 128:
            raise ValueError("Password must be 6-128 characters")
        return v


class AdminResetPasswordRequest(BaseModel):
    new_password: Optional[str] = None

    @validator("new_password")
    def validate_optional_password(cls, v):
        if v is None:
            return v
        if len(v) < 8 or len(v) > 128:
            raise ValueError("Password must be 8-128 characters")
        return v


def _can_administer_auth(user: dict) -> bool:
    return user.get("role") == "owner" or (
        user.get("role") == "admin" and user.get("sub_category") == "principal"
    )

# ─── POST /api/auth/login ───────────────────────────────────────────────────

def _auth_user_filter(user_id: str) -> dict:
    return {
        "$or": [
            {"user_info.id": user_id},
            {"id": user_id},
            {"user_id": user_id},
        ]
    }


def _jwt_payload_from_auth(auth: dict) -> tuple[dict, dict]:
    user_info = auth.get("user_info", {})
    user_id = user_info.get("id") or auth.get("id") or auth.get("user_id") or str(auth.get("_id", ""))
    role = user_info.get("role", auth.get("role", ""))
    user_info = {**user_info, "id": user_id, "role": role}

    jwt_payload = {
        "user_id": user_id,
        "role": role,
        "name": user_info.get("name", ""),
        "initials": user_info.get("initials", ""),
    }
    if user_info.get("sub_category"):
        jwt_payload["sub_category"] = user_info["sub_category"]
    if user_info.get("branch_id"):
        jwt_payload["branch_id"] = user_info["branch_id"]
    if auth.get("phone"):
        jwt_payload["phone"] = auth["phone"]
    from tenant import get_school_id as _get_school_id
    jwt_payload["school_id"] = (auth.get("schoolId") or "").strip() or _get_school_id()

    return jwt_payload, user_info


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    """
    Username + password login. All roles require credentials.
    Returns JWT token on success.
    """
    db = get_db()
    username = body.username
    password = body.password

    # Rate limiting: check login attempts (key includes school so one tenant's
    # failed attempts don't lock the same username at another tenant)
    from tenant import get_school_id as _get_sid
    _attempt_school = body.school_id or _get_sid()
    attempt_key = f"login:{username.lower()}:{_attempt_school}"
    attempts = await db.login_attempts.find_one({"key": attempt_key})
    if attempts:
        if attempts.get("count", 0) >= MAX_LOGIN_ATTEMPTS:
            locked_until = attempts.get("locked_until")
            if locked_until:
                if isinstance(locked_until, str):
                    locked_until = datetime.fromisoformat(locked_until)
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) < locked_until:
                    raise HTTPException(
                        429,
                        f"Too many login attempts. Try again after {LOCKOUT_MINUTES} minutes."
                    )
                else:
                    # Lockout expired, reset
                    await db.login_attempts.delete_one({"key": attempt_key})

    # Find user by username (case-insensitive, safe — no regex injection)
    username_lower = username.lower()
    lookup_filter = {"username_lower": username_lower}
    if body.school_id:
        lookup_filter["schoolId"] = body.school_id
    auth = await db.auth_users.find_one(lookup_filter)

    if not auth:
        # Backward compat: legacy rows that predate multi-tenancy — scope to env-var or client-provided school
        from tenant import get_school_id as _gs
        fallback_filter = {"username_lower": username_lower, "schoolId": body.school_id or _gs()}
        auth = await db.auth_users.find_one(fallback_filter)

    if not auth:
        await _record_failed_attempt(db, attempt_key)
        _log_login_failed(request, username, "user_not_found")
        raise HTTPException(401, "Invalid username or password")
    if auth.get("is_active") is False or auth.get("user_info", {}).get("is_active") is False:
        await _record_failed_attempt(db, attempt_key)
        _log_login_failed(request, username, "account_inactive")
        raise HTTPException(401, "Invalid username or password")

    stored_password = auth.get("password_hash", "")

    if not stored_password or not stored_password.startswith("$2"):
        await _record_failed_attempt(db, attempt_key)
        _log_login_failed(request, username, "missing_password_hash")
        raise HTTPException(401, "Invalid username or password")

    if not verify_password(password, stored_password):
        await _record_failed_attempt(db, attempt_key)
        _log_login_failed(request, username, "invalid_password")
        raise HTTPException(401, "Invalid username or password")

    # Successful login — clear attempts
    await db.login_attempts.delete_one({"key": attempt_key})

    jwt_payload, user_info = _jwt_payload_from_auth(auth)

    token = create_jwt(jwt_payload)
    refresh_token = await issue_refresh_token(db, jwt_payload["user_id"], request)
    set_refresh_cookie(response, refresh_token)

    logger.info(
        "login_success",
        extra={
            "event": "login_success",
            "username": username,
            "user_id": jwt_payload["user_id"],
            "role": user_info.get("role", ""),
            "ip": _client_ip(request),
        },
    )
    from services.layaastat import emit_event
    await emit_event("user_login", distinct_id=jwt_payload["user_id"], payload={"role": user_info.get("role", "")})

    response_data = {
        "success": True,
        "access_token": token,
        "token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": user_info,
    }
    if auth.get("must_change_password"):
        response_data["must_change_password"] = True
    return response_data


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    db = get_db()
    # Patch F: evict any phantom legacy /api/auth-scoped cookie before reading,
    # so browsers send only the canonical path=/ cookie on subsequent requests.
    clear_legacy_refresh_cookie(response)
    raw_token = get_refresh_cookie(request)
    record = await consume_refresh_token(db, raw_token)
    user_id = record["user_id"]
    auth = await db.auth_users.find_one(_auth_user_filter(user_id))
    if not auth or auth.get("is_active") is False or auth.get("user_info", {}).get("is_active") is False:
        clear_refresh_cookie(response)
        raise HTTPException(401, "Refresh token revoked")

    jwt_payload, user_info = _jwt_payload_from_auth(auth)
    token = create_jwt(jwt_payload)
    refresh_token = await issue_refresh_token(db, jwt_payload["user_id"], request)
    set_refresh_cookie(response, refresh_token)
    refresh_response = {
        "success": True,
        "access_token": token,
        "token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": user_info,
    }
    if auth.get("must_change_password"):
        refresh_response["must_change_password"] = True
    return refresh_response


@router.post("/logout")
async def logout(request: Request, response: Response):
    db = get_db()
    raw_token = request.cookies.get("eduflow_refresh_token")
    if raw_token:
        await revoke_refresh_token(db, raw_token)
    clear_refresh_cookie(response)
    return {"success": True}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    db = get_db()
    uid = current_user.get("id") or current_user.get("user_id", "")
    auth = await db.auth_users.find_one(_auth_user_filter(uid))
    if not auth:
        raise HTTPException(404, "Auth record not found")
    stored_hash = auth.get("password_hash", "")
    if not stored_hash:
        raise HTTPException(400, "Current password is incorrect")
    if not verify_password(body.current_password, stored_hash):
        raise HTTPException(400, "Current password is incorrect")
    await db.auth_users.update_one(
        _auth_user_filter(uid),
        {"$set": {"password_hash": hash_password(body.new_password), "must_change_password": False}},
    )
    # Revoke old tokens first, then issue a fresh one so the client session survives the redirect
    await revoke_user_refresh_tokens(db, uid, reason="password_changed")
    try:
        new_refresh = await issue_refresh_token(db, uid, request)
        set_refresh_cookie(response, new_refresh)
    except Exception:
        logger.warning("issue_refresh_token failed after password change user_id=%s", uid, exc_info=True)
    return {"success": True}


@router.post("/set-password")
async def set_password(
    body: SetPasswordRequest,
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """Allows any authenticated user to set a new password without providing the current one.
    Used by the Settings modal for all roles/sub-roles.
    """
    db = get_db()
    uid = current_user.get("id") or current_user.get("user_id", "")
    auth = await db.auth_users.find_one(_auth_user_filter(uid))
    if not auth:
        raise HTTPException(404, "Auth record not found")
    await db.auth_users.update_one(
        _auth_user_filter(uid),
        {"$set": {"password_hash": hash_password(body.new_password), "must_change_password": False}},
    )
    await revoke_user_refresh_tokens(db, uid, reason="password_changed")
    try:
        new_refresh = await issue_refresh_token(db, uid, request)
        set_refresh_cookie(response, new_refresh)
    except Exception:
        logger.warning("issue_refresh_token failed after set-password user_id=%s", uid, exc_info=True)
    return {"success": True}


async def _record_failed_attempt(db, key: str):
    """Record a failed login attempt for rate limiting."""
    now = datetime.now(timezone.utc)
    locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
    await db.login_attempts.update_one(
        {"key": key},
        {
            "$inc": {"count": 1},
            "$set": {"last_attempt": now.isoformat(), "locked_until": locked_until.isoformat()},
        },
        upsert=True,
    )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _log_login_failed(request: Request, username: str, reason: str) -> None:
    logger.warning(
        "login_failed",
        extra={
            "event": "login_failed",
            "username": username,
            "reason": reason,
            "ip": _client_ip(request),
        },
    )


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, body: AdminResetPasswordRequest, user: dict = Depends(require_role("owner", "admin"))):
    if not _can_administer_auth(user):
        raise HTTPException(403, "Only owner or principal admin can reset user passwords")
    db = get_db()
    auth_record = await db.auth_users.find_one(_auth_user_filter(user_id))
    if not auth_record:
        raise HTTPException(404, "User not found")

    target_role = (auth_record.get("user_info") or {}).get("role") or auth_record.get("role", "")

    # IT-tech cannot reset owner passwords
    if target_role == "owner" and user.get("role") != "owner":
        raise HTTPException(403, "Cannot reset owner password — contact system administrator")

    new_password = body.new_password or f"EduFlow-{uuid.uuid4().hex[:10]}"
    from tenant import get_school_id
    await db.auth_users.update_one(
        _auth_user_filter(user_id),
        {"$set": {"password_hash": hash_password(new_password), "must_change_password": True, "password_reset_by": user["id"], "password_reset_at": datetime.now(timezone.utc).isoformat()}},
    )
    await revoke_user_refresh_tokens(db, user_id, reason="admin_password_reset")
    await write_audit(
        db,
        action="admin_password_reset",
        entity_id=user_id,
        collection="auth_users",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"reset_for_role": target_role},
    )
    return {"success": True, "message": "Password reset successfully. Communicate new credentials securely."}


@router.post("/admin/users/{user_id}/unlock")
async def admin_unlock_user(user_id: str, user: dict = Depends(require_role("owner", "admin"))):
    if not _can_administer_auth(user):
        raise HTTPException(403, "Only owner or IT tech admin can unlock users")
    db = get_db()
    auth = await db.auth_users.find_one(_auth_user_filter(user_id))
    if not auth:
        raise HTTPException(404, "User not found")
    usernames = {
        auth.get("username"),
        auth.get("username_lower"),
        auth.get("email"),
        (auth.get("user_info") or {}).get("email"),
    }
    for value in [item for item in usernames if item]:
        await db.login_attempts.delete_one({"key": f"login:{str(value).lower()}"})
    await db.auth_users.update_one(
        _auth_user_filter(user_id),
        {
            "$set": {"is_active": True, "unlocked_by": user["id"], "unlocked_at": datetime.now(timezone.utc).isoformat()},
            "$unset": {"locked_at": "", "failed_attempts": "", "locked_until": ""},
        },
    )
    from tenant import get_school_id
    await write_audit(
        db,
        action="admin_unlock_user",
        entity_id=user_id,
        collection="auth_users",
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
        changes={"action": "unlock", "cleared_fields": ["locked_at", "failed_attempts", "locked_until"]},
    )
    return {"success": True}


# ─── GET /api/auth/me ─────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(request: Request):
    """Return current user profile from JWT token."""
    user = get_current_user(request)
    return {"success": True, "user": user}


# ─── GET /api/auth/seed-status ────────────────────────────────────────────────

@router.get("/seed-status")
async def seed_status():
    db = get_db()
    count = await db.auth_users.count_documents({})
    classes = await db.classes.count_documents({})
    students = await db.students.count_documents({})
    staff = await db.staff.count_documents({})
    return {"auth_users": count, "classes": classes, "students": students, "staff": staff}
