---
project_name: 'eduflow'
user_name: 'Abhimanyu'
date: '2026-05-15'
last_refresh: '2026-05-16'
sections_completed:
  - technology_stack
  - language_rules
  - framework_rules
  - testing_rules
  - code_quality
  - workflow_rules
  - critical_rules
  - ai_rate_limiting
  - announcement_moderation
  - reports
  - operator_endpoints
  - multi_tenancy
  - part3_owner_patterns
  - error_hygiene
  - notification_service_canonical
  - audit_service_canonical
  - branch_isolation_complete
  - new_routes_parts9_to_16
  - test_infrastructure
  - ai_layer_hardening
  - frontend_wiring_complete
existing_patterns_found: 55
---

# Project Context for AI Agents — EduFlow

_Critical rules and patterns AI agents must follow when implementing code in this project. Focus on unobvious details that agents might otherwise miss._

---

## Technology Stack & Versions

### Frontend
| Dependency | Version | Notes |
|---|---|---|
| React | 19.0.0 | No legacy lifecycle methods |
| React Router DOM | 7.5.1 | v7 API — `createBrowserRouter` or `<BrowserRouter>` |
| CRA + CRACO | react-scripts 5.0.1 + @craco/craco 7.1.0 | Build via `craco`, NOT `react-scripts` directly |
| Tailwind CSS | 3.4.17 | v3, NOT v4 — no @layer base conflicts |
| shadcn/ui (Radix UI) | various | Already installed — reuse, do not add duplicates |
| React Hook Form | 7.56.2 | + @hookform/resolvers 5.0.1 |
| Zod | 3.24.4 | Schema validation for forms |
| Recharts | 3.6.0 | Chart library — do not add chart.js/d3 |
| date-fns | **3.6.0** | **Pinned to v3** — react-day-picker 8.10.1 breaks with v4 |
| react-day-picker | **8.10.1** | **Pinned to 8.x** — v9 API is incompatible |
| axios | 1.8.4 | Use for multipart/file uploads only; use native `fetch` for all other calls |
| Lucide React | 0.507.0 | Only icon library — never import from another icon set |
| sonner | 2.0.3 | Toast notifications |

### Backend
| Dependency | Version | Notes |
|---|---|---|
| FastAPI | 0.110.1 | |
| Uvicorn | 0.25.0 | |
| Gunicorn | 21.2.0 | Production process manager |
| Python runtime | **3.9.x** | Use `from __future__ import annotations` as the **first import** in any file with `str \| None` union syntax — 3.10+ syntax on 3.9 silently breaks conftest `APP_AVAILABLE` and skips all integration tests |
| Motor (async MongoDB) | 3.3.1 | ALL DB ops must be `async`/`await` |
| pymongo | 4.5.0 | Sync client — only for index creation at startup |
| Pydantic | **v2** (≥2.6.4) | `@validator` is deprecated — use `@field_validator` |
| python-jose | ≥3.3.0 | JWT encode/decode |
| bcrypt | 4.1.3 | Password hashing |
| Azure OpenAI (via openai SDK) | ≥1.30.0 | Primary LLM — deployment `gpt-5.3-chat` |
| google-generativeai | ≥0.8.0 | Secondary LLM / image tasks |
| boto3 | ≥1.34 | S3 file storage |
| twilio | ≥9.2.0 | SMS |

### Infrastructure
- **Frontend hosting**: AWS Amplify — build command `yarn build`, output `build/`
- **Backend entry point**: `application.py` → `backend/server.py` (Gunicorn expects `application:application`)
- **Database**: MongoDB Atlas (connection via `MONGO_URL` env var, `mongodb+srv://` scheme)
- **File uploads**: AWS S3 bucket

---

## Critical Implementation Rules

### Language-Specific Rules (JavaScript/Python)

**JavaScript (Frontend is plain JS, NOT TypeScript)**
- All frontend files use `.js` / `.jsx` extensions — never create `.ts` / `.tsx` files
- `@/` alias maps to `src/` — use `import Foo from '@/components/Foo'` not relative `../../`
- `process.env.REACT_APP_BACKEND_URL` is the only env var for the backend URL — never hardcode
- Never use `async componentDidMount` — use `useEffect` with an inner async function
- Default export for every React component, named exports for utilities and hooks

**Python (Backend)**
- All route handler functions must be `async def` — Motor requires it
- All database calls must be `await`ed — `await db.collection.find_one(...)` etc.
- Never use `pymongo` (sync) for request-time queries — only Motor
- Use `re.escape()` on any user-supplied string before building a MongoDB `$regex` query
- Pydantic v2: use `@field_validator` not `@validator`; `model_config = ConfigDict(...)` not `class Config`
- **Python 3.9 compat**: add `from __future__ import annotations` as the first line in any route file that uses union type syntax (`str | None`, `list[str]`, etc.). Without it, the file fails to import at collection time and all fixture-dependent tests silently skip.

---

### Framework-Specific Rules

**React Patterns**
- Context providers: `UserContext` (auth) and `ThemeContext` (dark/light) wrap the entire app — always use `useUser()` and `useTheme()` hooks to access them
- Auth token: stored in `localStorage` as `'eduflow_token'`; user object as `'eduflow_user'`
- All API calls from React components must go through `apiFetch` (in `src/lib/api.js`) or `authFetch` (in `UserContext.js`) — these handle 401 → auto-logout redirect
- `executeTool` and all chat API functions are exported from `src/lib/api.js` — do not re-implement inline fetch in components
- Streaming chat responses use SSE (`sendMessageStream`) — never poll
- The floating chat input is pinned to `bottom: 0; left: 120px` — any new layout must respect the 120px fixed sidebar width

**FastAPI Patterns**
- Every router file imports `get_current_user` from `middleware.auth` — never redefine it locally
- **Role guard canonical pattern** — use `Depends()` from `middleware.auth`, never inline `if user["role"] not in [...]` in new code:
  - `Depends(require_role("owner", "admin"))` — generic role list
  - `Depends(require_owner)` — owner-only endpoints (e.g., all `/api/operator/*`)
  - `Depends(require_owner_or_principal)` — managerial decision gates (announcements, approvals)
- All routers use prefix `/api/<resource>` and are registered in `server.py` — add new routers there
- Return shape convention: `{"success": True, "data": [...], "meta": {...}}` for lists; `{"success": True, "data": {...}}` for single objects
- Error responses: raise `HTTPException(status_code, detail=str)` — never return raw error dicts

**MongoDB / Motor**
- Documents never have `_id` in responses — always project out: `.find(query, {"_id": 0})`
- IDs are strings (UUID4) — never use MongoDB ObjectId
- All multi-document queries must avoid N+1: batch lookup with `{"id": {"$in": [...]}}` then build a map
- Indexes are created in `database.py → _create_indexes()` — add new indexes there, not ad-hoc

**AI / LLM Integration**
- Primary LLM: `LLMClient` in `backend/ai/llm_client.py` — uses Azure OpenAI, deployment `gpt-5.3-chat`. **Per-call `timeout=45`** (P5) — do not remove.
- Tool authorization: `_is_tool_authorized(user, tool_def)` in `routes/chat.py` — single gate at keyword dispatch, LLM-tool dispatch, execute_action, and confirm dispatch. Never add per-tool body-level static role checks. Dynamic checks (e.g., `approval.routing`) may remain as body guards.
- **Scope enforcement**: `await resolve_scope(user)` before every tool invocation. `Scope.branch_id` is always populated from JWT for non-owner users. `scope.filter()` always emits a `branch_id` clause when set.
- **Tool signatures**: `(params, user, scope)` — 3-arg. `_tenant_query(scope, base)` in `tool_functions.py` composes branch_id + schoolId for v1 Mongo reads. Never re-introduce a 2-arg tool.
- **Audit log is write-ahead** (P4): `audit_ai_dispatch_pending(..., dispatch_id=f"ai-dispatch-{token}")` inserts `status="pending"` BEFORE the tool runs. The `dispatch_id` is derived from the confirm token — duplicate concurrent `/confirm` calls hit Mongo `_id` uniqueness and surface as 503. `audit_ai_dispatch_finalize()` always called after (both success and exception paths). If pending insert fails → abort with 503.
- **Error opacity** (P3): never put `str(e)` into tool_result.error, SSE events, or chat history. Use `{"error": "data_unavailable", "correlation_id": <uuid>}`; full exception to `logger.exception`.
- **Elision marker** (P2 fix): splice `[N messages omitted]` system message **AFTER** `_trim_history()`, not before. If spliced before, `_trim_history` pops it at index `HISTORY_KEEP_FIRST`. Use: `messages = _trim_history(messages); messages.insert(min(len(anchors), len(messages)), elision_msg)`.
- **SSE constants** (P5): `KEEPALIVE_INTERVAL = 5` (seconds — module constant in `routes/chat.py`); `LLM_WALLCLOCK_BUDGET = 90` (also module constant — do not redefine inline).
- **Content filter** (P8): `filter_response()` applied to LLM output, tool data JSON, `rich_blocks`, AND `action_buttons` before SSE emit for student-role users. Both `rich_blocks` and `action_buttons` must be filtered — not just `rich_blocks`.
- Write ops require confirm-action flow — add to `WRITE_ACTION_TOOLS` set in `routes/chat.py`.
- Max 3 tool-call rounds per turn (`MAX_TOOL_ROUNDS = 3`).
- **Confirm tokens persist school_id + branch_id** (P9): `issue_confirm_token` requires both; `consume_confirm_token` validates and raises 409 on mismatch. `peek_confirm_token` raises 503 on Mongo errors. Concurrent 409 replays trigger `decrement_count()`.

---

### Design System Rules

- **Dark-first**: default theme is dark. CSS variables are defined in `index.css` (dark) and overridden in `theme.css` for `[data-theme="light"]`
- **Use CSS variables, not raw hex**: `var(--bg-card)`, `var(--border)`, `var(--text-primary)` etc.
- **Fonts**: `Inter` (body), `JetBrains Mono` (monospace/code) — do not switch without approval
- **Tailwind + inline styles coexist**: match the local pattern of the file you're editing
- **Tool icon colors**: each tool has a designated accent from `design_guidelines.json`
- **shadcn/ui components** live in `src/components/ui/` — always import from there
- **Sidebar width is 120px fixed** — all content areas must account for `margin-left: 120px`
- **Chat bubble styles**: user messages = `bg-[#1C1C28] border border-[#222230] rounded-2xl`; AI messages = transparent with a leading avatar
- Add `data-testid` attributes to all interactive elements

---

### Testing Rules

- Test files live in `tests/` at project root — backend tests are Pytest
- Frontend has no test suite currently — when adding tests, use `craco test`
- Never test against the live MongoDB Atlas instance — mock `get_db()` in tests
- When testing auth-protected routes, inject a pre-signed JWT in the `Authorization` header
- **387 backend tests passing (0 skipped)**. The fix for Python 3.9 `str | None` syntax (`from __future__ import annotations`) unlocked the previously-silently-skipped 178 tests — always add this import to route files or the conftest `APP_AVAILABLE` check silently skips the entire integration suite.

---

### Code Quality & Style Rules

- **No TypeScript** — do not introduce it; keep plain JS
- **No comments that explain what the code does** — only add a comment if the WHY is non-obvious
- **No default error swallowing**: `except Exception: pass` is forbidden — always log or re-raise
- **Logging**: use Python `logging.getLogger(__name__)` in every module — never `print()`
- **Import order** (Python): stdlib → third-party → local, separated by blank lines
- **No wildcard imports**: `from module import *` is forbidden
- **ESLint rules** enforced: `react-hooks/rules-of-hooks: error`, `react-hooks/exhaustive-deps: warn`
- **Naming**:
  - React components: `PascalCase.js`
  - Utilities/hooks: `camelCase.js`
  - Python modules: `snake_case.py`
  - MongoDB collections: `snake_case` plural (e.g., `db.students`, `db.fee_transactions`)
  - IDs in documents: `id` field (string UUID), never `_id`

---

### Development Workflow Rules

- **Frontend start**: `cd frontend && yarn start` (uses CRACO)
- **Backend start**: `cd backend && uvicorn server:app --reload`
- **Environment variables**: backend reads from `backend/.env`; frontend reads from `frontend/.env`
- **New backend route**: create `backend/routes/<name>.py`, add router to `server.py`
- **New frontend tool panel**: create `frontend/src/components/tools/<ToolName>.js`, register in routing
- **Deployment**: push to `main` → AWS Amplify auto-builds frontend
- **`amplify.yml`** uses `--legacy-peer-deps` flag — do not remove
- **`date-fns` is pinned to v3** — never run `yarn upgrade date-fns`

---

### Critical Don't-Miss Rules

**Security**
- All user-supplied strings used in MongoDB `$regex` must be escaped with `re.escape()`
- JWT secret must be set via `JWT_SECRET` env var in production
- Never log JWT tokens, passwords, or PII
- CORS origins are explicit (env `CORS_ORIGINS`) — never set `allow_origins=["*"]`

**Multi-tenancy / Branch + School Scoping**

Two tenancy axes coexist: `branch_id` (per-branch) and `schoolId` (per-school, Story 1-3 multi-tenant forward-compat).

**Route handler rules (enforced in Parts 1–3):**
- Every READ must use `scoped_filter(query, get_school_id())` — no bare `db.col.find({})` on operational collections.
- Every INSERT must call `add_school_id(doc)` before insert. **Never pass raw request body directly to `add_school_id`** — strip `schoolId` from `body` first. `add_school_id` silently skips injection if `schoolId` is already present, so untrusted caller-supplied values will persist. Pattern: `doc = add_school_id({"field": body.get("field"), ...})` (never `add_school_id(body)`).
- Every UPDATE/DELETE must include `scoped_filter({"id": target_id}, get_school_id())` — not bare `{"id": target_id}`.
- `_notification_targets(db, query, projection)` — the query must be pre-scoped with `scoped_filter` before passing in. Cross-school user queries for notifications are a data exposure.

**When to use `scoped_filter` vs `scoped_query`:**
- `scoped_filter(query, school_id)` → adds **schoolId axis only**. Use in REST route handlers.
- `scoped_query(query, branch_id=..., school_id=...)` → adds **both schoolId AND branch_id**. Use when explicitly needing branch isolation (e.g., multi-branch admin logic). Located in `backend/tenant.py`.
- **Never use `scope.filter()` inside v1 AI tools** (`ai/tool_functions.py`) — it is collection-aware and injects entity-specific clauses (e.g., `student_id`, `class_ids`) that corrupt cross-collection queries. Use `_tenant_query(scope, base)` instead.

**context_builder.py** uses `_tenant_query(query)` = school-scoped only (NOT branch-scoped). This is **intentional** — it feeds the LLM system prompt with a school-level summary; branch-scoping would be wrong for owners and confusing for single-branch schools. Do not add branch filtering to `context_builder` without an explicit owner-role architectural decision.

**`_apply_branch_filter(query, scope)`** in `tool_functions_v2.py` mutates its argument dict in-place. Always pass a **fresh dict** per call — never reuse the same query dict across multiple `_apply_branch_filter` calls within a request handler.

**AI tools — v1 vs v2 tenancy helpers:**

| File | Helper | Axes covered | Use when |
|---|---|---|---|
| `ai/tool_functions.py` (v1) | `_tenant_query(scope, base)` | schoolId + branch_id | v1 tool reads; returns a new dict |
| `ai/tool_functions_v2.py` (v2) | `_apply_branch_filter(query, scope)` + `scoped_filter(query, get_school_id())` | branch_id (mutates) + schoolId (new dict) | v2 tool reads; two separate calls needed |

`owner` role has `branch_id=None` — no branch filter applied. All other roles get branch_id from JWT.

**Chat / SSE**
- SSE events follow the shape `data: {json}\n\n` with types: `thinking`, `text_delta`, `tool_call`, `tool_result`, `confirm_action`, `navigate`, `done`, `token_exhausted`
- `done` event must always be the last event emitted — missing it leaves the frontend spinner running
- Never `await` inside a generator that yields SSE

**AI Tool Design**
- Tools in `TOOL_REGISTRY` must include: `fn`, `description`, `params_schema`, `roles`, `sub_categories`, `dispatch_type`, `requires_confirmation`
- Never return raw MongoDB documents — always `{"_id": 0}` projection and return `_ok()` / `_empty_result()` shape
- Tool functions accept `(params: dict, user: dict, scope)` — always accept scope for filtering

**Date Handling**
- All dates stored in MongoDB as ISO strings — never store datetime objects
- Use `date.today().isoformat()` for today's date — never `str(datetime.now())`
- Use `datetime.now()` (not `datetime.utcnow()`) for bucket calculations that compare against locally-stored ISO dates

**Performance**
- Avoid N+1 queries — batch all secondary lookups
- Motor `.to_list(n)` always requires an explicit limit — never `.to_list(None)`
- `HISTORY_KEEP_FIRST=2`, `HISTORY_KEEP_RECENT=10` — never load full history

**Anti-Patterns to Avoid**
- Do NOT use `axios` for standard API calls — use `apiFetch` / `authFetch`
- Do NOT add a new icon library — use `lucide-react` exclusively
- Do NOT create TypeScript config or rename `.js` files to `.ts`
- Do NOT use `ObjectId` anywhere — all IDs are UUID strings
- Do NOT store sensitive fields without hashing
- Do NOT use `find().to_list(None)` — always set a limit
- Do NOT bind `_now` as a Python default argument — use `(now_fn or _now)()` pattern
- Do NOT call `add_school_id(body)` — strip schoolId from body first

---

## 403 Hygiene

- **All 403 responses in new code must use `detail="Forbidden"`** — never leak role names, sub_category values, or which roles would be permitted. Forbidden patterns: `"Owner only"`, `"Only IT & Tech staff"`, `"Only Maintenance Admin or Owner/Principal"`.
- Composite/dynamic auth gates (where `Depends(require_*)` cannot express the logic, e.g., routing-dependent approval decisions) must be annotated `# auth: <reason>` inline so the pattern is greppable.
- **Legacy routes** in `queries.py`, `students.py`, `issues.py`, `operations.py` may still have descriptive messages being migrated. Do not introduce new descriptive 403s; migrate old ones when touching those files.

---

## AI Rate Limiting (Story 7-48)

- Per-user-per-hour counter at `db.ai_rate_limit_counters`, keyed `(user_id, hour_bucket)` — NOT per-session.
- Hour bucket format: `"YYYY-MM-DDTHH:00:00Z"` (UTC). Helpers `hour_bucket(now)`, `seconds_until_next_hour(now)`, `hour_bucket_start(bucket)` in `backend/services/ai_rate_limiter.py`.
- Atomic increment via `find_one_and_update` with `$inc` + `$setOnInsert` + `return_document=ReturnDocument.AFTER`.
- Pre-check before increment: if `existing_count >= limit`, reject WITHOUT incrementing.
- Per-role defaults in `backend/config/ai_rate_limits.yaml` — mtime-cached. Operator override via `PATCH /api/operator/schools/{school_id}/ai-rate-limit`.
- Rate-limit check runs BEFORE `consume_confirm_token`.
- `peek_confirm_token` validates ownership BEFORE rate-check. Mongo errors raise 503 (P9).
- 429 shape: `{"success": false, "error": "rate_limit_exceeded", "retry_after_seconds": N, "limit": N, "window": "hour"}`. Use `JSONResponse(status_code=429, headers={"Retry-After": ...})`.
- **Override requires `expires_at`** (P10): absent key → 400. `expires_at: null` = permanent. Resolver ignores docs where `expires_at` field is **missing** (use `{"expires_at": {"$exists": True}, "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}]}`). Sort: `[("created_at", -1), ("_id", -1)]`.
- **Compensating decrement** (P9): 409 replay after pre-increment → call `decrement_count()`.

---

## Announcement Moderation (Story 7-47)

- `announcements` documents have `status`: `"active" | "pending_approval" | "rejected"`.
- **Canonical gate function**: `_announcement_requires_approval(audience_type, target_roles)` in `routes/operations.py`:
  ```python
  def _announcement_requires_approval(audience_type: str, target_roles: list[str]) -> bool:
      return audience_type in ("all", "class") or any(r in ("teacher", "student") for r in target_roles)
  ```
  The REST route calls this function directly. The AI tool (`tool_create_announcement`) mirrors this logic inline — if the gate condition changes, **update both places** and add a test. A shared import is not currently used due to circular import risk.
- Endpoints: `GET /api/ops/announcements/pending`, `PATCH .../approve`, `PATCH .../reject` (requires non-empty `reason`) — all gated with `Depends(require_owner_or_principal)`.
- All approve/reject decisions write to `db.audit_logs`.

---

## Reports Endpoints (Story 7-41)

- `GET /api/reports/attendance-trends?months=N` — owner OR principal. N clamped to [1, 12].
- `GET /api/reports/fee-collection-summary?months=N` — **owner only**. N clamped to [1, 24].
- Both are school-scoped via `scoped_filter`. Fee summary uses a date-windowed `$or` pre-filter to avoid full table scans:
  ```python
  {"$or": [
      {"paid_date": {"$gte": f"{earliest_bucket}-01"}},
      {"due_date": {"$gte": f"{earliest_bucket}-01"}, "status": {"$in": ["pending", "overdue", "unpaid"]}},
  ]}
  ```
- Use `datetime.now()` (not `utcnow()`) for bucket calculations — attendance and fee dates are stored in local timezone.
- Empty-state contract: `{"success": True, "empty": True, "data": []}`.

---

## Operator Endpoints

- All endpoints under `/api/operator/*` are owner-only — use `Depends(require_owner)` from `middleware.auth`. The old local `_require_owner(request)` function was removed in Part 1.5.
- Add new operator endpoints to `routes/operator.py`, not `routes/settings.py`.
- Standard response shape: `{"success": True, "data": {...}}`.

---

## Test Infrastructure

- `tests/backend/conftest.py` holds a session-wide `FakeDb` singleton (`_fake_db`) — collections persist across tests in the same session. **Always add an `autouse` cleanup fixture per test file**:
  ```python
  @pytest.fixture(autouse=True)
  def _clean(fake_db):
      fake_db.<collection>.docs[:] = []
      yield
      fake_db.<collection>.docs[:] = []
  ```
  **The `fake_db` fixture returns the same session-scoped singleton.** Mutations from one test (insert_one, update_one) leak into later tests unless reset.
- When adding new collections, register them as `FakeCollection()` on `FakeDb.__init__`. Patch `<routes_module>.get_db = lambda: _fake_db` in the APP_AVAILABLE block.
- When seeding `auth_users`, use **unique usernames per test file** to avoid session-DB collisions.
- Mock `_now` via `monkeypatch.setattr(module, "_now", lambda: <datetime>)` — only works if the module resolves `_now` at call time via `(now_fn or _now)()`.

**FakeCollection operator support:**

| Operator | find/find_one | update_one | update_many | find_one_and_update | aggregate |
|---|---|---|---|---|---|
| `$set` | — | ✅ | ✅ | ✅ | — |
| `$inc` | — | ✅ | ✅ | ✅ | — |
| `$push` | — | ✅ | ✅ | — | — |
| `$setOnInsert` | — | ✅ (upsert) | — | ✅ | — |
| `$gt/$gte/$lt/$lte` | ✅ (None-safe) | — | — | — | — |
| `$ne/$in/$nin` | ✅ | — | — | — | — |
| `$exists` | ✅ (key presence) | — | — | — | — |
| `$regex` + `$options` | ✅ | — | — | — | — |
| `$and`/`$or` | ✅ | — | — | — | — |
| `$match/$group/$sort` | — | — | — | — | ✅ |
| `$sum/$addToSet/$cond/$substr` | — | — | — | — | ✅ |

**Does NOT support:** `$type`, `$elemMatch`, full aggregation pipelines, change streams, transactions.

**Critical:** `update_many` supports `$set`, `$inc`, `$push`. Previous versions only supported `$set` — `$inc`/`$push` silently no-oped, hiding test bugs.

---

## Auth + RBAC — Part 1 hardening notes

**JWT staleness policy (accepted):**
- Claims frozen for 60-minute TTL. Role/sub_category changes take effect on next refresh.
- Mitigations: `consume_refresh_token` re-fetches `is_active`; password reset revokes all refresh tokens.

**Access-token revocation (accepted):**
- No deny-list. Logout revokes refresh token only. 60-minute leak window accepted.

**Role-check canonical pattern:**
- New routes: `Depends(require_role/require_owner/require_owner_or_principal)` — never inline.
- Error message: always `"Forbidden"` — no role-list leak.
- Composite/dynamic gates (e.g., `decide_approval_request` — owner can decide any, principal only `owner_and_principal` routing): annotate with `# auth: <reason>` and keep inline; Depends cannot express routing-dependent logic.

**Legacy admin permissiveness (FIXED):**
- Migration 016 backfills `sub_category="support_staff"` for rows missing sub_category.
- Resolver denies-by-default (`type="self_only"`) for missing sub_category.

**Dev JWT secret (FIXED):** `secrets.token_urlsafe(48)` per-process. Set `JWT_SECRET` in `.env` to persist sessions.

**Refresh cookie path (FIXED):** Widened from `/api/auth` to `/`. Security preserved by `HttpOnly + Secure + SameSite=Strict`.

**Combined-tenancy helper:** `scoped_query(query, branch_id=..., school_id=...)` in `backend/tenant.py` — satisfies BOTH axes in one call.

---

## Dead Code / Documentation Debt

- **`db.otps`** — RESOLVED in Part 4. Collection dropped via migration 018. Zero references remain.

---

## Migration Discipline

- Migrations: `backend/migrations/NNN_<slug>.py` — sequential prefix.
- Every migration: `async def migrate(db)`, idempotent, registered in `run_all.py` MIGRATIONS list.
- **Current range:** 001–021 all present and in run_all.py. Migration 014 gap was fixed in Part 4.
- TTL indexes: `expireAfterSeconds=0` + `expires_at` datetime field in the doc. Use `sparse=True` where TTL is conditional.
- **`sms_logs.created_at`** must be stored as native `datetime` object (not ISO string) for TTL index to fire. Fixed in Part 16.

---

## Canonical Services (Parts 5–7) — ALWAYS USE THESE

### Notification writes
```python
from services.notification_service import create_notification
# NEVER call db.notifications.insert_one() directly
await create_notification(db=db, user_id=user_id, title="...", body="...")
```

### Audit writes
```python
from services.audit_service import write_audit
# NEVER call db.audit_log.insert_one() directly
await write_audit(db=db, actor_id=user["id"], action="...", target_id=entity_id, changes={...})
# write_audit is fail-open — exceptions logged but never re-raised
```

### Fan-out notifications (multiple recipients)
```python
from services.notification_service import fan_out_notifications
await fan_out_notifications(db=db, user_ids=[...], title="...", body="...")
```

---

## Branch Isolation — THREE WAVES COMPLETE (Parts 4, 11, 12+13)

**Rule:** Every operational collection query must use `scoped_query(query, branch_id=bid)`, NOT bare `scoped_filter(query, get_school_id())`.

```python
bid = user.get("branch_id")  # always extract this first in every handler

# CORRECT — enforces both schoolId AND branch_id
db.students.find(scoped_query({"class_id": class_id}, branch_id=bid))

# CORRECT intentional cross-branch (document it)
db.classes.find(scoped_filter({}))  # branch-scope: intentional — class dropdown is school-wide

# WRONG — only enforces schoolId, branch leaks
db.students.find(scoped_filter({"class_id": class_id}, get_school_id()))
```

**Wave 1 (Part 4):** `tool_functions_v2.py` — 35 callsites migrated.
**Wave 2 (Part 11 review):** `issues.py` — 34 callsites migrated (facility/tech/maintenance/vendor).
**Wave 3 (Round 2 review):** `operations.py` — 19 callsites migrated (expenses/incidents/transport/assets/vehicles).

Remaining `scoped_filter` calls in `operations.py` are intentionally school-wide: `leave_requests`, `approval_requests`, `announcements`, `users` (notification fan-out). Each has a `# branch-scope: intentional` comment.

**Pre-merge CI check (mandatory for any route file change):**
```bash
grep -n "scoped_filter(" backend/routes/<file>.py
# Every hit must have # branch-scope: intentional comment OR be migrated
```

---

## New Routes Added (Parts 9–16) — Quick Reference

### Part 9 — Principal vertical
- `GET /api/attendance/class-summary` — per-class aggregation, `require_owner_or_principal`
- `GET /api/attendance/staff/today` — absent staff list, `require_owner_or_principal`
- `GET /api/academics/lesson-plan-completion?month=YYYY-MM` — per-class completion stats
- `PATCH /api/academics/results/{id}/publish` — publish exam results, `require_owner_or_principal`

### Part 10 — Accountant vertical
- `GET /api/fees/transactions/{id}/receipt` — JSON receipt for a payment
- `POST /api/fees/structures` / `PATCH /api/fees/structures/{id}` — owner-only
- `GET /api/fees/discounts/pending-approvals` — large discounts awaiting owner approval
- `PATCH /api/fees/discounts/pending-approvals/{id}/approve|reject` — owner-only
- `GET/POST /api/payroll/structures` / `GET/POST /api/payroll/disburse` / `PATCH /api/payroll/disbursements/{id}/process`
- `POST /api/fees/sync/trigger` — idempotent (returns existing in-progress job, times out hung jobs after 30min)

### Part 11 — Receptionist vertical
- `GET /api/ops/visitors/pending-checkout?stale_hours=N` — overdue visitor checkouts
- `POST /api/ops/certificates/{id}/escalate` — escalate to owner when SLA exceeded
- Certificate SLA: 48h → `is_overdue: true` flag on list

### Part 12 — Maintenance vertical
- `GET /api/issues/facility/cost-summary` — MongoDB `$sum` aggregation by category
- `GET /api/issues/facility/{request_id}` — single record
- `GET /api/issues/maintenance/schedule/upcoming?days=N` — upcoming tasks

### Part 13 — IT-Tech vertical
- `GET /api/settings/token-usage/admin` — per-user usage with `users_over_80_pct` meta
- `POST /api/settings/branches` — create branch with unique `(schoolId, branch_code)` index
- `POST /api/auth/admin/users/{id}/reset-password` — IT-tech blocked from resetting owner
- `POST /api/auth/admin/users/{id}/unlock` — clears locked_at/failed_attempts/locked_until

### Part 14 — Teacher vertical
- `PATCH /api/academics/results/{id}/publish` — principal/owner publishes results

### Parts 15–16 — Student + Integration
- `/api/fees/my` now returns `summary: {total_paid, outstanding_balance, last_payment_date}`
- `GET /api/health/ready` returns HTTP **503** (not 200) when `db_status == "error"`
- `401` responses include `WWW-Authenticate: Bearer` header

---

## Test Infrastructure (Parts 8–16)

### Locations
- `tests/backend/unit/` — pure unit tests (FakeDB, no network)
- `tests/backend/api/` — HTTP integration tests (TestClient)
- `tests/backend/factories.py` — shared test data factories (**use for all new tests**)
- `tests/load/locust_basic.py` — load test scaffold

### Factories (always use these, never inline dicts)
```python
from tests.backend.factories import (
    make_student, make_staff, make_fee_transaction,
    make_audit_record, make_notification, make_leave_request
)
# All include schoolId="aaryans-joya", branch_id="branch-a" by default
# All accept **kwargs to override any field
```

### Frontend test setup (Part 8)
- Jest + RTL installed in `frontend/` — `yarn test` runs unit tests
- `frontend/src/setupTests.js` configures RTL matchers
- `frontend/src/components/__tests__/` for component tests

### Current baseline: **699 backend tests, 0 skipped** (as of 2026-05-16)

---

## AI Layer Hardening (Parts 2 + AI Layer Hardening session)

### LLM Config
- **Temperature:** 0.2 for management roles (factual), 0.7 for student (conversational)
- **max_tokens:** 1200 per call
- **Model:** Azure OpenAI `gpt-5.3-chat` (env `AZURE_OPENAI_DEPLOYMENT`)

### New AI Tools (53 total in TOOL_REGISTRY)
- `get_timetable` — period-by-period schedule for a class
- `get_exam_results_summary` — avg/pass-rate/highest/lowest per exam
- `get_upcoming_events` — merged exam + announcement calendar (N days ahead)
- `draft_parent_message` — WhatsApp/SMS draft (fee_reminder, absence, exam, general)

### Content Filter (Hindi support added)
- 16 Devanagari patterns for drugs/suicide/bullying/ragging
- `get_blocked_response(message)` detects Devanagari and returns Hindi response

### Scope Resolver (Parts 4 + AI Hardening)
- `it_tech` → domain scope (`tech_issues`, `audit_log`, `system_health`)
- `maintenance` → domain scope (`facility_requests`, `maintenance_schedule`, `vendors`)
- `can_write: bool = True` field added to `Scope` dataclass (was dead guard)

---

## Fee Idempotency Key Format

```python
def _normalize_fee_key(student_id, fee_period, fee_head):
    return f"{student_id}|{fee_period}|{(fee_head or '').strip().lower()}"
    # Uses | not : — prevents collision when fee_head contains :
    # Key is ephemeral (within-request dedup only, not stored in DB)
```

---

## Payroll (Part 10) — Data Model

Collections: `salary_structures`, `salary_disbursements` (both created by migration 009).
Unique index: `(schoolId, staff_id, month)` on `salary_disbursements` — prevents double-disbursement.
Routes in `backend/routes/payroll.py`. RBAC: writes = owner only, reads = owner or accountant.

---

## SCHOOL_ID Startup Guard (Part 4)

`validate_school_id()` in `tenant.py` is called in `server.py` startup:
- Non-dev environment + `SCHOOL_ID` unset → `ValueError` (hard fail)
- Dev/test + `SCHOOL_ID` unset → warning log, continues with default `"aaryans-joya"`

`SKIP_CONSENT_CHECK=true` guard (Part 16): startup `ValueError` if set in prod/staging.
