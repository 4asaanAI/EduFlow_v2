from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from database import get_db

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 5 * 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def issue_confirm_token(
    *,
    action: str,
    params: dict[str, Any],
    user_id: str,
    session_id: str,
    db=None,
) -> str:
    """Create a one-time confirmation token for a pending AI write dispatch."""
    token = str(uuid.uuid4())
    expires_at = _now() + timedelta(seconds=TOKEN_TTL_SECONDS)
    token_db = db or get_db()
    document = {
        "token": token,
        "action": action,
        "params": params,
        "user_id": user_id,
        "session_id": session_id,
        "expires_at": expires_at,
        "used": False,
        "created_at": _now(),
    }

    try:
        await token_db.confirm_tokens.insert_one({**document, "_id": token})
    except Exception as exc:
        logger.error("failed to issue AI confirmation token", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Confirmation validation is unavailable. Write action rejected.",
        ) from exc

    return token


async def consume_confirm_token(
    *,
    token: str,
    user_id: str,
    session_id: str,
    db=None,
) -> dict[str, Any]:
    """
    Atomically marks a confirmation token used before action execution.

    Replays fail closed. Expired or missing tokens return 400, wrong-session
    tokens return 401, and already-used tokens return 409.
    """
    if not token:
        raise HTTPException(status_code=400, detail="Confirmation token is required")

    token_db = db or get_db()
    now = _now()

    try:
        update = await token_db.confirm_tokens.update_one(
            {
                "token": token,
                "user_id": user_id,
                "session_id": session_id,
                "used": False,
                "expires_at": {"$gt": now},
            },
            {"$set": {"used": True, "confirmed_at": now}},
        )
    except Exception as exc:
        logger.error("failed to validate AI confirmation token", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Confirmation validation is unavailable. Write action rejected.",
        ) from exc

    if getattr(update, "modified_count", 0) == 1:
        doc = await token_db.confirm_tokens.find_one({"token": token})
        if not doc:
            raise HTTPException(status_code=400, detail="Confirmation token not found")
        return doc

    try:
        doc = await token_db.confirm_tokens.find_one({"token": token})
    except Exception as exc:
        logger.error("failed to inspect rejected AI confirmation token", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Confirmation validation is unavailable. Write action rejected.",
        ) from exc

    if not doc:
        raise HTTPException(status_code=400, detail="Confirmation token not found")
    if doc.get("used"):
        raise HTTPException(status_code=409, detail="Confirmation token has already been used")
    if doc.get("user_id") != user_id or doc.get("session_id") != session_id:
        raise HTTPException(status_code=401, detail="Confirmation token does not belong to this session")
    if doc.get("expires_at") and doc["expires_at"] <= now:
        raise HTTPException(status_code=400, detail="Confirmation token has expired")

    raise HTTPException(status_code=400, detail="Confirmation token is invalid")


async def audit_ai_dispatch(
    *,
    tool_name: str,
    params: dict[str, Any],
    user_id: str,
    session_id: str,
    confirmed_at: datetime | None,
    result: dict[str, Any] | None = None,
    db=None,
) -> None:
    audit_db = db or get_db()
    now = _now()
    document = {
        "id": f"ai-dispatch-{uuid.uuid4()}",
        "tool_name": tool_name,
        "params": params,
        "user_id": user_id,
        "session_id": session_id,
        "confirmed_at": confirmed_at,
        "executed_at": now,
        "success": bool(result.get("success", True)) if isinstance(result, dict) else True,
    }

    try:
        await audit_db.ai_dispatch_audit_log.insert_one({**document, "_id": document["id"]})
    except Exception:
        logger.error("failed to write AI dispatch audit log", exc_info=True)
