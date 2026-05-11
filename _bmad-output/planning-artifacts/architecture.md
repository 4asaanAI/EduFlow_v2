---
stepsCompleted: [1, 2, 3, 4, 5, 6, 7, 8, 9]
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/prd-validation-report-v2.md'
  - '_bmad-output/project-context.md'
  - 'DEPLOYMENT_READINESS.md'
  - 'EDUFLOW_BUILD_PLAN.md'
workflowType: 'architecture'
project_name: 'EduFlow Enterprise Upgrade'
user_name: 'Abhimanyu'
date: '2026-05-12'
status: 'complete'
---

# Architecture Decision Document — EduFlow Enterprise Upgrade

**Author:** Abhimanyu
**Date:** 2026-05-12
**Scope:** Brownfield quality upgrade — documenting existing decisions + gaps to close

---

## 1. System Context & Boundaries

### What EduFlow Is

EduFlow is a **chat-first, multi-role school management SaaS** for The Aaryans (a multi-branch CBSE school group in UP). It replaces fragmented paper + WhatsApp workflows with one platform where every school operation — attendance, fees, staff, academics — is accessible through natural-language conversation and structured tool panels.

### System Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        EduFlow System                           │
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────────────────┐  │
│  │  React Frontend  │ ←SSE→  │      FastAPI Backend          │  │
│  │  (AWS Amplify)   │ ←REST→ │  (Elastic Beanstalk/EC2)     │  │
│  └──────────────────┘         └──────────┬───────────────────┘  │
│                                          │                       │
│                          ┌───────────────┼──────────────────┐   │
│                          │               │                  │   │
│                   MongoDB Atlas    Azure OpenAI        AWS S3   │
│                   (primary DB)     (LLM / GPT)      (file store)│
└─────────────────────────────────────────────────────────────────┘
```

### External Integrations

| Service | Purpose | SDK / Protocol |
|---|---|---|
| Azure OpenAI (AI Foundry) | LLM — intent extraction + response generation | `openai` Python SDK, REST |
| MongoDB Atlas | Primary database | `motor` (async), `pymongo` (index setup) |
| AWS S3 | File/photo storage | `boto3` |
| Twilio | SMS (OTP + alerts) | `twilio` Python SDK |
| AWS Amplify | Frontend hosting + CI/CD | `amplify.yml` build config |
| AWS Elastic Beanstalk | Backend hosting | `Procfile`, `application.py` entry point |

---

## 2. Frontend Architecture

### Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | React 19 (CRA + CRACO) | Build via `craco build`, NOT `react-scripts` |
| Routing | React Router DOM v7 | `<BrowserRouter>` pattern |
| Styling | Tailwind CSS v3.4 | v3 only — v4 breaks `@layer base` |
| UI Components | shadcn/ui (Radix UI) | Already installed — never add duplicates |
| Forms | React Hook Form 7 + Zod 3 | `@hookform/resolvers` for Zod integration |
| Charts | Recharts 3 | Only chart library — no Chart.js/D3 |
| Icons | Lucide React | Only icon set — no mixing |
| Toasts | Sonner 2 | via `sonner.jsx` wrapper |
| Date | date-fns **v3.6** + react-day-picker **8.10.1** | Pinned — v4/v9 break compatibility |
| HTTP | `fetch` (native) for all calls; `axios` only for multipart/file upload |

### Directory Structure

```
frontend/src/
├── App.js                    # Root — router + auth gate
├── index.js                  # ReactDOM entry
├── index.css / theme.css     # Global styles + CSS vars
├── lib/
│   ├── api.js                # All API calls — single source of truth
│   └── utils.js              # cn() helper + shared utilities
├── contexts/
│   ├── UserContext.js        # Auth state — JWT + user profile
│   └── ThemeContext.js       # Theme (light/dark/role-based)
├── hooks/
│   └── use-toast.js          # Toast hook (Sonner adapter)
├── components/
│   ├── Layout.js             # Shell: Header + Sidebar + main area
│   ├── ChatInterface.js      # SSE chat — the core UI
│   ├── InputBar.js           # Message input + send
│   ├── MessageRenderer.js    # Markdown + tool result rendering
│   ├── ThinkingProcess.js    # Animated thinking indicator
│   ├── ConfirmActionCard.js  # Write-op confirmation UI
│   ├── ToolDashboard.js      # Right panel — tool selection
│   ├── FloatingAssistant.js  # Floating chat bubble
│   ├── Header.js / Sidebar.js / Login.js
│   ├── ProfileModal.js / SettingsModal.js
│   ├── TokenBudgetBar.js     # Token usage display
│   ├── tools/                # Role-specific tool panels
│   │   ├── OwnerTools.js     # Owner dashboard tools
│   │   ├── AdminTools.js     # Admin tool panel
│   │   ├── TeacherTools.js   # Teacher tools
│   │   ├── StudentTools.js   # Student tools
│   │   ├── AttendanceRecorder.js
│   │   ├── FeeCollection.js
│   │   ├── SchoolPulse.js
│   │   ├── StaffTracker.js
│   │   ├── StudentDatabase.js
│   │   ├── QuerySection.js
│   │   ├── FileUpload.js
│   │   └── ToolPage.js       # Generic tool page wrapper
│   └── ui/                   # shadcn/ui components (do not modify)
```

### Auth Flow (Frontend)

1. `UserContext` checks `localStorage` for `eduflow_token` and `eduflow_user` on mount
2. If present → decode role → route to appropriate tool panel
3. All `api.js` calls inject `Authorization: Bearer <token>` header
4. On any 401 response → clear localStorage → redirect to `/`
5. Token stored as JWT (7-day expiry); refresh is not implemented — re-login on expiry

### SSE Chat Pattern

```
User types → InputBar → POST /api/chat/conversations/{id}/messages (SSE)
Backend streams events:
  { type: "thinking", text: "..." }    → ThinkingProcess component
  { type: "text",     text: "..." }    → MessageRenderer (streamed chars)
  { type: "tool",     name, result }   → MessageRenderer (tool result card)
  { type: "confirm",  action, params } → ConfirmActionCard (write ops)
  { type: "navigate", panel }          → ToolDashboard panel switch
  { type: "done" }                     → end of stream
```

---

## 3. Backend Architecture

### Stack

| Layer | Choice | Notes |
|---|---|---|
| Framework | FastAPI 0.110.1 | Async, OpenAPI auto-docs (dev only) |
| Server | Gunicorn + UvicornWorker | 4 workers, `application:application` entry |
| DB client | Motor 3.3.1 (async) | ALL DB ops must be `async/await` |
| Auth | python-jose + bcrypt | JWT HS256, 7-day expiry |
| LLM | Azure OpenAI via `openai` SDK | Deployment `gpt-5.3-chat` |
| File I/O | boto3 for S3 | Ephemeral disk in `/uploads` is a known gap |
| SMS | Twilio | OTP + alerts |

### Entry Point Chain

```
application.py                   ← Elastic Beanstalk / Gunicorn entry
  └── backend/server.py          ← FastAPI app, middleware, routers
        └── backend/database.py  ← Motor client, indexes
```

### Route Modules

| Router prefix | File | Domain |
|---|---|---|
| `/api/auth` | `routes/auth.py` | Login, OTP, JWT issue |
| `/api/chat` | `routes/chat.py` | Conversations + SSE streaming |
| `/api/students` | `routes/students.py` | Student CRUD |
| `/api/staff` | `routes/staff.py` | Staff CRUD |
| `/api/fees` | `routes/fees.py` | Fee structures + transactions |
| `/api/attendance` | `routes/attendance.py` | Attendance records |
| `/api/tools` | `routes/tools.py` | Tool-panel data endpoints |
| `/api/settings` | `routes/settings.py` | School + user settings |
| `/api/academics` | `routes/academics.py` | Classes, subjects, exams |
| `/api/operations` | `routes/operations.py` | Leave, announcements, visitors |
| `/api/search` | `routes/search.py` | Cross-entity search |
| `/api/notifications` | `routes/notifications.py` | In-app notifications |
| `/api/exports` | `routes/exports.py` | CSV/PDF export |
| `/api/upload` | `routes/upload.py` | File uploads (disk → S3 migration pending) |
| `/api/sms` | `routes/sms.py` | Twilio SMS send |
| `/api/tokens` | `routes/tokens.py` | Token budget + Razorpay top-up |
| `/api/queries` | `routes/queries.py` | Saved/quick queries |
| `/api/assistant` | `routes/assistant.py` | Non-chat AI endpoints |
| `/api/image-gen` | `routes/image_gen.py` | AI image generation |

### Middleware Stack (execution order)

```
1. CORSMiddleware          — explicit origin allowlist (CORS_ORIGINS env var)
2. security_headers        — X-Content-Type-Options, X-Frame-Options, HSTS (prod)
3. log_requests            — method + path + status + duration ms
4. Route handler
5. http_exception_handler  — StarletteHTTPException → JSON + CORS headers
6. validation_exception_handler — Pydantic 422 → JSON + CORS headers
7. global_exception_handler     — catch-all 500
```

### AI Pipeline

```
User message
  │
  ├─ check_input_safety()          ← block harmful content (student role)
  ├─ detect_language()             ← Hindi/English detection
  ├─ build_school_context()        ← inject live DB snapshot into prompt
  ├─ resolve_scope(user)           ← deterministic MongoDB filter per role
  │
  ├─ LLM Round 1: intent extraction + tool selection
  │     llm_client.chat(system_prompt, history)
  │     → parse tool call from response
  │
  ├─ [if tool call detected]
  │     ├─ WRITE_ACTION_TOOLS → emit "confirm" SSE event → wait for user
  │     └─ READ tools → execute via TOOL_REGISTRY[tool_name](params, scope)
  │           └─ up to MAX_TOOL_ROUNDS=3 chained tool calls
  │
  ├─ LLM Round N: generate final response with tool results in context
  │
  ├─ filter_response()             ← scrub PII for student role
  ├─ record_usage()                ← log tokens to token_usage collection
  └─ stream text chars via SSE
```

### Scope Resolver (RBAC)

Every tool call passes through `resolve_scope(user)` which produces a deterministic MongoDB filter:

| Role | Sub-category | Scope |
|---|---|---|
| `owner` | — | All branches, all data |
| `admin` | `principal` | All operational data |
| `admin` | `accountant` | Financial data only |
| `admin` | `transport_head` | Transport data only |
| `admin` | `receptionist` | Enquiries only |
| `admin` | `support_staff` | Self only |
| `teacher` | `hod` | Subject-wide, all classes |
| `teacher` | `coordinator` | Class range (1-5, 6-8, or 9-12) |
| `teacher` | `class_teacher` | Own class-section |
| `teacher` | `subject_teacher` | Assigned classes only |
| `student` | — | Self only |

Deny-by-default: unrecognised role/sub-category → self only.

### Token Budget Service

Monthly per-role limits enforced before each LLM call:

| Role | Default monthly limit |
|---|---|
| `owner` | Unlimited |
| `admin` | 100,000 tokens |
| `teacher` | 50,000 tokens |
| `student` | 20,000 tokens |

Collections: `token_balances` (per branch), `token_usage` (append-only log), `token_purchases` (Razorpay receipts).

---

## 4. Data Models & Collections

### MongoDB Collections

| Collection | Purpose | Key indexes |
|---|---|---|
| `users` | Auth identities (all roles) | `phone` (unique) |
| `students` | Student profiles | `class_id`, `admission_number` (unique, sparse) |
| `staff` | Staff profiles | `user_id` |
| `classes` | Class-sections per academic year | `academic_year_id` |
| `subjects` | Subjects per class | `class_id` |
| `guardians` | Parent/guardian records | `student_id` |
| `student_attendance` | Daily attendance per student | `(student_id, date)` unique |
| `staff_attendance` | Daily attendance per staff | `(staff_id, date)` unique |
| `fee_structures` | Fee templates per class/year | `academic_year_id` |
| `fee_transactions` | Individual fee payment records | `student_id`, `status` |
| `conversations` | Chat conversation metadata | `user_id` |
| `messages` | Chat messages per conversation | `conversation_id` |
| `assignments` | Homework/assignments | `class_id` |
| `leave_requests` | Staff leave applications | `staff_id` |
| `enquiries` | Prospective student enquiries | `status` |
| `otps` | OTP records (TTL auto-delete) | `expires_at` (TTL=0), `phone` |
| `token_balances` | Monthly token pool per branch | `branch_id` (unique) |
| `token_usage` | Per-call token log | `(branch_id, user_id, month)`, `created_at` |
| `token_purchases` | Razorpay top-up receipts | `payment_id` (unique) |

### ID Strategy

All IDs are UUID4 strings (`str(uuid.uuid4())`). MongoDB `_id` is separate from the application `id` field. No ObjectId is exposed to the frontend.

### Migrations

Sequential numbered scripts in `backend/migrations/` (001–011). Run via `backend/migrations/run_all.py`. Migrations are additive only — no destructive schema changes.

---

## 5. API Contracts

### Auth Conventions

- All protected endpoints require `Authorization: Bearer <jwt>` header
- JWT payload: `{ user_id, role, name, sub_category?, branch_id?, initials?, phone? }`
- 401 → not authenticated; 403 → role not authorised

### Response Shape Convention

```json
// Success list
{ "success": true, "data": [...], "meta": { "count": N, "query_time_ms": N } }

// Success single
{ "success": true, "data": {...} }

// Error
{ "detail": "Human-readable error message" }
```

### SSE Event Schema

```
data: {"type": "thinking", "text": "Checking attendance records…"}\n\n
data: {"type": "text", "text": "Here is today's summary…"}\n\n
data: {"type": "tool", "name": "get_fee_summary", "result": {...}}\n\n
data: {"type": "confirm", "action": "record_fee_payment", "params": {...}}\n\n
data: {"type": "navigate", "panel": "fee-collection"}\n\n
data: {"type": "done"}\n\n
```

### Key Endpoint Patterns

| Pattern | Meaning |
|---|---|
| `GET /api/{domain}` | List with optional filters |
| `POST /api/{domain}` | Create |
| `PATCH /api/{domain}/{id}` | Partial update |
| `DELETE /api/{domain}/{id}` | Soft or hard delete |
| `POST /api/chat/conversations/{id}/messages` | SSE stream — returns `text/event-stream` |
| `GET /api/health` | Health check (excluded from request logging) |

---

## 6. Infrastructure & Deployment

### Frontend — AWS Amplify

```yaml
# amplify.yml
preBuild: npm install --legacy-peer-deps   # required for peer dep conflicts
build:    npm run build                    # invokes craco build
output:   build/                           # CRA default output dir
```

- `REACT_APP_BACKEND_URL` env var sets backend base URL
- No SSR — pure SPA, served from S3+CloudFront via Amplify

### Backend — AWS Elastic Beanstalk

```
# Procfile
web: gunicorn application:application --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

- Entry: `application.py` → imports `backend/server.py::app as application`
- 4 Uvicorn workers — stateless, no shared in-memory state between workers
- `.ebextensions/01_environment.config` — EB environment variable injection

### Environment Variables Required

| Variable | Where used |
|---|---|
| `MONGO_URL` | MongoDB Atlas `mongodb+srv://` connection string |
| `DB_NAME` | MongoDB database name |
| `JWT_SECRET` | JWT signing key (required in production) |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI auth |
| `AZURE_OPENAI_ENDPOINT` | Azure AI Foundry endpoint (includes `/openai/v1`) |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name (`gpt-5.3-chat`) |
| `AZURE_OPENAI_API_VERSION` | API version (`2026-03-03`) |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `ENVIRONMENT` | `production` enables HSTS, disables `/api/docs` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 file storage |
| `S3_BUCKET_NAME` | S3 bucket for uploads |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | SMS |
| `TWILIO_PHONE_NUMBER` | Twilio sender number |

### Known Infrastructure Gap

**File uploads currently write to ephemeral local disk** (`backend/uploads/`). On Elastic Beanstalk, this data is lost on instance replacement or deployment. The `upload` router must be migrated to write directly to S3 before go-live. The boto3 client is already installed and configured.

---

## 7. Security & Auth

### Authentication Model

- Phone-number + OTP login (no passwords for most roles)
- Staff/admin may use password login via `routes/auth.py`
- JWT HS256, 7-day sliding window, stored in `localStorage`
- No refresh token — expired sessions require re-login
- OTP records auto-expire via MongoDB TTL index (`expires_at`)

### Authorization Model

- JWT payload carries `role` + `sub_category` + `branch_id`
- `require_role(*roles)` FastAPI dependency enforces role at route level
- `resolve_scope(user)` enforces data-level RBAC inside every tool call
- Write operations (fee collection, attendance, leave approval) require frontend confirmation via `ConfirmActionCard` — backend re-validates before executing

### Security Headers

All responses include: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`. Production adds `Strict-Transport-Security`.

### CORS

Explicit origin allowlist via `CORS_ORIGINS` env var. No wildcards. CORS headers are injected onto exception responses (bypasses middleware) via the `_add_cors()` helper.

### Known Security Gap

**Weak JWT_SECRET fallback in dev mode.** If `JWT_SECRET` is not set and `ENVIRONMENT != production`, it falls back to a hardcoded string with a warning log. CI must ensure the production environment always sets `JWT_SECRET`.

---

## 8. Testing Strategy

### Current State

- `tests/` directory exists with `__init__.py` only — no tests written yet
- `test_result.md` and `test_reports/pytest/` exist from prior runs

### Target Test Baseline (upgrade scope)

**Unit tests** (`tests/unit/`):
- `scope_resolver` — one test per role/sub-category combination
- `token_service` — limit enforcement, graceful fallback for missing balance doc
- `auth` — JWT creation, decode, expiry, invalid token
- `content_filter` — PII scrubbing for student role

**Integration tests** (`tests/integration/`):
- Full SSE chat flow (mock LLM client) — read tool, write tool + confirm
- Fee transaction create + fetch round-trip
- Attendance mark + conflict detection (duplicate unique index)
- Auth flow: OTP request → OTP verify → JWT issued

**Test framework**: pytest + httpx (async FastAPI test client)
**Test runner**: `pytest tests/ -v --tb=short`
**CI**: Add to Amplify/EB pipeline — backend tests must pass before deploy

### Frontend Testing

- No test suite currently
- Priority: smoke tests on ChatInterface SSE parsing and ConfirmActionCard flow
- Tool: React Testing Library + Jest (already available via CRA)

---

## 9. Key Architectural Decisions & Rationale

| Decision | Choice | Why |
|---|---|---|
| Streaming via SSE (not WebSocket) | SSE | Unidirectional server→client stream fits the LLM use case; simpler infra, no WS handshake overhead, works behind ALB |
| Multi-tool chaining (max 3 rounds) | Capped loop | Prevents runaway LLM → tool → LLM loops while allowing compound queries ("attendance + fee status") |
| Scope resolver as separate layer | `scope_resolver.py` | Decouples data-access policy from route handlers; single place to audit/test RBAC; deny-by-default |
| UUID4 strings as IDs | `str(uuid.uuid4())` | Avoids ObjectId serialisation issues in JSON responses; portable |
| Gunicorn + UvicornWorker | 4 workers | Balances CPU utilisation and async I/O; workers are stateless so horizontal scaling is trivial |
| Pinned date-fns v3 + react-day-picker 8 | Version lock | v4/v9 have breaking API changes; risk of silent breakage outweighs upgrade benefit within this scope |
| `fetch` native + axios only for multipart | Split | `fetch` is sufficient for JSON REST; `axios` handles multipart form-data streaming more reliably |
| Token budget with graceful fallback | Unlimited if no balance doc | Dev/new-branch safety net — never crashes on missing config |

---

## Open Architecture Gaps (to close in this upgrade)

| Gap | Impact | Fix |
|---|---|---|
| File uploads to ephemeral disk | Data loss on redeploy | Migrate `routes/upload.py` to S3 via `boto3` |
| No backend test suite | Regressions undetected | Write pytest baseline (scope_resolver, token_service, auth, SSE flow) |
| No frontend test suite | UI regressions undetected | React Testing Library smoke tests on ChatInterface |
| JWT no refresh token | Re-login every 7 days | Acceptable for Phase 1; add refresh in Phase 2 |
| Weak JWT_SECRET dev fallback | Accidental use in prod | CI env validation check on startup |
| Tool v1 + v2 split (`tool_functions.py` + `tool_functions_v2.py`) | Maintenance overhead | Consolidate into single registry in a future pass |
