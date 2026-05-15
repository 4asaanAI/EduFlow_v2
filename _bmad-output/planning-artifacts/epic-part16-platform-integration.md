---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 16'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 16
part_name: 'Platform Integration'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy', 'Part 14 Teacher role', 'Part 15 Student role']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 16: Platform Integration

## Context

Part 16 is the capstone quality sweep. By this point all role verticals (owner, admin, teacher, student) are individually hardened. Part 16 validates that these verticals work together correctly as an integrated system: data flows across roles without leakage, JWT expiry is handled gracefully, concurrent writes are idempotent, the platform meets its performance NFRs at expected load, Playwright E2E tests cover the most critical cross-role paths, SMS/WhatsApp integration is verified end-to-end, multi-branch isolation is validated under real conditions, and deployment/backup procedures are documented and tested.

**Entering baseline:** 387 backend tests passing. E2E tests exist in `tests/e2e/` covering: auth.spec.js, chat.spec.js, rate-limit.spec.js, students.spec.js. Cross-role E2E tests (teacher records → principal sees → accountant exports) do NOT exist. No performance benchmarks have been run. No backup/restore test has been conducted.

---

## Epic P16: Platform Integration

### Story P16.0: Establish performance baseline with realistic seed data

**Problem:** There is no performance regression baseline. Without one, it is impossible to tell whether a new index or query change improved or degraded query times.

**Scope:**
- Create a seed script that creates 2000 students, 100 staff, 10000 attendance records, 5000 fee_transactions
- Add `tests/performance/test_query_baseline.py` using `pytest-benchmark` or a simple `time.time()` wrapper
- Not a full load test — just a regression baseline

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a seed script that creates 2000 students, 100 staff, 10000 attendance records, 5000 fee_transactions, when `pytest tests/performance/test_query_baseline.py` runs against this seeded DB, then P95 query time for `GET /api/students`, `GET /api/attendance/student`, `GET /api/fees/transactions` is under 500ms each.

**AC2:** The baseline test is reproducible and can be run on demand against staging without affecting production.

**AC3:** Existing 387 tests still pass.

---

### Story P16.1: Cross-role E2E workflow — attendance recorded by teacher, seen by principal, exported by accountant

**Problem:** No integration test validates the end-to-end data flow from a write by one role through to read by another role. The attendance flow specifically is: teacher marks bulk attendance → SSE event is emitted to `attendance` channel → principal can see today's attendance → owner can export attendance CSV. This chain involves `POST /api/attendance/student/bulk`, `GET /api/attendance/student/today/{class_id}`, `GET /api/attendance/export`, and the SSE stream. If scoping or tenant isolation breaks at any step, the downstream readers may see wrong data or nothing.

**Scope:**
- Add integration test suite `tests/backend/integration/test_cross_role_attendance_flow.py`:
  1. Create a teacher JWT (class_teacher, class C1) and an admin JWT (principal) and an owner JWT
  2. Teacher POSTs bulk attendance for class C1, date D
  3. Principal GETs `/api/attendance/student?class_id=C1&date=D` → records visible
  4. Owner GETs `/api/attendance/export?class_id=C1&month=YYYY-MM` → CSV contains the marked students
  5. Verify scoping: principal query for class C2 on the same date returns only C2 records (not C1)
- Add integration test suite `tests/backend/integration/test_cross_role_fee_flow.py`:
  1. Accountant records fee payment for student S1
  2. Student (with consent) calls `GET /api/fees/my` → transaction visible
  3. Owner calls `GET /api/fees/transactions?student_id=S1` → same transaction visible
  4. Export: owner calls fee export → CSV contains S1 row
- Add Playwright E2E test `tests/e2e/teacher-attendance-flow.spec.js` covering the same flow through the UI

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given teacher T1 marks attendance for class C1 on date D, when principal calls `GET /api/attendance/student?class_id=C1&date=D`, then all marked records are returned with correct statuses.

**AC2:** Given teacher T1 marks attendance for class C1 on date D, when owner exports attendance CSV for C1 in month M, then the CSV contains rows for all students in C1 with statuses from date D.

**AC3:** Given principal queries for class C2 on date D, then zero records from class C1 appear in the response.

**AC4:** Given accountant records fee payment for S1, when student S1 calls `GET /api/fees/my`, then the transaction is visible.

**AC5:** Existing 387 tests still pass.

---

### Story P16.2: JWT expiry handling — silent failure prevention mid-session

**Problem:** The frontend uses a JWT with a fixed expiry (typically 60 minutes). During a long attendance session (teacher marking 40 students over 20 minutes), the JWT may expire before the teacher clicks "Save". The current behaviour is: the `POST /api/attendance/student/bulk` call returns HTTP 401, and the frontend either shows an error or — if the error is not caught — silently drops the saved data with no feedback to the user. The `AttendanceRecorder.js` error state only shows `"Error: Unable to load classes"` type messages; it does not have a specific handler for 401 responses mid-session.

**Scope:**
- Audit all frontend API calls in `AttendanceRecorder.js`, `StudentDatabase.js`, and `TeacherTools.js` for 401 handling:
  - If a 401 is returned, trigger the refresh-token flow (`POST /api/auth/refresh`) before retrying
  - If the refresh token is also expired, redirect to login with a toast: "Session expired. Your changes have been saved locally — please log in again."
- Implement local-storage draft backup for `AttendanceRecorder.js`: before saving, write the current attendance state to `localStorage["attendance_draft_{class_id}_{date}"]`; on mount, check for a draft and offer to restore it
- Add frontend unit tests for the 401 → refresh → retry flow (using MSW or fetch mock)
- Add backend integration test: verify that a request with an expired JWT returns HTTP 401 with the `WWW-Authenticate` header set (already implemented in `middleware/auth.py` — confirm it is present)

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a teacher has an expired JWT and submits attendance, when the 401 response is received, then the frontend attempts to refresh the token before retrying the save.

**AC2:** Given both the JWT and refresh token are expired, when the teacher tries to save attendance, then a toast message "Session expired" is shown and the attendance data is written to localStorage as a draft.

**AC3:** Given `localStorage["attendance_draft_C1_2026-05-15"]` is populated from a previous session, when `AttendanceRecorder.js` mounts for C1 and date 2026-05-15, then it offers a "Restore Draft" prompt.

**AC4:** The backend returns HTTP 401 with `WWW-Authenticate: Bearer` header for all expired/invalid JWT requests.

**AC5:** Existing 387 tests still pass.

---

### Story P16.3: Concurrent write protection — fee payment idempotency end-to-end

**Problem:** `POST /api/fees/transactions` already implements idempotency via `Idempotency-Key` header. However, the idempotency key format is `student_id:fee_period:fee_head` — this is coarse-grained. If two accountants in different browser tabs record a payment for the same student in the same period with the same fee_head within the TTL window, the second request returns the existing transaction (correct). But if they use slightly different `fee_head` values (e.g. "tuition" vs "Tuition"), the idempotency key differs and two transactions are created. There is also no idempotency on `POST /api/attendance/student/bulk` — two identical bulk submissions from different network requests (e.g. double-click on Save) will both upsert, which is ultimately harmless but wastes audit log entries.

**Scope:**
- Add `fee_head` normalisation in `POST /api/fees/transactions`: lowercase + strip whitespace before building the idempotency key so "Tuition" and "tuition" produce the same key
- Add a test for the normalisation: submit `fee_head="Tuition"` then `fee_head="tuition"` for the same student/period → second request returns the existing transaction (idempotent)
- Add request-level debounce to `POST /api/attendance/student/bulk` via a 5-second idempotency window keyed on `(class_id, date, marked_by)`: if the same (class, date, teacher) submits within 5 seconds of a previous identical submission, return the previous result with `idempotent: true`
- Add integration test: two concurrent fee payment requests for the same (student, period, fee_head) → only one transaction in the DB
- Add integration test: duplicate attendance bulk submission within 5 seconds → second returns `idempotent: true`, single audit log entry

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given fee payment is submitted with `fee_head="Tuition"`, when a second request is submitted with `fee_head="tuition"` (same student/period), then the second response returns `idempotent: true` and the same transaction document.

**AC2:** Given two identical `POST /api/fees/transactions` requests are sent concurrently, then exactly one `fee_transactions` document is created in the DB.

**AC3:** Given a teacher submits `POST /api/attendance/student/bulk` and immediately sends an identical request within 5 seconds, then the second response contains `idempotent: true` and no duplicate audit log entry is created.

**AC4:** Given two bulk attendance submissions for the same class+date come from two different teachers (different `marked_by`), then both are processed normally (not collapsed by idempotency).

**AC5:** Existing 387 tests still pass.

---

### Story P16.4: Scale test preparation — missing indexes and query audit

> ⚠️ This story has been MOVED to pre-Part-9 infrastructure (see sprint-status.yaml pre-p9-1-missing-mongodb-indexes). The index migration runs BEFORE the role vertical sprints (Parts 9-13) to avoid collection scans under load. The full specification remains here for reference, but implementation happens before Part 9.

**Problem:** The current `_create_indexes()` in `database.py` creates indexes for the most common collection queries but is missing several that will become bottlenecks at scale:
- `exam_results`: no index on `(exam_id, student_id)` — bulk result entry and cross-student queries do full collection scans
- `audit_logs`: no index on `(entity_type, entity_id)` — audit history queries scan the full collection
- `lesson_plans`: no index on `(teacher_id, created_at)` — teacher lesson plan list does a collection scan
- `ptm_notes`: no index on `(teacher_id)` or `(student_id)` — PTM note queries scan without index
- `sms_logs`: no index on `sent_at` — log listing is sorted by `sent_at` without an index

Expected peak usage: 500 concurrent users (400 students + 50 teachers + 50 admin), with bursts of 100 concurrent attendance submissions in the morning session window.

**Scope:**
- Add to `_create_indexes()` in `database.py`:
  - `exam_results`: index on `(student_id, exam_id)` — supports `GET /api/academics/results?student_id=X` and the exam results export
  - `audit_logs`: index on `(actor_id, created_at)` — supports `GET /api/audit-log?actor_id=X&from=Y`
  - `lesson_plans`: index on `(class_id, week)` — supports `GET /api/academics/lesson-plans?class_id=X&week=Y`
  - `sms_logs`: TTL index on `created_at` (expireAfterSeconds=7776000, i.e. 90 days) — prevents unbounded collection growth
  - `notifications`: compound index on `(user_id, read, created_at)` — supports `GET /api/notifications?read=false` sorted by date
  - `exam_results` (additional): compound index `(exam_id, student_id, subject_id)`, unique=True, sparse=True
  - `audit_logs` (additional): compound index `(entity_type, entity_id, created_at)`
  - `lesson_plans` (additional): compound index `(teacher_id, created_at)`
  - `ptm_notes`: index `teacher_id`, index `student_id`
  - `question_papers`: compound index `(teacher_id, created_at)`
  - `curriculum_progress`: compound index `(class_id, subject_id, topic)`, unique=True
- Add migration `020_add_performance_indexes.py` that calls `create_index` for all new indexes (idempotent)
- Add `020` to `run_all.py`
- Document the expected peak concurrent user count and the p95 latency target in `docs/architecture-backend.md`
- Add a test that verifies all expected indexes exist on a test database after startup

**Acceptance Criteria (Given/When/Then):**

**AC1:** After `_create_indexes()` runs, `db.exam_results.index_information()` contains an index with keys `exam_id`, `student_id`, `subject_id`.

**AC2:** After `_create_indexes()` runs, `db.audit_logs.index_information()` contains an index with keys `entity_type`, `entity_id`.

**AC3:** Migration `020` runs without error on a clean database and is idempotent on an already-migrated database.

**AC4:** `run_all.py` includes migration `020` in the correct sequential position.

**AC5:** Existing 387 tests still pass.

---

### Story P16.5: Playwright E2E test suite expansion — critical paths

**Problem:** The existing E2E tests (`auth.spec.js`, `chat.spec.js`, `rate-limit.spec.js`, `students.spec.js`) cover only individual-role actions. No E2E test covers:
- Owner login → AI query about fee status → correct answer with live data
- Admin/principal login → approve a leave request
- Teacher attendance recording end-to-end (UI flow)
- Student login → view own fee status

The Playwright configuration (`playwright.config.js`) exists but the test count is minimal, and there is no CI pipeline running E2E tests on pull requests.

**Scope:**
- Add `tests/e2e/teacher-attendance-flow.spec.js`: teacher logs in, selects class, marks attendance, saves, verifies success state
- Add `tests/e2e/owner-ai-fee-query.spec.js`: owner logs in, sends AI message "show me students with outstanding fees", verifies the response includes student data
- Add `tests/e2e/student-profile.spec.js`: student logs in, navigates to My Profile, verifies name and class displayed, navigates to Fee Status, verifies transactions visible
- Add `tests/e2e/principal-leave-approval.spec.js`: principal logs in, navigates to leave requests, approves one, verifies status change
- Add CI step to run E2E tests against a staging environment after deployment (GitHub Actions or AWS CodeBuild)
- All E2E tests must handle `SKIP_CONSENT_CHECK=true` in the test environment to avoid DPDP gate blocking student tests

**Acceptance Criteria (Given/When/Then):**

**AC1:** `teacher-attendance-flow.spec.js` passes: given a seeded teacher and class with students, when the teacher marks attendance and clicks Save, then the success confirmation is visible and the GET `/api/attendance/student/today/{class_id}` call returns the marked statuses.

**AC2:** `owner-ai-fee-query.spec.js` passes: given an owner logs in and sends a fee query, then the AI response streamed to the UI contains at least one student name or fee amount (live data, not placeholder text).

**AC3:** `student-profile.spec.js` passes: given a student logs in, then the My Profile page shows the correct `name` and `class_id`, and the Fee Status page shows the correct transaction count.

**AC4:** All 4 new Playwright specs pass in CI against the staging environment.

**AC5:** Existing 387 backend tests and the 4 existing E2E specs still pass.

---

### Story P16.6: NFR validation — response time, uptime SLA, and data loss prevention

**Problem:** The PRD specifies "response time < 2s for 95th percentile" and "99.9% uptime SLA" but there are no automated tests validating these targets. There is no load test. MongoDB Atlas backups are provisioned but no recovery test has been run. There is no zero-data-loss check (e.g. verifying that a server restart does not drop in-flight attendance writes).

**Scope:**
- Add a lightweight load test script `tests/load/locust_basic.py` using Locust:
  - Simulate 50 concurrent users: 70% read (GET /api/students, GET /api/attendance/student/today/{class_id}), 20% write (POST /api/attendance/student/bulk), 10% AI queries
  - Assert p95 response time < 2s for reads, < 5s for AI queries
  - Runs against staging, not production
- Add a data durability test: submit an attendance record, simulate a forced server restart (stop + start the FastAPI process in the test harness), verify the record is persisted in MongoDB
- Document the MongoDB Atlas backup policy in `docs/operations.md`: snapshot frequency (daily), point-in-time recovery window (7 days), how to trigger a restore
- Add a startup health check: `GET /api/health/ready` already exists — confirm it returns `200` with `db_connected: true` within 30 seconds of server start in the CI test environment
- Add a test: `GET /api/health/ready` on a server with a mocked DB connection failure returns `503`

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given the Locust load test runs against staging with 50 concurrent users, then p95 response time for `GET /api/students` is < 2 seconds.

**AC2:** Given an attendance record is submitted and then the FastAPI process is stopped and restarted, when the process comes back up and `GET /api/attendance/student` is queried, then the record is present in the response.

**AC3:** `GET /api/health/ready` returns HTTP 200 with `{"db_connected": true, "school_id_configured": true}` within 30 seconds of server start.

**AC4:** Given the DB is unreachable, `GET /api/health/ready` returns HTTP 503.

**AC5:** `docs/operations.md` exists and documents the backup policy, restore procedure, and RTO/RPO targets.

---

### Story P16.7: SMS/WhatsApp integration — end-to-end fee reminder verification

**Problem:** `backend/routes/sms.py` implements Twilio-based SMS via `POST /api/sms/send-reminder` and `POST /api/sms/send-bulk`. The Twilio client is correctly guarded: if `TWILIO_ACCOUNT_SID` is not set or equals the placeholder value, `get_twilio_client()` returns `None` and SMS status is set to `"not_configured"`. However:
1. No tests exist for `sms.py` — zero test files reference `sms`
2. The bulk send endpoint has no rate limit — a single request can trigger unlimited Twilio API calls
3. The `send-parent-message` endpoint queries `db.students.find_one({"id": sid})` without school scoping (`db.students` is ScopedCollection, so `schoolId` is enforced, but this is not tested)
4. SMS logs are stored without TTL — `sms_logs` will grow unboundedly

**Scope:**
- Add `tests/backend/api/test_sms.py`:
  - Test `POST /api/sms/send-reminder` with Twilio mocked: verify SMS log is created with correct fields
  - Test `POST /api/sms/send-reminder` with `TWILIO_ACCOUNT_SID` not set: verify `status="not_configured"` and HTTP 200 (not 500)
  - Test `POST /api/sms/send-bulk` with 5 recipients: verify 5 log entries created
  - Test `GET /api/sms/config-status` with credentials set vs. not set
- Add rate limit to `POST /api/sms/send-bulk`: max 500 recipients per request; raise HTTP 400 if `len(recipients) > 500`
- Add TTL index to `sms_logs`: `expireAfterSeconds=7776000` (90 days) on `created_at` field; add to `_create_indexes()` and migration `020`. At 2000 students with 5 SMS messages/year each, without TTL the collection grows by 10,000 records/year indefinitely.
- Add `schoolId` to all `sms_logs` inserts for multi-tenant hygiene
- Verify `send-parent-message` student/guardian lookup uses school-scoped DB (already goes through `db.students`, which is a `ScopedCollection` — add a test asserting this)

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given Twilio credentials are not configured (`TWILIO_ACCOUNT_SID` not set), when `POST /api/sms/send-reminder` is called, then the response is HTTP 200 with `status="not_configured"` and a log entry is created.

**AC2:** Given `POST /api/sms/send-bulk` is called with 600 recipients, then the response is HTTP 400 "Maximum 500 recipients per bulk send".

**AC3:** Given Twilio is mocked to return success, when `POST /api/sms/send-reminder` is called, then the `sms_logs` collection contains a document with `status="sent"`, `student_id`, `phone`, `message`, and `schoolId` fields.

**AC4:** `GET /api/sms/config-status` returns `{"configured": false}` when `TWILIO_ACCOUNT_SID` is not set, and `{"configured": true, "phone_number": "..."}` when all three vars are set.

**AC5:** Existing 387 tests still pass.

---

### Story P16.8: Multi-branch smoke test — data isolation with 2+ branches

**Problem:** The platform is deployed for The Aaryans which has multiple branches (e.g. Main Branch and Joya Branch). The current scoping architecture uses `schoolId` (env-var, same for all branches) and `branch_id` (in JWT). Story P4.5 addressed AI tool branch scoping. However, no end-to-end test has verified that two branches cannot read each other's data across all role-facing endpoints. With the teacher and student verticals now active, the risk surface is larger: a teacher at Branch A should never see students from Branch B.

**Scope:**
- Add integration test suite `tests/backend/integration/test_multi_branch_isolation.py`:
  - Seed: 2 branches (branch-a, branch-b), each with students, staff, attendance records
  - Create JWTs with `branch_id=branch-a` and `branch_id=branch-b` for owner, admin, teacher, and student roles
  - For each role, verify that queries return only their branch's data:
    - `GET /api/students/` → only branch-A students for branch-A JWT
    - `GET /api/attendance/student/today/{class_id}` → only branch-A records
    - `GET /api/fees/my` (student) → only branch-A transactions
    - `GET /api/academics/assignments` → only branch-A assignments
  - Verify owner (no branch_id in JWT) sees all branches' data
- Confirm `scoped_filter` and `ScopedCollection` correctly enforce `branch_id` isolation for all tested collections
- Add test: branch-A student JWT querying a branch-B student's `student_id` directly returns HTTP 403 (scope resolver prevents cross-branch `self_only` access)

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a teacher JWT with `branch_id=branch-a`, when they call `GET /api/students/`, then zero students from `branch-b` appear in the response.

**AC2:** Given a student JWT with `branch_id=branch-a`, when they call `GET /api/fees/my`, then zero transactions belonging to branch-b students are returned.

**AC3:** Given an owner JWT (no branch_id), when they call `GET /api/students/`, then students from both branches are returned.

**AC4:** Given a student JWT from branch-a directly queries a student_id that belongs to branch-b via `GET /api/students/{id}`, then the response is HTTP 403 or 404 (cross-branch isolation confirmed).

**AC5:** Existing 387 tests still pass.

---

### Story P16.9: Deployment runbook and operations documentation

**Problem:** There is no documented deployment procedure. AWS Amplify is used for the frontend and AWS Elastic Beanstalk (implied by the `SCHOOL_ID` env-var strategy) for the backend. There is no recorded procedure for: deploying a new backend version, rolling back a deployment, applying database migrations on the production Atlas instance, configuring environment variables for a new school, and running the seed script safely.

**Scope:**
- Create `docs/deployment-runbook.md` covering:
  1. **Pre-deploy checklist**: run tests locally, confirm `SCHOOL_ID` env var is set, confirm `run_all.py` migrations are idempotent against prod Atlas
  2. **Backend deploy steps**: EB CLI command or CI trigger, expected output, how to verify health via `GET /api/health/ready`
  3. **Migration procedure**: how to run `python migrations/run_all.py` against the prod Atlas URI without touching dev DB; expected idempotent output
  4. **Rollback procedure**: EB rollback command, how to restore Atlas to a point-in-time snapshot
  5. **Environment variables**: full list of required env vars (SCHOOL_ID, MONGODB_URI, JWT_SECRET, TWILIO_*, AWS_*, etc.) with examples
  6. **Seed procedure**: when and how to run `seed.py` on a fresh deployment; warning about running on an existing DB
  7. **Multi-school setup** (Option A — per-instance): how to deploy a second instance for a new school
- Verify `docs/operations.md` from P16.6 exists; link it from the runbook
- Add a CI check that validates the runbook is up-to-date when `run_all.py` or `.env.example` changes (lint rule that checks both files are modified in the same commit)

**Acceptance Criteria (Given/When/Then):**

**AC1:** `docs/deployment-runbook.md` exists and contains all 7 sections listed in the scope.

**AC2:** Given a new developer follows the runbook from a clean machine, the deployment procedure is unambiguous: no steps require undocumented tribal knowledge.

**AC3:** The environment variables section in the runbook lists every variable present in `backend/.env.example` (verified by a CI lint script that diffs the two files).

**AC4:** The runbook includes the rollback command for AWS Elastic Beanstalk and the Atlas point-in-time restore procedure.

**AC5:** No regressions to existing tests.

---

## NFRs

**NFR16.1 — Cross-role data integrity:** The cross-role E2E integration tests must pass on every pull request targeting `main`; a failure in `test_cross_role_attendance_flow.py` or `test_cross_role_fee_flow.py` blocks merge.

**NFR16.2 — Response time:** p95 response time for all non-AI read endpoints must be < 2 seconds under a 50-concurrent-user load, validated by the Locust script in P16.6. AI query endpoints target < 5 seconds for first token.

**NFR16.3 — Uptime SLA target:** 99.9% monthly uptime (allows 43.8 minutes of downtime per month). Health check endpoint `GET /api/health/ready` must respond within 5 seconds to be considered healthy; AWS Elastic Beanstalk health check interval set to 30 seconds.

**NFR16.4 — Zero data loss on restart:** Any database write confirmed by a HTTP 200/201 response must be recoverable after a server restart. MongoDB Atlas write concern `w: majority` enforced at the `MongoClient` level (confirm in `database.py`).

**NFR16.5 — Branch isolation:** Zero cross-branch data leakage verified by `test_multi_branch_isolation.py` running on every pull request.

**NFR16.6 — SMS compliance:** All SMS messages sent via Twilio must include the school name in the sender ID or message body; DND (Do Not Disturb) opt-out records must be checked before sending (future story hook — flag as NFR here for awareness).

---

## FR Coverage Map

| FR | Story | Endpoint(s) / Component(s) Covered |
|---|---|---|
| Cross-role attendance flow | P16.1 | POST /api/attendance/student/bulk → GET /api/attendance/student → GET /api/attendance/export |
| Cross-role fee flow | P16.1 | POST /api/fees/transactions → GET /api/fees/my → fee export |
| JWT expiry mid-session | P16.2 | POST /api/auth/refresh, AttendanceRecorder.js draft backup |
| Fee idempotency key normalisation | P16.3 | POST /api/fees/transactions |
| Attendance bulk idempotency | P16.3 | POST /api/attendance/student/bulk |
| Missing DB indexes | P16.4 | database.py _create_indexes(), migration 020 |
| Playwright E2E suite expansion | P16.5 | teacher-attendance, owner-AI, student-profile, principal-leave |
| NFR validation — load test | P16.6 | Locust script, /api/health/ready |
| Data durability test | P16.6 | MongoDB write durability |
| SMS end-to-end tests | P16.7 | POST /api/sms/send-reminder, /send-bulk, /send-parent-message |
| SMS TTL index | P16.7 | sms_logs collection, migration 020 |
| Multi-branch isolation tests | P16.8 | All role-facing endpoints, branch_id scoping |
| Deployment runbook | P16.9 | docs/deployment-runbook.md |

---

## Implementation Order

1. P16.4 — Missing indexes (lowest risk, highest payoff, no dependencies)
2. P16.7 — SMS tests (isolated, no dependencies)
3. P16.3 — Concurrent write protection (fee + attendance idempotency)
4. P16.1 — Cross-role E2E workflow tests (requires Parts 14 and 15 to be closed)
5. P16.8 — Multi-branch smoke test (requires Parts 14 and 15 to be closed)
6. P16.2 — JWT expiry handling (frontend + backend)
7. P16.5 — Playwright E2E suite expansion (requires full stack running)
8. P16.6 — NFR validation and load testing (requires all other stories closed)
9. P16.9 — Deployment runbook (documentation, can be written in parallel)

---

## Epic P16: Retrospective

A retrospective entry for Part 16 to be completed after all P16.1–P16.9 stories are done. This retrospective also serves as the platform quality sweep capstone review: a structured walkthrough with Aman and Adesh against the 10-question success criteria defined in the PRD.
