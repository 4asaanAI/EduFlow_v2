# EduFlow - Claude Code Project Context

**Model:** Claude Sonnet 4.6 (1M context)
**Last updated:** 2026-09-03
**Working agent:** any capable coding model (Anthropic Sonnet/Opus or other providers)

---

## Current Deploy State

**Latest backend:** `eduflow-classnotice-20260815-96499c9` · Frontend: Amplify job 169 · Commit: `96499c9`
**Rollback target:** `eduflow-approvals-20260815-69a2705`

Everything that was pending has shipped: class-targeted announcements, unified approvals
workflow, Chaman Singh's transport-head profile (R3-2), tenth profile for drivers and
conductors (R3-3), searchable drop-downs, entrance-test records (B1), admissions funnel
(A1–A6), audit log and honest menus (Release 4), photo-leak fixes, staff login narrowing,
parent messaging, and deferred Flo tool loading.

**Full release history and deploy hashes:** `_bmad-output/RELEASE-HISTORY.md`

---

## Active Holds — Do Not Start

- **B2, B3, B4** (admissions stage two) — ON HOLD by Abhimanyu's decision of 2026-08-15.
  He is asking the school whether the entrance test is sat on the platform or on paper.
  Do not start any of these three until that question is answered.
- **`announcement-broadcaster` and `circular-sender` merge** — NOT decided. They write
  class labels in different formats (`1-A` vs `1 A`) and target different roles, so
  merging means choosing one format and choosing wrong silently mis-targets circulars.
  Needs Abhimanyu.
- **R3-4** (handing Chaman his credentials) — a deliberate act nobody has taken yet.

---

## Active Constraints

> ### ⛔ A push to `main` IS a frontend deploy. Decide before pushing.
>
> Amplify app `ddxpej151tf13` (EduFlow_v2) builds **every** push to `main` automatically.
> "Code-complete, green, not deployed" is not a state this repository can hold for anything
> with a screen. Keep unfinished frontend off `main` or put the control behind a flag.
> Check deploy status: `aws amplify list-jobs --app-id ddxpej151tf13 --branch-name main`.

> ### ⛔ Never write a secret to a file inside this repository
>
> **This repository is PUBLIC.** Read credentials fresh from their source each time, never
> stage a scratch file holding one, and never `git add` without looking at what is being
> added. The old commit is still reachable by its id even after a force-push and history rewrite.

> ### ⚠️ Deploys MUST run as the `claude-hosting` IAM user
>
> Three AWS logins exist for account `210447603820`. Only **`claude-hosting`** carries
> `AdministratorAccess-AWSElasticBeanstalk`. The wrong key fails on `s3:DeleteObject`
> AFTER the version is created — it looks like a permission gap, not a wrong-key error.
> Do not ask anyone to widen IAM for it.
>
> Keys: `AWS_ACCESS_KEY_ID_HOSTING` / `AWS_SECRET_ACCESS_KEY_HOSTING` in the root `.env`
> (gitignored). Confirm identity before deploying: `aws sts get-caller-identity` — the Arn
> must end `user/claude-hosting`. A failed deploy never takes the school down; it leaves
> the environment Red with "incorrect application version".
>
> **Building the bundle** (no deploy script — build by hand and diff before uploading):
> ```bash
> SHA=$(git rev-parse --short HEAD); ZIP=deploy/eduflow-backend-main-$SHA.zip
> zip -qr $ZIP application.py Procfile requirements.txt backend .platform .ebextensions \
>   -x "*__pycache__*" "*.pyc" "backend/.env" "backend/.env.example" "backend/uploads/*"
> diff <(unzip -Z1 deploy/<last-good>.zip | sort) <(unzip -Z1 $ZIP | sort)  # expect no diff
> ```
> Then `aws s3 cp` to `elasticbeanstalk-ap-south-1-210447603820`, `create-application-version`,
> and `update-environment`. `deploy/*.zip` is gitignored.
>
> **Verify a deploy** by hitting a brand-new route: 401 = code is live and still guarded;
> 404 = it did not ship.

> ### ⚠️ WhatsApp cannot send in production — it is NOT just three unset env vars
>
> No production WhatsApp sender is registered. The only sender on the Twilio account is
> `whatsapp:+14155238886`, which is the shared sandbox number and it is `OFFLINE`. The
> sandbox can only message people who have themselves texted a join code. A WhatsApp
> Business Account does exist (`waba_id 757370660501818`); a real sender must be registered
> to it. No school templates exist; the three approved templates are Layaa AI sales outreach.
> SMS credentials are US numbers (`+12286410951`, `+15612508971`) — expensive and filtered by
> Indian carriers. Do not imply WhatsApp or SMS is ready for school use.

> ### ⚠️ LayaaStat runs on AWS Amplify, app `ddsqdblq9ge74`, NOT Vercel
>
> The repository carries a leftover `vercel.json` that reads as authoritative and is not.
> The Vercel account holds one unrelated project. Going to the wrong console costs time.

---

## Code Facts That Will Trip You Up

These are still live rules derived from production incidents; all are pinned by tests.

**Never return the dict you just passed to `insert_one`.** Mongo stamps `_id` (an
ObjectId) into the caller's dict in place. An ObjectId is not JSON, so FastAPI raises
AFTER the write commits — the caller is told the opposite of what happened. Read it back
with `{"_id": 0}` or strip the key before returning.

**All photos must go through `photo_url_service`.** `test_no_vendor_photo_link_escapes_2026_08_15.py`
fails if any NEW route module returns a person record without importing the service.

**Never bind a module constant as a default argument** (`max_rows: int = MAX_ROWS`).
Python evaluates it once at import; the constant stops being live and every test that
monkeypatches it is silently ignored. Default to `None` and resolve inside the function.

**`/api/audit-log`, not `/api/audit`.** Probing the shorter path returns a 404 that looks
exactly like a failed deploy.

**Adesh must NOT see Aman's changes in the audit trail.** This is a settled decision from
Release 4 (2026-08-12). Adesh seeing Aman's *approval decisions* (in the approvals
workflow) is different and intentional. Keep the two surfaces apart.

**`decide_leave` is deleted.** Everything goes through `decide_leave_request`. Do not
recreate the deleted path or route any leave approval through it.

**`$in` against a list field in `FakeCollection` now stamps correctly.** If you see `$in`
test failures against list fields it is almost certainly a conftest.py version mismatch,
not a logic error.

**`idleLogout.js` stores a deadline, not a countdown.** A sleeping laptop stops timers;
a countdown wakes with time still on it. The deadline is in localStorage and shared across
tabs. A missing deadline means "not idle" (a late sign-out is safer than throwing someone
out mid-sentence). One hour, every profile including the owner.

**The Tests tab (B1) was asserted ABSENT until B1 was built.** That assertion was flipped,
not deleted. It now fails if the tab exists without its panel.

**Announcement targeting is by class ID, never by printed label.** Two screens wrote
`10th A` and `10th-A` for the same class. Any label comparison picks a winner and
mis-targets the other. The rule lives in `backend/services/announcement_audience.py`.

**Transport head has FULL financial visibility of school transport** (fares, who owes
what). The original plan said zero money; Abhimanyu reversed that on 2026-08-15. Everything
else (tuition, concessions, salaries) stays refused — enforced by giving him ONE
purpose-built money tool, not the finance domain.

**TWO different things are called Release 3, and two are called Release 4.** Read
`_bmad-output/planning-artifacts/release-numbering-collision-2026-08-14.md` before using
a release number in any sentence or PR title.

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

EduFlow is a **chat-first, multi-role school management SaaS** for The Aaryans (CBSE school, Joya, Amroha, UP, India). **ONE branch, `branch-joya`, and all 1,876 students sit on it** (1,842 active; counted live 2026-08-08 — do not hardcode a roll anywhere: count it) — the trust has other branches but this platform serves Joya only (Abhimanyu, 2026-07-22; see `backend/school_identity.py`). Branch scoping exists in the code and stays, but it guards a future second branch, not a present one.

School staff (owner, principal, teachers, accountants, etc.) manage attendance, fees, academics, staff, and operations through an AI chat assistant + structured tool panels.

**Stack:** React 19 SPA (AWS Amplify) ↔ FastAPI + Python 3.9 (AWS Elastic Beanstalk) ↔ MongoDB Atlas + AWS S3 + Azure OpenAI

---

## Quality Sweep Status

**Master tracker:** `_bmad-output/platform-quality-sweep.md`
**Project context (34 patterns):** `_bmad-output/project-context.md` ← load this first
**Docs suite:** `docs/index.md` ← full project documentation

| Part | Status | Tests |
|------|--------|-------|
| 1 Auth + RBAC | ✅ Done | - |
| 2 AI Layer | ✅ Done | - |
| 3 Owner role | ✅ Done | - |
| 4 Multi-tenancy | ✅ Done | 387→420 |
| 5–16 | ✅ All Done | 699 tests, full party-mode + adversarial ceremony |
| **Operations.py** | 🔧 Wave 3 in progress | expenses/incidents/transport branch isolation |

> **These are historical per-part figures, not a baseline.** The bar is the FAILURE count
> and it is ZERO. No pass count is recorded here on purpose: every one ever written down
> went stale within days and was then copied forward as a target. Run the commands in
> **Running Tests** below and read the number they print.

**Epic files for all parts:** `_bmad-output/planning-artifacts/epic-part*.md`

---

## Critical Rules - Read Before Writing Any Code

### Python 3.9 (MANDATORY)
```python
from __future__ import annotations  # FIRST LINE in any file using str | None
```
Without this, the file fails to import at test collection time → all fixture-dependent tests silently skip. No exceptions.

### No TypeScript (MANDATORY)
All frontend files are `.js` / `.jsx`. Never create `.ts` / `.tsx`. No type annotations.

### Authentication
```python
# Always import from middleware.auth - never redefine locally
from middleware.auth import get_current_user, require_role, require_access, require_owner, require_owner_or_principal

# Role-only gate
Depends(require_role("owner", "admin"))

# Role + sub_category gate (use this for fine-grained access)
Depends(require_access("admin", sub_category="accountant"))

# Owner-only
Depends(require_owner)

# Owner or admin+principal
Depends(require_owner_or_principal)

# Owner, admin+accountant or admin+principal - the fee-reminder screens
# (WhatsApp defaulter list + bulk send). Widened from owner/accountant on
# 2026-08-08: the principal opens these screens, and the narrower gate made them
# look broken rather than forbidden.
Depends(require_owner_accountant_or_principal)
```

### Multi-tenancy (MANDATORY)
```python
# School scoping - automatic via ScopedDatabase
db = get_db()  # Always use this, never get_raw_db() for operational data
db.students.find(...)  # schoolId injected automatically by ScopedCollection

# Branch scoping - MUST pass explicitly
from tenant import scoped_query
db.students.find(scoped_query({"class_id": cls_id}, branch_id=user.get("branch_id")))

# Intentional school-wide (no branch filter) - add comment
db.classes.find(scoped_filter({}))  # branch-scope: intentional - cross-branch class list
```

**Scoped_query audit (Parts 9-13 MANDATORY):** Before merging any role-vertical story, run:
```bash
grep -n "scoped_filter(" backend/routes/<new_file>.py
```
Every hit must EITHER have a `# branch-scope: intentional - <reason>` comment (approved, do not change) OR be migrated to `scoped_query(branch_id=user.get("branch_id"))`. A hit WITH the comment is a passing result — never convert intentional cross-branch queries.

### Database
- All DB ops must be `async`/`await` with Motor — never pymongo in request handlers
- **Motor cursors:** `find()` returns a cursor, NOT a coroutine. Always chain `.to_list(N)`:
  ```python
  # CORRECT
  items = await db.students.find(query).to_list(500)
  # WRONG - awaiting a cursor object, not the data
  items = await db.students.find(query)
  ```
- Never expose `_id` in responses: `.find(query, {"_id": 0})`
- IDs are string UUID4 — never MongoDB ObjectId
- N+1 queries: batch with `{"id": {"$in": [...]}}` + build a dict, never loop queries
- New indexes go in `database.py → _create_indexes()` only
- New migrations: add to `backend/migrations/` AND update `backend/migrations/run_all.py` in the same PR

### ⛔ NEVER run `run_all.py` against the live school database

**Run migrations one at a time, after reading what that specific file does.** Not the runner.

`_create_indexes()` does **not** run in production (see `database.py` — it is gated on
`CREATE_INDEXES_ON_STARTUP` / non-prod `ENVIRONMENT`, deliberately, so deploying code can never
silently alter the school's data). That means migrations are the only way indexes reach
production, which makes the runner tempting. Do not use it.

**Why (2026-08-06).** The `_migrations` tracking collection was empty while the work behind
those migrations had long since been done by other means, so `run_all.py --status` reported
**0 of 29 applied** and the runner would have executed all of them against 1,802 real students.
Six of them insert **convincing fake data** into what they assume is a fresh demo school:
invented bus routes with real Joya stop names (004), NCERT library books (005), vendors like
"Sharma Furniture Works" (006), discount types plus a fee profile per student (007), events such
as "Republic Day Celebration" (008), and expenses billed to UPPCL (009). `002` reassigns houses
to students who already have them.

The tracking collection records each entry with a category and evidence, with
`marked_without_running: true` where nothing was executed.

**`012_migrate_uploads_to_s3` is CLOSED as NOT APPLICABLE (2026-08-15).** Production holds
five upload records: three are already on S3 and two point at a developer's own Mac
(`/Users/shashisharma/...`) — those bytes never existed on the server. Do not schedule a
rehearsal for it.

**What IS left:** two broken file links on two student records (a photo and a character
certificate). Leaving them or clearing them is a data-quality decision for Abhimanyu.

```bash
# Correct: read the file, then run that one migration and record it.
#   python -c "import 0NN_name; await 0NN_name.migrate(db=db)"  (see the pattern in git history)
# Wrong: python backend/migrations/run_all.py   ← executes every untracked migration
```

### Notification utility (canonical - set in Part 5)
```python
# ✅ CANONICAL (Part 5 ✅ shipped) - ALL notification writes use:
from services.notification_service import create_notification
await create_notification(db=db, user_id=..., title=..., body=...)
# NEVER call db.notifications.insert_one() directly in route handlers
```

### S3 key naming (canonical - set in Part 6)
```python
# ⚠️  Convention established in Part 6 - all new uploads after P6.2 ships use:
key = f"{school_id}/uploads/{file_id}/{safe_filename}"
# Never: f"uploads/{file_id}/{safe_filename}"  ← no school namespace
```

### API Conventions
```python
# Response shapes
{"success": True, "data": [...], "meta": {"count": N}}  # list
{"success": True, "data": {...}}                         # single object

# Errors - ALWAYS raise HTTPException, never return raw dicts
raise HTTPException(status_code=404, detail="Not found")

# 500 errors - global_exception_handler in server.py returns:
{"success": False, "detail": "An internal error occurred"}
# All other HTTPException handlers return:
{"detail": "message"}
# Do NOT add "success" field to non-500 error responses
```

### Frontend Conventions
```js
// API calls - always go through api.js, never inline fetch
import api from '@/lib/api'

// Auth state
const { user, token } = useContext(UserContext)

// File uploads only - use axios; all other calls use native fetch
import axios from 'axios'  // upload only

// Icons - Lucide only
import { Users, BookOpen } from 'lucide-react'

// Path aliases
import { Button } from '@/components/ui/button'  // not ../../components/...

// Tool routing - use React Router v7 primitives (useSearchParams or <Route>)
// NEVER use raw window.location.hash alongside react-router-dom - they conflict
```

### Approvals architecture (do not relax)
All six approval kinds route through `backend/services/approval_registry.py`. A seventh
adds one registry entry. `may_decide` mirrors the gate its own route carries — the
registry can only HIDE a row, never GRANT a decision someone doesn't hold. Flo is NEVER
in the shared approval thread — each person gets Flo privately. See
`_bmad-output/implementation-artifacts/release-3-access/PROGRESS.md` for the full record.

### Admissions: six traps
- **Enrolment has exactly ONE source: `enroll_application`.** `enrolled` was removed as a
  choice from every path including the owner's, and from Flo. Do not put it back.
- **`admission` is NOT a sub-category this platform recognises.** There is no admissions
  desk profile. Do not invent one and do not write a gate that depends on it.
- **`sub_categories` on a registry entry does NOT refuse the management head.**
  `profile_authorization_decision` ignores it for domain profiles by design. The mechanism
  that works is `denied_tools` in `profile_matrix.py`, where a denial wins.
- **TWO generated mirrors, never hand-edited**, each with a drift test:
  `profileMatrix.generated.js` and `admissionsJourney.generated.js`.
- **TWO different pinned count tests.** `EXPECTED_REACH` counts Flo TOOLS;
  `ProfileMenuSweep.test.js` counts SCREENS. They are not the same thing.
- **Stage two (B2–B4) is ON HOLD** — do not start.

---

## Testing Conventions (MANDATORY)

### Every new test file
```python
from __future__ import annotations
import pytest
# NO module-level `pytestmark = pytest.mark.asyncio`. `pytest.ini` sets
# `asyncio_mode = auto`, so every `async def test_…` is marked automatically.
# Adding the mark by hand also lands it on the SYNC tests in the same file, which
# pytest then warns about once per test - that produced 611 warnings before the
# 2026-08-05 audit (A-8). Only add an explicit mark for a tier marker, e.g.
# `pytestmark = [pytest.mark.mongo_real]`.
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
# ✅ CANONICAL (pre-p9-2 ✅ shipped) - use for ALL test data creation (Parts 9+):
from tests.backend.factories import make_student, make_staff, make_fee_transaction
# Do NOT create one-off dicts inline - they fragment into 6 different formats by Part 13
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
├── routes/            # 27 route files - one per domain
├── ai/                # tool_functions_v2.py (active), context_builder.py, llm_client.py
├── services/          # s3_storage, sse, email_service, token_service, confirm_tokens
│                      # notification_service.py ✅ (Part 5)
└── migrations/        # 29 scripts. Run ONE AT A TIME - never run_all.py on prod (see above)

frontend/src/
├── lib/api.js         # ALL API calls - single source of truth
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
├── project-context.md     # 34 critical patterns - load before implementing
├── platform-quality-sweep.md  # master sweep tracker
├── RELEASE-HISTORY.md     # full deploy record and historical release notes
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
| AI PII redaction | **`ai/redaction.py:redact_for_llm()`** - surgical (special-category keys only; never over-block the LLM) | ✅ AI-Hardening F.1 |
| AI-write kill-switch | **`services/ai_kill_switch.py`** (`db.system_flags.ai_writes_enabled`, fails open) | ✅ F.4 - runbook `docs/deployment-runbook.md` §8 |
| Phase-1 action lockdown | **`services/ai_action_policy.py`** single switch `LOCKDOWN_ENABLED` (Owner+Principal-only AI writes) | ✅ F.11/FR43 - Phase 2 widens it, no engine change |
| AI write-tool parity gate | **`tests/backend/parity/` corpus + CI drift gate** | ✅ F.6 - new write tool ⇒ add parity test + corpus entry |

---

## Hotfixes (Ship Before Part 5)

These are active production failures - do NOT wait for their respective sweep parts.
Sprint-status keys: `hotfix-1-file-serve-unauthenticated`, `hotfix-2-fee-collection-receipt-404`, `hotfix-3-leave-approval-rbac-any-admin`

| Hotfix | File | Fix |
|--------|------|-----|
| `hotfix-1-file-serve-unauthenticated` | `backend/routes/upload.py` | `GET /serve/{filename}` has NO auth at all. Add `Depends(get_current_user)` and a `schoolId`-scoped DB lookup. ⚠️ `hotfix-1` = minimal auth guard only. P6.1 (Part 6) adds the full presigned-URL rewrite on top of this guard - do them in order. |
| `hotfix-2-fee-collection-receipt-404` | `frontend/src/components/tools/FeeCollection.js` | `downloadReceipt` calls `GET /api/fees/transactions/{id}/receipt` which does not exist. Fix the URL to match an actual backend endpoint (e.g. re-use the export endpoint or create a minimal receipt route). |
| `hotfix-3-leave-approval-rbac-any-admin` | `backend/routes/staff.py` | `PATCH /leaves/{id}` uses `require_role("owner","admin")` allowing ANY admin sub_category to approve leaves. Use `Depends(require_owner_or_principal)` which correctly allows owner OR admin+principal only. ⚠️ Do NOT use `require_access("owner","admin", sub_category="principal")` - `require_access` does NOT bypass the sub_category check for owner, which would lock the owner out. |

---

## Part Coordination Notes

- **Parts 5 + 8 ship as a coordinated pair** - SSE keepalive contract (Part 5) must be stable before frontend SSE reconnect (Part 8) is implemented
- **Part 9 is the `require_access()` pattern-setter** - Parts 10-13 cross-reference Part 9 for the correct `require_access(role, sub_category)` usage pattern
- **Part 16 MongoDB indexes move to pre-Part-9** - index migration runs before role vertical work to avoid collection scans under load
- **P6.1 + P6.2 serve_file() collision** - both stories modify `serve_file()` in `upload.py`. P6.2 must EXTEND the auth check from P6.1, not replace it
- **Parts 14-15 gated on Story 7-39** - Story 7-39 activates teacher/student logins. Parts 14-15 cannot begin until 7-39 ships. Parts 9-13 are NOT gated

---

## Running Tests

```bash
# Backend (from repo root) - the bar is 0 failed. No pass count is pinned here: the count
# grows every epic, so a written-down number goes stale and then gets read as a target.
# A dozen or so deselected is normal (the credentialed mongo_real + llm_eval tiers).
# Pin the DB first, or a fail-closed guard in conftest.py stops the run (D-04):
#   MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test
python -m pytest tests/backend/ -q

# Frontend unit tests - the bar is 0 failed. RUN FROM THE `frontend/` FOLDER, not the root.
cd frontend && CI=true npx jest

# ⚠️  This line used to read `npx craco test --watchAll=false`. The frontend moved to Vite +
# plain Jest and craco is NOT installed - that command dies with "could not determine
# executable to run". There is no craco.config.js in the repo; do not reintroduce that command.

# Frontend production build - this is what Amplify runs, and it RUNS LINT FIRST
# (`npm run build` = `eslint src --max-warnings=0` then `vite build`). A lint warning
# fails the deploy, so run this before pushing frontend changes, not just the tests.
cd frontend && npm run build

# Frontend E2E
npx playwright test

# Phone and tablet - REAL device profiles (touch, isMobile, proper pixel ratio).
# The older `responsive-chromium` project is Desktop Chrome with the window made narrow.
# Phone and tablet are the PRIMARY devices; desktop is secondary.
npx playwright test --project=phone-pixel --project=tablet-ipad

# ⚠️ Running E2E on a port OTHER than 3000
# `tests/support/e2e_backend.py` now echoes the caller's origin back, so any port works.
# If :3000 is taken: build with `REACT_APP_BACKEND_URL=http://localhost:8000`,
# serve with `npx vite preview --port 3100`, pass `BASE_URL=http://localhost:3100`.

# Dev server
cd backend && uvicorn server:app --reload --port 8000
cd frontend && npm start        # Vite on :3000 (use npm, not yarn)
```

**If tests skip silently:** a file is missing `from __future__ import annotations` — find it and add it.

---

## Before Implementing Any Story

1. Read `_bmad-output/project-context.md` (34 patterns)
2. Read the relevant epic file in `_bmad-output/planning-artifacts/epic-part{N}-*.md`
3. Run `python -m pytest tests/backend/ -x -q` to confirm baseline
4. Check the specific route file + its test file before writing new code
5. Every new test file needs `from __future__ import annotations`. It does NOT need
   `pytestmark = pytest.mark.asyncio` — `asyncio_mode = auto` handles that (audit A-8)
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
AZURE_OPENAI_DEPLOYMENT=gpt-5.6-luna   # Azure deployment name - this is a Beanstalk env var,
# not a code constant. It was "Odin" through 2026-08-06, switched to gpt-5.6-luna same day.
# Always confirm the LIVE value via `aws elasticbeanstalk describe-configuration-settings`
# before trusting this file or llm_client.py's fallback default - both have drifted before.
# Non-dev: a missing Azure key OR endpoint raises ValueError at startup (fail-loud, like SCHOOL_ID)
S3_BUCKET=...
AWS_REGION=ap-south-1
```
