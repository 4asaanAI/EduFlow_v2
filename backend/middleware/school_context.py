"""School context middleware — injects per-request school_id from JWT."""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from database import get_raw_db
from middleware.auth import JWT_SECRET, JWT_ALGORITHM
from tenant import _school_id_var

logger = logging.getLogger(__name__)

# Paths that bypass school-context injection entirely (health + login/password-reset only).
# /api/auth/refresh and /api/auth/logout are NOT in _SKIP_PATHS — they go through the
# full middleware so school context is injected, but the deactivated-school 402 gate
# explicitly exempts them (inner bypass below) so deactivated users can sign out cleanly.
_SKIP_PATHS = {
    "/api/health",
    "/api/health/ready",
    "/api/health/system",
    "/api/auth/login",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
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
                try:
                    school_doc = await db.schools.find_one(
                        {"school_id": school_id}, {"status": 1, "_id": 0}
                    )
                    if school_doc and school_doc.get("status") == "deactivated":
                        # Allow refresh/logout so deactivated users can sign out cleanly
                        if request.url.path not in {"/api/auth/refresh", "/api/auth/logout"}:
                            return JSONResponse(
                                status_code=402,
                                content={
                                    "detail": "School account is deactivated. Contact support."
                                },
                            )
                except Exception:
                    logger.warning(
                        "school status check failed school_id=%s", school_id, exc_info=True
                    )
            return await call_next(request)
        finally:
            _school_id_var.reset(token_val)
