"""Operator endpoints — owner-only platform controls.

Currently holds AI rate-limit override management and per-session AI action
count read API used by Story 7-43 (operator health dashboard).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from database import get_db, get_raw_db, get_school_id
from middleware.auth import hash_password, require_owner
from services.ai_rate_limiter import get_current_count, resolve_limit
from services.audit_service import write_audit
from services.email_service import send_operator_completion_email, send_welcome_email
from tenant import scoped_filter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/operator", tags=["operator"])

# Part 1.5 Patch O: must match the canonical top-level user `role` field that
# resolve_limit / get_current_count look up. `principal`/`accountant` were
# previously allowed as override keys but no user has role=principal — those
# values are sub_categories, and an override targeting them silently never
# matches. If a school needs a sub_category-specific ceiling the schema needs
# a new (role, sub_category) tuple — out of scope for Part 1.5.
ALLOWED_ROLES = {"owner", "admin", "teacher", "student"}

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
_ALPHANUM = string.ascii_letters + string.digits


# ─── School onboarding helpers ─────────────────────────────────────────────────

def _generate_temp_password(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHANUM) for _ in range(length))


def _make_initials(name: str) -> str:
    words = name.strip().split()
    return "".join(w[0].upper() for w in words[:2]) if words else "SC"


async def _send_operator_slack(school_name: str) -> None:
    webhook_url = os.environ.get("OPERATOR_SLACK_WEBHOOK_URL")
    if not webhook_url:
        return
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(webhook_url, json={"text": f"School {school_name} onboarding complete."})


class CreateSchoolRequest(BaseModel):
    school_name: str
    school_id: str
    owner_email: str
    plan_tier: Literal["starter", "pro"]


# ─── School onboarding endpoints ───────────────────────────────────────────────

@router.post("/schools")
async def create_school(
    body: CreateSchoolRequest,
    user: dict = Depends(require_owner),
):
    """Create a new school with an isolated owner account. Owner-only."""
    school_id = body.school_id.strip()
    school_name = body.school_name.strip()
    owner_email = body.owner_email.strip()
    plan_tier = body.plan_tier.strip()

    if not SLUG_RE.match(school_id):
        raise HTTPException(
            status_code=400,
            detail="school_id must be 3-50 chars, lowercase alphanumeric and hyphens only",
        )
    if not school_name:
        raise HTTPException(status_code=400, detail="school_name is required")
    if not owner_email or "@" not in owner_email:
        raise HTTPException(status_code=400, detail="owner_email must be a valid email address")

    raw_db = get_raw_db()

    existing = await raw_db.schools.find_one({"school_id": school_id})
    if existing:
        raise HTTPException(status_code=409, detail="school_id already exists")

    now = datetime.now(timezone.utc)
    school_doc_id = str(uuid.uuid4())
    owner_user_id = str(uuid.uuid4())
    owner_auth_id = str(uuid.uuid4())
    temp_password = _generate_temp_password()

    school_doc = {
        "id": school_doc_id,
        "school_name": school_name,
        "school_id": school_id,
        "owner_email": owner_email,
        "plan_tier": plan_tier,
        "status": "onboarding",
        "created_at": now.isoformat(),
        "created_by": user.get("id"),
    }
    try:
        await raw_db.schools.insert_one({**school_doc, "_id": school_doc_id})
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="school_id already exists")
    except Exception as exc:
        logger.exception("schools insert failed school_id=%s", school_id)
        raise HTTPException(status_code=500, detail="Failed to create school") from exc

    settings_doc = {
        "id": "main",
        "school_name": school_name,
        "schoolId": school_id,
        "created_at": now.isoformat(),
    }
    try:
        await raw_db.school_settings.insert_one(settings_doc)
    except Exception as exc:
        logger.exception("school_settings insert failed school_id=%s", school_id)
        await raw_db.schools.delete_one({"school_id": school_id})
        raise HTTPException(status_code=500, detail="Failed to create school settings") from exc

    owner_auth_doc = {
        "id": owner_auth_id,
        "username": owner_email,
        "username_lower": owner_email.lower(),
        "password_hash": hash_password(temp_password),
        "role": "owner",
        "schoolId": school_id,
        "is_active": True,
        "must_change_password": True,
        "user_info": {
            "id": owner_user_id,
            "name": f"{school_name} Owner",
            "role": "owner",
            "initials": _make_initials(school_name),
            "schoolId": school_id,
        },
    }
    try:
        await raw_db.auth_users.insert_one(owner_auth_doc)
    except Exception as exc:
        logger.exception("auth_users insert failed school_id=%s", school_id)
        await raw_db.schools.delete_one({"school_id": school_id})
        await raw_db.school_settings.delete_one({"schoolId": school_id})
        raise HTTPException(status_code=500, detail="Failed to create owner account") from exc

    try:
        await asyncio.to_thread(send_welcome_email, owner_email, owner_email, temp_password)
    except Exception:
        logger.warning("send_welcome_email failed school_id=%s email=%s", school_id, owner_email, exc_info=True)

    return {
        "success": True,
        "data": {
            "school_id": school_id,
            "owner_username": owner_email,
            "temporary_password": temp_password,
        },
    }


@router.get("/schools/{school_id}/onboarding-status")
async def get_onboarding_status(
    school_id: str,
    user: dict = Depends(require_owner),
):
    """Return per-step onboarding checklist for a school. Owner-only."""
    if not SLUG_RE.match(school_id):
        raise HTTPException(status_code=400, detail="Invalid school_id format")

    raw_db = get_raw_db()

    school_doc, staff_count, class_count, student_count, fee_count = await asyncio.gather(
        raw_db.schools.find_one({"school_id": school_id}, {"_id": 0}),
        raw_db.staff.count_documents({"schoolId": school_id}),
        raw_db.classes.count_documents({"schoolId": school_id}),
        raw_db.students.count_documents({"schoolId": school_id}),
        raw_db.fee_structures.count_documents({"schoolId": school_id}),
    )

    if not school_doc:
        raise HTTPException(status_code=404, detail="School not found")

    steps = {
        "profile_created": True,
        "first_staff_added": staff_count > 0,
        "first_class_configured": class_count > 0,
        "first_student_imported": student_count > 0,
        "first_fee_record_created": fee_count > 0,
    }
    completed = all(steps.values())
    current_status = school_doc.get("status", "onboarding")

    if completed and current_status == "onboarding":
        try:
            await raw_db.schools.update_one(
                {"school_id": school_id},
                {"$set": {"status": "active", "activated_at": datetime.now(timezone.utc).isoformat()}},
            )
            current_status = "active"
        except Exception:
            logger.warning("failed to update school status to active school_id=%s", school_id, exc_info=True)

        if current_status == "active":
            school_name = school_doc.get("school_name", school_id)
            try:
                await asyncio.to_thread(send_operator_completion_email, school_name)
            except Exception:
                logger.warning("operator completion email failed school_id=%s", school_id, exc_info=True)
            try:
                await _send_operator_slack(school_name)
            except Exception:
                logger.warning("operator slack notification failed school_id=%s", school_id, exc_info=True)

    return {
        "success": True,
        "data": {
            "school_id": school_id,
            "school_name": school_doc.get("school_name"),
            "status": current_status,
            "steps": steps,
            "completed": completed,
        },
    }


@router.patch("/schools/{school_id}/deactivate")
async def deactivate_school(
    school_id: str,
    user: dict = Depends(require_owner),
):
    """Deactivate a school. Owner-only. Full 402 enforcement is Story 7-45."""
    if not SLUG_RE.match(school_id):
        raise HTTPException(status_code=400, detail="Invalid school_id format")

    raw_db = get_raw_db()

    school_doc = await raw_db.schools.find_one({"school_id": school_id})
    if not school_doc:
        raise HTTPException(status_code=404, detail="School not found")

    await raw_db.schools.update_one(
        {"school_id": school_id},
        {"$set": {"status": "deactivated", "deactivated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Invalidate refresh tokens for all users of this school so they can't re-authenticate.
    # refresh_tokens has no schoolId — look up user_ids via auth_users first.
    school_users = await raw_db.auth_users.find(
        {"schoolId": school_id}, {"user_info": 1, "id": 1, "user_id": 1, "_id": 0}
    ).to_list(5000)
    user_ids = [
        (u.get("user_info") or {}).get("id") or u.get("id") or u.get("user_id")
        for u in school_users
        if (u.get("user_info") or {}).get("id") or u.get("id") or u.get("user_id")
    ]
    if user_ids:
        await raw_db.refresh_tokens.delete_many({"user_id": {"$in": user_ids}})
        logger.info(
            "refresh_tokens cleared for deactivated school school_id=%s users=%d",
            school_id,
            len(user_ids),
        )
    await write_audit(
        raw_db,
        action="school_deactivated",
        entity_id=school_id,
        collection="schools",
        changed_by=user.get("id", ""),
        changed_by_role=user.get("role", "owner"),
        school_id=school_id,
        changes={"status": "deactivated"},
    )
    return {"success": True, "data": {"school_id": school_id, "status": "deactivated"}}


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

    if "expires_at" not in body:
        raise HTTPException(
            status_code=400,
            detail="expires_at is required; use null for a permanent (non-expiring) override",
        )
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


# ─── Platform Health helpers ──────────────────────────────────────────────────

async def _ph_db_check(db) -> str:
    try:
        await db.command("ping")
        return "ok"
    except Exception:
        logger.warning("platform_health db check failed", exc_info=True)
        return "error"


async def _ph_ai_check() -> str:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        return "degraded"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(endpoint.rstrip("/"))
        return "ok" if response.status_code < 500 else "degraded"
    except Exception:
        logger.warning("platform_health ai check degraded", exc_info=True)
        return "degraded"


async def _ph_s3_check() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME") or os.environ.get("S3_BUCKET")
    if not bucket:
        return "not_configured"
    try:
        def _call():
            from services.s3_storage import get_s3_client
            get_s3_client().list_objects_v2(Bucket=bucket, MaxKeys=1)

        await asyncio.wait_for(asyncio.to_thread(_call), timeout=3.0)
        return "ok"
    except Exception:
        logger.warning("platform_health s3 check degraded", exc_info=True)
        return "degraded"


async def _ph_sms_check() -> str:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid:
        return "not_configured"
    if not token:
        return "degraded"
    try:
        async with httpx.AsyncClient(timeout=3.0, auth=(sid, token)) as client:
            response = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
        return "ok" if response.status_code < 500 else "degraded"
    except Exception:
        logger.warning("platform_health sms check degraded", exc_info=True)
        return "degraded"


@router.get("/platform-health")
async def get_platform_health(user: dict = Depends(require_owner)):
    """Aggregated platform health for the operator dashboard (owner-only)."""
    db = get_db()
    school_id = get_school_id()

    # ── Service checks (run concurrently) ──────────────────────────────────
    db_status, ai_status, s3_status, sms_status = await asyncio.gather(
        _ph_db_check(db),
        _ph_ai_check(),
        _ph_s3_check(),
        _ph_sms_check(),
    )

    checks = {"db": db_status, "ai": ai_status, "s3": s3_status, "sms": sms_status}
    if db_status == "error":
        overall = "down"
    elif any(v == "degraded" for v in checks.values()):
        overall = "degraded"
    else:
        overall = "ok"

    # ── Token pool ──────────────────────────────────────────────────────────
    branch_id = user.get("branch_id")
    balance_doc = await db.token_balances.find_one({"branch_id": branch_id}, {"_id": 0}) or {}
    token_pool = {
        "school_topup_pool": balance_doc.get("school_topup_pool", 0),
        "subscription_status": balance_doc.get("subscription_status"),
        "subscription_plan": balance_doc.get("subscription_plan"),
    }

    # ── Fee sync last job (school-wide, not branch-scoped) ──────────────────
    # branch-scope: intentional — fee sync is a school-wide operation
    jobs = await db.fee_sync_jobs.find(
        scoped_filter({}, school_id),
        {"_id": 0},
    ).sort("started_at", -1).to_list(1)
    job = jobs[0] if jobs else None
    fee_sync_last = None
    if job:
        fee_sync_last = {
            "job_id": job.get("id"),
            "status": job.get("status"),
            "started_at": job.get("started_at"),
            "completed_at": job.get("completed_at"),
        }

    # ── Error rate (last 60 min, school-wide) ───────────────────────────────
    # branch-scope: intentional — operator health is a school-wide aggregate view
    now = datetime.now(timezone.utc)
    sixty_min_ago = now - timedelta(minutes=60)
    error_query = scoped_filter(
        {
            "created_at": {"$gte": sixty_min_ago},
            "action": {"$regex": "fail|error", "$options": "i"},
        },
        school_id,
    )
    error_count = await db.audit_logs.count_documents(error_query)

    # ── Active user count (school-wide) ────────────────────────────────────
    # branch-scope: intentional — operator health is a school-wide aggregate view
    active_user_count = await db.auth_users.count_documents(
        scoped_filter({"is_active": True}, school_id)
    )

    return {
        "success": True,
        "data": {
            "service_checks": {**checks, "overall": overall},
            "token_pool": token_pool,
            "fee_sync_last": fee_sync_last,
            "error_rate": {
                "error_count": error_count,
                "window_minutes": 60,
                "since": sixty_min_ago.isoformat(),
            },
            "active_user_count": active_user_count,
            "generated_at": now.isoformat(),
        },
    }
