from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from database import get_db

logger = logging.getLogger(__name__)


def _hmac_key() -> bytes:
    """Resolve the signing key for the plan-integrity MAC (XM6).

    Keyed with the same `JWT_SECRET` used for auth so a tampered persisted plan
    cannot be re-MAC'd by anyone without the server secret. Read via
    `middleware.auth` (which handles dev generation/caching) with an env
    fallback, at call time, so a test-set secret is honoured."""
    try:
        from middleware import auth as _auth

        if getattr(_auth, "JWT_SECRET", None):
            return _auth.JWT_SECRET.encode("utf-8")
    except Exception:  # pragma: no cover - defensive; auth import should not fail
        pass
    return (os.environ.get("JWT_SECRET") or "eduflow-dev-plan-mac").encode("utf-8")

TOKEN_TTL_SECONDS = 5 * 60

# Epic E (AD3/P4): the on-disk plan/token schema version. Bump only on a
# breaking change to the stored `plan` shape or the hash canonicalization, so
# a token issued under an older planner is recognisably stale.
PLAN_SCHEMA_VERSION = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _intent_summary(doc: dict[str, Any]) -> dict[str, Any]:
    """PII-free echo of what the token was going to do (XM6/AC3).

    Attached to post-consume validation-failure responses so the frontend can
    offer a one-tap "ask again" without the user re-typing. Only tool/action
    labels are echoed — never resolved params (which may carry student PII)."""
    plan = doc.get("plan")
    if plan:
        tools = [
            s.get("tool")
            for s in plan
            if s.get("kind", "write") == "write" and s.get("tool")
        ]
        return {"kind": "plan", "tools": tools}
    return {"kind": "action", "action": doc.get("action")}


def compute_plan_hash(
    plan: list[dict[str, Any]] | None,
    *,
    school_id: str | None,
    branch_id: str | None,
) -> str:
    """Canonical HMAC-SHA256 over the resolved plan + tenant binding (AD3/P4/XM6).

    The SAME helper is used at issue and consume so a tampered persisted plan
    (DB-level edit, mismatched tenant) is detected. Prior to XM6 this was an
    UNKEYED sha256 stored beside the plan — anyone able to edit the stored plan
    could recompute a matching digest. It is now an HMAC keyed with the server's
    `JWT_SECRET`, so a valid MAC cannot be forged without the secret.
    Canonicalization is a sorted-key, separator-tight JSON dump; entity IDs
    already live inside each step's resolved `params`, so they are covered.
    `default=str` keeps it total for any stray datetime/UUID that slips into
    params.
    """
    payload = {
        "plan": plan or [],
        "school_id": school_id,
        "branch_id": branch_id,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), default=str
    )
    return hmac.new(_hmac_key(), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


async def issue_confirm_token(
    *,
    action: str,
    params: dict[str, Any],
    user_id: str,
    session_id: str,
    school_id: str | None = None,
    branch_id: str | None = None,
    plan: list[dict[str, Any]] | None = None,
    db=None,
) -> str:
    """Create a one-time confirmation token for a pending AI write dispatch.

    Epic E (AD3): when a multi-step `plan` is supplied the token additionally
    binds the ordered, resolved plan + its `plan_hash` + `schema_version`. A
    token issued WITHOUT a plan is a legacy single-action token and consumes as
    a length-1 plan (back-compat by data, not branching).
    """
    token = str(uuid.uuid4())
    expires_at = _now() + timedelta(seconds=TOKEN_TTL_SECONDS)
    token_db = db or get_db()
    document = {
        "token": token,
        "action": action,
        "params": params,
        "user_id": user_id,
        "session_id": session_id,
        "school_id": school_id,
        "branch_id": branch_id,
        "expires_at": expires_at,
        "used": False,
        "created_at": _now(),
    }
    if plan is not None:
        document["plan"] = plan
        document["plan_hash"] = compute_plan_hash(
            plan, school_id=school_id, branch_id=branch_id
        )
        document["schema_version"] = PLAN_SCHEMA_VERSION

    try:
        await token_db.confirm_tokens.insert_one({**document, "_id": token})
    except Exception as exc:
        logger.error("failed to issue AI confirmation token", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Confirmation validation is unavailable. Write action rejected.",
        ) from exc

    return token


async def peek_confirm_token(
    *,
    token: str,
    user_id: str,
    session_id: str,
    db=None,
) -> dict[str, Any] | None:
    """Read a confirmation token without consuming it.

    Used by the dispatch path to (1) validate token ownership before
    incrementing the rate-limit counter, and (2) populate audit-log forensic
    context when a request is rejected.

    Returns the token document if it belongs to (user_id, session_id), else
    None. Already-used tokens ARE returned — for replay forensics, the action
    and params remain valuable even after consumption. The caller is
    responsible for treating used tokens correctly (consume_confirm_token
    raises 409 on replay).
    """
    if not token:
        return None
    token_db = db or get_db()
    try:
        doc = await token_db.confirm_tokens.find_one({"token": token})
    except Exception as exc:
        logger.error("failed to peek AI confirmation token", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Confirmation validation is unavailable. Please retry.",
        ) from exc
    if not doc:
        return None
    if doc.get("user_id") != user_id or doc.get("session_id") != session_id:
        return None
    return doc


async def consume_confirm_token(
    *,
    token: str,
    user_id: str,
    session_id: str,
    school_id: str | None = None,
    branch_id: str | None = None,
    db=None,
) -> dict[str, Any]:
    """
    Atomically marks a confirmation token used before action execution.

    Replays fail closed. Expired or missing tokens return 400, wrong-session
    tokens return 401, already-used tokens return 409, and tenant drift
    (school_id/branch_id mismatch) returns 409 to signal the token cannot
    be replayed in this tenant context.
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
                # P11 E8: use $gte so a token expiring exactly at `now` is still
                # accepted (eliminates the 1-second boundary rejection window).
                "expires_at": {"$gte": now},
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
        # P9: Tenant binding check — reject if the request context drifted from
        # the tenant context at token-issue time.
        if school_id is not None and doc.get("school_id") is not None:
            if doc["school_id"] != school_id:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "token_tenant_mismatch",
                        "message": "Confirmation token tenant mismatch",
                        "intent": _intent_summary(doc),
                    },
                )
        if branch_id is not None and doc.get("branch_id") is not None:
            if doc["branch_id"] != branch_id:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "token_tenant_mismatch",
                        "message": "Confirmation token tenant mismatch",
                        "intent": _intent_summary(doc),
                    },
                )
        # Epic E (AD3/P4): plan-hash revalidation. A token carrying a multi-step
        # `plan` must hash to exactly what was stored at issue — a tampered
        # persisted plan (or a tenant the plan was not bound to) is rejected with
        # the distinct `plan_tampered` 409 the frontend maps to "re-confirm".
        # A legacy token (no `plan`) skips this — it consumes as a length-1 plan.
        if doc.get("plan") is not None:
            expected_hash = compute_plan_hash(
                doc.get("plan"),
                school_id=doc.get("school_id"),
                branch_id=doc.get("branch_id"),
            )
            # Constant-time compare — the MAC is a secret-derived value (XM6).
            if not hmac.compare_digest(expected_hash, str(doc.get("plan_hash") or "")):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "plan_tampered",
                        "message": (
                            "The approved plan could not be verified and was "
                            "rejected. Please ask again so a fresh plan can be built."
                        ),
                        # AC3: echo the original intent so the client can re-issue
                        # in one tap (the token is already consumed here).
                        "intent": _intent_summary(doc),
                    },
                )
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
        # AC2: typed reason code so the caller/frontend never string-matches on
        # "expired". The intent echo lets the user re-issue in one tap.
        raise HTTPException(
            status_code=400,
            detail={
                "code": "token_expired",
                "message": "Confirmation token has expired",
                "intent": _intent_summary(doc),
            },
        )

    raise HTTPException(status_code=400, detail="Confirmation token is invalid")


def _infer_success(result: Any) -> bool:
    """Part 2 Patch P4: previously defaulted to True when ``success`` was missing,
    so a tool returning ``{}`` or ``{"error": "x"}`` recorded as a successful
    write. New rule: a dispatch is successful iff the result explicitly says so.
    """
    if not isinstance(result, dict):
        return False
    if result.get("success") is True:
        return True
    status = result.get("status")
    if isinstance(status, str) and status.lower() in ("ok", "success", "succeeded"):
        return True
    return False


async def audit_ai_dispatch_pending(
    *,
    tool_name: str,
    params: dict[str, Any],
    user_id: str,
    session_id: str,
    confirmed_at: datetime | None,
    school_id: str | None = None,
    branch_id: str | None = None,
    dispatch_id: str | None = None,
    db=None,
) -> str:
    """Part 2 Patch P4: write-ahead audit row.

    Insert a ``status='pending'`` row BEFORE the tool runs. The caller updates it
    to success/failure after; if the pre-write fails the caller must NOT execute
    the tool. Returns the audit row id so the caller can update it.
    """
    audit_db = db or get_db()
    now = _now()
    audit_id = dispatch_id or f"ai-dispatch-{uuid.uuid4()}"
    document = {
        "id": audit_id,
        "tool_name": tool_name,
        "params": params,
        "user_id": user_id,
        "session_id": session_id,
        "confirmed_at": confirmed_at,
        "started_at": now,
        "executed_at": None,
        "success": False,
        "status": "pending",
        "rate_limit_hit": False,
        "school_id": school_id,
        "branch_id": branch_id,
    }
    # Allow the insert to raise — caller must abort the tool if audit fails.
    await audit_db.ai_dispatch_audit_log.insert_one({**document, "_id": audit_id})
    return audit_id


async def audit_ai_dispatch_finalize(
    *,
    audit_id: str | None,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    rate_limit_hit: bool = False,
    db=None,
) -> None:
    """Part 2 Patch P4: update the write-ahead row with the dispatch outcome."""
    if audit_id is None:
        return
    audit_db = db or get_db()
    now = _now()
    success = _infer_success(result) if error is None else False
    update = {
        "executed_at": now,
        "success": success,
        "status": "success" if success else "failure",
        "rate_limit_hit": rate_limit_hit,
    }
    if error is not None:
        update["error"] = error
    try:
        await audit_db.ai_dispatch_audit_log.update_one(
            {"id": audit_id}, {"$set": update}
        )
    except Exception:
        logger.error("failed to finalize AI dispatch audit log id=%s", audit_id, exc_info=True)


async def audit_ai_dispatch(
    *,
    tool_name: str,
    params: dict[str, Any],
    user_id: str,
    session_id: str,
    confirmed_at: datetime | None,
    result: dict[str, Any] | None = None,
    rate_limit_hit: bool = False,
    school_id: str | None = None,
    branch_id: str | None = None,
    db=None,
) -> None:
    """Legacy single-shot audit insert.

    Kept for callers (rate-limit-hit path) where there is no pre-execution
    phase. New dispatch flow uses ``audit_ai_dispatch_pending`` +
    ``audit_ai_dispatch_finalize`` so a Mongo failure does not silently drop
    the forensic row of a successful write.
    """
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
        # Part 2 Patch P4: missing-key now resolves to False (was True).
        "success": _infer_success(result),
        "status": "success" if _infer_success(result) else "failure",
        "rate_limit_hit": rate_limit_hit,
        "school_id": school_id,
        "branch_id": branch_id,
    }

    try:
        await audit_db.ai_dispatch_audit_log.insert_one({**document, "_id": document["id"]})
    except Exception:
        logger.error("failed to write AI dispatch audit log", exc_info=True)


async def audit_ai_rate_limit_hit(
    *,
    tool_name: str,
    params: dict[str, Any],
    user_id: str,
    session_id: str,
    limit: int,
    db=None,
) -> None:
    """Write an ai_dispatch_audit_log row for a request rejected by the rate limiter.

    Rate-limited attempts never execute, so executed_at is null and success is
    False. The row carries enough context to forensically reconstruct who tried
    to do what during a suspected compromise.
    """
    audit_db = db or get_db()
    document = {
        "id": f"ai-dispatch-{uuid.uuid4()}",
        "tool_name": tool_name,
        "params": params,
        "user_id": user_id,
        "session_id": session_id,
        "confirmed_at": None,
        "executed_at": None,
        "success": False,
        "rate_limit_hit": True,
        "rate_limit_value": limit,
        "rejected_at": _now(),
    }

    try:
        await audit_db.ai_dispatch_audit_log.insert_one({**document, "_id": document["id"]})
    except Exception:
        logger.error("failed to write AI rate-limit audit log", exc_info=True)
