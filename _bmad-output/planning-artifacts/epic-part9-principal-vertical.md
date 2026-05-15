---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 9'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 9
part_name: 'Principal Role Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy', 'Part 8 Frontend Foundation']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 9: Principal Role Vertical

## Context

Part 9 targets the completeness and correctness of the principal (admin + sub_category=principal) role vertical. The principal is the most operationally active role in the platform: approving leaves, broadcasting announcements, reviewing attendance, monitoring academic performance, and escalating incidents. Auditing `PrincipalDailyOps.js`, `backend/routes/staff.py`, `backend/routes/attendance.py`, `backend/routes/operations.py`, and `backend/routes/reports.py` reveals that the principal role has the authorization checks in place (via `require_owner_or_principal`) but several workflows are incomplete: leave approvals do not notify the staff member, the daily ops panel covers only substitutions (not leave approvals + attendance overview), fee-collection-summary is owner-only (principal cannot access it), and the incident escalation flow is read-only for the principal.

**Entering baseline:** 387 backend tests, 0 skipped.

---

## Epic P9: Principal Role Vertical

### Story P9.1: PrincipalDailyOps.js — expand from substitution-only to full daily operations dashboard

**Problem:** `PrincipalDailyOps.js` shows exactly one data set: the substitution plan for absent teachers. A real principal's morning routine requires: (1) pending leave requests, (2) today's attendance summary by class, (3) any unread announcements awaiting approval, (4) open incident reports assigned to principal. None of these are present in the current component — they exist in separate tools or not at all.

**Scope:**
- Add a "Pending Leave Requests" section to `PrincipalDailyOps.js` by fetching `GET /api/staff/leaves/pending`. Display staff name, leave type, dates, and Approve/Reject action buttons that call `PATCH /api/staff/leaves/{id}` (using the existing `updateLeave` API function in `api.js`).
- Add a "Today's Attendance" summary strip: fetch `GET /api/attendance/today` (or the existing attendance summary endpoint). Show: total teachers expected, present, absent — and a "View absences" link to the substitution plan.
- Add a "Pending Announcements" count badge fetching `GET /api/ops/announcements/pending`. Clicking the badge navigates to the announcement moderation view (dispatch `eduflow-navigate` event).
- Add an "Open Incidents" count fetching `GET /api/ops/incidents?status=open`. Clicking navigates to incidents panel.
- Organise the four sections in a 2×2 responsive grid above the existing substitution table.

**Acceptance Criteria:**
- `PrincipalDailyOps` fetches and displays pending leave requests with approve/reject buttons
- Attendance summary strip shows today's teacher presence counts
- Pending announcements badge is visible with correct count
- Open incidents count is visible
- All four data fetches happen in parallel (single `Promise.all` on mount)
- No regressions in existing substitution plan display

---

### Story P9.2: Leave approval — staff notification and audit trail

**Problem:** `PATCH /api/staff/leaves/{leave_id}` in `staff.py` (lines 281–293) updates the leave status and sets `approved_by` and `approved_at` but does NOT notify the staff member. The staff member only learns of the decision by polling `GET /api/staff/leaves/my`. Additionally:

1. There is no audit trail for leave decisions — `audit_logs` is not written for leave approval/rejection.
2. Leave approval in `staff.py` uses `require_role("owner", "admin")` which is broader than needed — any admin sub-category (accountant, maintenance, etc.) can approve leaves. The check should be `require_owner_or_principal` to enforce the correct authority.
3. The leave approval endpoint in `operations.py` (`POST /api/ops/decide_leave/{leave_id}` at line 120) is a SEPARATE endpoint with notification support. There are TWO leave approval paths and only one has a notification. The `staff.py` path is the one used by the frontend (`AdminTools.js` calls `updateLeave` which maps to `staff.py`).

**Scope:**
- In `staff.py` `update_leave`, add a notification insert to `db.notifications` when the status changes to `approved` or `rejected` (same pattern as `operations.py` `_notify` helper):
  - Message: `"Your leave request from {start_date} to {end_date} has been {status}"`.
  - `user_id`: the `user_id` field from the leave request document.
- Add an audit log write to `db.audit_logs` for the leave approval/rejection action.
- Change `require_role("owner", "admin")` in the `update_leave` endpoint to `require_owner_or_principal` to tighten the authority.
- Add a comment near `operations.py` line 120 noting the second (fully-featured) leave-decision endpoint so future developers do not add a third.
- Add backend unit tests: approve a leave → notification created; reject a leave → notification created; accountant role → 403.

**Acceptance Criteria:**
- `PATCH /api/staff/leaves/{id}` with `approved` status inserts a notification document for the staff's `user_id`
- `PATCH /api/staff/leaves/{id}` with `rejected` status inserts a notification document
- Audit log entry created for every leave decision
- Accountant sub-category admin receives 403 from the leave approval endpoint
- At least 3 new backend unit tests
- Existing 387 tests still pass

---

### Story P9.3: Attendance oversight — principal class-level summary and absent-teacher identification

**Problem:** The principal currently has access to `GET /api/attendance/today` and `GET /api/attendance/stats` but:

1. There is no endpoint that returns today's class-level attendance summary (count present/absent per class) without paginating through individual records.
2. The staff attendance (`db.staff_attendance`) is tracked by biometric or manual entry, but there is no `GET /api/attendance/staff/today` endpoint that the principal can call to see which specific teachers are absent today (as distinct from the substitution plan which only shows timetable conflicts).
3. `PrincipalDailyOps.js` shows absent teacher count from the substitution plan meta, but this only counts teachers with active timetable slots — a teacher with no scheduled periods today appears absent without appearing in the plan.

**Scope:**
- Add `GET /api/attendance/class-summary?date={date}` endpoint in `attendance.py`: returns an array of `{class_id, class_name, total_students, present, absent, not_marked}` for each class. Auth: `require_owner_or_principal`.
- Add `GET /api/attendance/staff/today?date={date}` endpoint in `attendance.py`: returns list of staff with `{staff_id, staff_name, status, marked_at}` from `db.staff_attendance` for the given date. Auth: `require_owner_or_principal`.
- Update `PrincipalDailyOps.js` to call both new endpoints and display:
  - A class attendance summary table (class name, total, present%, absent count).
  - An "Absent Staff Today" list (staff name, role) with a "Mark in timetable" shortcut.
- Add backend tests for both new endpoints: data returned, correct school scoping, 403 for non-principal/non-owner.

**Acceptance Criteria:**
- `GET /api/attendance/class-summary` returns per-class attendance counts scoped to schoolId
- `GET /api/attendance/staff/today` returns staff attendance for the requested date
- Both endpoints return 403 for roles other than owner/principal
- `PrincipalDailyOps.js` renders the class summary table and absent staff list
- At least 4 new backend tests (2 per endpoint)
- Existing 387 tests still pass

---

### Story P9.4: Announcement moderation — principal broadcast to all students/parents

**Problem:** The announcement moderation flow in `operations.py` (line 716+) allows a principal to approve or reject announcements via `PATCH /api/ops/announcements/{ann_id}/approve`. This path is functional. However:

1. A principal cannot directly POST a broadcast announcement to all students and parents without the owner's approval gate — `POST /api/ops/announcements` (line 716) requires `audience_type` targeting, and the approval requirement is determined by `_announcement_requires_approval` (line 41). According to the code, an announcement to `teacher` or `student` audience requires approval if the poster is NOT owner/principal. A principal IS in the exception set and should be able to broadcast directly.
2. `_announcement_requires_approval` (line 41) checks `audience_type` but the code at line 724 does NOT call `_announcement_requires_approval` with the poster's role — so the logic is incomplete: ANY sender posting to `student` audience gets `status=pending_approval`, including the principal.
3. There is no frontend panel for announcement composition in the principal vertical — the principal can only VIEW pending announcements in the current `PrincipalDailyOps.js` (badge link), not compose new ones.

**Scope:**
- Fix `POST /api/ops/announcements`: if the poster is owner or principal (`_is_owner_or_principal(user)`), set `status = "approved"` directly regardless of audience. Existing tests cover the approval gate for other roles.
- Add an "Compose Announcement" panel to `PrincipalDailyOps.js` (or a dedicated sub-page): form fields for title, body, audience (all/teachers/students/parents), and a "Post" button that calls `POST /api/ops/announcements`.
- The compose panel should show a confirmation preview before posting (repurpose the `ConfirmActionCard` pattern).
- Add backend tests: principal posts to `student` audience → status is `approved`, not `pending_approval`; teacher posts to `student` audience → status is `pending_approval`.

**Acceptance Criteria:**
- Principal-posted announcements are approved directly (no owner gate)
- Owner-posted announcements are approved directly
- Teacher-posted announcements to student audience remain in `pending_approval`
- Frontend compose panel accessible from the principal daily ops view
- At least 2 new backend tests
- Existing 387 tests still pass

---

### Story P9.5: Academic oversight — exam results across all classes and lesson plan completion

**Problem:** The principal currently has no single-screen view of exam results across all classes or lesson plan completion rates. Exam results exist in `db.exam_results` and are accessible via `GET /api/academics/exam-results` (restricted to owner/admin). Lesson plans exist in `db.lesson_plans`. Neither is surfaced in the principal vertical frontend.

**Scope:**
- Verify `GET /api/academics/exam-results` is accessible with `require_owner_or_principal` (or `require_role("owner", "admin")`). If it uses `require_owner` only, broaden to include principal.
- Add `GET /api/academics/lesson-plan-completion?month={yyyy-mm}` endpoint in `academics.py`: returns `{class_id, class_name, teacher_name, total_plans, completed, completion_pct}` per class. Auth: `require_owner_or_principal`.
- Add an "Academics Overview" tab to `PrincipalDailyOps.js` (or a separate `PrincipalAcademics` component) with:
  - A per-class exam results summary table (class, last exam date, avg score, pass %).
  - A lesson plan completion bar chart (using `BarChartWidget` from `ToolPage.js`).
- Add backend tests for the lesson-plan-completion endpoint: data returned per class, correct scoping, 403 for wrong roles.

**Acceptance Criteria:**
- `GET /api/academics/exam-results` accessible to principal role
- `GET /api/academics/lesson-plan-completion` endpoint exists, scoped, and returns per-class completion data
- Principal sees exam results and lesson plan completion in the frontend
- At least 3 new backend tests
- Existing 387 tests still pass

---

### Story P9.6: Report access — fee-collection-summary blocked for principal

**Problem:** `GET /api/reports/fee-collection-summary` in `reports.py` (line 136) uses `require_owner` — it is owner-only. The `GET /api/reports/attendance-trends` endpoint (line 61) correctly uses `require_owner_or_principal`. This asymmetry is inconsistent: the principal needs the fee-collection summary to understand whether the school is meeting its financial targets (not to make changes to transactions — just read-only trend data).

**Scope:**
- Change the `require_owner` dependency on `GET /api/reports/fee-collection-summary` to `require_owner_or_principal`.
- Update the docstring on the endpoint to note that principal access is read-only view.
- Add backend tests: principal role → 200 with data; accountant role → 403.
- Update the frontend `ReportsTrends` component in `AdminTools.js` (currently only fetches attendance-trends and blocks fee-collection-summary behind a comment "Story 7-41 — Principal reports panel. Attendance trend only (no fees per RBAC)") to now also fetch and display `fee-collection-summary` for principal and owner.

**Acceptance Criteria:**
- `GET /api/reports/fee-collection-summary` returns 200 for principal role
- `GET /api/reports/fee-collection-summary` returns 403 for accountant role
- `ReportsTrends` component fetches and renders fee collection summary for owner/principal
- Comment in `AdminTools.js` updated to reflect the RBAC change
- At least 2 new backend tests
- Existing 387 tests still pass

---

### Story P9.7: Staff management — class assignment and leave balance adjustment

**Problem:** The principal can view and update staff profiles via `PATCH /api/staff/{id}` (guarded by `_is_owner_or_principal` for the `LEAVE_BALANCE_FIELDS`). However:

1. There is no UI in the principal vertical for adjusting leave balances — the only interface is the owner's admin panel.
2. Class assignment (linking a teacher to a class section) is done via `db.timetable` or `db.classes.teacher_id` — there is no dedicated endpoint or UI for the principal to reassign a teacher to a class.
3. `PATCH /api/staff/{id}` allows updating `role` and `sub_category` fields for a principal — this is an over-permission: a principal should NOT be able to change another admin's `role` to `owner` or `sub_category`.

**Scope:**
- In `PATCH /api/staff/{id}`, add a guard: if the requesting user is principal (not owner), disallow updates to `role` and `sub_category` fields. Only owner can change roles.
- Add `GET /api/staff/{staff_id}/leave-balance` endpoint: returns `{casual_leave_balance, medical_leave_balance, earned_leave_balance}` for the given staff. Auth: `require_owner_or_principal`.
- Add a "Leave Balance" adjustment section to the principal's staff management view: a form to increment/decrement leave balance fields. Calls `PATCH /api/staff/{id}` with only the leave balance fields.
- Add backend tests: principal updates `role` field → 403; owner updates `role` field → 200; principal updates `casual_leave_balance` → 200.

**Acceptance Criteria:**
- Principal cannot update `role` or `sub_category` of any staff member (403)
- Owner can update `role` of any staff member (200)
- `GET /api/staff/{id}/leave-balance` endpoint returns leave balance fields
- Leave balance adjustment UI accessible in the principal vertical
- At least 3 new backend tests
- Existing 387 tests still pass

---

### Story P9.8: Incident escalation — teacher can escalate to principal for review

**Problem:** `GET /api/ops/incidents` (line 341 in `operations.py`) is accessible to `owner/admin`. Incidents have a `status` field. However:

1. Teachers have no way to create or escalate incidents to the principal — `POST /api/ops/incidents` (if it exists) is likely restricted to owner/admin.
2. There is no "escalated_to_principal" status or `assigned_to` field on incidents.
3. The principal can read open incidents (line 352 adds principal filter) but cannot act on them (no `PATCH /api/ops/incidents/{id}/resolve` endpoint surfaced in the audit).

**Scope:**
- Add `POST /api/ops/incidents` endpoint if it does not exist: allows any authenticated user (teacher, admin, owner) to create an incident with fields `{title, description, severity, class_id, student_ids}`. Auth: any authenticated user.
- Add an `assigned_to` field to incidents: `"principal"` or `"owner"`. When severity is `high`, default `assigned_to = "principal"`.
- Add `PATCH /api/ops/incidents/{id}` endpoint: allows owner or principal to update `status` (open → investigating → resolved) and add `resolution_note`. Auth: `require_owner_or_principal`.
- Add a "Report Incident" button to the teacher-facing attendance or class view that opens a modal to create an incident.
- Add backend tests: teacher creates incident → 201; principal resolves incident → 200 with status change; teacher tries to resolve → 403.

**Acceptance Criteria:**
- `POST /api/ops/incidents` accessible to teachers (auth: any logged-in user)
- High-severity incidents auto-assigned to principal
- `PATCH /api/ops/incidents/{id}` allows principal to update status and add resolution note
- Teacher cannot resolve an incident (403)
- At least 3 new backend tests
- Existing 387 tests still pass

---

## FR Coverage Map

| FR ID | Story | Description |
|-------|-------|-------------|
| FR-P9.1 | P9.1 | PrincipalDailyOps shows leave requests, attendance, announcements, incidents |
| FR-P9.2 | P9.2 | Leave approval creates staff notification and audit log entry |
| FR-P9.3 | P9.2 | Leave approval restricted to owner/principal only |
| FR-P9.4 | P9.3 | Class-level attendance summary endpoint for principal |
| FR-P9.5 | P9.3 | Staff attendance today endpoint for principal |
| FR-P9.6 | P9.4 | Principal broadcast announcements bypass approval gate |
| FR-P9.7 | P9.5 | Principal can view exam results across all classes |
| FR-P9.8 | P9.5 | Lesson plan completion endpoint for principal |
| FR-P9.9 | P9.6 | Principal can read fee-collection-summary report |
| FR-P9.10 | P9.7 | Principal cannot update role/sub_category of staff |
| FR-P9.11 | P9.8 | Teacher can create/escalate incidents |
| FR-P9.12 | P9.8 | Principal can resolve incidents with resolution note |

---

## NFRs

| NFR ID | Category | Requirement |
|--------|----------|-------------|
| NFR-P9.1 | Performance | `PrincipalDailyOps` initial load must fetch all four data sources in parallel; total load time < 2s on a 100ms-latency connection |
| NFR-P9.2 | Audit | Every leave decision (approve/reject) must produce an audit log entry in `db.audit_logs` |
| NFR-P9.3 | Security | Principal role must not be able to escalate its own permissions (no role/sub_category self-update, no updating other admins to owner) |
| NFR-P9.4 | Correctness | All attendance and report endpoints for principal must be scoped to `schoolId` (no cross-school data leakage) |

---

## Implementation Order

1. **P9.6** (report access fix) — single-line auth change, very low risk, unblocks frontend work
2. **P9.2** (leave approval notification + audit) — backend-only, no frontend change, high value
3. **P9.3** (attendance summary endpoints) — new backend endpoints, needed by P9.1 UI
4. **P9.4** (announcement broadcast fix) — fixes a logic bug in operations.py
5. **P9.7** (staff management guards) — closes a privilege escalation gap
6. **P9.1** (PrincipalDailyOps expansion) — frontend; requires P9.3 endpoints to be live
7. **P9.5** (academic oversight) — new backend endpoint + frontend panel
8. **P9.8** (incident escalation) — new endpoint + teacher UI; depends on stable ops.py from P9.4

---

## Epic P9: Retrospective

A retrospective entry for Part 9 to be completed after all P9.1–P9.8 stories are done.
