"""
Shared auth middleware for EduFlow.

Provides JWT-based authentication with dev-mode header fallback.
All route files import get_current_user from here instead of defining locally.
"""

import os
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Depends
from jose import jwt, JWTError, ExpiredSignatureError
import bcrypt

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    if os.environ.get("ENVIRONMENT") == "production":
        raise ValueError("JWT_SECRET environment variable is required in production")
    # Part 1 hardening: dev secret is now per-process random instead of a
    # committed constant. Prevents accidental cross-environment token reuse;
    # tokens issued by one dev process are invalid for any other. Tests can
    # still set JWT_SECRET explicitly via env var.
    JWT_SECRET = secrets.token_urlsafe(48)
    logger.warning(
        "JWT_SECRET not set — using a per-process random secret. "
        "Tokens issued by this process will not be valid after restart. "
        "Set JWT_SECRET in .env to persist sessions across restarts."
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60


# ─── JWT helpers ─────────────────────────────────────────────────────────────

def create_jwt(payload: dict) -> str:
    """
    Create a short-lived JWT access token.
    payload should include: user_id, role, name, and optionally sub_category, branch_id
    """
    to_encode = {**payload}
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRY_MINUTES)
    to_encode["exp"] = expire
    to_encode["iat"] = datetime.now(timezone.utc)
    token = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt(token: str) -> dict:
    """
    Decode and validate a JWT token. Returns user dict.
    Raises HTTPException 401 if invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # Build user dict from payload
        user = {
            "id": payload.get("user_id", ""),
            "role": payload.get("role", ""),
            "name": payload.get("name", ""),
        }
        # Include optional fields if present
        if payload.get("sub_category"):
            user["sub_category"] = payload["sub_category"]
        if payload.get("branch_id"):
            user["branch_id"] = payload["branch_id"]
        if payload.get("initials"):
            user["initials"] = payload["initials"]
        if payload.get("phone"):
            user["phone"] = payload["phone"]
        return user
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Password helpers ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ─── Core auth dependency ────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict:
    """
    Extract current user from JWT in Authorization: Bearer <token> header.
    Raises 401 if no valid token found.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return decode_jwt(token)

    raise HTTPException(status_code=401, detail="Not authenticated")


# ─── Role-based access dependency ────────────────────────────────────────────

def require_role(*roles: str):
    """
    FastAPI dependency that checks if the current user has one of the allowed roles.
    Usage:
        @router.get("/admin-only", dependencies=[Depends(require_role("owner", "admin"))])
        async def admin_endpoint(user: dict = Depends(require_role("owner", "admin"))):
            ...
    Returns the user dict so handlers don't need a separate get_current_user call.
    Error message does NOT leak the allowed-role list — clients only learn
    "forbidden", not which roles would have worked.
    """
    def dependency(request: Request):
        user = get_current_user(request)
        if user["role"] not in roles:
            logger.info(
                "role check failed: role=%s required=%s path=%s",
                user.get("role"), roles, request.url.path,
            )
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dependency


def require_owner_or_principal(request: Request):
    """Dependency: owner or admin-with-sub_category=principal only.

    Codifies the most common 'managerial decision-maker' gate (announcements,
    leave approvals, attendance reviews) that was previously inline-duplicated
    across at least five routes.
    """
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    if user.get("role") == "admin" and user.get("sub_category") == "principal":
        return user
    logger.info(
        "owner/principal gate failed: role=%s sub=%s path=%s",
        user.get("role"), user.get("sub_category"), request.url.path,
    )
    raise HTTPException(status_code=403, detail="Forbidden")


def require_owner(request: Request):
    """Dependency: owner role only. Replaces _require_owner inlined in routes/operator.py."""
    user = get_current_user(request)
    if user.get("role") != "owner":
        logger.info(
            "owner-only gate failed: role=%s path=%s",
            user.get("role"), request.url.path,
        )
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
