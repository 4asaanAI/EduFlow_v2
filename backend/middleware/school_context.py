"""School context middleware — injects per-request school_id from JWT."""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from database import get_raw_db
from middleware.auth import JWT_SECRET, JWT_ALGORITHM
from tenant import _school_id_var

logger = logging.getLogger(__name__)

# R14.2 (P-M5): Per-process TTL cache for school deactivation status.
# Bounds the per-request DB round-trip on the hot path to at most one lookup
# per school per SCHOOL_STATUS_CACHE_TTL_SECONDS.
#
# DELIBERATE POSTURE: FAIL-OPEN on DB exception.
# If the Mongo lookup throws (network blip, timeout, replica failover) we let
# the request through rather than returning a 402. Rationale: the deactivation
# gate is an operator-controlled billing/safety brake; a stuck-closed brake
# caused by transient DB errors would be its own availability incident. We log
# a WARNING so ops can detect a sustained degradation. See deployment-runbook.md §9.
SCHOOL_STATUS_CACHE_TTL_SECONDS = 30
_school_status_cache: dict[str, Tuple[Optional[str], float]] = {}


def _get_cached_school_status(school_id: str) -> Optional[str]:
    entry = _school_status_cache.get(school_id)
    if entry is None:
        return None
    status, expiry = entry
    if time.monotonic() > expiry:
        _school_status_cache.pop(school_id, None)
        return None
    return status


def _set_cached_school_status(school_id: str, status: Optional[str]) -> None:
    _school_status_cache[school_id] = (status, time.monotonic() + SCHOOL_STATUS_CACHE_TTL_SECONDS)


def _clear_school_status_cache(school_id: Optional[str] = None) -> None:
    """Invalidate the cache. Pass school_id to clear one entry; None clears all."""
    if school_id is None:
        _school_status_cache.clear()
    else:
        _school_status_cache.pop(school_id, None)

# Paths that bypass school-context injection entirely (health + login only).
# /api/auth/refresh and /api/auth/logout are NOT in _SKIP_PATHS — they go through the
# full middleware so school context is injected, but the deactivated-school 402 gate
# explicitly exempts them (inner bypass below) so deactivated users can sign out cleanly.
_SKIP_PATHS = {
    "/api/health",
    "/api/health/ready",
    "/api/health/system",
    "/api/auth/login",
    "/api/docs",
    "/api/openapi.json",
}


class SchoolContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            from jose import jwt as _jose_jwt
            from jose.exceptions import ExpiredSignatureError
            token = auth_header[7:]
            try:
                payload = _jose_jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            except ExpiredSignatureError:
                # Still extract school_id from expired token so context is correct for the 401 path
                payload = _jose_jwt.decode(
                    token, JWT_SECRET, algorithms=[JWT_ALGORITHM], options={"verify_exp": False}
                )
            school_id = payload.get("school_id")
        except Exception:
            return await call_next(request)

        if not school_id:
            return await call_next(request)

        token_val = _school_id_var.set(school_id)
        try:
            db = get_raw_db()
            if db is not None:
                cached_status = _get_cached_school_status(school_id)
                if cached_status is None:
                    try:
                        school_doc = await db.schools.find_one(
                            {"school_id": school_id}, {"status": 1, "_id": 0}
                        )
                        cached_status = school_doc.get("status") if school_doc else "active"
                        _set_cached_school_status(school_id, cached_status)
                    except Exception:
                        # DELIBERATE FAIL-OPEN (see module docstring above).
                        logger.warning(
                            "school status check failed school_id=%s — failing open", school_id, exc_info=True
                        )
                        cached_status = "active"

                if cached_status == "deactivated":
                    # Allow refresh/logout so deactivated users can sign out cleanly
                    if request.url.path not in {"/api/auth/refresh", "/api/auth/logout"}:
                        return JSONResponse(
                            status_code=402,
                            content={
                                "detail": "School account is deactivated. Contact support."
                            },
                        )
            return await call_next(request)
        finally:
            _school_id_var.reset(token_val)
