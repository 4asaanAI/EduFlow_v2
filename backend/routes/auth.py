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
from fastapi import APIRouter, HTTPException, Request

from database import get_db
from middleware.auth import (
    create_jwt,
    get_current_user,
    verify_password,
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

@router.post("/login")
async def login(body: LoginRequest):
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
    auth = await db.auth_users.find_one(
        {"username_lower": username_lower},
        {"_id": 0},
    )

    if not auth:
        # Also try exact match for backward compatibility
        auth = await db.auth_users.find_one(
            {"username": username},
            {"_id": 0},
        )

    if not auth:
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

    user_info = auth.get("user_info", {})

    jwt_payload = {
        "user_id": user_info.get("id", ""),
        "role": user_info.get("role", auth.get("role", "")),
        "name": user_info.get("name", ""),
        "initials": user_info.get("initials", ""),
    }
    if user_info.get("sub_category"):
        jwt_payload["sub_category"] = user_info["sub_category"]
    if user_info.get("branch_id"):
        jwt_payload["branch_id"] = user_info["branch_id"]
    if auth.get("phone"):
        jwt_payload["phone"] = auth["phone"]

    token = create_jwt(jwt_payload)

    logger.info(f"Login success: {username} (role={user_info.get('role', '?')})")

    return {
        "success": True,
        "token": token,
        "user": user_info,
    }


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
