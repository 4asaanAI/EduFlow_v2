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
import os
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
from services.email_service import send_password_reset_email
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
PASSWORD_RESET_TTL_MINUTES = 15
PASSWORD_RESET_RATE_LIMIT = 3
PASSWORD_RESET_RATE_WINDOW_HOURS = 1


# ─── Request models ──────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

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


class ForgotPasswordRequest(BaseModel):
    email: str

    @validator("email")
    def validate_email(cls, v):
        v = v.strip().lower()
        if not v or "@" not in v or len(v) > 254:
            raise ValueError("Valid email is required")
        return v


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @validator("new_password")
    def validate_new_password(cls, v):
        if len(v or "") < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be 8-128 characters")
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
        user.get("role") == "admin" and user.get("sub_category") == "it_tech"
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

    # Rate limiting: check login attempts
    attempt_key = f"login:{username.lower()}"
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
    auth = await db.auth_users.find_one({"username_lower": username_lower})

    if not auth:
        # Also try exact match for backward compatibility
        auth = await db.auth_users.find_one({"username": username})

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

    return {
        "success": True,
        "access_token": token,
        "token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": user_info,
    }


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
    return {
        "success": True,
        "access_token": token,
        "token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": user_info,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    db = get_db()
    raw_token = request.cookies.get("eduflow_refresh_token")
    if raw_token:
        await revoke_refresh_token(db, raw_token)
    clear_refresh_cookie(response)
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


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    db = get_db()
    email = body.email
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=PASSWORD_RESET_RATE_WINDOW_HOURS)
    recent_count = await db.password_reset_requests.count_documents(
        {"email": email, "created_at": {"$gte": window_start}}
    )
    if recent_count >= PASSWORD_RESET_RATE_LIMIT:
        raise HTTPException(429, "Too many password reset requests. Try again later.")

    await db.password_reset_requests.insert_one({"email": email, "created_at": now})

    auth = await db.auth_users.find_one({"email": email})
    if not auth:
        auth = await db.auth_users.find_one({"user_info.email": email})

    if auth:
        token = str(uuid.uuid4())
        jwt_payload, user_info = _jwt_payload_from_auth(auth)
        expires_at = now + timedelta(minutes=PASSWORD_RESET_TTL_MINUTES)
        await db.password_reset_tokens.insert_one(
            {
                "token": token,
                "user_id": jwt_payload["user_id"],
                "email": email,
                "expires_at": expires_at,
                "used": False,
                "created_at": now,
            }
        )
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        reset_link = f"{frontend_url}/reset-password?token={token}"
        try:
            send_password_reset_email(email, reset_link)
        except Exception:
            logger.error("password reset email failed", exc_info=True)

    return {"success": True, "message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    db = get_db()
    now = datetime.now(timezone.utc)
    result = await db.password_reset_tokens.update_one(
        {
            "token": body.token,
            "used": False,
            "expires_at": {"$gt": now},
        },
        {"$set": {"used": True, "used_at": now}},
    )
    if result.modified_count != 1:
        raise HTTPException(400, "Invalid or expired reset token")

    reset_doc = await db.password_reset_tokens.find_one({"token": body.token})
    if not reset_doc:
        raise HTTPException(400, "Invalid or expired reset token")

    user_id = reset_doc["user_id"]
    password_hash = hash_password(body.new_password)
    await db.auth_users.update_one(_auth_user_filter(user_id), {"$set": {"password_hash": password_hash}})
    await revoke_user_refresh_tokens(db, user_id, reason="password_reset")
    return {"success": True}


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, body: AdminResetPasswordRequest, user: dict = Depends(require_role("owner", "admin"))):
    if not _can_administer_auth(user):
        raise HTTPException(403, "Only owner or IT tech admin can reset user passwords")
    db = get_db()
    auth = await db.auth_users.find_one(_auth_user_filter(user_id))
    if not auth:
        raise HTTPException(404, "User not found")
    new_password = body.new_password or f"EduFlow-{uuid.uuid4().hex[:10]}"
    await db.auth_users.update_one(
        _auth_user_filter(user_id),
        {"$set": {"password_hash": hash_password(new_password), "must_change_password": True, "password_reset_by": user["id"], "password_reset_at": datetime.now(timezone.utc).isoformat()}},
    )
    await revoke_user_refresh_tokens(db, user_id, reason="admin_password_reset")
    return {"success": True, "temporary_password": new_password}


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
    await db.auth_users.update_one(_auth_user_filter(user_id), {"$set": {"is_active": True, "unlocked_by": user["id"], "unlocked_at": datetime.now(timezone.utc).isoformat()}})
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
