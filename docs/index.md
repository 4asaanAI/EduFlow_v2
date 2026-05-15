# EduFlow — Project Documentation Index

_Generated: 2026-05-15 | Mode: initial_scan | Scan level: deep_

---

## Project Overview

- **Type:** Multi-part (SPA + REST API)
- **Primary Languages:** JavaScript (frontend), Python 3.9 (backend)
- **Architecture:** React 19 SPA + FastAPI domain-routed monolith + MongoDB Atlas
- **Hosting:** AWS Amplify (frontend) + AWS Elastic Beanstalk (backend)

---

## Quick Reference

### Frontend (`frontend/`)
- **Type:** Web SPA
- **Tech Stack:** React 19, CRA + CRACO, Tailwind CSS v3, shadcn/ui, plain JS
- **Root:** `frontend/src/index.js`
- **API client:** `frontend/src/lib/api.js`

### Backend (`backend/`)
- **Type:** REST API
- **Tech Stack:** FastAPI 0.110.1, Python 3.9, Motor/MongoDB, Pydantic v2, JWT
- **Root:** `backend/server.py`
- **Entry (EB):** `application.py`

---

## Generated Documentation

### Core
- [Project Overview](./project-overview.md) — Platform summary, capabilities, user roles, quality status
- [Source Tree Analysis](./source-tree-analysis.md) — Annotated directory tree + critical entry points

### Architecture
- [Architecture — Frontend](./architecture-frontend.md) — React SPA architecture, component structure, auth flow, role-based rendering
- [Architecture — Backend](./architecture-backend.md) — FastAPI architecture, multi-tenancy, auth, AI layer, security controls

### API & Data
- [API Contracts — Backend](./api-contracts-backend.md) — All 180+ endpoints by domain with auth requirements
- [Data Models — Backend](./data-models-backend.md) — All MongoDB collections, fields, indexes, migration history

### Integration
- [Integration Architecture](./integration-architecture.md) — Frontend↔Backend REST+SSE, Backend↔MongoDB/S3/OpenAI/Gemini/Twilio

### Development Guides
- [Development Guide — Backend](./development-guide-backend.md) — Python setup, env vars, running tests, migrations, code conventions
- [Development Guide — Frontend](./development-guide-frontend.md) — Node/Yarn setup, path aliases, adding tools/API calls, shadcn/ui usage

---

## Existing Documentation

- [README.md](../README.md) — Minimal (placeholder only)
- [DEPLOYMENT_READINESS.md](../DEPLOYMENT_READINESS.md) — AWS EB readiness assessment (dated 2026-04-30; S3 migration since completed)
- [DEPLOYMENT_AWS_SETUP.md](../DEPLOYMENT_AWS_SETUP.md) — AWS infrastructure setup guide
- [tests/README.md](../tests/README.md) — Test suite documentation
- [_bmad-output/project-context.md](../_bmad-output/project-context.md) — AI agent context (34 critical patterns, last refreshed 2026-05-15) ⭐
- [_bmad-output/platform-quality-sweep.md](../_bmad-output/platform-quality-sweep.md) — Quality sweep master tracker ⭐

---

## Getting Started

### Run the backend
```bash
cd backend
python3.9 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in MONGO_URL, DB_NAME, JWT_SECRET
uvicorn server:app --reload --port 8000
```

### Run the frontend
```bash
cd frontend
yarn install
REACT_APP_API_URL=http://localhost:8000 yarn start
```

### Run backend tests
```bash
APP_AVAILABLE=true pytest tests/backend/ -v
# Expected: 387 passed, 0 skipped
```

### Run migrations
```bash
cd backend
python migrations/run_all.py
```

---

## Key Files At a Glance

| File | Purpose |
|------|---------|
| `backend/server.py` | FastAPI app + all routers + middleware stack |
| `backend/database.py` | MongoDB + ScopedDatabase (schoolId auto-injection) |
| `backend/tenant.py` | `scoped_filter()`, `scoped_query()` (branch + school tenancy) |
| `backend/middleware/auth.py` | `get_current_user`, `require_role`, `require_owner` |
| `backend/ai/tool_functions_v2.py` | All AI tool implementations |
| `backend/migrations/run_all.py` | Migration runner |
| `frontend/src/lib/api.js` | Central API client (all fetch calls) |
| `frontend/src/contexts/UserContext.js` | Auth state (user, token, login, logout) |
| `frontend/src/App.js` | Route definitions + protected routes |

---

## Part 4 — Multi-Tenancy Focus Areas

> The next quality sweep (Part 4) targets these specific areas:

1. **`backend/routes/exports.py`** — exam-results enrichment uses cross-tenant class/subject lookups
2. **`backend/middleware/auth.py`** — `require_role()` cannot express `sub_category` constraint; need `require_access(role, sub_category)` helper
3. **`backend/migrations/run_all.py`** — verify migration 014 (`ensure_maintenance_user`) is included
4. **`backend/database.py`** — `otps` collection has indexes defined but zero application code; candidate for removal
5. **`backend/ai/tool_functions_v2.py`** — ~30 AI tool callsites that do not pass `branch_id` to `scoped_query()`
6. **`backend/tenant.py`** — `schoolId` is env-var only (not in JWT); architectural decision needed for true multi-school SaaS
7. **`backend/routes/audit.py`** — audit write-ahead gate is synchronous; availability risk at scale

---

_This index is the primary entry point for AI-assisted development on EduFlow. When starting a new feature, point your AI agent here first._
