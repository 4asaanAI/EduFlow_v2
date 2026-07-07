---
story_id: "7.45"
story_key: 7-45-multi-tenancy-schema-per-tenant-enforcement
epic: 7
story: 45
status: review
priority: critical
effort: large
created: "2026-05-18"
---

# Story 7.45: Multi-Tenancy — Schema-Per-Tenant Enforcement

## User Story

**As** the system,
**I want** all data queries to be hard-scoped to the requesting school's `schoolId`,
**so that** school #2's data is fully isolated from The Aaryans and no cross-tenant data leak is possible.

---

## Acceptance Criteria

- [x] **AC1 — Per-request school context:** A new `contextvars.ContextVar` in `tenant.py` holds `school_id` per request. `get_school_id()` returns the context var value first, env var second, default third — backward compatible with single-school deployments.
- [x] **AC2 — Middleware injects school context:** `backend/middleware/school_context.py` extracts `school_id` from the JWT on every request (where a Bearer token is present) and sets the context var. Non-authenticated endpoints (e.g. `/api/health`, `/api/auth/login`, `/api/auth/refresh`) skip the school context injection without error.
- [x] **AC3 — Deactivated school enforcement (402):** The school context middleware checks `schools.status` after setting `school_id`. If `status == "deactivated"`, all requests except login/health return HTTP 402 with `{"detail": "School account is deactivated. Contact support."}`. Refreshing tokens for a deactivated school is still allowed (so users can call logout cleanly).
- [x] **AC4 — school_id in JWT:** `_jwt_payload_from_auth()` in `routes/auth.py` includes `school_id` in the JWT payload (read from the `auth_users` document's `schoolId` field). `decode_jwt()` in `middleware/auth.py` extracts `school_id` from the payload and includes it in the returned user dict.
- [x] **AC5 — Login scoped to school:** The login endpoint accepts an optional `school_id` field in the request body. When provided, the `auth_users` lookup adds `{"schoolId": school_id}` to the filter. This prevents two schools sharing the same operator email from getting the wrong account on login.
- [x] **AC6 — Cross-school username uniqueness index:** A compound unique index `[("username_lower", 1), ("schoolId", 1)]` is added to `auth_users` in `database.py:_create_indexes()`. Ensures the same email cannot be used twice within a single school; allows the same operator email to own multiple schools (different `schoolId`).
- [x] **AC7 — Strict schoolId filter:** `scoped_filter()` in `tenant.py` drops the `{"schoolId": {"$exists": False}}` fallback clause. The new filter is `{"schoolId": current_school_id}` only — no cross-document leakage from pre-backfill rows. (Story 1-3 backfilled all documents; the fallback is no longer needed and is a security gap in a multi-school environment.)
- [x] **AC8 — Cross-tenant isolation integration test:** A test in `test_multi_tenancy_enforcement.py` seeds documents for `school_a` and `school_b`, then authenticates as a `school_a` user and asserts that `GET` requests return zero documents belonging to `school_b`.
- [x] **AC9 — Auth matrix extended:** All existing auth matrix tests pass. No new test skips.
- [x] **AC10 — Deactivated school JWT invalidation:** When `PATCH /api/operator/schools/{id}/deactivate` is called, the route additionally calls `db.refresh_tokens.delete_many({"schoolId": school_id})` on `get_raw_db()` to invalidate all existing refresh tokens for that school. Access tokens (max 60 min TTL) are accepted until expiry — this is the accepted trade-off for short-lived JWTs (documented in deferred-work.md from 7-39).

---

## Scope Boundary

**This story implements:**
- Per-request school context via `contextvars.ContextVar`
- JWT `school_id` claim injection + extraction
- Deactivated school → 402 enforcement at middleware
- Strict `schoolId` filter (removes `$exists: False` fallback)
- Cross-school login disambiguation
- Compound unique index for `auth_users`
- Refresh token invalidation on deactivation

**NOT in this story:**
- Google Maps integration (7-46)
- WhatsApp/Twilio (7-40)
- Per-school rate limits on AI endpoints (already done in 7-48)
- Full presigned-URL or S3 per-school namespace (done in P6)

---

## Architecture: What Exists Today

### Current Multi-Tenancy Model (env-var per instance — ADR-001)

```
SCHOOL_ID env var → tenant.get_school_id() → ScopedDatabase → schoolId injected into all queries
```

- `tenant.py:get_school_id()` reads `os.environ.get("SCHOOL_ID", "aaryans-joya")`
- `ScopedDatabase.__getattr__` wraps every collection in `ScopedCollection` (except `SYSTEM_COLLECTIONS`)
- `scoped_filter()` builds `{"$or": [{"schoolId": current}, {"schoolId": {"$exists": False}}]}` — backward compat

### SYSTEM_COLLECTIONS (NOT school-scoped today)
```python
SYSTEM_COLLECTIONS = {"_migrations", "auth_users", "login_attempts", "refresh_tokens"}
```
`auth_users` bypasses scoping — login finds users across all schools. OK for single-school; broken for multi-school.

### JWT payload today (NO `school_id` claim)
```python
jwt_payload = {"user_id": ..., "role": ..., "name": ..., "initials": ..., "sub_category"?: ..., "branch_id"?: ...}
```

### Login lookup today
```python
auth = await db.auth_users.find_one({"username_lower": username_lower})
# db.auth_users is NOT scoped (SYSTEM_COLLECTIONS) → finds ANY school's user with that username
```

---

## Files to Create

### 1. `backend/middleware/school_context.py` (NEW)

Starlette middleware (not FastAPI dependency — must run before route handlers):

```python
from __future__ import annotations
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from tenant import _school_id_var  # context var to set
from database import get_raw_db
from middleware.auth import decode_jwt

logger = logging.getLogger(__name__)

# Paths that skip school-context injection entirely
_SKIP_PATHS = {
    "/api/health", "/api/health/ready", "/api/health/system",
    "/api/auth/login", "/api/auth/refresh", "/api/auth/logout",
    "/api/auth/request-password-reset", "/api/auth/reset-password",
    "/api/docs", "/api/openapi.json",
}

class SchoolContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _SKIP_PATHS or not request.headers.get("Authorization"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            from jose import jwt as _jose_jwt, JWTError
            import os
            token = auth_header[7:]
            payload = _jose_jwt.decode(token, os.environ.get("JWT_SECRET", ""), algorithms=["HS256"])
            school_id = payload.get("school_id")
        except Exception:
            return await call_next(request)

        if not school_id:
            return await call_next(request)

        token_val = _school_id_var.set(school_id)
        try:
            # Deactivated school check
            db = get_raw_db()
            school_doc = await db.schools.find_one({"school_id": school_id}, {"status": 1, "_id": 0})
            if school_doc and school_doc.get("status") == "deactivated":
                # Allow refresh endpoint so logout works cleanly
                if request.url.path not in {"/api/auth/refresh", "/api/auth/logout"}:
                    return JSONResponse(
                        status_code=402,
                        content={"detail": "School account is deactivated. Contact support."},
                    )
            return await call_next(request)
        finally:
            _school_id_var.reset(token_val)
```

**Important:** Register with `app.add_middleware(SchoolContextMiddleware)` in `server.py` **after** (below in code, but runs before in Starlette middleware chain) the CORS middleware. Starlette middleware runs in reverse registration order — add it last so it executes first.

---

## Files to Update

### 2. `backend/tenant.py` — Add context var + tighten scoped_filter

```python
# Add at top of file
import contextvars

_school_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("school_id", default=None)

def get_school_id() -> str:
    # Context var is set by SchoolContextMiddleware for authenticated requests
    ctx_val = _school_id_var.get()
    if ctx_val:
        return ctx_val
    return os.environ.get("SCHOOL_ID", DEFAULT_SCHOOL_ID)

def scoped_filter(query: dict | None, school_id: str | None = None) -> dict:
    base = query or {}
    current_school_id = school_id or get_school_id()
    if "schoolId" in base:
        return base
    # Strict filter — no $exists:False fallback (Story 1-3 backfilled all docs)
    school_clause = {"schoolId": current_school_id}
    if not base:
        return school_clause
    return {"$and": [base, school_clause]}
```

**CRITICAL:** Removing `$exists: False` is a one-way change. Before shipping, confirm that Story 1-3 (`1-3-school-id-forward-compatibility-backfill`) ran successfully and all documents in the DB have `schoolId` set. In test environments, always include `schoolId` in seeded docs (the cleanup fixtures in existing tests already do this correctly).

**`scoped_query()` does not need changes** — it calls `scoped_filter()` internally and will inherit the tightened filter.

### 3. `backend/middleware/auth.py` — Extract `school_id` in `decode_jwt`

In `decode_jwt()`, add `school_id` extraction alongside existing fields:

```python
if payload.get("school_id"):
    user["school_id"] = payload["school_id"]
```

No other changes to `auth.py` (the middleware file) — `get_current_user`, `require_role`, `require_access` all remain unchanged.

### 4. `backend/routes/auth.py` — Add `school_id` to JWT payload + scope login lookup

In `_jwt_payload_from_auth()`:
```python
# auth document has schoolId field (set in create_school flow from 7-44)
if auth.get("schoolId"):
    jwt_payload["school_id"] = auth["schoolId"]
```

Note: `auth` is the raw `auth_users` document. It was created by `create_school` (7-44) with `schoolId` field. For legacy users created before 7-44 (The Aaryans), `schoolId` may not exist on their `auth_users` doc — fall back to `get_school_id()` (env var) in that case.

```python
# Fallback for pre-7-44 users (The Aaryans initial data)
from tenant import get_school_id as _get_school_id
jwt_payload["school_id"] = auth.get("schoolId") or _get_school_id()
```

In `LoginRequest` Pydantic model, add optional field:
```python
class LoginRequest(BaseModel):
    username: str
    password: str
    school_id: str | None = None  # For multi-school disambiguation
```

In the `login()` handler, scope the `auth_users` lookup when `school_id` provided:
```python
# Use raw DB for auth_users (SYSTEM_COLLECTION — not auto-scoped)
raw_db = get_raw_db()
lookup_filter = {"username_lower": username_lower}
if body.school_id:
    lookup_filter["schoolId"] = body.school_id
auth = await raw_db.auth_users.find_one(lookup_filter)
if not auth:
    # Backward compat: exact match without school scope
    auth = await raw_db.auth_users.find_one({"username": username})
```

### 5. `backend/database.py` — Add compound unique index for auth_users

In `_create_indexes()`, add (inside try/except):
```python
# Story 7-45: Cross-school username uniqueness — same email can own multiple schools,
# but must be unique within one school
try:
    await db.auth_users.create_index(
        [("username_lower", 1), ("schoolId", 1)], unique=True,
        name="auth_users_username_school_unique",
    )
except Exception:
    logger.warning("auth_users compound unique index creation failed", exc_info=True)
```

### 6. `backend/routes/operator.py` — Add refresh token invalidation on deactivate

In `deactivate_school()` handler, after updating school status to `"deactivated"`, add:
```python
# Invalidate all refresh tokens for this school so deactivated users can't re-authenticate
raw_db = get_raw_db()
await raw_db.refresh_tokens.delete_many({"schoolId": school_id})
logger.info("refresh_tokens cleared for deactivated school school_id=%s", school_id)
```

But refresh_tokens is a SYSTEM_COLLECTION today — it does NOT have `schoolId`. You must first check: do refresh tokens carry `schoolId`? Look at `services/token_service.py` or wherever `issue_refresh_token` is defined.

If `refresh_tokens` does NOT have `schoolId`, alternative approach:
```python
# Get all user_ids for this school from auth_users, then delete their tokens
school_users = await raw_db.auth_users.find({"schoolId": school_id}, {"user_id": 1, "_id": 0}).to_list(500)
user_ids = [u["user_id"] for u in school_users if u.get("user_id")]
if user_ids:
    await raw_db.refresh_tokens.delete_many({"user_id": {"$in": user_ids}})
```

Check `backend/routes/auth.py` and `backend/services/` for how refresh tokens are structured before implementing.

### 7. `backend/server.py` — Register middleware

After all existing `app.add_middleware()` calls:
```python
from middleware.school_context import SchoolContextMiddleware
app.add_middleware(SchoolContextMiddleware)
```

Starlette middleware is LIFO — last registered = first to execute. `SchoolContextMiddleware` should run after CORS (so CORS preflight bypasses school check). Register it last.

---

## Files to Create: Tests

### `tests/backend/unit/test_multi_tenancy_enforcement.py`

```python
from __future__ import annotations

import os
import sys
import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

pytestmark = pytest.mark.asyncio

from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import APP_AVAILABLE, FakeCollection

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from server import app
from tests.backend.conftest import _fake_db

def _bearer(payload):
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}

def _school_a_headers():
    return _bearer({"user_id": "ua1", "role": "owner", "name": "OwnerA", "school_id": "school-a"})

def _school_b_headers():
    return _bearer({"user_id": "ub1", "role": "owner", "name": "OwnerB", "school_id": "school-b"})

@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
```

**Test cases to write:**

1. `test_scoped_filter_strict_no_exists_false` — unit test of `scoped_filter()` — asserts the output does NOT contain `$exists` key.
2. `test_get_school_id_reads_context_var` — set `_school_id_var` manually, assert `get_school_id()` returns it.
3. `test_get_school_id_falls_back_to_env` — context var not set, assert env var is returned.
4. `test_school_a_cannot_read_school_b_students` — seed `_fake_db.students.docs` with docs for both schools; monkeypatch school context middleware to set `school-a`; call an endpoint; assert only school-a docs returned.
5. `test_deactivated_school_returns_402` — seed `_fake_db.schools.docs` with `{"school_id": "school-a", "status": "deactivated"}`; call any authenticated endpoint with school-a JWT; assert 402.
6. `test_deactivated_school_login_still_works` — login endpoint is in `_SKIP_PATHS`; assert 200.
7. `test_jwt_contains_school_id` — monkeypatch login, assert JWT payload has `school_id` field.
8. `test_active_school_passes_middleware` — seed `{"school_id": "school-a", "status": "active"}`; call endpoint; assert NOT 402.

---

## Critical Anti-Patterns to Avoid

### DON'T break existing test suite
- All 751 existing tests use `SCHOOL_ID` env var (not JWT school_id) — the context var fallback to env var is what preserves them.
- Do NOT remove the env var fallback in `get_school_id()`.
- Do NOT remove the env var from `conftest.py` — it's not set there (`SCHOOL_ID` is intentionally absent in test env, defaulting to `"aaryans-joya"`).

### DON'T call `db.schools.find_one(...)` inside middleware with `get_db()`
- `get_db()` returns `ScopedDatabase` which calls `get_school_id()` — but at middleware time, the context var is already set. This creates a circular dependency if the schools collection itself is school-scoped.
- **Use `get_raw_db()` for the deactivation check inside the middleware.** The `schools` collection is an operator-level (cross-school) collection, not a school-scoped collection. This is consistent with how `operator.py` already uses `get_raw_db()`.

### DON'T add `schoolId` filter to SYSTEM_COLLECTIONS in ScopedDatabase
- `auth_users`, `login_attempts`, `refresh_tokens` remain in SYSTEM_COLLECTIONS.
- The login endpoint handles school scoping explicitly via the `school_id` field in `LoginRequest`.
- This is intentional: system collections need cross-school lookups (refresh token validation, etc.).

### DON'T forget the ContextVar reset in middleware
- Always use `token_val = _school_id_var.set(school_id)` and `_school_id_var.reset(token_val)` in a `finally` block — the ContextVar must be reset after the request so the next request in the same thread doesn't inherit the previous value.

### DON'T double-wrap in `$and` when base already has `$and`
- `scoped_filter()` already handles this correctly in existing code. Do not simplify it — the `if "$and" in base` check in `scoped_query()` is important.

---

## Previous Story Intelligence (7-44)

Story 7-44 (School Onboarding Flow) established:
- `backend/routes/operator.py` — uses `get_raw_db()` for all schools-collection operations (cross-school by design). **Story 7-45 must continue this pattern for the deactivation check.**
- `create_school()` inserts into `auth_users` with `{"schoolId": school_id, "must_change_password": True, ...}`. So new-school owners DO have `schoolId` in `auth_users`.
- `deactivate_school()` sets `schools.status = "deactivated"` — story 7-45 adds token invalidation on top of this.
- Deferred: "JWT sessions not invalidated on deactivation" — **MUST be resolved in this story**.
- Deferred: "Same owner email cross-school duplicate username_lower" — **MUST be resolved with compound index in this story**.

From 7-44's `write_audit()` pattern:
```python
await write_audit(
    get_db(),  # <-- NOTE: uses get_db(), not get_raw_db(), for audit logs
    action="school_deactivated",
    ...
)
```
Story 7-45 adds refresh token deletion. `refresh_tokens` deletion uses `get_raw_db()` directly.

---

## Testing Requirements

Every new test file MUST have:
```python
from __future__ import annotations
pytestmark = pytest.mark.asyncio
```

Security tests (per CLAUDE.md convention):
```python
def test_middleware_unauthenticated_passthrough(client):
    # No Bearer token → middleware skips school injection → route returns 401 (not 500)
    resp = client.get("/api/students")
    assert resp.status_code == 401

def test_deactivated_school_returns_402(client, monkeypatch):
    ...
    assert resp.status_code == 402
```

Run baseline before and after: `python -m pytest tests/backend/ -x -q` — must show 751+ passed, 0 skipped.

---

## Dev Agent Record

### Agent Model Used
Claude Sonnet 4.6

### Debug Log
- Removed `$exists: False` fallback from `scoped_filter()` — caused 8 regressions in test docs that predated the `schoolId` field. Fixed all test docs to include `schoolId: "aaryans-joya"`. Also updated `test_tenant.py` test that explicitly asserted the old `$or` structure.
- `refresh_tokens` collection has no `schoolId` field. Used `auth_users.find({"schoolId": school_id})` to collect `user_info.id` values, then deleted by `user_id` — matches the `user_id` stored by `issue_refresh_token`.
- `SchoolContextMiddleware` uses `get_raw_db()` for the deactivation check (consistent with `operator.py` pattern). Added null-guard (`if db is not None`) and inner try/except for test environment safety. Patched `middleware.school_context.get_raw_db = lambda: _fake_db` in conftest.py.

### Completion Notes
All 10 ACs implemented and tested. 19 new tests added. Test count: 751 → 770 (0 skipped).

**Files changed:**
- `backend/tenant.py` — AC1 ContextVar + AC7 strict scoped_filter
- `backend/middleware/school_context.py` (NEW) — AC2 + AC3
- `backend/middleware/auth.py` — AC4 decode_jwt extracts school_id
- `backend/routes/auth.py` — AC4 JWT payload + AC5 login scoping
- `backend/database.py` — AC6 compound unique index
- `backend/routes/operator.py` — AC10 refresh token invalidation on deactivate
- `backend/server.py` — AC2 middleware registration
- `tests/backend/conftest.py` — patch school_context.get_raw_db
- `tests/backend/unit/test_multi_tenancy_enforcement.py` (NEW) — AC8 + AC9
- `tests/backend/unit/test_tenant.py` — updated for strict scoped_filter
- `tests/backend/api/test_announcement_moderation.py` — added schoolId to seeded docs
- `tests/backend/api/test_reports.py` — added schoolId to seeded docs

### Status
done

## File List

- backend/tenant.py
- backend/middleware/school_context.py
- backend/middleware/auth.py
- backend/routes/auth.py
- backend/database.py
- backend/routes/operator.py
- backend/server.py
- tests/backend/conftest.py
- tests/backend/unit/test_multi_tenancy_enforcement.py
- tests/backend/unit/test_tenant.py
- tests/backend/api/test_announcement_moderation.py
- tests/backend/api/test_reports.py

## Change Log

- 2026-05-19: Story 7-45 implemented — per-request school context via ContextVar, strict scoped_filter, SchoolContextMiddleware (402 enforcement), JWT school_id claim, login scoping, compound unique index, refresh token invalidation on deactivate. Test count: 751 → 770.

### Review Findings

- [x] [Review][Patch] JWT_SECRET inconsistency — school_context.py reads `os.environ.get("JWT_SECRET", "")` at request time; auth.py resolves it at module import time (with dev file-cache fallback). If they differ, JWT decode in middleware fails silently and school_id ContextVar is never set, causing scoped_filter() to fall back to the env-default school on every request — silent cross-tenant isolation failure. Fix: import `JWT_SECRET` from `middleware.auth` instead of re-reading `os.environ`. [`backend/middleware/school_context.py:46`]
- [x] [Review][Patch] Backward-compat login fallback uses case-sensitive `username` field — the primary lookup uses `username_lower` (case-insensitive) but the fallback fires `find_one({"username": username})` with original case and NO `schoolId` scope. This allows cross-tenant login and breaks case-insensitive matching for legacy users. Fix: change fallback to `{"username_lower": username_lower}` without `schoolId`. [`backend/routes/auth.py:208`]
- [x] [Review][Patch] Deactivation token invalidation misses users without `user_info.id` nesting — `_jwt_payload_from_auth()` also falls back to `auth.get("id") or auth.get("user_id")`, but the invalidation list comprehension only extracts `(u.get("user_info") or {}).get("id")`. Users with top-level-only `id`/`user_id` fields retain live refresh tokens after school deactivation. Fix: add fallback in the list comprehension: `u.get("user_info", {}).get("id") or u.get("id") or u.get("user_id")`. [`backend/routes/operator.py:265`]
- [x] [Review][Patch] Deactivation token invalidation capped at `.to_list(500)` — users 501+ retain live refresh tokens after deactivation. Fix: increase to `.to_list(5000)` or use cursor iteration. [`backend/routes/operator.py:264`]
- [x] [Review][Patch] Stale `scoped_query()` docstring contradicts AC7 — still reads "The schoolId clause tolerates documents that predate the schoolId field via `$exists: False`" after AC7 removed this fallback. Fix: update the docstring. [`backend/tenant.py:102`]
- [x] [Review][Patch] Missing test: deactivated school calling `/api/auth/refresh` (AC3 bypass untested) — `test_deactivated_school_login_not_blocked` covers login but not the refresh bypass that AC3 explicitly names. Add `test_deactivated_school_refresh_not_blocked`. [`tests/backend/unit/test_multi_tenancy_enforcement.py`]
- [x] [Review][Patch] `write_audit` in `deactivate_school()` passes `get_school_id()` which returns the operator's school_id (from ContextVar), not the target school being deactivated. The audit entry is misattributed to the wrong tenant. Fix: pass `school_id` (the route parameter) directly. [`backend/routes/operator.py:284`]
- [x] [Review][Patch] Dead code: `/api/auth/refresh` and `/api/auth/logout` are in both `_SKIP_PATHS` AND the inner bypass set `{"/api/auth/refresh", "/api/auth/logout"}`. Since `_SKIP_PATHS` exits before any JWT decode, the inner bypass can never execute. Fix: remove refresh/logout from `_SKIP_PATHS` so they get school context injected when a Bearer token is present, while the inner bypass set prevents the 402 for deactivated schools. [`backend/middleware/school_context.py:24-25,66`]
- [x] [Review][Defer] Compound unique index creation fails silently if Story 1-3 backfill left `(username_lower, schoolId=null)` duplicates [`backend/database.py:263`] — deferred, pre-existing: depends on Story 1-3 backfill completion; acceptable fail-open behavior at startup
- [x] [Review][Defer] `_SKIP_PATHS` exact-match doesn't handle trailing-slash variants [`backend/middleware/school_context.py:20`] — deferred, pre-existing: FastAPI normalizes paths; this pattern is used throughout the project
- [x] [Review][Defer] `scoped_filter()` bypassed when caller already supplies `schoolId` in base query [`backend/tenant.py:53`] — deferred, pre-existing: intentional operator-level design constraint; fixing requires broader refactor
- [x] [Review][Defer] Background `asyncio.create_task()` tasks inherit ContextVar and lose school context on `finally` reset in parent [`backend/middleware/school_context.py:78`] — deferred, pre-existing: asyncio task isolation is an architectural concern; no current route spawns background tasks that call `get_school_id()`
- [x] [Review][Defer] TOCTOU deactivation race: in-flight requests that passed the middleware check before status update completes can write to a now-deactivated school [`backend/middleware/school_context.py`] — deferred, pre-existing: inherent to middleware-based enforcement; requires distributed locking to fix
