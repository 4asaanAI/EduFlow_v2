"""
Shared auth middleware for EduFlow.

Provides JWT-based authentication with dev-mode header fallback.
All route files import get_current_user from here instead of defining locally.
"""

from __future__ import annotations

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

    # Part 1.5 Patch N: a per-process random secret is fine for a single
    # dev worker but silently breaks multi-worker setups (each worker would
    # issue tokens the others reject — unreproducible 401s). Refuse to start
    # if the configuration looks like staging or `gunicorn -w N`.
    _env = os.environ.get("ENVIRONMENT", "").lower()
    try:
        _workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    except ValueError:
        _workers = 1
    if _env in ("staging", "preview") or _workers > 1:
        raise ValueError(
            "JWT_SECRET must be set when ENVIRONMENT=%r or WEB_CONCURRENCY=%d. "
            "Without it each worker generates its own secret and tokens issued "
            "by one worker are invalid for the others. See backend/.env.example."
            % (_env, _workers)
        )

    # Part 1.5 Patch N: cache the dev secret to disk so `uvicorn --reload`
    # does not invalidate every active session each time the file is saved.
    # File-mode 0600 under the user's cache dir (gitignored, machine-local).
    import pathlib
    _cache_dir = pathlib.Path(
        os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    ) / "eduflow"
    _cache_file = _cache_dir / "dev_jwt_secret"
    try:
        if _cache_file.is_file():
            JWT_SECRET = _cache_file.read_text(encoding="utf-8").strip()
        if not JWT_SECRET:
            JWT_SECRET = secrets.token_urlsafe(48)
            _cache_dir.mkdir(parents=True, exist_ok=True)
            _cache_file.write_text(JWT_SECRET, encoding="utf-8")
            try:
                os.chmod(_cache_file, 0o600)
            except OSError:
                pass
    except OSError:
        # Cache directory unwritable — fall back to ephemeral per-process secret.
        JWT_SECRET = secrets.token_urlsafe(48)

    logger.warning(
        "JWT_SECRET not set — using a dev secret cached at %s. "
        "Set JWT_SECRET in .env to override or in production environments.",
        _cache_file,
    )

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_MINUTES = 60

# ─── Canonical sub_category identifiers ───────────────────────────────────────
# The single source of truth for every `sub_category` the platform recognizes,
# grouped by the role it qualifies. The AI prompt↔registry parity gate imports
# this set and asserts that every prompt tool-list key is a subset — so a legacy
# or typo'd key (e.g. "accounts" vs the canonical "accountant") can never again
# silently route an accountant to a fallback tool list / over-exposed context
# (audit C4). Add new sub_categories here first.
# UI-Sweep Story 1.2: the same set, but grouped by the role each sub_category
# qualifies. Grouping is not decoration — a sub_category paired with the wrong
# role matches no permission rule, so the holder silently gets nothing. The
# staff write path rejects such a pairing, and it can only do that if the
# role→sub_category relationship is written down somewhere. This is that place.
SUB_CATEGORIES_BY_ROLE = {
    "owner": frozenset({"owner"}),
    "admin": frozenset({
        "principal", "accountant", "transport_head", "receptionist",
        "it_tech", "maintenance", "management", "support_staff",
    }),
    "teacher": frozenset({
        "class_teacher", "hod", "coordinator", "subject_teacher", "kg_incharge",
    }),
    "student": frozenset({"student"}),
}

# The flat set, derived so the two can never drift apart. Callers that only ask
# "is this a sub_category the platform recognizes at all?" keep using this name.
VALID_SUB_CATEGORIES = frozenset().union(*SUB_CATEGORIES_BY_ROLE.values())

# Every role the platform issues a token for. `VALID_ROLES` answers "does this
# string mean anything?"; it does NOT answer "may this be assigned here" —
# `owner` is a valid role that the staff API refuses to grant (Story 1.1).
VALID_ROLES = frozenset(SUB_CATEGORIES_BY_ROLE)


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
        if payload.get("school_id"):
            user["school_id"] = payload["school_id"]
        return user
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired", headers={"WWW-Authenticate": "Bearer"})
    except JWTError as e:
        logger.warning(f"JWT decode error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"})


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

    raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})


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
    # Part 1.5 hardening (Patch K): reject empty-tuple at factory time. A
    # `Depends(require_role())` with no args silently denied every request
    # before this guard — surfaced as a generic 403 instead of a programmer
    # error.
    if not roles:
        raise ValueError("require_role() requires at least one role argument")

    def dependency(request: Request):
        user = get_current_user(request)
        if user.get("role") not in roles:
            logger.info(
                "role check failed: role=%s required=%s path=%s",
                user.get("role"), roles, request.url.path,
            )
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dependency


def require_access(*roles: str, sub_category: str | tuple[str, ...] | None = None):
    """
    FastAPI dependency checking role AND optional sub_category.
    Returns user dict on success. Raises 403 on role/sub_category mismatch.
    Raises ValueError at factory time if called with no role arguments.

    Examples:
      Depends(require_access("owner"))
      Depends(require_access("admin", sub_category="accountant"))
      Depends(require_access("owner", "admin", sub_category=("principal", "accountant")))
    """
    if not roles:
        raise ValueError("require_access() requires at least one role argument")

    def dependency(request: Request):
        user = get_current_user(request)
        if user.get("role") not in roles:
            logger.info(
                "role check failed: role=%s required=%s path=%s",
                user.get("role"), roles, request.url.path,
            )
            raise HTTPException(status_code=403, detail="Forbidden")
        if sub_category is not None:
            allowed_subs = (sub_category,) if isinstance(sub_category, str) else sub_category
            if user.get("sub_category") not in allowed_subs:
                logger.info(
                    "sub_category check failed: sub=%s required=%s path=%s",
                    user.get("sub_category"), allowed_subs, request.url.path,
                )
                raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return dependency


def require_owner(request: Request):
    """Owner role only. Thin wrapper over require_access."""
    return require_access("owner")(request)


def require_owner_or_principal(request: Request):
    """Owner or admin+principal.

    Semantics: owner role is allowed regardless of sub_category;
    admin is allowed only when sub_category == 'principal'.
    Implemented as two require_access probes so behaviour is identical
    to the original inline logic.
    """
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    try:
        return require_access("admin", sub_category="principal")(request)
    except HTTPException:
        logger.info(
            "owner/principal gate failed: role=%s sub=%s path=%s",
            user.get("role"), user.get("sub_category"), request.url.path,
        )
        raise HTTPException(status_code=403, detail="Forbidden")


def require_owner_principal_or_management(request: Request):
    """Owner, admin+principal, or admin+management.

    Semantics: owner role is allowed regardless of sub_category; admin is allowed
    only when sub_category is 'principal' or 'management'. Used for the academic
    structure (class/subject) management section, which is restricted to the
    Principal and Management admin sub-roles.
    """
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    if user.get("role") == "admin" and user.get("sub_category") in ("principal", "management"):
        return user
    logger.info(
        "owner/principal/management gate failed: role=%s sub=%s path=%s",
        user.get("role"), user.get("sub_category"), request.url.path,
    )
    raise HTTPException(status_code=403, detail="Forbidden")


def require_exam_manager(request: Request):
    """Owner, admin+principal, admin+management, or teacher can manage exams."""
    user = get_current_user(request)
    role = user.get("role")
    if role in ("owner", "teacher"):
        return user
    if role == "admin" and user.get("sub_category") in ("principal", "management"):
        return user
    logger.info(
        "exam manager gate failed: role=%s sub=%s path=%s",
        user.get("role"), user.get("sub_category"), request.url.path,
    )
    raise HTTPException(status_code=403, detail="Forbidden")


def require_exam_editor(request: Request):
    """Exam *write* gate — admin+principal, admin+management, or teacher.

    Differs from ``require_exam_manager`` by EXCLUDING the owner: the owner is
    view-only for exam editing (scheduling subject dates, entering marks). Used
    for the per-subject datesheet/schedule write endpoints.
    """
    user = get_current_user(request)
    role = user.get("role")
    if role == "teacher":
        return user
    if role == "admin" and user.get("sub_category") in ("principal", "management"):
        return user
    logger.info(
        "exam editor gate failed: role=%s sub=%s path=%s",
        user.get("role"), user.get("sub_category"), request.url.path,
    )
    raise HTTPException(status_code=403, detail="Forbidden")


def require_owner_or_accountant(request: Request):
    """Owner or admin+accountant.

    Semantics: owner role is allowed regardless of sub_category;
    admin is allowed only when sub_category == 'accountant'.
    Used for fee-related WhatsApp reminder endpoints.
    """
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    try:
        return require_access("admin", sub_category="accountant")(request)
    except HTTPException:
        logger.info(
            "owner/accountant gate failed: role=%s sub=%s path=%s",
            user.get("role"), user.get("sub_category"), request.url.path,
        )
        raise HTTPException(status_code=403, detail="Forbidden")
