---
project_name: 'eduflow'
user_name: 'Abhimanyu'
date: '2026-05-11'
sections_completed:
  - technology_stack
  - language_rules
  - framework_rules
  - testing_rules
  - code_quality
  - workflow_rules
  - critical_rules
existing_patterns_found: 18
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
- Primary LLM: `LLMClient` in `backend/ai/llm_client.py` — uses Azure OpenAI via OpenAI SDK, deployment `gpt-5.3-chat`
- Tool calls: tools are registered in `TOOL_REGISTRY` (dict in `tool_functions_v2.py`) with `roles` list — always check role before exposing a tool
- Scope enforcement: call `await resolve_scope(user)` before every tool invocation; use `scope.filter()` to get the MongoDB filter dict
- Write operations (`mark_attendance`, `record_fee_payment`, etc.) require a confirm-action flow — add to `WRITE_ACTION_TOOLS` set in `routes/chat.py`
- Max 3 tool-call rounds per chat turn (`MAX_TOOL_ROUNDS = 3`) — design tools to be composable, not monolithic
- Content filter: `check_input_safety()` and `filter_response()` from `ai/content_filter.py` run for student-role users — student-facing AI responses must pass the filter

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

**Multi-tenancy / Branch Scoping**
- Every MongoDB query on operational data (students, fees, attendance, staff) MUST include `branch_id` filter
- The scope resolver (`resolve_scope`) is the single source of truth for what a user can see — never bypass it
- `owner` role can see all branches; all other roles are scoped to their `branch_id` from the JWT payload
- Default `branch_id` fallback in chat.py is `"branch-aaryans-joya"` — this is intentional for dev but must not reach production without a real branch_id in the JWT

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
