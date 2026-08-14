# EduFlow - Project Documentation Index

_First generated 2026-05-15 by a deep scan. Kept current by hand since; each page below
says what was last checked against the code and when._

> **Read this before trusting a page here.** These docs were machine-generated from a scan
> in May and then edited by hand as the platform changed, so age varies page by page. Where
> a page has been checked against the running code, it says so and gives a date. Where it
> has not, treat it as a starting point and read the code.
>
> **`CLAUDE.md` at the repository root is the live record of what shipped**, and it is
> ahead of this suite. The per-release detail lives in
> `_bmad-output/implementation-artifacts/`.
>
> Corrected 2026-08-14: the deployment runbook described commands that do not exist in this
> repository (`make package-backend`, `eb use eduflow-prod`, `api.example.com`), and the
> data model for enquiries listed a field that has never existed. Both are now written
> against the real thing. If you find another, fix it rather than working around it.

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
- **Tech Stack:** React 19, Vite 6, Tailwind CSS v3, shadcn/ui, plain JS
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
- [Project Overview](./project-overview.md) - Platform summary, capabilities, user roles, what has shipped _(capabilities and shipped list checked 2026-08-14)_
- [Source Tree Analysis](./source-tree-analysis.md) - Annotated directory tree + critical entry points

### Architecture
- [Architecture - Frontend](./architecture-frontend.md) - React SPA architecture, component structure, auth flow, role-based rendering
- [Architecture - Backend](./architecture-backend.md) - FastAPI architecture, multi-tenancy, auth, AI layer, security controls

### API & Data
- [API Contracts - Backend](./api-contracts-backend.md) - All 180+ endpoints by domain with auth requirements. **Admissions (`/api/admissions` and `/api/commercial/crm`) documented 2026-08-14**, including who may enrol and the follow-up worklist
- [Data Models - Backend](./data-models-backend.md) - All MongoDB collections, fields, indexes, migration history. **Admissions collections corrected and expanded 2026-08-14**

### Integration
- [Integration Architecture](./integration-architecture.md) - Frontend↔Backend REST+SSE, Backend↔MongoDB/S3/OpenAI/Gemini/Twilio

### Development Guides
- [Development Guide - Backend](./development-guide-backend.md) - Python setup, env vars, running tests, migrations, code conventions
- [Development Guide - Frontend](./development-guide-frontend.md) - Node/Yarn setup, path aliases, adding tools/API calls, shadcn/ui usage, and **tables: filters, downloads, "All", and the phone/tablet floors** (Release 3)

### Running It
_These pages existed but were missing from this index until 2026-08-14._
- [Deployment Runbook](./deployment-runbook.md) - How a deploy is actually done, the AWS login that catches people out, building and checking the bundle, and proving the new code is live. **Rewritten 2026-08-14 against a real deploy**; the previous version described commands this repository does not have
- [Operations](./operations.md) - Backups, restore procedure, monitoring

### For the People Using It
- [Admin Role Guide](./admin-role-guide.md) - Every admin desk, screen by screen, in plain language. **Admissions rewritten 2026-08-14**: one screen, the follow-up call list, and why nobody can mark a family enrolled by hand
- [Staff Onboarding](./staff-onboarding.md) - Getting a new staff member started
- [Tools - Student and Teacher](./tools-student-teacher.md) - The student and teacher screens

---

## Existing Documentation

- **[CLAUDE.md](../CLAUDE.md) - the live record of what has shipped, and the traps. Ahead of this suite; read it first** ⭐
- [README.md](../README.md) - Minimal (placeholder only)
- [DEPLOYMENT_READINESS.md](../DEPLOYMENT_READINESS.md) - AWS EB readiness assessment (dated 2026-04-30; S3 migration since completed)
- [DEPLOYMENT_AWS_SETUP.md](../DEPLOYMENT_AWS_SETUP.md) - AWS infrastructure setup guide
- [tests/README.md](../tests/README.md) - Test suite documentation
- [_bmad-output/project-context.md](../_bmad-output/project-context.md) - AI agent context (34 critical patterns, last refreshed 2026-05-15) ⭐
- [_bmad-output/platform-quality-sweep.md](../_bmad-output/platform-quality-sweep.md) - Quality sweep master tracker ⭐

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
VITE_BACKEND_URL=http://localhost:8000 yarn start
```

### Run backend tests
```bash
MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test python -m pytest tests/backend/ -q
# Required result: zero failures; the pass count is intentionally not pinned.
```

### Run a migration
```bash
cd backend
# Read and rehearse the specific migration against a production copy first.
python migrations/NNN_specific_migration.py
```

Never run `migrations/run_all.py` against the live school database.

---

## Key Files At a Glance

| File | Purpose |
|------|---------|
| `backend/server.py` | FastAPI app + all routers + middleware stack |
| `backend/database.py` | MongoDB + ScopedDatabase (schoolId auto-injection) |
| `backend/tenant.py` | `scoped_filter()`, `scoped_query()` (branch + school tenancy) |
| `backend/middleware/auth.py` | `get_current_user`, `require_role`, `require_owner` |
| `backend/ai/tool_functions_v2.py` | All AI tool implementations |
| `backend/migrations/run_all.py` | Fresh/test DB aggregate runner; prohibited on live school data |
| `frontend/src/lib/api.js` | Central API client (all fetch calls) |
| `frontend/src/contexts/UserContext.js` | Auth state (user, token, login, logout) |
| `frontend/src/App.js` | Route definitions + protected routes |

---

The active quality and release status is maintained in
`_bmad-output/platform-quality-sweep.md` and the repository `AGENTS.md` banner.

---

_This index is the primary entry point for AI-assisted development on EduFlow. When starting a new feature, point your AI agent here first._
