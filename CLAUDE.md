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
| **Hotfixes** | **🔥 Ship first** | file-serve auth, receipt 404, leave-approval RBAC |
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

**Scoped_query audit (Parts 9-13 MANDATORY):** Before merging any role-vertical story, run:
```bash
grep -n "scoped_filter(" backend/routes/<new_file>.py
```
Every hit must have a `# branch-scope: intentional` comment or be migrated to `scoped_query()`.

### Database
- All DB ops must be `async`/`await` with Motor — never pymongo in request handlers
- **Motor cursors:** `find()` returns a cursor, NOT a coroutine. Always chain `.to_list(N)`:
  ```python
  # CORRECT
  items = await db.students.find(query).to_list(500)
  # WRONG — awaiting a cursor object, not the data
  items = await db.students.find(query)
  ```
- Never expose `_id` in responses: `.find(query, {"_id": 0})`
- IDs are string UUID4 — never MongoDB ObjectId
- N+1 queries: batch with `{"id": {"$in": [...]}}` + build a dict, never loop queries
- New indexes go in `database.py → _create_indexes()` only
- New migrations: add to `backend/migrations/` AND update `backend/migrations/run_all.py` in the same PR

### Notification utility (canonical — set in Part 5)
```python
# After Part 5 ships, ALL notification writes use:
from services.notification_service import create_notification
await create_notification(db=db, user_id=..., title=..., body=...)
# NEVER call db.notifications.insert_one() directly in route handlers
```

### S3 key naming (canonical — set in Part 6)
```python
# All S3 keys must be namespaced by school_id:
key = f"{school_id}/uploads/{file_id}/{safe_filename}"
# Never: f"uploads/{file_id}/{safe_filename}"  ← no school namespace
```

### API Conventions
```python
# Response shapes
{"success": True, "data": [...], "meta": {"count": N}}  # list
{"success": True, "data": {...}}                         # single object

# Errors — ALWAYS raise HTTPException, never return raw dicts
raise HTTPException(status_code=404, detail="Not found")

# 500 errors — global_exception_handler in server.py returns:
{"success": False, "detail": "An internal error occurred"}
# All other HTTPException handlers return:
{"detail": "message"}
# Do NOT add "success" field to non-500 error responses
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

// Tool routing — use React Router v7 primitives (useSearchParams or <Route>)
// NEVER use raw window.location.hash alongside react-router-dom — they conflict
```

---

## Testing Conventions (MANDATORY)

### Every new test file
```python
from __future__ import annotations
import pytest
pytestmark = pytest.mark.asyncio  # ← CRITICAL RULE — goes in EVERY async test file
```

### FakeCursor pattern (async iteration support)
```python
# FakeCursor in conftest.py supports both .to_list() AND async-for
# Use it for any collection that's iterated with `async for doc in cursor:`
from tests.backend.conftest import FakeCollection, FakeCursor
```

### Tenant isolation in fixtures
```python
# Every fixture that creates DB documents must include schoolId:
{"id": "test-id", "schoolId": "aaryans-joya", "branch_id": "branch-a", ...}

# For cross-tenant tests, create docs with different schoolId values:
{"id": "other-school-doc", "schoolId": "other-school", ...}
# Then verify the SUT does NOT return other-school docs
```

### Security test convention (MANDATORY for every new endpoint)
```python
# Every new route MUST have these two tests:
def test_endpoint_unauthenticated_returns_401(client):
    resp = client.get("/api/new-endpoint")  # no Authorization header
    assert resp.status_code == 401

def test_endpoint_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "u1", "role": "student", "name": "T"})
    resp = client.get("/api/new-endpoint", headers=headers)
    assert resp.status_code == 403
```

### Async test timing (keepalive, TTL, delays)
```python
# NEVER sleep(30) in tests. Always monkeypatch the constant:
def test_keepalive_sends_ping(monkeypatch):
    monkeypatch.setattr("services.sse.KEEPALIVE_SECONDS", 0.05)
    # now the loop fires in 50ms, testable with asyncio.wait_for
```

### Shared test factories
```python
# Use tests/backend/factories.py for all test data creation (Part 9+)
from tests.backend.factories import make_student, make_staff, make_fee_transaction
# Do NOT create one-off dicts inline — they fragment into 6 different formats by Part 13
```

### Parametrize decision rule
- Use `@pytest.mark.parametrize` when testing the same code path with N ≥ 3 input variations
- Use separate test functions when each case needs different setup/teardown or different assertions
- Never parametrize across security boundaries (each role variant should be its own named test)

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
│                      # notification_service.py (created in Part 5)
└── migrations/        # 018 scripts, run via run_all.py

frontend/src/
├── lib/api.js         # ALL API calls — single source of truth
├── contexts/          # UserContext (auth), ThemeContext
├── components/        # Layout, ChatInterface, ConfirmActionCard, etc.
└── components/tools/  # Role-specific panels: TeacherTools, FeeCollection, etc.

tests/backend/
├── conftest.py        # FakeCollection, FakeCursor (has __aiter__/__anext__)
├── factories.py       # Shared test data factories (created in Part 9)
├── api/               # HTTP integration tests
├── unit/              # Unit tests
└── test_unauthenticated_surface.py  # Enumerates all routes, asserts 401 (created Part 5)

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
| Notification utility | **`create_notification()` canonical** | set in Part 5 |
| S3 key namespace | **`{school_id}/uploads/...`** | set in Part 6 |
| Audit service | **`write_audit()` via `audit_service.py`** | set in Part 7 |

---

## Hotfixes (Ship Before Part 5)

These are active production failures — do NOT wait for their respective sweep parts:

| Hotfix | File | Fix |
|--------|------|-----|
| `hotfix-1-file-serve-auth` | `backend/routes/upload.py` | Add `Depends(get_current_user)` + schoolId scope to `GET /serve/{filename}` |
| `hotfix-2-receipt-404` | `frontend/src/components/tools/FeeCollection.js` | Fix `downloadReceipt` URL to match actual backend endpoint |
| `hotfix-3-leave-approval-rbac` | `backend/routes/staff.py` | Change `PATCH /leaves/{id}` from `require_role("owner","admin")` to `require_access("owner","admin", sub_category=("principal","hr"))` |

---

## Part Coordination Notes

- **Parts 5 + 8 ship as a coordinated pair** — SSE keepalive contract (Part 5) must be stable before frontend SSE reconnect (Part 8) is implemented
- **Part 9 is the `require_access()` pattern-setter** — Parts 10-13 cross-reference Part 9 for the correct `require_access(role, sub_category)` usage pattern
- **Part 16 MongoDB indexes move to pre-Part-9** — index migration runs before role vertical work to avoid collection scans under load
- **P6.1 + P6.2 serve_file() collision** — both stories modify `serve_file()` in `upload.py`. P6.2 must EXTEND the auth check from P6.1, not replace it
- **Parts 14-15 gated on Story 7-39** — Story 7-39 activates teacher/student logins. Parts 14-15 cannot begin until 7-39 ships. Parts 9-13 are NOT gated

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
6. Every new endpoint needs: unauthenticated test + wrong-role test (security convention)
7. Role-vertical stories (Parts 9-13): run `grep -n "scoped_filter(" backend/routes/<file>.py` and audit every hit

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
