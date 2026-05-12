from __future__ import annotations

"""
Auth routes — Password login and JWT token management.

Endpoints:
  POST /api/auth/login           — Username/password login (primary)
  GET  /api/auth/me              — Get current user profile from JWT
  GET  /api/auth/seed-status     — Check seed data counts (public)
"""

import re
import logging
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, validator
from fastapi import APIRouter, HTTPException, Request, Response

from database import get_db
from middleware.auth import (
    create_jwt,
    get_current_user,
    verify_password,
)
from services.auth_tokens import (
    clear_refresh_cookie,
    consume_refresh_token,
    get_refresh_cookie,
    issue_refresh_token,
    revoke_refresh_token,
    set_refresh_cookie,
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
        raise HTTPException(401, "Invalid username or password")
    if auth.get("is_active") is False or auth.get("user_info", {}).get("is_active") is False:
        await _record_failed_attempt(db, attempt_key)
        raise HTTPException(401, "Invalid username or password")

    stored_password = auth.get("password_hash", "")

    if not stored_password or not stored_password.startswith("$2"):
        await _record_failed_attempt(db, attempt_key)
        raise HTTPException(401, "Invalid username or password")

    if not verify_password(password, stored_password):
        await _record_failed_attempt(db, attempt_key)
        raise HTTPException(401, "Invalid username or password")

    # Successful login — clear attempts
    await db.login_attempts.delete_one({"key": attempt_key})

    jwt_payload, user_info = _jwt_payload_from_auth(auth)

    token = create_jwt(jwt_payload)
    refresh_token = await issue_refresh_token(db, jwt_payload["user_id"], request)
    set_refresh_cookie(response, refresh_token)

    logger.info(f"Login success: {username} (role={user_info.get('role', '?')})")

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
