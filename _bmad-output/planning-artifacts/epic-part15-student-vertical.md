---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 15'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 15
part_name: 'Student Role Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy', 'Part 14 Teacher role']
test_baseline: '387 backend tests passing, 0 skipped'
gating_dependency: 'Story 7-39 — student auth_users must be activated; DPDP parental consent model must be in place before student data is accessible to students directly'
---

# EduFlow Quality Sweep — Part 15: Student Role Vertical

## Dual Gating Dependencies

Gate 1 — Story 7-39: Student login requires teacher/student auth activation.
Same condition as Part 14.

Gate 2 — DPDP parental consent: The Digital Personal Data Protection Act 2023
(India) requires verifiable parental consent for data access by minors (under 18).
DPDP consent is NOT currently modeled anywhere in EduFlow. Part 15 Story P15.1
creates the consent model. Until P15.1 ships, student data access via the student
login role is a compliance risk.

Parts 14-15 should be planned together — teacher activation (7-39) likely precedes
student activation by one sprint to allow DPDP consent infrastructure to be in place.

## Context

Part 15 activates and hardens the Student role end-to-end. Student auth_users ARE seeded in `seed.py` — every student gets a `username = admission_number` and `password_hash = bcrypt("student@123")`. The student role is partially implemented: `GET /api/students/me`, `GET /api/fees/my`, scope_resolver returns `type="self_only"` with `student_id` populated, and `StudentTools.js` has 10 components. However, the student role has never been tested in production, carries specific DPDP (India's Data Protection and Digital Personal Data) obligations for minors, and has several gaps that would make the experience unusable or insecure.

**Entering baseline:** 387 backend tests, 0 skipped. Student-specific API tests: `test_students.py` covers admin-facing CRUD only. Zero tests for `GET /api/students/me`, `GET /api/fees/my`, student-scoped attendance, or student-scoped results. `StudentTools.js` has 10 components but several call endpoints that do not correctly enforce the student-scope server-side.

**Gating dependency (dual gate):**
1. Story 7-39: teacher/student login activation — the same prerequisite as Part 14.
2. DPDP Parental Consent: before students (minors under 18) can log in and view personal data, a parental consent record must exist for that student. No consent model is currently present in the codebase. This gate must be resolved before student logins go live to avoid violating India's DPDP Act 2023.

---

## Epic P15: Student Role Vertical

### Story P15.1: Student login activation and first-login password flow (Story 7-39 prerequisite)

**Problem:** Student auth_users are seeded with `username = admission_number` and a shared password `student@123`. There is no `force_password_change` flag, so students never change the shared default password. The `_jwt_payload_from_auth` function does not include the student's `class_id` in the JWT payload — this means the frontend must always fetch the student record from `GET /api/students/me` to determine which class they are in. There is no integration test for the student login path.

**Scope:**
- Add integration test: student login via `POST /api/auth/login` with `username=admission_number` and `password=student@123` → JWT contains `role=student` and the correct `user_id`
- Add `force_password_change: True` to all student auth_user seed documents; implement the first-login redirect on the frontend (same pattern as teacher)
- Add `class_id` to `user_info` in the student auth_user document (populated at seed/import time) so it propagates into the JWT and the frontend does not need a round-trip for class-gating
- Add integration test: `GET /api/auth/me` with student JWT returns `name`, `role`, `class_id`, `admission_number`
- Confirm `resolve_scope(user)` for a student with a valid active student record returns `type="self_only"` with `student_id` populated

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given student S1 has `username=ADM20250001` and `password_hash=bcrypt("student@123")`, when `POST /api/auth/login` is called with those credentials, then the response contains a JWT with `role=student` and `user_id` matching the student's auth_user id.

**AC2:** Given a student JWT, when `GET /api/auth/me` is called, then the response includes `name`, `role=student`, and `class_id`.

**AC3:** Given a seeded student account with `force_password_change=True`, when they log in for the first time, then the frontend routes them to the password change screen before any tool panel is shown.

**AC4:** Given `resolve_scope(user)` is called with a student user dict where the student record is active, then `scope.type == "self_only"` and `scope.student_id` is non-null.

**AC5:** Existing 387 tests still pass.

---

### Story P15.2: DPDP parental consent model and minor data access gate

**Problem:** EduFlow serves students who are minors (age 5–17) at a CBSE school in Uttar Pradesh. India's DPDP Act 2023 (effective 2025) requires verifiable parental consent before processing personal data of a minor. Currently, there is no consent record model — students can log in and immediately view their personal data (profile, attendance, fees) with no consent recorded. `GET /api/students/{student_id}/erase` is the only DPDP-adjacent feature implemented (data erasure). The absence of consent records means EduFlow cannot demonstrate regulatory compliance if audited.

**Scope:**
- Create `dpdp_consents` collection with schema: `{id, student_id, guardian_id, consent_type: "login_access", granted: bool, granted_at, granted_by_name, granted_by_phone, revoked_at, revoked_by}`
- Add migration `019_dpdp_consent_collection.py`: creates the collection and a sparse unique index on `(student_id, consent_type)`
- Add `POST /api/students/{student_id}/consent` endpoint: `require_role("owner", "admin")` — records guardian consent
- Add `GET /api/students/{student_id}/consent` endpoint: `require_role("owner", "admin", "teacher")` — returns consent status
- Add middleware gate: before any student-role request reaches a data-returning endpoint, check `dpdp_consents` for the student; if no `consent_type="login_access"` record with `granted=True` exists, return HTTP 403 "Parental consent required"
- The middleware gate is implemented as a dependency (`require_student_consent`) applied to student-facing endpoints: `GET /api/students/me`, `GET /api/fees/my`, `GET /api/attendance/student`
- Seed data: create consent records for all students created in `seed.py` (development mode only — `SKIP_CONSENT_CHECK=true` in `.env.test`)

**Acceptance Criteria (Given/When/Then):**

**Required consent record fields:** The consent record must include: student_id, guardian_id (who gave consent), consent_date, consent_version (for future re-consent on policy changes), consent_channel ('in_person' | 'sms' | 'app').

**AC-pre-1:** Without an active consent record for a student, `GET /api/students/me` returns 403 with detail "Parental consent required".

**AC-pre-2:** The consent record is created by an admin (owner/principal) after obtaining physical consent — students cannot create their own consent records.

**AC1:** Given student S1 has no DPDP consent record, when they call `GET /api/students/me`, then the response is HTTP 403 "Parental consent required to access student data".

**AC2:** Given an admin creates a consent record for student S1 via `POST /api/students/S1/consent`, when student S1 then calls `GET /api/students/me`, then the response is HTTP 200 with their profile.

**AC3:** Given a consent record is revoked (`revoked_at` set), when the student calls `GET /api/students/me`, then the response is HTTP 403.

**AC4:** Given `SKIP_CONSENT_CHECK=true` in the test environment, then all student requests proceed without the consent gate (enabling existing tests to pass without consent setup).

**AC5:** Migration `019` runs idempotently on a clean database without errors. Existing 387 tests still pass.

---

### Story P15.3: Student self-profile — field visibility and update restrictions

**Problem:** `GET /api/students/me` returns the full student document including `medical_notes`, `emergency_contact`, `blood_group`, `height_cm`, `weight_kg`, and all guardian details. Some fields (e.g. `annual_income` in the guardian object) are sensitive financial information that the student should not be able to see directly. There is no `PATCH /api/students/me` endpoint — students cannot update any of their own fields (e.g. updating their `emergency_contact` phone number).

**Scope:**
- Audit the fields returned by `GET /api/students/me` and create a student-facing projection that excludes: `guardian.annual_income`, `guardian.occupation` (partial redaction: keep name and phone), any internal admin fields
- Add `PATCH /api/students/me` endpoint: `require_role("student")`; allow update of only: `emergency_contact`, student's own phone (if present), and `medical_notes` (self-reported allergies/conditions)
- Add consent check dependency to `PATCH /api/students/me`
- Add integration tests: student GET /me returns correct fields but not `annual_income`, student PATCH /me can update emergency_contact, student PATCH /me cannot update `class_id` or `admission_number`

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a student calls `GET /api/students/me`, then the response does NOT include `guardian.annual_income` or `guardian.occupation`.

**AC2:** Given a student calls `GET /api/students/me`, then the response DOES include `name`, `admission_number`, `class_id`, `dob`, `gender`, `blood_group`, and `guardian.name`, `guardian.phone`.

**AC3:** Given a student sends `PATCH /api/students/me` with `{"emergency_contact": "9876543210"}`, then the update is saved and a DPDP-aware audit log is created.

**AC4:** Given a student sends `PATCH /api/students/me` with `{"class_id": "cls-7"}`, then the response is HTTP 400 "Field not updatable by student".

**AC5:** Existing 387 tests still pass.

---

### Story P15.4: Fee history — itemized view and outstanding balance

**Problem:** `GET /api/fees/my` returns raw `fee_transactions` documents for the student. The response is not enriched with `fee_head` display name, total outstanding balance, or a chronological summary. `FeeStatusViewer` in `StudentTools.js` currently calls `GET /api/fees/my` but the response structure shows only transaction records — there is no aggregated `total_paid`, `total_due`, or `outstanding_balance` field. Additionally, `GET /api/fees/my` calls `_fee_query({"user_id": user["id"]})` to find the student record — this queries students by `user_id` but uses `_fee_query` (the school-scoped filter) rather than `_student_query`, making it slightly inconsistent with the rest of the student lookup pattern.

**Scope:**
- Enrich `GET /api/fees/my` response to include:
  - `transactions`: array of fee_transactions (existing)
  - `summary.total_paid`: sum of amounts where `status=paid`
  - `summary.total_pending`: sum of amounts where `status=pending`
  - `summary.outstanding_balance`: total_pending (for display)
  - `summary.last_payment_date`: most recent `paid_date` value
- Fix the student lookup in `GET /api/fees/my` to use `_student_query` (school-scoped) consistently
- Ensure `FeeStatusViewer` in `StudentTools.js` renders the summary card with `outstanding_balance` and `last_payment_date`
- Add integration tests: student with 3 transactions (2 paid, 1 pending) → summary reflects correct totals, student with zero transactions → returns empty list and zero balance

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given student S1 has 2 paid transactions of ₹5000 each and 1 pending transaction of ₹3000, when they call `GET /api/fees/my`, then `summary.total_paid=10000`, `summary.total_pending=3000`, `summary.outstanding_balance=3000`.

**AC2:** Given student S1 calls `GET /api/fees/my` with zero transactions, then `summary.total_paid=0`, `summary.outstanding_balance=0`, and `transactions=[]`.

**AC3:** Given `FeeStatusViewer` is rendered for a student with an outstanding balance, then it displays "Outstanding: ₹3000" prominently.

**AC4:** The student lookup uses `scoped_filter({"user_id": user["id"]}, get_school_id())` rather than `_fee_query({"user_id": user["id"]})` for the student record query.

**AC5:** Existing 387 tests still pass.

---

### Story P15.5: Attendance self-view — percentage, date-wise breakdown, and calendar

**Problem:** `GET /api/attendance/student` allows `role=student` and correctly gates by `user_id` ownership: a student cannot query another student's `student_id`. However, `AttendanceSelfCheck` in `StudentTools.js` calls `GET /api/attendance/student?student_id={id}` but must first know its own `student_id` from a prior `GET /api/students/me` call. There is no server-side aggregation endpoint for "my attendance percentage this month" — the frontend would need to fetch all records and compute it client-side, which is fragile.

**Scope:**
- Add `GET /api/attendance/student/my/summary` endpoint: `require_role("student")`, returns:
  - `this_month.percentage`, `this_month.present_days`, `this_month.absent_days`, `this_month.total_days`
  - `this_year.percentage`, `this_year.present_days`, `this_year.absent_days`
  - `low_attendance_warning: true/false` (threshold: < 75%)
- Add DPDP consent gate to both `GET /api/attendance/student` (student role path) and the new summary endpoint
- Update `AttendanceSelfCheck` in `StudentTools.js` to use the new `/my/summary` endpoint and display a colour-coded attendance meter (green ≥ 75%, amber 60–74%, red < 60%)
- Add integration tests: student with 20 present/5 absent days → correct percentages, student below 75% threshold → `low_attendance_warning=true`

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given student S1 has 20 present and 5 absent records in the current month, when they call `GET /api/attendance/student/my/summary`, then `this_month.percentage=80.0`, `present_days=20`, `absent_days=5`, `low_attendance_warning=false`.

**AC2:** Given student S1 has 60% attendance this year, when they call the summary endpoint, then `low_attendance_warning=true`.

**AC3:** Given a student without DPDP consent calls the summary endpoint, then HTTP 403 is returned.

**AC4:** `AttendanceSelfCheck` renders a colour-coded attendance percentage meter based on the summary response.

**AC5:** Existing 387 tests still pass.

---

### Story P15.6: Assignment and result student views — class-scope and publish gate

> **Cross-Part Dependency:** P15.4 (student result visibility) depends on P14.6 (publish gate) from Part 14. P15 implementation should begin only after P14.6 is complete, regardless of the 7-39 gate status. Note: P14.6 in the implementation order refers to the publish gate story (Story P14.4 in this epic series).

**Problem:** `GET /api/academics/assignments` for students correctly queries by `class_id` (resolved from the student's record). `GET /api/academics/results` for students filters to `student_id=own["id"]`. However: (1) The assignment view in `HomeworkViewer` (`StudentTools.js`) does not display `due_date` proximity warnings (i.e. "due in 2 days"). (2) Results are visible to students regardless of `is_published` because the publish gate from Story P14.4 does not exist yet — Part 15 depends on Part 14 closing this. (3) The practice test component (`PracticeTest.js`) calls the AI chat endpoint without any rate-limiting specific to the student role, meaning a student could exhaust the AI token budget.

**Scope:**
- After Part 14's `is_published` gate is in place: verify `GET /api/academics/results` correctly hides unpublished results for students; add integration test
- Update `HomeworkViewer` to compute and display `days_until_due` badge from `due_date`: "Due in N days" (green if >3 days, amber if 1–3 days, red if past due)
- Add student-specific AI rate limit: `POST /api/chat/conversations/{id}/messages` with student JWT must be subject to the existing rate limiter, but with a tighter per-student daily cap (configurable via `STUDENT_AI_DAILY_MESSAGES`, default 20)
- Add DPDP consent gate to `GET /api/academics/assignments` and `GET /api/academics/results` for the student role path
- Add integration tests: student cannot see unpublished results, student sees correct assignments for their class only, student AI rate limit enforced after threshold

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given exam results for student S1 have `is_published=False`, when S1 calls `GET /api/academics/results`, then zero results are returned.

**AC2:** Given exam results for student S1 have `is_published=True`, when S1 calls `GET /api/academics/results`, then the results are returned.

**AC3:** Given `HomeworkViewer` renders an assignment with `due_date` 2 days from today, then it displays "Due in 2 days" with an amber badge.

**AC4:** Given a student has sent 20 AI messages today (at the default cap), when they send message 21, then the response is HTTP 429 "Daily message limit reached".

**AC5:** Existing 387 tests still pass.

---

### Story P15.7: PTM summary and form submissions — student-safe access

**Problem:** `PtmSummaryViewer` and `FormSubmissions` are exported from `StudentTools.js`. `GET /api/academics/ptm-notes` for students correctly scopes to `student_id=own["id"]`. However, PTM notes may include sensitive teacher observations about a student's behaviour or academic performance. There is no mechanism for the student to see only a sanitised summary (principal decides which notes are shared with students) vs. the full raw teacher notes (which should be private to staff). `FormSubmissions` appears to be a stub that renders `ComingSoon`.

**Scope:**
- Add `is_shared_with_student` flag to PTM note schema; default `False`
- `GET /api/academics/ptm-notes` for students: only return notes where `is_shared_with_student=True`
- Add `PATCH /api/academics/ptm-notes/{id}/share` endpoint: `require_role("admin", "owner")` — toggles `is_shared_with_student`
- Update `PtmSummaryViewer` to display only shared notes, with a message "No meeting summaries have been shared with you yet" when none exist
- Confirm `FormSubmissions` is correctly gated as `ComingSoon` and does not make real API calls to unimplemented endpoints
- Add DPDP consent gate to `GET /api/academics/ptm-notes` for student role path
- Add integration tests: student without shared notes → empty list, admin marks note as shared → student can see it

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given student S1 has 3 PTM notes, all with `is_shared_with_student=False`, when they call `GET /api/academics/ptm-notes`, then an empty list is returned.

**AC2:** Given an admin calls `PATCH /api/academics/ptm-notes/{id}/share`, then `is_shared_with_student` is set to `True`.

**AC3:** Given student S1 has one shared PTM note, when they call `GET /api/academics/ptm-notes`, then exactly one note is returned.

**AC4:** Given `PtmSummaryViewer` renders with zero shared notes, then it displays "No meeting summaries have been shared with you yet" rather than an empty table.

**AC5:** Existing 387 tests still pass.

---

## NFRs

**NFR15.1 — DPDP compliance:** Every student-data endpoint accessible with `role=student` must check the DPDP consent gate before returning personal data; this must be verified by an automated test that confirms a student without consent receives HTTP 403.

**NFR15.2 — Scope isolation:** A student can never retrieve another student's data via any endpoint; verified by integration tests with two distinct student JWTs querying each other's student_id.

**NFR15.3 — Password hygiene:** All seeded student passwords (`student@123`) must be force-changed on first login; the platform must not allow a student to proceed without setting a personal password.

**NFR15.4 — AI token budget:** Student AI usage must be subject to the tighter daily cap (`STUDENT_AI_DAILY_MESSAGES`) and must count against the branch token budget with the same rules as other roles.

**NFR15.5 — Test baseline:** After Part 15, the test count must be at least the Part 14 baseline + 40 additional tests covering the P15 stories.

---

## FR Coverage Map

| FR | Story | Endpoint(s) Covered |
|---|---|---|
| Student login JWT path | P15.1 | POST /api/auth/login, GET /api/auth/me |
| Scope resolve for student | P15.1 | scope_resolver.py (student path) |
| DPDP consent model | P15.2 | POST/GET /api/students/{id}/consent |
| Consent gate middleware | P15.2 | GET /api/students/me, GET /api/fees/my, GET /api/attendance/student |
| Student profile field redaction | P15.3 | GET /api/students/me |
| Student self-update | P15.3 | PATCH /api/students/me (new) |
| Fee summary enrichment | P15.4 | GET /api/fees/my |
| Attendance percentage summary | P15.5 | GET /api/attendance/student/my/summary (new) |
| Low attendance warning | P15.5 | GET /api/attendance/student/my/summary |
| Assignment due-date badge | P15.6 | GET /api/academics/assignments (frontend enrichment) |
| Results publish gate (student) | P15.6 | GET /api/academics/results |
| Student AI rate limit | P15.6 | POST /api/chat/conversations/{id}/messages |
| PTM note share gate | P15.7 | GET /api/academics/ptm-notes, PATCH .../share (new) |

---

## Implementation Order

1. P15.1 — Student login activation (unblocks all downstream)
2. P15.2 — DPDP consent model (legal gate — must close before student data is exposed)
3. P15.3 — Student self-profile (depends on login + consent)
4. P15.4 — Fee history enrichment (high daily-use priority)
5. P15.5 — Attendance self-view summary (high daily-use priority)
6. P15.6 — Assignments and results views (depends on Part 14 P14.4)
7. P15.7 — PTM summary and form submissions (lower urgency)

---

## Epic P15: Retrospective

A retrospective entry for Part 15 to be completed after all P15.1–P15.7 stories are done.
