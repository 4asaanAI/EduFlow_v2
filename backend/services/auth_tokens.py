"""Refresh-token persistence and cookie helpers."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response


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


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_TOKEN_TTL_SECONDS,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path="/api/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path="/api/auth",
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


async def revoke_refresh_token(db, raw_token: str, reason: str = "logout") -> None:
    await db.refresh_tokens.update_one(
        {"token_hash": hash_refresh_token(raw_token), "revoked_at": None},
        {"$set": {"revoked_at": utc_now(), "revoked_reason": reason}},
    )


async def revoke_user_refresh_tokens(db, user_id: str, reason: str = "user_deactivated") -> int:
    result = await db.refresh_tokens.update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": utc_now(), "revoked_reason": reason}},
    )
    return result.modified_count
