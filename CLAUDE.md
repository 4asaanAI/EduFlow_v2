# EduFlow — Claude Code Project Context

**Model:** Claude Sonnet 4.6 (1M context)  
**Last updated:** 2026-05-15  
**Working agent:** Sonnet handles all implementation from Part 5 onward

---

## What This Project Is

EduFlow is a **chat-first, multi-role school management SaaS** for The Aaryans (multi-branch CBSE school, UP, India). School staff (owner, principal, teachers, accountants, etc.) manage attendance, fees, academics, staff, and operations through an AI chat assistant + structured tool panels.

**Stack:** React 19 SPA (AWS Amplify) ↔ FastAPI + Python 3.9 (AWS Elastic Beanstalk) ↔ MongoDB Atlas + AWS S3 + Azure OpenAI

---

## Quality Sweep Status

**Master tracker:** `_bmad-output/platform-quality-sweep.md`  
**Project context (34 patterns):** `_bmad-output/project-context.md` ← load this first  
**Docs suite:** `docs/index.md` ← full project documentation  

| Part | Status | Tests |
|------|--------|-------|
| 1 Auth + RBAC | ✅ Done | — |
| 2 AI Layer | ✅ Done | — |
| 3 Owner role | ✅ Done | — |
| 4 Multi-tenancy | ✅ Done | 387→420 |
| **5 SSE/Notifications** | **🔜 Next** | 420 baseline |
| 6–16 | 🟦 Queued | — |

**Epic files for all parts:** `_bmad-output/planning-artifacts/epic-part*.md`

---

## Critical Rules — Read Before Writing Any Code

### Python 3.9 (MANDATORY)
```python
from __future__ import annotations  # FIRST LINE in any file using str | None
```
Without this, the file fails to import at test collection time → all fixture-dependent tests silently skip. No exceptions.

### No TypeScript (MANDATORY)
All frontend files are `.js` / `.jsx`. Never create `.ts` / `.tsx`. No type annotations.

### Authentication
```python
# Always import from middleware.auth — never redefine locally
from middleware.auth import get_current_user, require_role, require_access, require_owner, require_owner_or_principal

# Role-only gate
Depends(require_role("owner", "admin"))

# Role + sub_category gate (use this for fine-grained access)
Depends(require_access("admin", sub_category="accountant"))

# Owner-only
Depends(require_owner)

# Owner or admin+principal
Depends(require_owner_or_principal)
```

### Multi-tenancy (MANDATORY)
```python
# School scoping — automatic via ScopedDatabase
db = get_db()  # Always use this, never get_raw_db() for operational data
db.students.find(...)  # schoolId injected automatically by ScopedCollection

# Branch scoping — MUST pass explicitly
from tenant import scoped_query
db.students.find(scoped_query({"class_id": cls_id}, branch_id=user.get("branch_id")))

# Intentional school-wide (no branch filter) — add comment
db.classes.find(scoped_filter({}))  # branch-scope: intentional — cross-branch class list
```

### Database
- All DB ops must be `async`/`await` with Motor — never pymongo in request handlers
- Never expose `_id` in responses: `.find(query, {"_id": 0})`
- IDs are string UUID4 — never MongoDB ObjectId
- N+1 queries: batch with `{"id": {"$in": [...]}}` + build a dict, never loop queries
- New indexes go in `database.py → _create_indexes()` only

### API Conventions
```python
# Response shapes
{"success": True, "data": [...], "meta": {"count": N}}  # list
{"success": True, "data": {...}}                         # single object

# Errors
raise HTTPException(status_code=404, detail="Not found")  # never return raw dicts
```

### Frontend Conventions
```js
// API calls — always go through api.js, never inline fetch
import api from '@/lib/api'

// Auth state
const { user, token } = useContext(UserContext)

// File uploads only — use axios; all other calls use native fetch
import axios from 'axios'  // upload only

// Icons — Lucide only
import { Users, BookOpen } from 'lucide-react'

// Path aliases
import { Button } from '@/components/ui/button'  // not ../../components/...

// HTTP
fetch()  // for all endpoints except uploads
axios    // for multipart/file uploads only
```

---

## Project Structure Quick Reference

```
backend/
├── server.py          # FastAPI app + all routers registered here
├── database.py        # ScopedDatabase, ScopedCollection, _create_indexes()
├── tenant.py          # scoped_filter(), scoped_query(), validate_school_id()
├── middleware/auth.py # get_current_user, require_role, require_access, require_owner*
├── routes/            # 27 route files — one per domain
├── ai/                # tool_functions_v2.py (active), context_builder.py, llm_client.py
├── services/          # s3_storage, sse, email_service, token_service, confirm_tokens
└── migrations/        # 018 scripts, run via run_all.py

frontend/src/
├── lib/api.js         # ALL API calls — single source of truth
├── contexts/          # UserContext (auth), ThemeContext
├── components/        # Layout, ChatInterface, ConfirmActionCard, etc.
└── components/tools/  # Role-specific panels: TeacherTools, FeeCollection, etc.

_bmad-output/
├── project-context.md     # 34 critical patterns — load before implementing
├── platform-quality-sweep.md  # master sweep tracker
├── planning-artifacts/    # epic files for all parts
└── parts/                 # per-part ADRs, architecture, epics
```

---

## Architecture Decisions (ADRs)

| Decision | Verdict | File |
|----------|---------|------|
| schoolId: env-var vs JWT | **env-var per instance** (Option A) | `parts/multi-tenancy/adr-001` |
| Audit gate: sync vs fail-open | **fail-open** (logger.warning + proceed) | `parts/multi-tenancy/adr-002` |
| Branch scoping: auto vs explicit | **explicit** (`scoped_query(branch_id=...)`) | `architecture.md §3` |
| Auth: one helper vs per-role | **`require_access()` canonical** | `middleware/auth.py` |

---

## Running Tests

```bash
# Backend (from repo root) — must show 420 passed, 0 skipped
python -m pytest tests/backend/ -x -q

# Frontend E2E
npx playwright test

# Dev server
cd backend && uvicorn server:app --reload --port 8000
cd frontend && yarn start
```

**If tests skip silently:** a file is missing `from __future__ import annotations` — find it and add it.

---

## Before Implementing Any Story

1. Read `_bmad-output/project-context.md` (34 patterns)
2. Read the relevant epic file in `_bmad-output/planning-artifacts/epic-part{N}-*.md`
3. Run `python -m pytest tests/backend/ -x -q` to confirm baseline
4. Check the specific route file + its test file before writing new code
5. Every new test file needs: `from __future__ import annotations` + `pytestmark = pytest.mark.asyncio`

---

## Key Env Vars (Backend)

```bash
MONGO_URL=mongodb+srv://...    # Required
DB_NAME=eduflow                # Required
JWT_SECRET=...                 # Required in non-dev
SCHOOL_ID=aaryans-joya        # Required in non-dev (raises ValueError if missing)
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development        # development | staging | production
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_KEY=...
S3_BUCKET=...
AWS_REGION=ap-south-1
```
