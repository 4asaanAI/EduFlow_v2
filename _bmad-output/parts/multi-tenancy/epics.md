---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - '_bmad-output/planning-artifacts/epic-part4-multitenancy.md'
  - '_bmad-output/parts/multi-tenancy/architecture.md'
  - '_bmad-output/parts/multi-tenancy/adr-001-school-id-strategy.md'
  - '_bmad-output/parts/multi-tenancy/adr-002-audit-gate-strategy.md'
  - '_bmad-output/project-context.md'
workflowType: 'epics'
project_name: 'EduFlow Quality Sweep — Part 4: Multi-tenancy + Data Layer'
user_name: 'Abhimanyusingh'
date: '2026-05-15'
status: 'complete'
part: 4
totalEpics: 4
totalStories: 11
---

# EduFlow Quality Sweep — Part 4: Multi-tenancy + Data Layer — Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for **Part 4 of the EduFlow Platform Quality Sweep**. It decomposes the 9 FRs, 6 NFRs, and 6 architectural requirements into 4 epics and 11 implementation-ready stories. Every story targets structural correctness of the multi-tenancy model, not feature additions.

**Entering baseline:** 387 backend tests, 0 skipped. Python 3.9. `project-context.md` at `e260247`.
**Target on completion:** ≥ 412 backend tests, 0 skipped.

---

## Requirements Inventory

### Functional Requirements

```
FR1: exports.py exam-results enrichment must use ScopedCollection (get_db()) for all
     class/subject lookups — no bare collection access that bypasses schoolId filter.

FR2: A require_access(*roles, sub_category=None) FastAPI dependency must exist in
     middleware/auth.py, supporting both single and tuple role/sub_category args,
     logging denied attempts, raising ValueError on empty invocation, and returning
     the user dict (identical contract to require_role()).

FR3: run_all.py must include all 17 migration scripts (001–017) in sequential order,
     including the previously-missing 014_ensure_maintenance_user. A test must verify
     all migration files are present in run_all.py.

FR4: db.otps must have zero code references in all backend source files. Migration 018
     must drop the collection idempotently. otps must be removed from SYSTEM_COLLECTIONS
     and from _create_indexes() in database.py.

FR5: Every AI tool query on per-branch operational data in tool_functions_v2.py (and
     tool_functions.py v1) must call scoped_query(query, branch_id=branch_id). Intentional
     school-wide queries must carry a # branch-scope: intentional — <reason> comment.
     branch_id must be threaded from user context into all tool functions.

FR6: SCHOOL_ID env var missing at startup must raise ValueError with a clear message in
     non-dev environments (ENVIRONMENT != "development"). /api/health/ready must include
     school_id_configured: true/false. SCHOOL_ID must be documented in .env.example.

FR7: Audit pre-write failures must NOT block AI responses. The gate must wrap the write
     in try/except, emit logger.warning("audit_pre_write_failed", ...) with action and
     user_id structured fields on failure, and proceed without re-raising.

FR8: context_builder.py must have at least 7 unit tests (one per role-specific sub-helper)
     verifying school-scoped behavior and explicitly documenting the intentional absence of
     branch_id scoping via a module-level comment block.

FR9: require_owner() and require_owner_or_principal() must be refactored as thin wrappers
     over require_access(), eliminating the divergent implementation. All tests must continue
     to pass. The public API (function names) must remain unchanged for backwards compatibility.
```

### Non-Functional Requirements

```
NFR1: All 387 existing backend tests must pass after every story implementation — no regressions.

NFR2: Part 4 must add ≥ 25 new tests → target ≥ 412 total at part close.

NFR3: run_all.py migration execution must be idempotent — re-running on an already-migrated
      database must produce no errors and must not create duplicate data.

NFR4: Audit gate failure log must include structured extra fields: action_name and user_id,
      compatible with EduFlow's existing structlog/JSON logging format.

NFR5: Every new backend file using str | None union syntax must include
      `from __future__ import annotations` as the first import (Python 3.9 compatibility).

NFR6: require_access() must be validated via HTTP integration tests through actual FastAPI
      TestClient calls — not just unit tests — verifying the full dependency injection path.
```

### Additional Requirements from Architecture

```
- ADR-001: schoolId from SCHOOL_ID env var (Option A); startup guard required in non-dev.
- ADR-002: Audit gate fail-open with try/except + logger.warning pattern (implementation
           code specified in adr-002-audit-gate-strategy.md).
- ADR-003: CI grep rule — scoped_filter( in tool_functions_v2.py without # branch-scope
           comment is a build failure (grep rule documented but not auto-enforced in Part 4).
- ADR-004: require_access() signature: require_access(*roles, sub_category=None).
- Migration 018 drops otps idempotently (collection.drop() wrapped in if-exists check).
- /api/health/ready must return school_id_configured alongside existing db/ai fields.
```

### UX Design Requirements

```
N/A — Part 4 is backend-only. No frontend changes required.
```

### FR Coverage Map

```
FR1:  P4-E1, Story P4-1.1 — exports.py cross-tenant enrichment fix
FR2:  P4-E2, Story P4-2.1 — require_access() new helper
FR3:  P4-E1, Story P4-1.2 — migration 014 + run_all.py completeness audit
FR4:  P4-E1, Story P4-1.3 — drop db.otps
FR5:  P4-E3, Story P4-3.1 — branch_id enforcement in AI tool queries
FR6:  P4-E4, Story P4-4.1 — SCHOOL_ID startup guard + health endpoint field
FR7:  P4-E4, Story P4-4.2 — audit gate fail-open
FR8:  P4-E3, Story P4-3.2 — context_builder scoping tests + comment block
FR9:  P4-E2, Story P4-2.2 — consolidate require_owner / require_owner_or_principal
NFR1-6: All stories (cross-cutting quality constraints)
```

---

## Epic List

### P4-E1: Trustworthy Data Exports
School administrators can export accurate, school-scoped data from a correctly deployed and fully migrated system.
**FRs covered:** FR1, FR3, FR4

### P4-E2: Unified Role Access Control
All role-based and sub_category access gates in the platform use a single canonical helper — no divergent implementations.
**FRs covered:** FR2, FR9

### P4-E3: Branch-Scoped AI Responses
AI tool responses return branch-isolated data and the context builder's school-scope behavior is documented and tested.
**FRs covered:** FR5, FR8

### P4-E4: Deployment Resilience
Operators detect schoolId misconfiguration at startup, and the AI assistant continues working through brief MongoDB hiccups.
**FRs covered:** FR6, FR7

---

## P4-E1: Trustworthy Data Exports

**Goal:** School administrators can export accurate, school-scoped data from a correctly deployed and fully migrated system. This epic eliminates cross-tenant data leaks in exports, fixes the missing migration, and removes dead database code.

---

### Story P4-1.1: Fix cross-tenant enrichment in exam-results export

As a school administrator,
I want the exam results export to only include class and subject names from my school,
So that exported data is always school-scoped and cannot leak data from other schools sharing the same Atlas cluster.

**Acceptance Criteria:**

**Given** the backend has two schools (School A, School B) in the same Atlas database with different classes
**When** a School A administrator calls `GET /api/export/exam-results`
**Then** all class_name and subject_name values in the CSV are from School A only
**And** no School B class or subject names appear, even if their IDs match

**Given** `exports.py` performs class/subject enrichment lookups
**When** those lookups are inspected
**Then** every `find_one` call goes through `get_db()` (ScopedCollection) — not `get_raw_db()`
**And** no bare `_db.classes.find_one({...})` calls without schoolId filter exist

**Given** the enrichment lookup finds no matching class for a result row
**When** the export is generated
**Then** that row's class_name field is set to `"Unknown"` (not an empty string or None)
**And** the export still completes without error

**Given** all 387 existing backend tests
**When** the fix is applied
**Then** all 387 tests still pass
**And** 1 new integration test for cross-school isolation passes

---

### Story P4-1.2: Migration completeness audit — add 014 and add CI guard

As a platform operator deploying EduFlow on a fresh database,
I want all migrations to run correctly from a clean state,
So that I get a fully functional system including the maintenance user without manual intervention.

**Acceptance Criteria:**

**Given** `run_all.py` is executed against a fresh MongoDB database
**When** all 17 migrations (001–017) run
**Then** execution completes without errors
**And** the `_migrations` collection contains 17 completed entries
**And** `auth_users` contains a maintenance user with `role=admin` and `sub_category=maintenance`

**Given** migration `014_ensure_maintenance_user` was missing from `run_all.py`
**When** it is added in its correct sequential position (after 013, before 015)
**Then** running `run_all.py` on a database that already ran 001–013 applies 014–017 correctly
**And** running `run_all.py` again on a fully migrated database is idempotent (no errors, no duplicates)

**Given** a test in `tests/backend/test_migrations.py`
**When** it scans `backend/migrations/` for `.py` files (excluding `__init__.py` and `run_all.py`)
**Then** every file found is imported/listed in `run_all.py`
**And** the test fails if a migration file exists that is not in `run_all.py`

**Given** the test suite
**When** all fixes are applied
**Then** all 387 + 2 new tests pass (cross-school isolation test + migration completeness test)

---

### Story P4-1.3: Drop db.otps — remove dead collection and indexes

As a platform maintainer,
I want the `otps` collection and its indexes removed from the codebase,
So that the codebase accurately reflects what is actually used and no Atlas resources are wasted on dead indexes.

**Acceptance Criteria:**

**Given** the `otps` collection is referenced in `database.py` (`SYSTEM_COLLECTIONS` and `_create_indexes`)
**When** Story P4-1.3 is complete
**Then** `grep -rn "db\.otps\|\.otps\|\"otps\"" backend/` returns zero hits except in migration 018

**Given** migration `018_drop_otps_collection.py`
**When** it runs against a database that has an `otps` collection
**Then** the collection is dropped and the `_migrations` record is written
**When** it runs against a database that does NOT have an `otps` collection
**Then** it completes without error (idempotent)

**Given** `database.py` `_create_indexes()`
**When** the server starts after Story P4-1.3
**Then** no OTP-related index creation calls are made
**And** `SYSTEM_COLLECTIONS` does not include `"otps"`

**Given** migration 018 is added to `run_all.py`
**When** `run_all.py` is run on a fresh database
**Then** migration 018 executes in sequence (after 017) without error

**Given** all existing 387 + new tests from P4-1.1 and P4-1.2
**When** P4-1.3 is applied
**Then** all tests continue to pass

---

## P4-E2: Unified Role Access Control

**Goal:** All role-based and sub_category access gates use a single canonical helper. No route should implement inline sub_category checks or one-off helper functions. All existing helpers become thin wrappers.

---

### Story P4-2.1: Add require_access() canonical auth helper

As a backend developer adding a new role-gated endpoint,
I want a single `require_access(*roles, sub_category=None)` dependency,
So that I can express any combination of role + sub_category in one line without writing one-off helpers or inline if-blocks.

**Acceptance Criteria:**

**Given** `require_access("admin", sub_category="accountant")` is used as a FastAPI dependency
**When** a user with `role=admin, sub_category=accountant` calls the endpoint
**Then** the request succeeds and the user dict is returned

**When** a user with `role=admin, sub_category=principal` calls the endpoint
**Then** a 403 Forbidden response is returned
**And** `logger.info("role check failed: ...")` is emitted

**Given** `require_access("owner", "admin", sub_category=("principal", "accountant"))` is used
**When** a user with `role=owner` calls the endpoint
**Then** the request succeeds (owner passes regardless of sub_category)

**When** a user with `role=admin, sub_category=receptionist` calls the endpoint
**Then** a 403 Forbidden is returned

**Given** `require_access()` is called with no arguments (empty)
**When** the application starts (or dependency is constructed)
**Then** a `ValueError` is raised immediately with a clear message
**And** the error does NOT reach a live request handler

**Given** a TestClient call to a test endpoint protected by `require_access("admin", sub_category="accountant")`
**When** called with an admin+accountant JWT
**Then** 200 is returned
**When** called with an admin+principal JWT
**Then** 403 is returned
**When** called with a teacher JWT
**Then** 403 is returned
**When** called without Authorization header
**Then** 401 is returned

**Given** all 387 + prior P4-E1 tests
**When** require_access() is added
**Then** all existing tests still pass (require_access() is purely additive — no existing calls changed)

---

### Story P4-2.2: Consolidate require_owner and require_owner_or_principal into require_access()

As a platform maintainer reviewing the auth layer,
I want `require_owner()` and `require_owner_or_principal()` to delegate to `require_access()` internally,
So that there is one implementation of the auth logic and future changes to logging, error format, or role structure only need to be made in one place.

**Acceptance Criteria:**

**Given** the existing `require_owner()` function in `middleware/auth.py`
**When** Story P4-2.2 is complete
**Then** `require_owner()` is implemented as a direct call to `require_access("owner")`
**And** its public signature and behavior (403 for non-owner, user dict returned for owner) are unchanged
**And** all existing routes using `Depends(require_owner)` continue to work

**Given** the existing `require_owner_or_principal()` function
**When** Story P4-2.2 is complete
**Then** it is implemented as `require_access("owner", "admin", sub_category="principal")`
**And** its behavior (allows owner or admin+principal, 403 for others) is unchanged
**And** all existing routes using `Depends(require_owner_or_principal)` continue to work

**Given** any inline sub_category checks in existing routes (e.g., `if user.get("sub_category") != "accountant": raise HTTPException(403)`)
**When** Story P4-2.2 is complete
**Then** those checks are replaced by `Depends(require_access("admin", sub_category="accountant"))`
**And** the route handler no longer contains manual sub_category logic

**Given** the full test suite
**When** Story P4-2.2 is applied
**Then** all tests pass including the new require_access() HTTP integration tests from P4-2.1
**And** no new test failures are introduced

---

## P4-E3: Branch-Scoped AI Responses

**Goal:** AI tool responses return branch-isolated data for every query on per-branch collections. The context builder's intentional school-wide scope is documented and tested so future developers cannot accidentally break either behavior.

---

### Story P4-3.1: Enforce branch_id in AI tool layer — full scoped_query audit

As a teacher at Branch A of a multi-branch school,
I want AI responses to only include my branch's students, attendance, fees, and academic data,
So that I do not accidentally see or act on Branch B's data through the AI assistant.

**Acceptance Criteria:**

**Given** `tool_functions_v2.py` contains queries on per-branch collections (students, staff, attendance, fees, exam_results, assignments, lesson_plans)
**When** Story P4-3.1 is complete
**Then** every such query passes `branch_id=branch_id` to `scoped_query()`
**And** `branch_id` is sourced from `context["user"].get("branch_id")`

**Given** a query that is intentionally school-wide (e.g., fetching all classes for selection)
**When** Story P4-3.1 is complete
**Then** the query uses `scoped_filter()` (not `scoped_query()`)
**And** the same line or the line above has a comment: `# branch-scope: intentional — <reason>`

**Given** `grep -n "scoped_filter(" backend/ai/tool_functions_v2.py`
**When** Story P4-3.1 is complete
**Then** every line returned has a corresponding `# branch-scope: intentional` comment

**Given** `tool_functions.py` (v1, legacy)
**When** Story P4-3.1 is complete
**Then** every `scoped_filter(` call is either migrated to `scoped_query()` or carries `# branch-scope: intentional` comment
**And** no undocumented bare `scoped_filter` calls remain in either tool file

**Given** an integration test with a mock two-branch setup
**When** the AI calls `get_students` tool as a Branch A teacher
**Then** only Branch A students are returned
**When** the AI calls `get_attendance` tool as a Branch A teacher
**Then** only Branch A attendance records are returned
**When** the AI calls `get_fee_status` tool as a Branch A accountant
**Then** only Branch A fee records are returned

**Given** all prior tests
**When** Story P4-3.1 is complete
**Then** all pass, plus ≥ 3 new branch-isolation integration tests pass

---

### Story P4-3.2: Document and test context_builder school-wide scope

As a backend developer maintaining the AI context builder,
I want explicit documentation and tests that confirm context_builder uses school-wide scope intentionally,
So that I understand the design contract and cannot accidentally add branch_id filtering that would break the AI's awareness of the full school.

**Acceptance Criteria:**

**Given** `backend/ai/context_builder.py`
**When** Story P4-3.2 is complete
**Then** the module begins with a comment block (≥5 lines) explaining:
  - That context_builder is school-scoped (not branch-scoped) by design
  - Why: AI needs awareness of the whole school, not just one branch
  - Where branch isolation actually happens (tool_functions_v2.py at execution time)
  - A reference to ADR-003 in the architecture doc

**Given** `tests/backend/test_context_builder.py` (new file)
**When** Story P4-3.2 is complete
**Then** the file contains ≥ 7 test functions, one per role-specific context builder sub-helper:
  - `test_owner_context_uses_get_db` — verifies get_db() used (not get_raw_db())
  - `test_principal_context_uses_get_db`
  - `test_accountant_context_uses_get_db`
  - `test_teacher_context_uses_get_db`
  - `test_receptionist_context_uses_get_db`
  - `test_maintenance_context_uses_get_db`
  - `test_it_tech_context_uses_get_db`

**And** each test has a docstring: "School-scoped only — branch_id intentionally omitted per architecture ADR-003"

**Given** the full test suite after P4-3.2
**When** all tests run
**Then** all pass, including the 7+ new context builder tests
**And** the total test count increases by ≥ 7

---

## P4-E4: Deployment Resilience

**Goal:** Operators detect schoolId misconfiguration at startup with a clear error (not a silent wrong-school default), and the AI assistant continues working through brief MongoDB write hiccups.

---

### Story P4-4.1: SCHOOL_ID startup guard and health endpoint field

As a platform operator deploying EduFlow for a new school,
I want the server to fail fast with a clear error if SCHOOL_ID is not configured,
So that I cannot accidentally deploy a misconfigured instance that silently routes to the wrong school.

**Acceptance Criteria:**

**Given** the server starts with `ENVIRONMENT=production` and `SCHOOL_ID` is not set
**When** `uvicorn server:app` is run
**Then** a `ValueError` is raised during startup with message containing "SCHOOL_ID" and "required"
**And** the server does NOT start in a degraded state silently using "aaryans-joya" default
**And** the Gunicorn/EB healthcheck fails (server is not available)

**Given** the server starts with `ENVIRONMENT=development` and `SCHOOL_ID` is not set
**When** `uvicorn server:app --reload` is run
**Then** the server starts normally using the hardcoded dev default
**And** a warning log is emitted: "SCHOOL_ID not set — using dev default"

**Given** the server starts with `SCHOOL_ID=aaryans-joya` (any environment)
**When** `GET /api/health/ready` is called
**Then** the response JSON includes `"school_id_configured": true`
**And** the existing `db`, `ai`, and `overall` fields are unchanged

**Given** the server starts without SCHOOL_ID in development
**When** `GET /api/health/ready` is called
**Then** the response includes `"school_id_configured": false`

**Given** `backend/.env.example`
**When** Story P4-4.1 is complete
**Then** the file contains a `SCHOOL_ID=` entry with a comment explaining its purpose
**And** the comment notes that missing SCHOOL_ID causes startup failure in production

**Given** all tests (including test suite which runs in development mode)
**When** Story P4-4.1 is applied
**Then** all existing tests pass (dev fallback still works in test environment)
**And** 2 new tests added: startup guard unit test + health/ready field integration test

---

### Story P4-4.2: Audit write-ahead gate — fail-open with structured warning

As a school teacher recording attendance during morning rush,
I want the AI assistant to work even when MongoDB has a brief write latency spike,
So that a temporary database hiccup doesn't block me from using the AI for attendance or fee operations.

**Acceptance Criteria:**

**Given** the AI dispatch path attempts to write a pre-write audit record
**When** the MongoDB write raises an exception (any exception — timeout, network, etc.)
**Then** the exception is caught and NOT re-raised
**And** the AI dispatch continues and returns a response to the user

**Given** the audit write failure is caught
**When** the warning is logged
**Then** `logger.warning("audit_pre_write_failed", ...)` is called
**And** the structured log includes `action_name` (the AI action being dispatched)
**And** the structured log includes `user_id` (from the current user context)
**And** `exc_info=True` is set so the traceback is captured

**Given** an integration test that patches the audit write to raise `Exception("simulated timeout")`
**When** the AI chat endpoint is called with a valid message
**Then** the response is 200 (or SSE stream completes successfully)
**And** the test can assert the warning was logged via caplog

**Given** the AI dispatch succeeds (no MongoDB error)
**When** the audit write succeeds
**Then** behavior is identical to before this story — no change to the happy path

**Given** all tests after Story P4-4.2
**When** run
**Then** all pass, plus 2 new tests (fail-open behavior + structured log fields) pass

---

## Requirements Coverage Verification

| FR | Story | Status |
|----|-------|--------|
| FR1 | P4-1.1 | ✅ Covered — cross-tenant enrichment + isolation test |
| FR2 | P4-2.1 | ✅ Covered — require_access() helper + HTTP integration tests |
| FR3 | P4-1.2 | ✅ Covered — migration 014 + completeness CI test |
| FR4 | P4-1.3 | ✅ Covered — drop otps + migration 018 |
| FR5 | P4-3.1 | ✅ Covered — full scoped_query audit + branch isolation tests |
| FR6 | P4-4.1 | ✅ Covered — startup guard + health field + .env.example |
| FR7 | P4-4.2 | ✅ Covered — fail-open try/except + structured warning log |
| FR8 | P4-3.2 | ✅ Covered — 7 context_builder tests + module comment |
| FR9 | P4-2.2 | ✅ Covered — consolidate require_owner* wrappers |
| NFR1 | All | ✅ Covered — 387 passing at every step (acceptance criteria) |
| NFR2 | All | ✅ Covered — ≥25 new tests across all stories |
| NFR3 | P4-1.2 | ✅ Covered — idempotency AC in Story P4-1.2 |
| NFR4 | P4-4.2 | ✅ Covered — structured log fields in AC |
| NFR5 | All | ✅ Covered — new files must have `from __future__ import annotations` |
| NFR6 | P4-2.1 | ✅ Covered — HTTP integration test via TestClient |

**Coverage: 100% — all 9 FRs and 6 NFRs mapped to stories with testable acceptance criteria.**

---

## Implementation Order

Per the architecture doc (`parts/multi-tenancy/architecture.md` §8):

| Order | Story | Rationale |
|-------|-------|-----------|
| 1 | **P4-1.2** | Migration fix — lowest risk, operationally critical, no dependencies |
| 2 | **P4-1.1** | Data correctness — Critical priority, export fix |
| 3 | **P4-1.3** | Cleanup — zero risk, removes dead code |
| 4 | **P4-2.1** | Add require_access() — additive, no breaking changes |
| 5 | **P4-2.2** | Consolidate helpers — after P4-2.1 exists |
| 6 | **P4-3.1** | Branch enforcement — most callsites, methodical audit |
| 7 | **P4-3.2** | Test-only — context_builder documentation tests |
| 8 | **P4-4.1** | Startup guard — small change, high operational value |
| 9 | **P4-4.2** | Fail-open gate — targeted change, needs careful test |

**Epics flow:** E1 (data integrity) → E2 (auth) → E3 (AI scoping) → E4 (resilience)
