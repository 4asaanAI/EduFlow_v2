"""Operator endpoints — owner-only platform controls.

Currently holds AI rate-limit override management and per-session AI action
count read API used by Story 7-43 (operator health dashboard).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_owner
from services.ai_rate_limiter import get_current_count, resolve_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operator", tags=["operator"])

# Part 1.5 Patch O: must match the canonical top-level user `role` field that
# resolve_limit / get_current_count look up. `principal`/`accountant` were
# previously allowed as override keys but no user has role=principal — those
# values are sub_categories, and an override targeting them silently never
# matches. If a school needs a sub_category-specific ceiling the schema needs
# a new (role, sub_category) tuple — out of scope for Part 1.5.
ALLOWED_ROLES = {"owner", "admin", "teacher", "student"}


def _parse_iso(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="expires_at must be ISO8601 string or null")
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid expires_at: {exc}") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.patch("/schools/{school_id}/ai-rate-limit")
async def upsert_ai_rate_limit_override(
    school_id: str,
    request: Request,
    user: dict = Depends(require_owner),
):
    """Create or replace the AI rate-limit override for a (school, role) pair.

    Body: { role, limit, reason, expires_at? }. expires_at may be omitted or
    null for a non-expiring override (it can still be removed by writing a
    fresh override later — older rows are ignored once a newer one exists).
    """
    db = get_db()
    body = await request.json()

    role = body.get("role")
    limit_raw = body.get("limit")
    reason = (body.get("reason") or "").strip()

    if role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role; must be one of {sorted(ALLOWED_ROLES)}")
    try:
        limit = int(limit_raw)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="limit must be an integer") from exc
    if limit < 0:
        raise HTTPException(status_code=400, detail="limit must be >= 0")
    if not reason:
        raise HTTPException(status_code=400, detail="reason is required for audit trail")

    expires_at = _parse_iso(body.get("expires_at"))
    now = datetime.now(timezone.utc)

    document = {
        "id": f"airl-override-{uuid.uuid4()}",
        "school_id": school_id,
        "role": role,
        "limit": limit,
        "reason": reason,
        "expires_at": expires_at,
        "created_at": now,
        "created_by": user.get("id"),
    }

    # Mark any prior active overrides for this (school, role) as superseded
    # so the resolver returns exactly one row. Keeps history for audit; avoids
    # unbounded growth of "active" rows and tie-on-created_at indeterminacy.
    try:
        await db.ai_rate_limit_overrides.update_many(
            {"school_id": school_id, "role": role, "superseded": {"$ne": True}},
            {"$set": {"superseded": True, "superseded_at": now}},
        )
    except Exception:
        logger.exception("Failed to supersede prior overrides school=%s role=%s", school_id, role)
        # Continue anyway — resolver's deterministic sort still picks the newest.

    try:
        await db.ai_rate_limit_overrides.insert_one({**document, "_id": document["id"]})
    except Exception as exc:
        logger.exception("ai_rate_limit_overrides insert failed school=%s role=%s", school_id, role)
        raise HTTPException(status_code=500, detail="Failed to persist override") from exc

    effective = await resolve_limit(role=role, school_id=school_id, db=db)
    return {
        "success": True,
        "data": {
            "override_id": document["id"],
            "school_id": school_id,
            "role": role,
            "limit": limit,
            "effective_limit": effective,
            "expires_at": expires_at.isoformat() if expires_at else None,
        },
    }


@router.get("/ai-action-counts")
async def get_ai_action_counts(
    user_id: str,
    session_id: str,
    operator: dict = Depends(require_owner),
):
    """Return the current-hour AI write count + configured limit for a session.

    Owner-only. Used by Story 7-43 platform health dashboard.
    """
    db = get_db()

    target = await db.auth_users.find_one({"$or": [{"id": user_id}, {"user_info.id": user_id}]})
    target_info = (target or {}).get("user_info") or {}
    target_role = target_info.get("role") or (target or {}).get("role") or ""
    target_school = target_info.get("schoolId") or (target or {}).get("schoolId")

    count_doc = await get_current_count(user_id=user_id, session_id=session_id, db=db)
    effective_limit = await resolve_limit(role=target_role, school_id=target_school, db=db)

    return {
        "success": True,
        "data": {
            **count_doc,
            "role": target_role,
            "school_id": target_school,
            "limit": effective_limit,
            "queried_by": operator.get("id"),
        },
    }
