# EduFlow — Claude Code Project Context

**Model:** Claude Sonnet 4.6 (1M context)
**Last updated:** 2026-08-05
**Working agent:** any capable coding model (Anthropic Sonnet/Opus or other providers) — execution protocols are written model-agnostically

> ## SHIPPED: Enterprise Commercial Operations (2026-08-05)
>
> Commit `3d989e1` is merged to `origin/main`. EduFlow now has lightweight legal-entity
> ownership/reporting, admissions CRM activities and opportunities, campus POS/retail with
> shifts, split payments and returns, entity-aware accounting-period controls, confirmed Flo
> write tools backed by the same domain services as REST, a permanent built-in `/stop-slop`
> communication habit, hardened prompt/KB context, and nine responsive owner/principal
> management hubs. Branding, theme, legacy records, the single active Joya branch, and current
> deep links were preserved. Hostel and full ERPNext/Frappe framework complexity remain out of
> scope. Source of truth: `_bmad-output/implementation-artifacts/spec-enterprise-commercial-operations.md`.
> Release gate: backend 2,163 passed / 0 failed / 15 credentialed deselected; frontend 439
> passed; responsive Chromium 3 passed; production build passed. No live school database was
> read or modified. The code is pushed, but backend deployment is not verified: the configured
> AWS identity can see no Elastic Beanstalk application or environment in any enabled region.

---

> ## ✅ SHIPPED — AI Layer Reliability (Zero Silent Failures) — completed 2026-07-10
>
> This initiative is **DONE and merged** — all 11 epics (R1–R11) shipped, plus the companion
> non-AI reliability set (R12–R15). See `_bmad-output/platform-quality-sweep.md` rows 18–19
> and `_bmad-output/implementation-artifacts/ai-reliability/epic-R*-completed.md`. Its planning
> docs remain in `_bmad-output/planning-artifacts/` for reference; the execution protocol
> (`EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md`) and its 7 standing rules still govern any
> follow-on AI-layer work. *(This banner previously read "implementation has NOT started" —
> that was true when written and became stale after the work shipped; corrected 2026-07-23.)*
>
> ## 🚧 CURRENT INITIATIVE — UI Sweep (owner-reported defects, 2026-07-22) — branch `ui-sweep-2026-07-22`
>
> Decomposes the owner's reported defects into epics; same 7 standing rules and one-epic-per-run
> discipline. Plan: `_bmad-output/planning-artifacts/epics-ui-sweep-2026-07-22.md`; live logs in
> `_bmad-output/implementation-artifacts/ui-sweep/`. As of 2026-07-23, Epics 1–6, 8, 9, 10 are
> shipped and Epic 7 (School Directory) is built and gate-green, awaiting deploy. The remaining
> open work is the deeper tool-merge consolidation (`epic-7-tool-merge-impact-note.md`, D-44).
> **Baseline note (corrected 2026-08-04):** the "25 pinned failures" phrasing below is
> historical, and so is the "2–3 order-dependent failures" note that replaced it — D-03 ×2 and
> D-35 were all fixed on 2026-07-23. **The suite baseline is 0 failures.** It was 1967 passed /
> **1 failed** between 2026-07-25 and 2026-08-04 (the certificate permission test, NEW-01/02);
> that is now closed. Never re-pin a non-zero baseline.
>
> ## 🚧 CURRENT INITIATIVE — Inspection Remediation (2026-08-04) — branch `inspection-remediation-2026-08-04`
>
> The 14 findings of the 2026-08-04 platform inspection, worked in 3 blocks of 5/5/4.
> Process and the fixed handoff prompt: `_bmad-output/INSPECTION-REMEDIATION-PROTOCOL-2026-08-04.md`.
> **The register is the only source of truth for progress:**
> `_bmad-output/planning-artifacts/inspection-findings-2026-08-04.md`.
> Logs in `_bmad-output/implementation-artifacts/inspection-2026-08-04/`.

---

## How To Talk To The Humans Here (MANDATORY)

**Always use plain, human, non-technical language** when explaining, reporting, or
replying — every message, not just end-of-task summaries. Abhimanyu and Shubham
read these to make decisions and to relay them to the school's staff, not to
review implementation detail.

- Lead with what it means in ordinary words. Use a technical name only when they
  have to type or click it — then give the exact string, clearly marked.
- Leave out internal machinery (file paths, class names, framework terms) unless
  asked, or unless it's the thing that must change.
- Plain ≠ vague or softened. Be just as direct about failures, costs, and risks —
  only in everyday words. If tests fail, say so plainly.
- This governs prose written *to* the user. Code, commit messages, and the epic
  logs keep their normal technical precision.

---

---

## IMPORTANT: `owner` is a SCHOOL role, not Abhimanyu

`owner` in this codebase is **the school's owner** (the account is "Aman Litt"). Abhimanyu is
the **founder of the platform** — he commissions the work and approves deploys, and he does
NOT hold the `owner` role. Corrected 2026-08-04 after several documents addressed him as
though he did ("your AI limit is used up", "only you can print certificates"), which is a
statement about a school staff account and could have produced the wrong decision about who
may do what.

In prose written to Abhimanyu, never say "you" for an `owner`-role capability — say "the
school's owner". In code, `owner` means exactly what it always did; nothing about the
permission model changes.

## What This Project Is

EduFlow is a **chat-first, multi-role school management SaaS** for The Aaryans (CBSE school, Joya, Amroha, UP, India). **ONE branch, `branch-joya`, and all 1,802 students sit on it** — the trust has other branches but this platform serves Joya only (Abhimanyu, 2026-07-22; see `backend/school_identity.py`). The wording here used to say "multi-branch", which was wrong and led an agent to raise branch-scoping as a live gap on 2026-08-04. Branch scoping still exists in the code and stays, but it guards a future second branch, not a present one.

School staff (owner, principal, teachers, accountants, etc.) manage attendance, fees, academics, staff, and operations through an AI chat assistant + structured tool panels.

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
| 5–16 | ✅ All Done | 699 tests, full party-mode + adversarial ceremony |
| **Operations.py** | 🔧 Wave 3 in progress | expenses/incidents/transport branch isolation |

> **These are historical per-part figures, not a baseline.** They record how many tests each
> part added at the time it shipped; they are not the size of the suite today and must never
> be copied into a "the suite should show N" instruction (D-51/D-56). The current measured
> numbers live in **Running Tests** below: backend 2012 passed / 0 failed / 14 deselected,
> frontend 286 passed / 0 failed, both measured 2026-08-04. The bar is the FAILURE count.

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
Every hit must EITHER have a `# branch-scope: intentional — <reason>` comment (approved, do not change) OR be migrated to `scoped_query(branch_id=user.get("branch_id"))`. A hit WITH the comment is a passing result — never convert intentional cross-branch queries.

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
# ✅ CANONICAL (Part 5 ✅ shipped) — ALL notification writes use:
from services.notification_service import create_notification
await create_notification(db=db, user_id=..., title=..., body=...)
# NEVER call db.notifications.insert_one() directly in route handlers
```

### S3 key naming (canonical — set in Part 6)
```python
# ⚠️  Convention established in Part 6 — all new uploads after P6.2 ships use:
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
# ✅ CANONICAL (pre-p9-2 ✅ shipped) — use for ALL test data creation (Parts 9+):
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
│                      # notification_service.py ✅ (Part 5)
└── migrations/        # 018 scripts, run via run_all.py

frontend/src/
├── lib/api.js         # ALL API calls — single source of truth
├── contexts/          # UserContext (auth), ThemeContext
├── components/        # Layout, ChatInterface, ConfirmActionCard, etc.
└── components/tools/  # Role-specific panels: TeacherTools, FeeCollection, etc.

tests/backend/
├── conftest.py        # FakeCollection, FakeCursor (has __aiter__/__anext__)
├── factories.py       # Shared test data factories ✅ (pre-p9-2)
├── api/               # HTTP integration tests
├── unit/              # Unit tests
└── test_unauthenticated_surface.py  # Enumerates all routes, asserts 401 ✅ (pre-p9-3)

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
| Branch scoping: auto vs explicit | **explicit** (`scoped_query(branch_id=...)`) | `_bmad-output/parts/multi-tenancy/architecture.md §3` |
| Auth: one helper vs per-role | **`require_access()` canonical** | `middleware/auth.py` |
| Notification utility | **`create_notification()` canonical** | set in Part 5 |
| S3 key namespace | **`{school_id}/uploads/...`** | set in Part 6 |
| Audit service | **`write_audit()` via `audit_service.py`** | ✅ Part 7 shipped |
| AI PII redaction | **`ai/redaction.py:redact_for_llm()`** — surgical (special-category keys only; never over-block the LLM) | ✅ AI-Hardening F.1 |
| AI-write kill-switch | **`services/ai_kill_switch.py`** (`db.system_flags.ai_writes_enabled`, fails open) | ✅ F.4 — runbook `docs/deployment-runbook.md` §8 |
| Phase-1 action lockdown | **`services/ai_action_policy.py`** single switch `LOCKDOWN_ENABLED` (Owner+Principal-only AI writes) | ✅ F.11/FR43 — Phase 2 widens it, no engine change |
| AI write-tool parity gate | **`tests/backend/parity/` corpus + CI drift gate** | ✅ F.6 — new write tool ⇒ add parity test + corpus entry |

---

## Hotfixes (Ship Before Part 5)

These are active production failures — do NOT wait for their respective sweep parts.
Sprint-status keys: `hotfix-1-file-serve-unauthenticated`, `hotfix-2-fee-collection-receipt-404`, `hotfix-3-leave-approval-rbac-any-admin`

| Hotfix | File | Fix |
|--------|------|-----|
| `hotfix-1-file-serve-unauthenticated` | `backend/routes/upload.py` | `GET /serve/{filename}` has NO auth at all. Add `Depends(get_current_user)` and a `schoolId`-scoped DB lookup. ⚠️ `hotfix-1` = minimal auth guard only. P6.1 (Part 6) adds the full presigned-URL rewrite on top of this guard — do them in order. |
| `hotfix-2-fee-collection-receipt-404` | `frontend/src/components/tools/FeeCollection.js` | `downloadReceipt` calls `GET /api/fees/transactions/{id}/receipt` which does not exist. Fix the URL to match an actual backend endpoint (e.g. re-use the export endpoint or create a minimal receipt route). |
| `hotfix-3-leave-approval-rbac-any-admin` | `backend/routes/staff.py` | `PATCH /leaves/{id}` uses `require_role("owner","admin")` allowing ANY admin sub_category to approve leaves. Use `Depends(require_owner_or_principal)` which correctly allows owner OR admin+principal only. ⚠️ Do NOT use `require_access("owner","admin", sub_category="principal")` — `require_access` does NOT bypass the sub_category check for owner, which would lock the owner out. |

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
# Backend (from repo root) — 0 failed. The "420 passed" here was the Part-4 number and
# went stale years of work ago; the count grows every epic, so the number that matters is
# the FAILURE count. 14 deselected is normal (the credentialed mongo_real + llm_eval tiers).
# Pin the DB first, or a fail-closed guard in conftest.py stops the run (D-04):
#   MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test
python -m pytest tests/backend/ -q

# Frontend unit tests — 2 pre-existing failures in LayoutRouting.test.js (NEW-10 / T12)
CI=true npx craco test --watchAll=false

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
AZURE_OPENAI_API_KEY=...        # preferred (SDK-native); AZURE_OPENAI_KEY also accepted (R9.1)
AZURE_OPENAI_DEPLOYMENT=gpt-5.3-chat   # Azure deployment name (default in llm_client.py)
# Non-dev: a missing Azure key OR endpoint raises ValueError at startup (fail-loud, like SCHOOL_ID)
S3_BUCKET=...
AWS_REGION=ap-south-1
```
