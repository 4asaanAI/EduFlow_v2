---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 14'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 14
part_name: 'Teacher Role Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy']
test_baseline: '387 backend tests passing, 0 skipped'
gating_dependency: 'Story 7-39 — teacher/student auth_users must be activated before teachers can log in'
---

# EduFlow Quality Sweep — Part 14: Teacher Role Vertical

## Gating Dependency: Story 7-39

Story 7-39 activates teacher and student logins by:
- Creating auth_users records for teachers (seeded in seed.py with 7 accounts)
- Exposing the login flow to teacher/student roles (currently owner-only)
- Setting force_password_change=false on initial seeded accounts

Parts 9-13 (role verticals for admin sub-categories) are NOT gated — they use the
existing admin login flow. Only teacher and student login is gated.

Go/no-go checkpoint: Story 7-39 is done when a teacher account can successfully call
POST /api/auth/login and receive a JWT with role=teacher.

## Parallel-Path Contingency for Gated Work

While gated on 7-39, the following can be built and tested in Part 14 using MOCK AUTHENTICATION (hardcoded test JWTs with role=teacher):
- P14.2 assignment ownership check — does not require actual teacher login
- P14.3 marks ceiling validation — does not require actual teacher login
- P14.5 student class scope — does not require actual teacher login
The gated parts (P14.1 teacher login flow, P14.4 teacher attendance self-view) require 7-39.

## Context

Part 14 activates and hardens the Teacher role end-to-end. Teacher auth_users ARE seeded in `seed.py` (7 teacher accounts with sub-categories: class_teacher x2, subject_teacher x2, coordinator, hod, kg_incharge). However, the PRD explicitly defers teacher login to Phase 2, designating this as Story 7-39. Until that story is closed, teacher login is latent — credentials exist, but the platform has not been validated for teacher daily use.

The codebase already has significant teacher-facing logic: attendance bulk-mark (`POST /api/attendance/student/bulk`), assignment CRUD, lesson plan management, question paper generation, result entry, and 10 components in `TeacherTools.js`. What is missing is the validation, guard rails, and test coverage required before real teachers start using the platform.

**Entering baseline:** 387 backend tests, 0 skipped. Teacher-specific API tests: ZERO dedicated files for academics, lesson plans, question papers, or results. The `tests/backend/api/` directory has no `test_academics.py`, `test_lesson_plans.py`, or `test_question_papers.py`.

**Gating dependency:** All stories in Part 14 require Story 7-39 (teacher/student login activation) to be shipped to production before teacher-facing features go live. Story 7-39 specifically means: teacher auth_user records verified active, first-login password change flow implemented, teacher role correctly propagated in JWT, and `scope_resolver.py` teacher path confirmed end-to-end in production.

---

## Epic P14: Teacher Role Vertical

### Story P14.1: Teacher login activation (Story 7-39 prerequisite verification)

**Problem:** Teacher auth_users exist in `seed.py` with valid `password_hash` values, roles, and sub-categories. However, there is no integration test confirming the full login-to-JWT path for a teacher user. The `_jwt_payload_from_auth` function in `auth.py` correctly propagates `sub_category` and `branch_id` into the JWT, but no test exercises this for the teacher role. Additionally, there is no first-login flow — teachers are seeded with a shared password (`teacher@123`) that is never forced to change.

**Scope:**
- Add integration test: teacher login via `POST /api/auth/login` → JWT contains `role=teacher`, `sub_category`, and correct `user_id`
- Add integration test: `GET /api/auth/me` with teacher JWT returns correct profile fields
- Add `force_password_change` flag to `auth_users` for seeded teacher accounts; implement the UI prompt on first login
- Confirm `scope_resolver.py` correctly resolves all 5 teacher sub-categories (hod, coordinator, class_teacher, subject_teacher, kg_incharge) with live DB lookups
- Add integration test per teacher sub-category confirming scope type:
  - `class_teacher` → `type="class_list"` with 1 class id
  - `subject_teacher` → `type="class_list"` with assigned class ids
  - `coordinator` → `type="class_list"` with range-resolved class ids
  - `hod` → `type="subject"` with subject name populated
  - `kg_incharge` → `type="class_list"` with KG class id

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a teacher auth_user exists with `role=teacher` and `sub_category=class_teacher`, when `POST /api/auth/login` is called with correct credentials, then the response contains a JWT, and decoding the JWT reveals `role=teacher`, `sub_category=class_teacher`, and the correct `user_id`.

**AC2:** Given a teacher JWT, when `GET /api/auth/me` is called, then the response includes `name`, `role`, `sub_category`, and `initials`.

**AC3:** Given a seeded teacher account, when `resolve_scope(user)` is called with each of the 5 sub-categories and a real DB with staff records, then each returns the expected `Scope.type` value.

**AC4:** Given a teacher seeded with `force_password_change=True`, when they log in for the first time, then the UI prompts them to set a new password before accessing any tool.

**EC-14.4:** Given a teacher with `force_password_change=true` navigates directly to `/?tool=attendance` (bypassing the password-change prompt), When any tool panel attempts to load, Then they are redirected to the password-change screen regardless of the URL.

**AC5:** Existing 387 tests still pass.

**Implementation note (EC-14.4 — force_password_change route guard):** The `force_password_change` check must be a route guard applied in the frontend BEFORE tool panels render. In `App.js`: `if (user.force_password_change) { return <Redirect to='/change-password' /> }` — this must wrap ALL protected routes, not just the login redirect. A direct URL navigation must not bypass this guard.

---

### Story P14.2: Attendance recording — duplicate-date guard and teacher scope

**Problem:** `POST /api/attendance/student/bulk` allows `role=teacher` in `require_role("owner", "admin", "teacher")`. However, there is no check that the teacher is recording attendance for a class they are assigned to — a teacher with `class_teacher_of=cls-1` can submit attendance for class `cls-7`. The bulk endpoint uses `upsert=True`, so recording twice for the same date silently overwrites the earlier record with no audit trail of who submitted the final version. `AttendanceRecorder.js` does not warn the user if attendance already exists for the selected date — it silently re-saves.

**Scope:**
- Add teacher-class ownership check in `POST /api/attendance/student/bulk`: resolve the teacher's scope (`resolve_scope(user)`) and verify `class_id` is in `scope.class_ids`; raise HTTP 403 if not
- Add a `previously_marked` flag in `GET /api/attendance/student/today/{class_id}` response: if any attendance record exists for this class+date, include `"already_marked": true` in the response metadata
- Update `AttendanceRecorder.js` to display a warning banner if `already_marked=true`: "Attendance already submitted for this date. Any saves will overwrite the previous record."
- Add audit trail to the bulk upsert: when a record is upserted (not just inserted), emit an `update` audit log entry alongside the existing `bulk` source tag
- Add integration tests: teacher marking attendance for own class (200), teacher marking attendance for a foreign class (403), second submission for same date triggers audit log update

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given teacher A is class_teacher of class C1, when they submit `POST /api/attendance/student/bulk` with `class_id=C2`, then the response is HTTP 403 "Forbidden: not your class".

**AC2:** Given teacher A submits attendance for class C1 on date D, when they re-submit the same class+date, then the `already_marked` flag is visible in the `GET /api/attendance/student/today/C1?date=D` response before the second submission.

**AC3:** Given attendance has already been marked for class C1 on date D, when a second bulk submission is sent, then an audit log entry is created with `action="bulk_update"` and `changed_by` capturing the second submitter's id.

**AC4:** Given `AttendanceRecorder.js` is rendered for a class that already has attendance marked, when the teacher selects that date, then a warning banner is displayed before they attempt to save.

**EC-14.1 (bulk audit granularity):** Given `POST /api/attendance/student/bulk` with 40 student records, When the write completes, Then exactly ONE audit log entry is created with `action='attendance_bulk', entity_id=class_id, changes={'count_marked': 40, 'date': today}`.

**AC5:** Existing 387 tests still pass.

**Implementation note (EC-14.1 — bulk attendance audit granularity decision):** Bulk attendance writes require a decision on audit granularity: (A) One audit entry per student (N writes per bulk call, max 40 for a full class) — fine-grained but higher write cost. (B) One audit entry for the whole class (1 write, loses per-student granularity). **Decision for Part 14: use Option B** (one entry per class bulk call) with `entity_id=class_id` and `count_marked=N` in the `changes` field. Document this decision with a code comment: `# AUDIT: one entry per bulk call (not per student) — see Part 14 decision log`.

---

### Story P14.3: Assignment management — teacher scope enforcement and cross-class isolation

**Problem:** `GET /api/academics/assignments` correctly filters by `teacher_id` when `user["role"] == "teacher"`. However, `PATCH /api/academics/assignments/{id}` and `DELETE /api/academics/assignments/{id}` do NOT check ownership — any teacher can update or delete any assignment. The `update_one` in PATCH uses `{"id": assignment_id}` without a teacher ownership clause. A class_teacher of Class 10A should not be able to delete an assignment created by the HoD for Class 11.

**Scope:**
- Add ownership check to `PATCH /api/academics/assignments/{id}`: fetch the assignment first; if `user["role"] == "teacher"` and `assignment["teacher_id"] != user["id"]`, return HTTP 403
- Add ownership check to `DELETE /api/academics/assignments/{id}`: same pattern; admins and owners bypass
- Add validation in `POST /api/academics/assignments`: if `user["role"] == "teacher"`, verify `class_id` is in the teacher's resolved scope class_ids
- Add `max_marks` field to assignment schema (currently not persisted) as a foundation for results validation
- Add integration tests: create assignment as teacher T1 → T2 attempting patch/delete returns 403, admin can patch/delete any assignment

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given teacher A creates assignment X, when teacher B (different staff_id, same school) calls `PATCH /api/academics/assignments/{X_id}`, then 403 is returned.

**AC2:** Given teacher A creates assignment X, when teacher A calls `PATCH /api/academics/assignments/{X_id}`, then 200 is returned.

Fix: add `if assignment['created_by'] != user['id'] and user['role'] != 'owner': raise HTTPException(403, 'Not your assignment')`

**AC3:** Given teacher T1 creates assignment A1, when teacher T2 sends `DELETE /api/academics/assignments/A1`, then the response is HTTP 403.

**AC4:** Given teacher T1 is scoped to class C1, when they create an assignment with `class_id=C2` (foreign class), then the response is HTTP 403.

**EC-14.2 (HoD subject scope — no AttributeError):** Given a teacher with `sub_category='hod'` and `scope.type='subject'` creates an assignment, When the class_id ownership check runs, Then it does NOT raise `AttributeError`.

**EC-14.2 (HoD cross-class authority):** Given a HoD creates an assignment with `class_id='cls-1'` (any class in their subject), Then the assignment is created successfully (HoD has cross-class subject authority).

**AC5:** Given an admin user, when they send `PATCH` or `DELETE` on any assignment regardless of `teacher_id`, then the operation succeeds.

**AC6:** Existing 387 tests still pass.

**Implementation note (EC-14.2 — HoD scope.type='subject' guard):** Check scope type before accessing `class_ids`: `if hasattr(scope, 'type') and scope.get('type') == 'subject': pass  # HoD has cross-class authority for their subject, skip class_id validation. elif scope.get('class_ids') and class_id not in scope.get('class_ids', []): raise HTTPException(403, 'Not your class')`. Never access `scope.class_ids` without first confirming `scope.type != 'subject'`.

---

### Story P14.4: Exam results — validation, marks ceiling, and publication gate

> **Cross-Part Dependency:** The `is_published` field on exam results is required by P15.4 (Student role — students see results only when published). P14.4 must be implemented before P15 starts or P15.4 must use a feature flag.

**Problem:** `POST /api/academics/results/bulk` has no validation that `marks_obtained <= max_marks`. A teacher can submit `{"marks_obtained": 150, "max_marks": 100}` and the record is saved without error. There is no concept of "published" results — as soon as a result is entered, it is visible to students via `GET /api/academics/results`. There is also no check that the teacher is entering results only for their own class students.

**Scope:**
- Add validation in `POST /api/academics/results/bulk`: if `marks_obtained > max_marks`, return HTTP 400 for that row with a descriptive error; skip or reject depending on configuration
- Add `is_published` flag to exam results: default `False`; students can only see results where `is_published=True` in `GET /api/academics/results`
- Add `PATCH /api/academics/results/{result_id}/publish` endpoint: `require_role("admin", "owner")` only (principal publishes results, not teachers)
- Add teacher-class ownership check in bulk results entry: teacher can only enter results for students in their scoped class_ids
- Add integration tests: marks exceed max_marks → 400, student queries results before publish → empty list, after publish → result visible, teacher entering results for foreign student → 403

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a bulk results request where one row has `marks_obtained=110` and `max_marks=100`, when submitted, then that row is rejected with `{"student_id": "...", "status": "error", "error": "marks_obtained exceeds max_marks"}` and other valid rows are still saved.

**AC2:** Given exam results have been entered but `is_published=False`, when a student queries `GET /api/academics/results`, then the results list is empty.

**AC3:** Given a principal issues `PATCH /api/academics/results/{id}/publish`, then `is_published` is set to `True` and the result becomes visible to students.

**AC4:** Given teacher T1 is scoped to class C1, when they attempt to submit a result for a student in class C2, then the row is rejected with HTTP 403.

**EC-14.3 (partial failure response shape):** Given `POST /api/academics/results/bulk` with 10 rows where 2 have marks > max_marks, When the request is processed, Then the response is `{'success': 'partial', 'saved': 8, 'errors': [{'row': 3, 'reason': 'marks 105 exceeds max_marks 100'}, {'row': 7, 'reason': 'marks 110 exceeds max_marks 100'}]}`.

**EC-14.3 (all-valid response shape):** Given all 10 rows are valid, Then response is `{'success': True, 'data': {'saved': 10}}`.

**AC5:** Existing 387 tests still pass.

**Implementation note (EC-14.3 — bulk partial success response shape):** Define a new response shape for bulk partial success — this deviates from the standard `{'success': True, 'data': [...]}` convention. Document in the route's docstring: `# Response shape: {'success': True|'partial'|False, 'saved': int, 'errors': list}`. The `'partial'` string value is intentional to distinguish from full success (`True`) and full failure (`False`).

---

### Story P14.5: Lesson plan management — principal review workflow

**Problem:** `POST /api/academics/lesson-plans` and `GET /api/academics/lesson-plans` work correctly. However, there is no status workflow: a lesson plan is submitted and is immediately final with no review step. There is no way for a principal to see lesson plans for the whole school vs. only their own (teachers see only `teacher_id=user.id`). The `GET /api/academics/lesson-plans` admin path returns all lesson plans without pagination, risking large payloads.

**Scope:**
- Add `status` field to lesson plan schema: `draft | submitted | reviewed | approved | rejected`; new plans default to `draft`
- Add `PATCH /api/academics/lesson-plans/{id}/submit` for teachers: moves plan from `draft` to `submitted`
- Add `PATCH /api/academics/lesson-plans/{id}/review` for admin/principal: accepts `status` (approved/rejected) and optional `review_notes`
- Add pagination to `GET /api/academics/lesson-plans`: `page` and `limit` parameters; admin sees all, teacher sees only own
- Add integration tests: teacher submits plan, principal reviews → status transitions correctly; teacher cannot approve own plan

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a teacher creates a lesson plan, when they call `PATCH /api/academics/lesson-plans/{id}/submit`, then `status` changes from `draft` to `submitted`.

**AC2:** Given a plan is in `submitted` status, when a principal calls `PATCH /api/academics/lesson-plans/{id}/review` with `status=approved`, then `status` becomes `approved` and `review_notes` is persisted.

**AC3:** Given a teacher attempts to call the `/review` endpoint, then the response is HTTP 403.

**AC4:** Given `GET /api/academics/lesson-plans?limit=10&page=2` is called by a principal, then the response includes pagination metadata (`page`, `total`, `per_page`).

**AC5:** Existing 387 tests still pass.

---

### Story P14.6: Question paper generation — class-binding and AI input validation

**Problem:** `POST /api/academics/question-papers/generate` accepts free-form `subject`, `chapters`, and `total_marks` from the request body with no validation. A teacher can submit `subject=""` or `total_marks=-50`, causing either a nonsense AI prompt or an invalid DB record. The generated paper is not linked to a specific class — `qp.class_id` is never set. Teachers can list all question papers regardless of who generated them (the filter `query["teacher_id"] = user["id"]` only applies to the teacher role via `GET /api/academics/question-papers`).

**Scope:**
- Add input validation in `POST /api/academics/question-papers/generate`:
  - `subject`: non-empty string, max 100 chars
  - `total_marks`: integer between 10 and 200
  - `easy + medium + hard` must sum to 100
  - `exam_type`: must be one of `["Unit Test", "Half Yearly", "Annual", "Practice"]`
- Add `class_id` field to the question paper schema; require it in the POST body for teachers
- Add teacher-class ownership check: teacher can only generate papers for their scoped class_ids
- Fix `GET /api/academics/question-papers/{paper_id}` to include ownership check for teachers: teacher can only fetch their own paper
- Add integration tests: invalid inputs → 400, valid generation → paper saved with class_id, teacher fetching foreign paper → 403

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given a request with `easy=40, medium=40, hard=30` (sum=110), when `POST /api/academics/question-papers/generate` is called, then the response is HTTP 400 "difficulty percentages must sum to 100".

**AC2:** Given `total_marks=-50` in the request body, then the response is HTTP 400 "total_marks must be between 10 and 200".

**AC3:** Given a teacher generates a question paper for class C1, then the saved document contains `class_id=C1`.

**AC4:** Given teacher T1 tries to fetch a question paper generated by teacher T2 via `GET /api/academics/question-papers/{id}`, then the response is HTTP 403.

**AC5:** Existing 387 tests still pass.

---

### Story P14.7: Teacher's own attendance and leave visibility

**Problem:** `GET /api/attendance/staff` requires `require_role("owner", "admin")` — teachers cannot view their own attendance records. This means a teacher has no way to see how many days they have been present this month, or verify their leave application was processed. The leave request flow (`POST /api/leave/requests`) exists but `LeaveApplication.js` in `TeacherTools.js` only shows status — there is no direct endpoint for a teacher to view their own leave history without an admin role.

**Scope:**
- Add `GET /api/attendance/staff/me` endpoint: `require_role("teacher")`, returns attendance records for the authenticated teacher's `staff_id` (looked up from `db.staff` via `user_id`)
- Add `GET /api/leave/requests/my` endpoint: `require_role("teacher")`, returns leave requests where `staff_id` matches the teacher's staff record
- Update `LeaveApplication.js` component in `TeacherTools.js` to call `GET /api/leave/requests/my` to show the teacher their own leave history with statuses
- Add integration tests: teacher gets own attendance → 200 with filtered records, teacher cannot query another staff member's attendance via `/staff/me`

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given teacher T1 has staff_id S1 with 3 attendance records, when they call `GET /api/attendance/staff/me`, then the response contains exactly those 3 records for S1.

**AC2:** Given teacher T1 calls `GET /api/attendance/staff/me`, then no records from other staff members are returned.

**AC3:** Given teacher T1 calls `GET /api/leave/requests/my`, then only their own leave requests are returned (not requests from other teachers).

**AC4:** Given the `LeaveApplication` component is loaded for a teacher, then it displays their pending, approved, and rejected leave requests fetched from `GET /api/leave/requests/my`.

**AC5:** Existing 387 tests still pass.

---

### Story P14.8: Student profile access — teacher can view class students with guardian contact

**Problem:** `GET /api/students/` currently allows `READ_ROLES = {"owner", "admin", "teacher"}` — teachers can see student lists. However, the scope resolver knows a teacher's `class_ids` but the `/api/students/` endpoint does NOT apply scope filtering for teachers — it returns all students when no `class_id` filter is provided. A subject_teacher assigned to classes 9A and 10B can query all students from all classes. Guardian contact info is included in `GET /api/students/{id}` but the teacher endpoint does not verify the student is in the teacher's class.

**Scope:**
- In `GET /api/students/`, when `user["role"] == "teacher"`, resolve scope and add `class_id: {$in: scope.class_ids}` to the query automatically (unless `class_id` param is already provided and is in `scope.class_ids`)
- In `GET /api/students/{id}`, when `user["role"] == "teacher"`, verify the student's `class_id` is in the teacher's `scope.class_ids` before returning; 403 otherwise
- Add integration tests: teacher with class C1 can list students in C1, teacher with class C1 cannot list students in C2, teacher can view guardian info for their own class student

**Acceptance Criteria (Given/When/Then):**

**AC1:** Given teacher T1 is scoped to class C1, when they call `GET /api/students/` with no class_id filter, then only students from C1 are returned.

**AC2:** Given teacher T1 is scoped to class C1, when they call `GET /api/students/{student_id}` for a student in class C2, then the response is HTTP 403.

**AC3:** Given teacher T1 is scoped to class C1, when they call `GET /api/students/{student_id}` for a student in C1, then the response includes `guardians` array with contact info.

**AC4:** Given a teacher with `hod` sub-category and `subject=Mathematics`, when they call `GET /api/students/`, then students from all Math-teaching classes are returned (cross-class subject scope).

**AC5:** Existing 387 tests still pass.

---

## NFRs

**NFR14.1 — Response time:** All teacher-facing read endpoints (`GET /api/academics/assignments`, `GET /api/attendance/student/today/{class_id}`, `GET /api/academics/lesson-plans`) must return within 2 seconds at p95 for classes of up to 50 students.

**NFR14.2 — Scope isolation:** Zero cross-class data leakage for any teacher sub-category verified by integration tests; a teacher in Class 10A must never receive student data, assignments, or results from Class 11B in a single query.

**NFR14.3 — Audit completeness:** Every attendance write (bulk or individual) emitted by a teacher must produce a corresponding audit log entry in `db.audit_logs` with `changed_by`, `changed_by_role`, and `action` fields populated.

**NFR14.4 — Gating discipline:** No teacher-facing feature is deployed to production until Story 7-39 is marked closed in the tracker; a CI lint rule or deployment gate enforces this.

**NFR14.5 — Test baseline:** After Part 14, the test count must be at least 387 + 40 (40 net-new tests covering the stories above).

---

## FR Coverage Map

| FR | Story | Endpoint(s) Covered |
|---|---|---|
| Teacher login JWT path | P14.1 | POST /api/auth/login, GET /api/auth/me |
| Scope per sub-category verified | P14.1 | scope_resolver.py (all 5 sub-types) |
| Attendance class-ownership check | P14.2 | POST /api/attendance/student/bulk |
| Duplicate-date warning | P14.2 | GET /api/attendance/student/today/{class_id} |
| Assignment PATCH/DELETE ownership | P14.3 | PATCH/DELETE /api/academics/assignments/{id} |
| Assignment class scope at create | P14.3 | POST /api/academics/assignments |
| Marks ceiling validation | P14.4 | POST /api/academics/results/bulk |
| Results publication gate | P14.4 | GET /api/academics/results (student view) |
| Results publish endpoint | P14.4 | PATCH /api/academics/results/{id}/publish |
| Lesson plan status workflow | P14.5 | PATCH /api/academics/lesson-plans/{id}/submit, /review |
| Lesson plan pagination | P14.5 | GET /api/academics/lesson-plans |
| Question paper input validation | P14.6 | POST /api/academics/question-papers/generate |
| Question paper class binding | P14.6 | POST /api/academics/question-papers/generate |
| Teacher self-attendance view | P14.7 | GET /api/attendance/staff/me (new) |
| Teacher leave history | P14.7 | GET /api/leave/requests/my (new) |
| Student list scoped to teacher | P14.8 | GET /api/students/ |
| Student profile auth for teacher | P14.8 | GET /api/students/{id} |

---

## Implementation Order

1. P14.1 — Teacher login activation (unblocks all downstream stories)
2. P14.8 — Student profile access scoping (foundational for all teacher-student interactions)
3. P14.2 — Attendance recording guards (highest daily-use risk)
4. P14.3 — Assignment ownership enforcement
5. P14.4 — Exam results validation and publish gate
6. P14.5 — Lesson plan status workflow
7. P14.7 — Teacher self-attendance and leave
8. P14.6 — Question paper validation (AI path, lower risk)

---

## Epic P14: Retrospective

A retrospective entry for Part 14 to be completed after all P14.1–P14.8 stories are done.
