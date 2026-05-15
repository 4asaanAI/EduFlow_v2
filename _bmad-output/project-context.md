---
project_name: 'eduflow'
user_name: 'Abhimanyu'
date: '2026-05-15'
last_refresh: '2026-05-15'
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
existing_patterns_found: 24
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
- Role guard pattern: `if user["role"] not in ["owner", "admin"]: raise HTTPException(403, "Forbidden")`
- `require_role(*roles)` dependency exists for FastAPI `Depends()` — use it for cleaner guards
- All routers use prefix `/api/<resource>` and are registered in `server.py` — add new routers there
- Return shape convention: `{"success": True, "data": [...], "meta": {...}}` for lists; `{"success": True, "data": {...}}` for single objects
- Error responses: raise `HTTPException(status_code, detail=str)` — never return raw error dicts

**MongoDB / Motor**
- Documents never have `_id` in responses — always project out: `.find(query, {"_id": 0})`
- IDs are strings (UUID4 via `gen_id()` in `models/schemas.py`) — never use MongoDB ObjectId
- All multi-document queries must avoid N+1: batch lookup with `{"id": {"$in": [...]}}` then build a map
- Every query that operates on tenant data MUST include `branch_id` filter — use `_apply_branch_filter(query, scope)` from `tool_functions_v2.py`
- Indexes are created in `database.py → _create_indexes()` — add new indexes there, not ad-hoc

**AI / LLM Integration**
- Primary LLM: `LLMClient` in `backend/ai/llm_client.py` — uses Azure OpenAI via OpenAI SDK, deployment `gpt-5.3-chat`. **Per-call `timeout=45` is set** (Part 2 P5) — do not remove; the SDK default of ~600s leaks SSE workers under flaky LLM conditions.
- Tool calls: tools are registered in `TOOL_REGISTRY` (dict in `tool_functions_v2.py`) with `roles` AND `sub_categories` lists — always call `_is_tool_authorized(user, tool_def)` in `routes/chat.py`, never check `role in tool_def["roles"]` directly. `sub_categories: None` means any admin; `sub_categories: [...]` means admin must have a matching sub_category; non-admin roles in `roles` bypass the sub_category check.
- **Single authorization gate** (Part 2 P6): `_is_tool_authorized` is called at keyword dispatch, LLM-tool dispatch, execute_action, and confirm dispatch. Do NOT add per-tool body-level role/sub_category checks for static authorization — the registry is the source of truth. Dynamic checks (e.g. record.routing field) may remain as body-level guards.
- Scope enforcement: call `await resolve_scope(user)` before every tool invocation; use `scope.filter()` to get the MongoDB filter dict. **Part 2 P1: `Scope.branch_id` is now ALWAYS populated from the JWT** for non-owner users; `scope.filter()` always emits a `branch_id` clause when set. Tool authors do NOT need to pass branch_id manually — the helper covers it.
- Tool signatures: prefer `(params, user, scope)`. v1 tools in `ai/tool_functions.py` are now all 3-arg (Part 2 P1 migration); never re-introduce a 2-arg tool. The helper `_tenant_query(scope, base)` composes branch_id + schoolId for every Mongo read.
- Write operations (`mark_attendance`, `record_fee_payment`, etc.) require a confirm-action flow — add to `WRITE_ACTION_TOOLS` set in `routes/chat.py`
- **Audit log is write-ahead** (Part 2 P4): `audit_ai_dispatch_pending()` inserts a `status="pending"` row BEFORE the tool runs; `audit_ai_dispatch_finalize()` updates with success/failure after. If the pending insert fails, abort the dispatch with 503. `_infer_success` returns False on missing/non-bool `success` key. Always finalize on exception paths.
- **Tool errors leak nothing** (Part 2 P3): never put `str(e)` into a `tool_result.error`, SSE event, or chat history. Use `{"error": "data_unavailable", "correlation_id": <uuid>}`; full exception goes to `logger.exception(..., correlation_id)`. Same rule for 5xx HTTPException details.
- Max 3 tool-call rounds per chat turn (`MAX_TOOL_ROUNDS = 3`) — design tools to be composable, not monolithic. Part 2 P5 fixed the off-by-one: `tool_rounds` initialises to 1 when a keyword tool fires.
- Conversation history (Part 2 P2): load `HISTORY_KEEP_FIRST` anchors ASC + `HISTORY_KEEP_RECENT` recent DESC and reverse. Never use `.sort(created_at, ASC).to_list(HISTORY_LIMIT)` — loads the OLDEST messages and silently strips recent context. Insert an elision marker between anchors and recent so the LLM does not hallucinate continuity.
- Name resolution (Part 2 P1): `_resolve_params(params, db, scope)` is scope-aware. Ambiguous matches set `_resolution_error` and the chat handler surfaces it to the user BEFORE issuing a confirm token. Inactive matches add `_resolved_inactive: True` instead of silently failing.
- SSE generator (Part 2 P5): the LLM call is wrapped in `try/finally` that always sets `llm_task_done` and `task.cancel()`s on exit. Wallclock cap 90s; poll `request.is_disconnected()` between keepalives. Pass `request=` to `_generate_chat_sse` so disconnect detection works.
- Content filter (Part 2 P8): `filter_response()` is applied to (a) LLM natural-language output; (b) tool data JSON string before injecting into LLM messages for student users; (c) rich_blocks JSON before SSE emit for student users. `check_input_safety()` checks user input. Both use `ai/content_filter.py`.
- **Confirm tokens persist school_id + branch_id** (Part 2 P9): `issue_confirm_token` requires `school_id` and `branch_id` kwargs; `consume_confirm_token` validates them and raises 409 on mismatch. `peek_confirm_token` raises 503 on Mongo errors (no longer silent None). Concurrent 409 replays trigger a compensating `decrement_count()` call so the rate counter stays accurate.
- **Announcement moderation via AI** (Part 2 P7): `tool_create_announcement` in `tool_functions_v2.py` applies the Story 7-47 gate — when `audience_roles` includes `teacher` or `student`, status is `pending_approval` and `sent_at` is None. Mirrors `routes/operations.py` semantics exactly.

---

### Design System Rules

- **Dark-first**: default theme is dark. CSS variables are defined in `index.css` (dark) and overridden in `theme.css` for `[data-theme="light"]`
- **Use CSS variables, not raw hex**: `var(--bg-card)`, `var(--border)`, `var(--text-primary)` etc. Raw hex is only acceptable in Tailwind arbitrary values when a CSS variable doesn't exist
- **Fonts**: `Inter` (body, loaded from Google Fonts in `index.css`), `JetBrains Mono` (monospace/code). The design guidelines specify `Outfit`/`Manrope` but the live codebase uses `Inter` — do not switch fonts without explicit approval
- **Tailwind + inline styles coexist**: existing components mix Tailwind classes and `style={{}}` objects — match the local pattern of the file you're editing
- **Tool icon colors**: each tool has a designated accent from `design_guidelines.json` (`pulse=#F97316`, `fee=#3B82F6`, `staff=#10B981`, etc.) — use these consistently
- **shadcn/ui components** live in `src/components/ui/` — always import from there; never use Radix UI primitives directly in feature components
- **Sidebar width is 120px fixed** — all content areas must account for `margin-left: 120px` or `left: 120px`
- **Chat bubble styles**: user messages = `bg-[#1C1C28] border border-[#222230] rounded-2xl`; AI messages = transparent with a leading avatar
- Add `data-testid` attributes to all interactive elements (buttons, inputs, key sections)

---

### Testing Rules

- Test files live in `tests/` at project root — backend tests are Pytest
- Frontend has no test suite currently — when adding tests, use `craco test` (not `react-scripts test`)
- Backend route tests: use `pytest` with `httpx.AsyncClient` and FastAPI `TestClient` — Motor must be mocked
- Test result state is tracked in `test_result.md` — update it after any test run
- Never test against the live MongoDB Atlas instance — mock `get_db()` in tests
- When testing auth-protected routes, inject a pre-signed JWT in the `Authorization` header

---

### Code Quality & Style Rules

- **No TypeScript** — do not introduce it; keep plain JS
- **No comments that explain what the code does** — only add a comment if the WHY is non-obvious
- **No default error swallowing**: `except Exception: pass` is forbidden — always log or re-raise
- **Logging**: use Python `logging.getLogger(__name__)` in every module — never `print()` in production paths (print is acceptable for startup messages only)
- **Import order** (Python): stdlib → third-party → local, separated by blank lines
- **No wildcard imports**: `from module import *` is forbidden
- **ESLint rules** enforced: `react-hooks/rules-of-hooks: error`, `react-hooks/exhaustive-deps: warn` — do not disable these
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
- **Environment variables**: backend reads from `backend/.env`; frontend reads from `frontend/.env` (`REACT_APP_BACKEND_URL`)
- **New backend route**: create `backend/routes/<name>.py`, add router to `server.py` imports and `app.include_router()` list
- **New frontend tool panel**: create `frontend/src/components/tools/<ToolName>.js`, register in the tool routing in `Layout.js` or `Sidebar.js`
- **Deployment**: push to `main` → AWS Amplify auto-builds frontend; backend deploys via Gunicorn with `application:application`
- **`amplify.yml`** uses `applications:` key with `--legacy-peer-deps` flag — do not remove this flag (needed for React 19 peer dep resolution)
- **`date-fns` is pinned to v3** — never run `yarn upgrade date-fns` or allow it to drift to v4

---

### Critical Don't-Miss Rules

**Security**
- All user-supplied strings used in MongoDB `$regex` must be escaped with `re.escape()` — prevents ReDoS and NoSQL injection
- JWT secret must be set via `JWT_SECRET` env var in production — the fallback dev secret will raise `ValueError` if `ENVIRONMENT=production`
- Never log JWT tokens, passwords, or PII
- CORS origins are explicit (env `CORS_ORIGINS`) — never set `allow_origins=["*"]`

**Multi-tenancy / Branch + School Scoping**
- TWO tenancy axes coexist: `branch_id` (per-branch within a school — legacy) and `schoolId` (per-school — Story 1-3 forward-compat for multi-tenant)
- Every MongoDB query on operational data (students, fees, attendance, staff) MUST include `branch_id` filter via `_apply_branch_filter(query, scope)` in `ai/tool_functions_v2.py`
- `schoolId` is applied via helpers in `backend/tenant.py` — `add_school_id(doc)` for inserts and `scoped_filter(query)` for reads. New code should always set both
- The scope resolver (`resolve_scope`) is the single source of truth for what a user can see — never bypass it
- `owner` role can see all branches; all other roles are scoped to their `branch_id` from the JWT payload
- Default `schoolId` is `"aaryans-joya"` (env `SCHOOL_ID`); default `branch_id` fallback in chat.py is `"branch-aaryans-joya"` — both intentional for single-tenant dev, must be overridden via env/JWT before multi-school production
- For per-tenant overrides (e.g., AI rate-limit overrides), `school_id` MUST come from `tenant.get_school_id()` unconditionally — never trust caller-supplied `user.schoolId` (spoofable)

**Chat / SSE**
- SSE events follow the shape `data: {json}\n\n` with types: `thinking`, `text_delta`, `tool_call`, `tool_result`, `confirm_action`, `navigate`, `done`, `token_exhausted`
- `done` event must always be the last event emitted — missing it leaves the frontend spinner running
- Never `await` inside a generator that yields SSE — use `asyncio.to_thread` for sync I/O inside async generators

**AI Tool Design**
- Tools registered in `TOOL_REGISTRY` must include: `function`, `description`, `parameters` (JSON Schema), `roles` list
- Never return raw MongoDB documents from a tool — always project `{"_id": 0}` and return the `_ok()` / `_empty_result()` shape
- Tool functions are called with `(params: dict, scope: Scope)` — always accept and use `scope` for filtering

**Date Handling**
- All dates stored in MongoDB as ISO strings (e.g., `"2025-06-15"`) — never store datetime objects
- Use `date.today().isoformat()` for today's date in backend — never `str(datetime.now())`
- Frontend date display: use `date-fns` v3 functions (`format`, `parseISO`) — the API is different from v2

**Performance**
- Avoid N+1 queries — batch all secondary lookups
- Motor `.to_list(n)` always requires an explicit limit — never call `.to_list(None)` on unbounded collections
- HISTORY_LIMIT in chat is 20 messages; keep first 2 + last 10 (`HISTORY_KEEP_FIRST=2`, `HISTORY_KEEP_RECENT=10`) — do not load full history

**Anti-Patterns to Avoid**
- Do NOT use `axios` for standard API calls — use `apiFetch` / `authFetch` (native fetch wrappers)
- Do NOT add a new icon library — use `lucide-react` exclusively
- Do NOT create a TypeScript config or rename `.js` files to `.ts`
- Do NOT use `ObjectId` anywhere — all IDs are UUID strings
- Do NOT store sensitive fields (passwords, tokens) in MongoDB documents without hashing
- Do NOT use `find().to_list(None)` — always set a limit
- Do NOT add new npm packages without checking if a shadcn/ui or Radix primitive already covers the use case
- Do NOT bind `_now` (or any time function) as a Python default argument value — Python evaluates defaults at definition time, breaking `monkeypatch.setattr(module, "_now", ...)`. Use `now_fn: Optional[Callable] = None` and resolve via `(now_fn or _now)()` inside the function.

---

## AI Rate Limiting (Story 7-48)

- Per-user-per-hour counter at `db.ai_rate_limit_counters`, keyed `(user_id, hour_bucket)` — **NOT** per-session. Counter must never be keyed on session_id (allows rotation bypass).
- Hour bucket format: `"YYYY-MM-DDTHH:00:00Z"` (UTC, top of hour). Helpers `hour_bucket(now)`, `seconds_until_next_hour(now)`, `hour_bucket_start(bucket)` in `backend/services/ai_rate_limiter.py`.
- Atomic increment via `find_one_and_update` with `$inc` + `$setOnInsert` + `return_document=ReturnDocument.AFTER`. Falls back to `update_one(upsert=True)` + `find_one` if driver lacks `find_one_and_update`.
- Pre-check before increment: if `existing_count >= limit`, return rejection WITHOUT incrementing. Counter must not inflate past limit (operator dashboard would show counts > limit).
- Per-role defaults in `backend/config/ai_rate_limits.yaml` — mtime-cached. Operator override via `PATCH /api/operator/schools/{school_id}/ai-rate-limit` lives in `db.ai_rate_limit_overrides`. Override semantics: insert + mark prior `(school_id, role)` active rows as `superseded: True`. Resolver filters `superseded: {"$ne": True}` AND unexpired.
- Rate-limit check runs BEFORE `consume_confirm_token` in `_execute_confirmed_dispatch` — rejected requests must not burn the confirm token.
- `peek_confirm_token` validates ownership (user_id + session_id match) BEFORE rate-check. Invalid tokens must not burn rate slots. Used/replayed tokens still returned for forensic audit-log context. Mongo errors raise 503 (Part 2 P9).
- 429 response shape: status 429, header `Retry-After: <seconds>`, body `{"success": false, "error": "rate_limit_exceeded", "retry_after_seconds": N, "limit": N, "window": "hour"}`. Use `JSONResponse(status_code=429, headers={...})` — `HTTPException` cannot set custom headers.
- Audit log (`db.ai_dispatch_audit_log`) gained `rate_limit_hit: bool` field. Rate-limited rejections write `executed_at: None`, `success: False`, `rate_limit_hit: True`, `rate_limit_value: <limit>` via `audit_ai_rate_limit_hit`.
- **Rate-limit override requires `expires_at`** (Part 2 P10): `PATCH /api/operator/.../ai-rate-limit` now rejects if `expires_at` key is absent (400). Use `expires_at: null` for permanent overrides. Migration 017 backfills existing rows. Resolver sort is `[("created_at", -1), ("_id", -1)]` for stable tiebreak.
- **Compensating decrement** (Part 2 P9): if `consume_confirm_token` raises 409 (concurrent replay), `decrement_count(user_id, db)` is called to undo the rate-limit increment. Net delta = exactly +1 for the winning request.

---

## Announcement Moderation (Story 7-47)

- `announcements` documents gained `status` field: `"active" | "pending_approval" | "rejected"`. Legacy rows without `status` are treated as `active` for backward compatibility (filter: `{"$or": [{"status": "active"}, {"status": {"$exists": False}}]}`).
- `POST /api/ops/announcements`: when `target_roles` (or `audience_roles`) includes `teacher` or `student`, status defaults to `pending_approval`; admin-only audiences bypass the gate.
- Endpoints: `GET /api/ops/announcements/pending` (principal/owner only), `PATCH /api/ops/announcements/{id}/approve`, `PATCH /api/ops/announcements/{id}/reject` (requires non-empty `reason`).
- Approver gate uses `_can_decide(user)` from `routes/operations.py` (owner OR admin with `sub_category == "principal"`).
- Rejection notifies the original author via `_notify(db, user_id=..., ...)` helper.
- All approve/reject decisions write to `db.audit_logs` via `_audit_doc(action, entity_type, entity_id, user, changes, reason)`.

---

## Reports Endpoints (Story 7-41)

- `GET /api/reports/attendance-trends?months=N` — owner OR principal (admin+sub_category=principal). N clamped to [1, 12]. Returns `overall` series + per-class breakdown.
- `GET /api/reports/fee-collection-summary?months=N` — **owner only** (principal does not see financial data — RBAC). N clamped to [1, 24].
- Empty-state contract: `{"success": True, "empty": True, "data": []}` when no data exists. Frontend renders empty-state message instead of chart.
- Month-bucket key format: `YYYY-MM` (string substring of ISO date). `student_attendance.date` and `fee_transactions.paid_date` are ISO strings, so lexicographic comparison works.
- Frontend: use existing `LineChartWidget` / `BarChartWidget` from `ToolPage.js` (both Recharts-backed, `ResponsiveContainer`-wrapped — mobile-responsive by default).

---

## Operator Endpoints (Story 7-48)

- All endpoints under `/api/operator/*` are owner-only. Use the `_require_owner(request)` helper from `routes/operator.py` (raises 403 with `"Owner-only endpoint"`).
- Add new operator endpoints to `routes/operator.py`, not `routes/settings.py` — operator-namespace is for platform-level controls (rate limits, health, etc.), settings for school-level config.
- Operator endpoint responses follow the standard shape: `{"success": True, "data": {...}}`.

---

## Test Infrastructure

- `tests/backend/conftest.py` holds a session-wide `FakeDb` singleton (`_fake_db`) — collections persist across tests in the same session. **Always add an `autouse` cleanup fixture per test file** that wipes the specific collections the file uses:
  ```python
  @pytest.fixture(autouse=True)
  def _clean(fake_db):
      fake_db.<collection>.docs[:] = []
      yield
      fake_db.<collection>.docs[:] = []
  ```
- When adding new collections, register them as `FakeCollection()` attributes on `FakeDb.__init__`. Same for new route modules — patch `<routes_module>.get_db = lambda: _fake_db` in the APP_AVAILABLE block.
- `FakeCollection` supports `find_one`, `find` (cursor), `count_documents`, `insert_one`, `update_one` (with upsert), `update_many`, `delete_one`, `delete_many`, `aggregate` (limited pipeline), `find_one_and_update` (with `$inc` + `$setOnInsert` + `return_document=AFTER`). It does NOT support: full aggregation pipeline, change streams, transactions.
- When seeding `auth_users` for role-specific test logins, use **unique usernames per test file** (e.g., `principal_rpt` not `principal`). The session-wide DB means name collisions cause the wrong row to win at login.
- Mock `_now` for time-sensitive tests via `monkeypatch.setattr(module, "_now", lambda: <datetime>)` — only works if the module looks up `_now` at call time (not as a default arg).

---

## Auth + RBAC — Part 1 hardening notes

**JWT staleness policy (accepted limitation):**
- Access tokens are issued at login + refresh; claims (including `role`, `sub_category`, `branch_id`) are frozen for the access token's 60-minute TTL.
- If a user's `sub_category` or role changes server-side (e.g., admin promoted to principal), the change takes effect on the **next refresh** (within 60 minutes), not immediately.
- This is an accepted trade-off — re-fetching the user record on every request would double the DB read load.
- Mitigations: `consume_refresh_token` re-fetches `is_active` on every refresh, so deactivation propagates within 60 minutes. Password reset revokes all refresh tokens immediately.
- **Do not add custom session-cache logic per-request** without an explicit performance budget — the staleness window is documented and accepted.

**Access-token revocation (accepted limitation):**
- We do not maintain an access-token deny-list. An access token is valid for its full 60-minute TTL even after the user logs out.
- Logout revokes the **refresh** token, so the user cannot extend the session beyond the access-token's natural expiry.
- Acceptable for the 60-minute window. If short-window leak becomes a concern, add a `token_revocations` collection keyed on JWT `jti` claim — but only if needed.

**Role-check canonical pattern (Part 1 hardening):**
- New routes MUST use one of these dependencies from `middleware/auth.py`:
  - `Depends(require_role("owner", "admin"))` — generic role list
  - `Depends(require_owner)` — owner-only (platform/operator endpoints)
  - `Depends(require_owner_or_principal)` — managerial decision gates
- Error message is always `"Forbidden"` — no allowed-role list leak.
- Legacy inline `if user["role"] not in [...]` checks are tolerated but should be migrated when touching the file. Follow-up story will batch the remaining ~25 routes.

**Legacy admin permissiveness (FIXED in Part 1):**
- `scope_resolver` previously fell through to `type="all"` for any admin row missing `sub_category` (security bug).
- Migration `016_admin_sub_category_default` backfills `sub_category="support_staff"` for these rows.
- Resolver now denies-by-default (`type="self_only"`) for missing sub_category.

**Dev JWT secret (FIXED in Part 1):**
- No longer a committed constant. `secrets.token_urlsafe(48)` is generated per-process when `JWT_SECRET` env var is absent and `ENVIRONMENT != production`.
- Side effect: dev tokens are invalidated on process restart. Set `JWT_SECRET` in `.env` to persist sessions locally.

**Refresh cookie path (FIXED in Part 1):**
- Path widened from `/api/auth` to `/`. Future auth-adjacent endpoints (e.g., `/api/account/*`) now receive the cookie.
- Security still enforced by `HttpOnly + Secure + SameSite=Strict` trio.

**Combined-tenancy helper (Part 1):**
- `scoped_query(query, branch_id=..., school_id=...)` in `backend/tenant.py` returns a MongoDB query satisfying BOTH `branch_id` AND `schoolId` axes.
- New operational queries should use this helper rather than applying `branch_id` and `scoped_filter` separately (which historically dropped one or the other).

---

## Dead Code / Documentation Debt

- **`db.otps` collection** has indexes in `backend/database.py` but **zero references** in active route code. Legacy artifact from a planned phone-OTP login that was never implemented. Password resets use `db.password_reset_tokens`, not `otps`. Do not write to `otps` — the collection should be dropped during Part 4 (Multi-tenancy + Data Layer) audit.

---

## Migration Discipline

- Migrations live in `backend/migrations/NNN_<slug>.py` — sequential numeric prefix.
- Every migration must:
  - Export an `async def migrate(db=None)` callable accepting an optional driver
  - Be idempotent (re-run safe) — wrap mutations in conditional checks where needed
  - Be registered in `run_all.py`'s `MIGRATIONS` list (sequential — DO NOT skip numbers)
- **Known landmine:** `014_ensure_maintenance_user` exists but is NOT in `run_all.py` — flag for repair during Part 4 (Multi-tenancy + Data Layer).
- For TTL indexes, use `expireAfterSeconds=0` and store the actual expiry datetime in the doc's `expires_at` field. Use `sparse=True` for collections where TTL is conditional (some rows persist forever).

