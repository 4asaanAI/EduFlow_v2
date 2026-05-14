"""Refresh-token persistence and cookie helpers."""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response

logger = logging.getLogger(__name__)


REFRESH_COOKIE_NAME = "eduflow_refresh_token"
REFRESH_TOKEN_TTL_DAYS = 7
REFRESH_TOKEN_TTL_SECONDS = REFRESH_TOKEN_TTL_DAYS * 24 * 60 * 60


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def cookie_secure() -> bool:
    return os.environ.get("ENVIRONMENT") == "production"


# Part 1 hardening: cookie path widened from "/api/auth" to "/".
# Rationale: future endpoints outside /api/auth (e.g. /api/account) need the
# refresh cookie to be re-issued automatically. Security is preserved by the
# HttpOnly + Secure + SameSite=Strict trio, which already prevents reuse from
# malicious origins regardless of path scope.
REFRESH_COOKIE_PATH = "/"

# Part 1.5 Patch F: the cookie path widened from /api/auth → / in Part 1.
# Pre-deploy users still have a stale cookie at /api/auth. Browsers happily
# store both; the resulting "two cookies, one named eduflow_refresh_token"
# state caused subtle logout/login loops. Until the 7-day TTL has expired
# everywhere we evict both paths on every clear / refresh-entry call.
# Safe to remove this dual-clear after 2026-08-15 (deploy day + 7d + buffer).
LEGACY_REFRESH_COOKIE_PATH = "/api/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_TOKEN_TTL_SECONDS,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path=REFRESH_COOKIE_PATH,
    )
    # Evict any phantom cookie left over from the old /api/auth path.
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path=LEGACY_REFRESH_COOKIE_PATH,
    )


def clear_legacy_refresh_cookie(response: Response) -> None:
    """Evict the /api/auth-scoped phantom cookie on every refresh attempt.

    Called at the entry of /api/auth/refresh so a stale path-scoped cookie
    does not race the new one. Safe to remove after 2026-08-15.
    """
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path=LEGACY_REFRESH_COOKIE_PATH,
    )


def get_refresh_cookie(request: Request) -> str:
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(401, "Refresh token missing")
    return token


async def issue_refresh_token(db, user_id: str, request: Request | None = None) -> str:
    token = new_refresh_token()
    now = utc_now()
    expires_at = now + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    await db.refresh_tokens.insert_one(
        {
            "token_hash": hash_refresh_token(token),
            "user_id": user_id,
            "created_at": now,
            "expires_at": expires_at,
            "revoked_at": None,
            "user_agent": request.headers.get("user-agent") if request else None,
            "ip": request.client.host if request and request.client else None,
        }
    )
    return token


async def consume_refresh_token(db, raw_token: str) -> dict:
    token_hash = hash_refresh_token(raw_token)
    now = utc_now()
    record = await db.refresh_tokens.find_one({"token_hash": token_hash})
    if not record:
        raise HTTPException(401, "Invalid refresh token")
    if record.get("revoked_at"):
        raise HTTPException(401, "Refresh token revoked")
    expires_at = record.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        raise HTTPException(401, "Refresh token expired")

    result = await db.refresh_tokens.update_one(
        {"_id": record["_id"], "revoked_at": None},
        {"$set": {"revoked_at": now, "revoked_reason": "rotated"}},
    )
    if result.modified_count != 1:
        raise HTTPException(401, "Refresh token already used")

    return record


async def revoke_refresh_token(db, raw_token: str, reason: str = "logout") -> int:
    """Revoke a refresh token by raw value. Returns modified_count (0 or 1).

    Part 1.5 Patch L: callers can now distinguish "revoked successfully" from
    "token unknown / already revoked" — useful for logout audit, and for
    surfacing password-reset misroutes that previously absorbed silently.
    """
    result = await db.refresh_tokens.update_one(
        {"token_hash": hash_refresh_token(raw_token), "revoked_at": None},
        {"$set": {"revoked_at": utc_now(), "revoked_reason": reason}},
    )
    if result.modified_count == 0:
        logger.debug("revoke_refresh_token: no active token matched (reason=%s)", reason)
    return result.modified_count


async def revoke_user_refresh_tokens(db, user_id: str, reason: str = "user_deactivated") -> int:
    result = await db.refresh_tokens.update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": utc_now(), "revoked_reason": reason}},
    )
    return result.modified_count
