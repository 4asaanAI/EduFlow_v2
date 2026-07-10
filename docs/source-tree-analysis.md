# Source Tree Analysis — EduFlow

_Generated: 2026-05-15 | Scan: deep_

---

## Repository Structure

EduFlow is a **multi-part** project: a React SPA frontend and a FastAPI backend, co-located in a single repository.

```
eduflow/                            # Repository root
├── application.py                  # AWS Elastic Beanstalk entry point → calls backend/server.py
├── Procfile                        # Gunicorn process definition
├── requirements.txt                # Top-level Python deps (mirrors backend/)
├── pytest.ini                      # Backend test configuration
├── playwright.config.js            # E2E test configuration
├── amplify.yml                     # AWS Amplify (frontend) build spec
├── Makefile                        # Dev shortcut commands
│
├── backend/                        # FastAPI API server
│   ├── server.py                   # ★ Entry point — FastAPI app, all routers, middleware
│   ├── database.py                 # MongoDB connection + ScopedDatabase/ScopedCollection
│   ├── tenant.py                   # Multi-tenancy helpers: scoped_filter(), scoped_query()
│   ├── logging_config.py           # Structured JSON logging with contextvars
│   ├── seed.py                     # Seed data script for dev
│   │
│   ├── middleware/
│   │   └── auth.py                 # JWT decode, get_current_user, require_role, require_owner
│   │
│   ├── routes/                     # One file per domain — all import from middleware/auth.py
│   │   ├── auth.py                 # /api/auth — login, refresh, logout, forgot/reset password
│   │   ├── students.py             # /api/students — CRUD + guardians + photo + erase
│   │   ├── staff.py                # /api/staff — CRUD + leave management
│   │   ├── attendance.py           # /api/attendance — student + staff + bulk + SSE stream
│   │   ├── fees.py                 # /api/fees — structures, transactions, discounts + SSE
│   │   ├── academics.py            # /api/academics — assignments, exams, results, lesson plans, AI Q-papers
│   │   ├── operations.py           # /api/ops, /api/operations, /api/transport — ops + workflow + transport
│   │   ├── settings.py             # /api/settings — school config, forms, year-end transition
│   │   ├── exports.py              # /api/export — CSV/Excel exports for all domains
│   │   ├── notifications.py        # /api/notifications — CRUD + unread count
│   │   ├── queries.py              # /api/queries — support ticket management
│   │   ├── search.py               # /api/search — cross-entity search
│   │   ├── sms.py                  # /api/sms — Twilio SMS sending + logs
│   │   ├── upload.py               # /api/uploads — S3-backed file upload/serve/delete
│   │   ├── chat.py                 # /api/chat — conversation CRUD + AI message stream
│   │   ├── chat_upload.py          # /api/chat/upload — file attachment for AI chat
│   │   ├── tools.py                # /api/tools/{tool_id}/execute — AI tool executor
│   │   ├── tokens.py               # /api/tokens — AI token budget management
│   │   ├── operator.py             # /api/operator — super-admin: rate limit overrides
│   │   ├── reports.py              # /api/reports — attendance trends, fee summary charts
│   │   ├── issues.py               # /api/issues — facility/tech/maintenance issue tracking
│   │   ├── audit.py                # /api/audit-log — audit trail read access
│   │   ├── activities.py           # /api/activities — houses, positions, teams
│   │   ├── image_gen.py            # /api/image-gen — AI certificate/ID card generation
│   │   └── import_data.py          # /api/import — CSV data import (validate + commit)
│   │
│   ├── services/                   # Standalone service modules
│   │   ├── ai_rate_limiter.py      # Per-action AI rate limiting with Redis-like counters
│   │   ├── auth_tokens.py          # Refresh token issuance, consumption, revocation
│   │   ├── confirm_tokens.py       # Confirmation token management
│   │   ├── email_service.py        # Transactional email via SMTP
│   │   ├── idempotency.py          # Idempotency-Key middleware storage
│   │   ├── s3_storage.py           # AWS S3 upload/download/delete helpers
│   │   ├── sse.py                  # Server-Sent Events streaming utilities
│   │   └── token_service.py        # AI token budget deduction + balance tracking
│   │
│   ├── ai/                         # AI / LLM layer
│   │   ├── llm_client.py           # Azure OpenAI + Gemini client wrappers
│   │   ├── context_builder.py      # Builds context payload for AI prompt
│   │   ├── scope_resolver.py       # Resolves which data scope to show the AI per role
│   │   ├── content_filter.py       # Content safety filter
│   │   ├── prompts.py              # System prompt templates per role
│   │   ├── tool_functions.py       # AI tool implementations (v1)
│   │   └── tool_functions_v2.py    # AI tool implementations (v2 — active)
│   │
│   ├── config/
│   │   └── ai_rate_limits.yaml     # Per-role AI action rate limit configuration
│   │
│   ├── migrations/                 # MongoDB migration scripts
│   │   ├── run_all.py              # ★ Migration runner — execute all pending migrations
│   │   ├── 001_add_branches.py     # through
│   │   └── 017_backfill_rate_limit_override_expires_at.py
│   │
│   ├── models/
│   │   └── schemas.py              # Pydantic models / request/response schemas
│   │
│   └── uploads/                    # (Legacy) local file storage — replaced by S3
│
├── frontend/                       # React SPA
│   ├── package.json                # Frontend dependencies
│   ├── craco.config.js             # Build config (path aliases: @/ → src/)
│   ├── jsconfig.json               # JS path resolution
│   ├── tailwind.config.js          # Tailwind v3 config
│   ├── components.json             # shadcn/ui config
│   │
│   └── src/
│       ├── index.js                # ★ React entry point
│       ├── App.js                  # ★ Router setup + protected routes
│       │
│       ├── contexts/
│       │   ├── UserContext.js      # Auth state: user, token, login(), logout()
│       │   └── ThemeContext.js     # Light/dark theme state
│       │
│       ├── hooks/
│       │   └── use-toast.js        # Toast notification hook (sonner)
│       │
│       ├── lib/
│       │   ├── api.js              # ★ Central API client — all fetch() calls
│       │   ├── authSession.js      # Auth session persistence helpers
│       │   └── utils.js            # Shared utility functions (cn() etc.)
│       │
│       ├── components/             # Application-level components
│       │   ├── Layout.js           # Main layout (sidebar + header + content)
│       │   ├── Sidebar.js          # Navigation sidebar (role-aware)
│       │   ├── Header.js           # Top header bar
│       │   ├── Login.js            # Login form
│       │   ├── ForgotPassword.js   # Password reset request
│       │   ├── ResetPassword.js    # Password reset form
│       │   ├── ChatInterface.js    # AI chat UI (SSE streaming)
│       │   ├── CommandPalette.js   # ⌘K command palette
│       │   ├── InputBar.js         # Chat input with attachments
│       │   ├── MessageRenderer.js  # Markdown/artifact renderer for AI messages
│       │   ├── ThinkingProcess.js  # AI thinking step visualization
│       │   ├── ConfirmActionCard.js # Confirm destructive AI actions
│       │   ├── ToolDashboard.js    # Tool navigation hub
│       │   ├── ProfileModal.js     # User profile editor
│       │   ├── SettingsModal.js    # School settings editor
│       │   ├── TokenBudgetBar.js   # AI token budget display
│       │   ├── Toast.js            # Toast notification display
│       │   └── ErrorBoundary.js    # React error boundary
│       │
│       ├── components/tools/       # Role-specific tool panels
│       │   ├── ToolPage.js         # Tool page wrapper/router
│       │   ├── AdminTools.js       # Admin/owner tool collection
│       │   ├── OwnerTools.js       # Owner-only school management
│       │   ├── PrincipalDailyOps.js # Principal daily operations
│       │   ├── TeacherTools.js     # Teacher classroom tools
│       │   ├── StudentTools.js     # Student self-service tools
│       │   ├── AttendanceRecorder.js # Attendance recording UI
│       │   ├── FeeCollection.js    # Fee payment collection UI
│       │   ├── FeeSync.js          # Fee sync operations
│       │   ├── StudentDatabase.js  # Student management CRUD
│       │   ├── StaffTracker.js     # Staff management + leave
│       │   ├── SchoolPulse.js      # Dashboard/analytics overview
│       │   ├── AuditLog.js         # Audit log viewer
│       │   ├── FileUpload.js       # Document upload UI
│       │   ├── IncidentTracker.js  # Incident reporting UI
│       │   ├── MaintenanceTools.js # Maintenance request UI
│       │   ├── QuerySection.js     # Support ticket UI
│       │   ├── SchoolActivities.js # Houses/teams/activities UI
│       │   └── TimetableBuilder.js # Timetable builder UI
│       │
│       └── components/ui/          # shadcn/ui base components (Radix UI wrappers)
│           ├── button.jsx, input.jsx, dialog.jsx, ...
│           └── (40+ primitive components)
│
├── tests/                          # Backend test suite
│   ├── backend/                    # Integration tests (48 files)
│   │   ├── conftest.py             # Pytest fixtures + TestClient setup
│   │   ├── test_auth.py            # Auth flow tests
│   │   ├── test_students.py        # Student CRUD tests
│   │   └── ... (per-domain test files)
│   ├── e2e/                        # Playwright E2E tests
│   └── support/                    # Shared test utilities
│
├── _bmad-output/                   # BMAD planning artifacts
│   ├── project-context.md          # ★ AI agent context (34 patterns) — keep current
│   ├── platform-quality-sweep.md   # Master quality sweep tracker
│   └── parts/                      # Per-part PRDs, stories, test artifacts
│
└── docs/                           # ★ This documentation suite
    ├── index.md                    # Master navigation index
    ├── project-overview.md
    ├── architecture-frontend.md
    ├── architecture-backend.md
    ├── api-contracts-backend.md
    ├── data-models-backend.md
    ├── source-tree-analysis.md     # (this file)
    ├── component-inventory-frontend.md
    ├── development-guide-frontend.md
    ├── development-guide-backend.md
    ├── integration-architecture.md
    └── project-scan-report.json   # Scan state
```

---

## Critical Entry Points

| Entry Point | Path | Purpose |
|-------------|------|---------|
| Backend app | `backend/server.py` | FastAPI app + all routers + middleware |
| Backend EB | `application.py` | AWS EB WSGI entry point |
| Frontend app | `frontend/src/index.js` | React bootstrap |
| Frontend routing | `frontend/src/App.js` | Protected routes + role-based rendering |
| API client | `frontend/src/lib/api.js` | All HTTP calls to backend |
| Auth context | `frontend/src/contexts/UserContext.js` | Auth state management |
| DB connection | `backend/database.py` | MongoDB + ScopedDatabase |
| Multi-tenancy | `backend/tenant.py` | `scoped_filter`, `scoped_query` |
| Auth middleware | `backend/middleware/auth.py` | `get_current_user`, `require_role` |

---

## Key Integration Points

```
frontend/src/lib/api.js
    ↓ fetch() with Authorization: Bearer <token>
backend/server.py (CORS, logging, idempotency middleware)
    ↓
backend/middleware/auth.py (JWT validation)
    ↓
backend/routes/*.py (domain handlers)
    ↓
backend/database.py → ScopedDatabase → MongoDB Atlas
    + backend/ai/* (Azure OpenAI / Gemini)
    + backend/services/s3_storage.py (AWS S3)
    + backend/services/email_service.py (SMTP)
    + backend/services/sse.py (SSE streaming)
```
