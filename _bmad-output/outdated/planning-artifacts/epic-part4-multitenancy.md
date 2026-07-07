---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 4'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 4
part_name: 'Multi-tenancy + Data Layer'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 4: Multi-tenancy + Data Layer

## Context

Part 4 targets structural correctness of the multi-tenancy architecture across the full backend. Items were identified and deferred from Parts 1–3 adversarial reviews. The `schoolId` / `branch_id` dual-axis tenancy model is in place but has enforcement gaps, data hygiene issues, and architectural decisions that must be resolved before the platform can support multiple schools (true SaaS).

**Entering baseline:** 387 backend tests, 0 skipped. `project-context.md` refreshed at `e260247`.

---

## Epic P4: Multi-tenancy + Data Layer Hardening

### Story P4.1: Fix exports.py cross-tenant exam-results enrichment

**Problem:** `GET /api/export/exam-results` enriches each result row with class name and subject name by issuing bare `db.classes.find_one({"id": class_id})` and `db.subjects.find_one({"id": subject_id})` calls. These queries lack `schoolId` — they will match any school's class/subject document under a shared Atlas database. Since `ScopedDatabase` wraps the collections, the calls correctly use `db.classes` — BUT if `get_db()` is called outside of a request context or the class_id crosses school boundaries, the filter is not applied.

**Scope:**
- Audit `backend/routes/exports.py` enrichment helpers for all bare collection queries
- Ensure every enrichment lookup uses `get_db()` (not `get_raw_db()`) and passes the correct `schoolId` scope
- Confirm `exam_results` export includes class name, subject name, and student name correctly scoped
- Add integration test: export exam results for school A does not leak school B's class/subject names

**Acceptance Criteria:**
- All enrichment lookups in `exports.py` go through `ScopedCollection` (i.e. use `get_db()`)
- No bare `db.classes.find_one({"id": ...})` without schoolId enforcement
- Integration test passes: cross-school isolation verified for exam-results export
- Existing 387 tests still pass

---

### Story P4.2: Add require_access(role, sub_category) auth helper

**Problem:** `require_role()` in `middleware/auth.py` checks `user["role"]` but cannot express sub_category constraints. Routes that need `admin` + `sub_category=principal` must either use the hardcoded `require_owner_or_principal()` (only two pre-built variants exist) or inline the check. As verticals grow (accountant, receptionist, it_tech, maintenance), the inline pattern spreads and the number of ad-hoc helpers grows unbounded.

**Scope:**
- Add `require_access(role_or_roles, sub_category=None)` to `middleware/auth.py`
  - Accepts a single role string or tuple of roles (matches `require_role()` signature)
  - Optionally accepts `sub_category` string or tuple of sub_categories
  - If `sub_category` is given, user must match BOTH role AND sub_category
  - Returns user dict (same as `require_role`)
  - Logs denied attempts (same style as `require_role`)
  - Factory raises `ValueError` if called with no args (like `require_role`)
- Migrate any inline `sub_category` checks in existing routes to use `require_access()`
- Add unit tests for: role match + sub_category match, role match + sub_category mismatch, role mismatch, no-args guard

**Acceptance Criteria:**
- `require_access("admin", sub_category="accountant")` works as FastAPI dependency
- `require_access(("owner", "admin"), sub_category=("principal", "accountant"))` works
- All existing `require_role()` usages continue to work unchanged
- At least 4 unit tests covering the new helper
- Existing 387 tests still pass

---

### Story P4.3: Add migration 014 to run_all.py and audit all migrations

**Problem:** `014_ensure_maintenance_user` exists in `backend/migrations/` but is NOT included in `backend/migrations/run_all.py`. A fresh database deployment will miss the maintenance user, causing silent failures when the maintenance role tries to log in.

**Scope:**
- Add `014_ensure_maintenance_user` to `run_all.py` in the correct sequential position
- Audit ALL migrations (001–017) to confirm every file in `migrations/` is in `run_all.py` and in the correct order
- Run `run_all.py` against a test database to confirm idempotent execution (no failures on re-run)
- Add a CI-level check: `run_all.py` must list every `.py` migration file in `migrations/` (or document intentional exclusions)
- Add integration test: run all migrations on a fresh test DB, verify `auth_users` has a maintenance user document

**Acceptance Criteria:**
- `run_all.py` includes all 17 migration scripts (001–017) in order
- `run_all.py` executes without error on a clean database
- Re-running `run_all.py` on an already-migrated database is idempotent
- Migration 014 creates the maintenance user with `role=admin`, `sub_category=maintenance`
- Integration test confirms maintenance user present after fresh migration run

---

### Story P4.4: Drop db.otps collection and remove dead code

**Problem:** The `otps` collection is defined in `SYSTEM_COLLECTIONS` in `database.py` and has TTL indexes created at startup (`expires_at`, `phone`). However, there are ZERO code references to this collection anywhere in the codebase (routes, services, AI tools, tests). The indexes consume resources and the collection name creates false expectations for future developers.

**Scope:**
- Confirm zero-reference status: `grep -rn "db.otps\|\.otps" backend/` across all files
- Remove `otps` from `SYSTEM_COLLECTIONS` in `database.py`
- Remove OTP index creation calls from `_create_indexes()` in `database.py`
- Add migration `018_drop_otps_collection.py` that drops the `otps` collection if it exists
- Add `018` to `run_all.py`
- Update `data-models-backend.md` to remove OTP collection entry
- Add a code-level comment or grep CI rule: "if you add OTP auth in future, revisit migration 018"

**Acceptance Criteria:**
- `grep -rn "db.otps\|\.otps" backend/` returns zero hits (except migration 018 itself)
- `database.py` no longer references `otps` in indexes or SYSTEM_COLLECTIONS
- Migration 018 drops the collection without error (idempotent if collection doesn't exist)
- Existing 387 tests still pass
- `run_all.py` includes migration 018

---

### Story P4.5: Enforce branch_id in AI tool layer (scoped_query audit)

**Problem:** ~30 callsites in `backend/ai/tool_functions_v2.py` use `scoped_filter()` (school-only) instead of `scoped_query(..., branch_id=branch_id)` (school + branch). This means AI tool responses may include data from other branches of the same school — a data leak within a multi-branch school.

**Scope:**
- Audit every MongoDB query in `tool_functions_v2.py`:
  - Replace `scoped_filter(...)` with `scoped_query(..., branch_id=branch_id)` wherever branch_id is available in the tool's context
  - Document any callsite where branch_id is intentionally omitted (cross-branch queries) with `# branch-scope: intentional — <reason>` comment
- Ensure the `branch_id` value is threaded from the calling context into tool functions (from `user["branch_id"]`)
- Add a CI grep rule: any new `scoped_filter(` call in `tool_functions_v2.py` (or `tool_functions.py`) must have a companion comment justifying it
- Add integration tests: AI tool response for branch A does not include branch B's data

**Acceptance Criteria:**
- Zero undocumented `scoped_filter(` calls in `tool_functions_v2.py`
- All intentional omissions have `# branch-scope: intentional` comment
- At least 3 integration tests verifying branch isolation in AI tool responses
- `branch_id` is passed from user context to tool queries throughout
- Existing 387 tests still pass

---

### Story P4.6: Architectural decision — schoolId in JWT vs env var

**Problem:** `schoolId` (tenant identifier) currently comes from `os.environ.get("SCHOOL_ID", "aaryans-joya")` — one school per deployment. This is incompatible with true multi-school SaaS where a single backend serves multiple schools. JWT contains `branch_id` but NOT `schoolId`. Every `scoped_filter()` call silently uses the env-var school, so cross-school requests are impossible to make even deliberately.

**Scope (this story is an architectural decision + foundational code change):**
- Document the decision: **env-var-per-instance vs JWT schoolId claim**
  - Option A (current): One EB instance per school — simple, safe, no JWT change needed. Viable for ≤10 schools.
  - Option B (future): Single instance, schoolId in JWT — full SaaS. Requires JWT changes, all `scoped_filter` callsites to use JWT value, auth_users to be cross-school.
- **For Part 4:** Implement Option A hardening:
  - Add a startup validation: if `SCHOOL_ID` is not set, fail with a clear error (not silent default to `aaryans-joya`)
  - Add `SCHOOL_ID` to `backend/.env.example` with documentation
  - Add a health check field: `GET /api/health/ready` should return `school_id` in the response (not the actual value — just `"configured": true/false`)
  - Document Option B migration path in `docs/architecture-backend.md` as a future section
- Write ADR (Architecture Decision Record) to `_bmad-output/parts/multi-tenancy/adr-001-school-id-strategy.md`

**Acceptance Criteria:**
- `SCHOOL_ID` missing at startup raises `ValueError` with clear message in non-dev environments
- `SCHOOL_ID` is in `.env.example` with documentation comment
- `/api/health/ready` includes `"school_id_configured": true/false`
- ADR written and committed
- Existing 387 tests still pass (dev fallback still works in test environment)

---

### Story P4.7: Audit synchronous audit write-ahead gate for availability risk

**Problem:** The audit write-ahead gate (`audit_ai_dispatch_pending` in the AI dispatch path) is synchronous — it blocks the AI response until the audit write completes. If MongoDB is slow or unavailable, this will make ALL AI requests fail (even if the AI itself is healthy). At scale with multiple branches, this is an availability risk.

**Scope:**
- Audit `backend/routes/audit.py` and any AI dispatch path that calls audit write:
  - Identify every synchronous audit write in the hot path (AI dispatch, tool execution)
  - Measure the risk: what happens if the audit write fails? Does the AI request fail-closed or fail-open?
- **Decision:** fail-closed (write required, request fails if audit fails) vs fail-open (write attempted, logged if fails, request proceeds)
- **For Part 4:** Implement fail-open with error logging:
  - Wrap synchronous audit writes in try/except
  - Log a warning if audit write fails, but allow the AI response to proceed
  - Add a metric counter or log field: `audit_write_failed: true`
- Add integration test: simulate audit write failure → AI response still returns (with degraded-mode flag)
- Write decision to ADR `_bmad-output/parts/multi-tenancy/adr-002-audit-gate-strategy.md`

**Acceptance Criteria:**
- Audit write failure does NOT block AI response (fail-open)
- `logger.warning(...)` emitted when audit write fails
- Integration test: mock audit write failure → verify AI response succeeds
- ADR written
- Existing 387 tests still pass

---

### Story P4.8: Add scoping tests for context_builder sub-helpers

**Problem:** `backend/ai/context_builder.py` has 7+ role-specific sub-helpers (e.g. `_build_teacher_context`, `_build_accountant_context`). These helpers fetch school-level data but do NOT enforce `branch_id` scoping. This is currently acceptable (context_builder is school-level) but is undocumented and untested — meaning it could accidentally be broken by a future change that adds branch filtering.

**Scope:**
- Add unit tests for each `context_builder` sub-helper:
  - Verify the helper returns data (smoke test)
  - Verify the helper does NOT apply branch_id filter (intentional — document why)
  - Verify the helper uses `get_db()` (not `get_raw_db()`) for schoolId scoping
- Add a comment block at the top of `context_builder.py` documenting the school-vs-branch scoping decision
- Add at least 7 unit tests (one per role-specific helper)

**Acceptance Criteria:**
- 7+ new unit tests in `tests/backend/test_context_builder.py`
- Each test verifies school-scoped behavior and documents intentional absence of branch scope
- Context builder comment block explains the decision
- All 387 + new tests pass

---

## Epic P4: Retrospective

A retrospective entry for Part 4 to be completed after all P4.1–P4.8 stories are done.
