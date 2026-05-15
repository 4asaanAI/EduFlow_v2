---
workflowType: 'epics'
project_name: 'EduFlow Quality Sweep — Pre-Part-9 Infrastructure'
user_name: 'Abhimanyusingh'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 'pre-p9'
part_name: 'Pre-Part-9 Infrastructure'
note: 'Run before Part 9 (Principal). Moved from Part 16 per party-mode review 2026-05-15.'
---

# Pre-Part-9 Infrastructure

Run before Part 9 starts. Contains items moved from Part 16 (MongoDB indexes)
and new items identified in party-mode review (test factories, unauthenticated surface test).

## Requirements

FR1: 5 missing MongoDB indexes added to database.py _create_indexes() before Part 9 starts
FR2: shared test factories in tests/backend/factories.py before Part 9 tests are written
FR3: unauthenticated surface test enumerates all routes and asserts 401 for unprotected endpoints

NFR1: index migration is idempotent (safe to run against already-indexed DB)
NFR2: factories.py produces consistent test documents across all parts 9-16
NFR3: surface test runs in CI and fails the build if any route returns 200 without auth

## FR Coverage Map
FR1: pre-p9-1-missing-mongodb-indexes
FR2: pre-p9-2-shared-test-factories
FR3: pre-p9-3-unauthenticated-surface-test

## Epic: Pre-Part-9 Infrastructure

### Story pre-p9-1: Add 5 missing MongoDB indexes

As a platform operator,
I want all frequently-queried collections to have appropriate indexes,
So that role-vertical queries don't cause collection scans under school-hour load.

**Acceptance Criteria:**

**Given** the following indexes are added to `database.py _create_indexes()`:
- `db.exam_results.create_index([("student_id", 1), ("exam_id", 1)])` — for result queries
- `db.audit_log.create_index([("actor_id", 1), ("created_at", -1)])` — for audit queries
- `db.lesson_plans.create_index([("class_id", 1), ("week", 1)])` — for lesson plan queries
- `db.sms_logs.create_index("created_at", expireAfterSeconds=7776000)` — TTL, 90-day retention
- `db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])` — for unread count

**When** the server starts after adding these indexes
**Then** all 5 indexes are created without error (idempotent if already present)

**Given** a test in `tests/backend/test_migrations.py` (extending the existing file)
**When** it calls `db.command("listIndexes", "exam_results")`
**Then** a compound index on `(student_id, exam_id)` is present

**Given** all 420 existing tests
**When** these indexes are added
**Then** all 420 still pass

---

### Story pre-p9-2: Create shared test data factories

As a backend developer writing tests for Parts 9-16,
I want a shared `tests/backend/factories.py` with consistent data factories,
So that every part uses the same document structure and I don't end up with 6 different ways to create a test student.

**Acceptance Criteria:**

**Given** `tests/backend/factories.py` exists with these factory functions:
- `make_student(class_id="cls-1", branch_id="branch-a", **kwargs) -> dict`
- `make_staff(role="teacher", sub_category=None, branch_id="branch-a", **kwargs) -> dict`
- `make_fee_transaction(student_id="stu-1", amount=5000, **kwargs) -> dict`
- `make_audit_record(actor_id="u1", action="student_created", **kwargs) -> dict`
- `make_notification(user_id="u1", read=False, **kwargs) -> dict`
- `make_leave_request(staff_id="s1", status="pending", **kwargs) -> dict`

**When** any factory is called
**Then** it returns a dict with `schoolId="aaryans-joya"` and `branch_id` set by default
**And** kwargs override any field
**And** the returned dict includes a generated `id` (UUID4 string) if not overridden

**Given** a test in `tests/backend/test_factories.py`
**When** `make_student(class_id="cls-2", name="Alice")` is called
**Then** the result has `class_id="cls-2"`, `name="Alice"`, `schoolId="aaryans-joya"`, and a valid `id` field

---

### Story pre-p9-3: Unauthenticated surface test

As a security-conscious developer,
I want a CI test that hits every endpoint without a token and asserts 401,
So that no new endpoint is accidentally left unauthenticated.

**Acceptance Criteria:**

**Given** `tests/backend/test_unauthenticated_surface.py` exists
**When** it runs
**Then** it dynamically discovers all routes from the FastAPI app's `app.routes`
**And** for each route (except the public whitelist), sends a request with NO Authorization header
**And** asserts the response status is 401 (or 403 for role-gate endpoints that still authenticate first)

**Given** the public whitelist:
`/api/health`, `/api/health/ready`, `/api/auth/login`, `/api/auth/forgot-password`,
`/api/auth/reset-password`, `/api/auth/seed-status`, `/api/docs`, `/openapi.json`

**When** a new route is added to server.py without `get_current_user` dependency
**Then** this test fails in CI, catching the oversight

**Given** all 420 existing tests still run
**When** this new test is added
**Then** total count is 420 + N where N = number of newly tested endpoints

## Implementation Order
1. pre-p9-1 (indexes) — no dependencies, ship first
2. pre-p9-2 (factories) — no dependencies, can be parallel with pre-p9-1
3. pre-p9-3 (surface test) — no dependencies, can be parallel with above

## Epic retrospective: optional
