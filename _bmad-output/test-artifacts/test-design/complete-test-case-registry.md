---
project: EduFlow — The Aaryans
document: complete-test-case-registry
author: Master Test Architect (BMAD TEA)
date: 2026-05-21
coverage: All 290 endpoints × 9 roles × 20 UI tools
format: Numbered checklist — tick as you pass each case
total_test_cases: 310
---

# EduFlow — Complete Test Case Registry

> Companion to `manual-dataflow-test-plan.md`. That doc tests **data flows** end-to-end.
> This doc tests **every individual feature** in every tool for every role.
>
> **How to use:** Work module by module. Each `[ ]` is one test. Mark ✅ pass / ❌ fail.
> Swagger UI (`http://localhost:8000/docs`) for API cases. Browser for UI cases.

---

## Accounts Quick Reference

| # | Username | Password | Role |
|---|---|---|---|
| U1 | `owner` | `owner@123` | Owner |
| U2 | `admin` | `admin@123` | Principal |
| U3 | `accountant` | `accountant@123` | Accountant |
| U4 | `ittech` | `ittech@123` | IT & Tech |
| U5 | `maintenance` | `maintenance@123` | Maintenance |
| U6 | `reception` | `reception@123` | Receptionist |
| U7 | `Rajesh Kumar` | `teacher@123` | Teacher (Class 9A) |
| U8 | `ADM20250001` | `student@123` | Student |
| U9 | `Sunita Devi` | `teacher@123` | Teacher (Class 9B) |

---

## MODULE 1 — Authentication

### 1.1 Login

- [ ] **TC-001** (All roles) Login with correct credentials → 200, `access_token` returned, `eduflow_token` in localStorage
- [ ] **TC-002** (Any) Login with wrong password → 401 "Invalid credentials"
- [ ] **TC-003** (Any) Login with non-existent username → 401
- [ ] **TC-004** (Any) Login 5× with wrong password → account locked message on 5th attempt
- [ ] **TC-005** (U1) Login as owner → redirected to Owner dashboard with Owner Tools sidebar
- [ ] **TC-006** (U2) Login as principal → redirected to Principal dashboard with PrincipalDailyOps
- [ ] **TC-007** (U3) Login as accountant → FeeCollection tool visible
- [ ] **TC-008** (U7) Login as teacher → TeacherTools visible
- [ ] **TC-009** (U8) Login as student → StudentTools visible, no admin panels
- [ ] **TC-010** (Any) Login without body → 422 validation error

### 1.2 Token & Session

- [ ] **TC-011** (Any) `GET /api/auth/me` with valid token → current user object returned
- [ ] **TC-012** (Any) `GET /api/auth/me` without token → 401 + `WWW-Authenticate: Bearer` header
- [ ] **TC-013** (Any) `POST /api/auth/refresh` with valid refresh cookie → new access_token
- [ ] **TC-014** (Any) `POST /api/auth/refresh` with no cookie → 401
- [ ] **TC-015** (Any) `POST /api/auth/logout` → refresh cookie cleared, subsequent refresh returns 401

### 1.3 Password Management

- [ ] **TC-016** (Any) `POST /api/auth/change-password` with correct current password → 200, can login with new password
- [ ] **TC-017** (Any) Change password with wrong current password → 400/401
- [ ] **TC-018** (Any) Change password with weak new password (<8 chars) → 422
- [ ] **TC-019** (Any) `POST /api/auth/forgot-password` with valid email → 200 (email sent or dev log)
- [ ] **TC-020** (Any) `POST /api/auth/reset-password` with valid reset token → password changed
- [ ] **TC-021** (Any) Reset password with expired token → 400/401

### 1.4 Admin Password Reset (IT Tech)

- [ ] **TC-022** (U4) `POST /api/auth/admin/users/{teacher_id}/reset-password` → 200, teacher can login with new password
- [ ] **TC-023** (U4) Reset owner's password → 403 "Cannot reset owner password"
- [ ] **TC-024** (U3) Accountant tries admin reset → 403
- [ ] **TC-025** (U7) Teacher tries admin reset → 403

### 1.5 Account Unlock (IT Tech)

- [ ] **TC-026** (U4) `POST /api/auth/admin/users/{id}/unlock` on locked account → 200, account unlocked
- [ ] **TC-027** (U4) Unlock already-active account → 200 (idempotent)
- [ ] **TC-028** (U3) Accountant tries unlock → 403

---

## MODULE 2 — Student Database

**Tool:** StudentDatabase.js | **Primary roles:** U1 (owner), U2 (principal), U7/U9 (teacher)

### 2.1 List & Search Students

- [ ] **TC-029** (U1) `GET /api/students/` → all students returned, schoolId-scoped
- [ ] **TC-030** (U2) `GET /api/students/` → same, principal sees all
- [ ] **TC-031** (U7) `GET /api/students/` → only branch students visible
- [ ] **TC-032** (U8) `GET /api/students/` → 403 (student cannot list all)
- [ ] **TC-033** (U1) `GET /api/students/?class_id=<9A_id>` → only Class 9A students
- [ ] **TC-034** (U1) `GET /api/students/?q=Rahul` → search by name returns matching students
- [ ] **TC-035** (U1) `GET /api/students/classes/all` → all classes list

### 2.2 Create Student

- [ ] **TC-036** (U2) `POST /api/students/` with full required fields → 200, student created with UUID id
- [ ] **TC-037** (U2) Create student missing required field (name) → 422
- [ ] **TC-038** (U7) Teacher tries to create student → 403
- [ ] **TC-039** (U8) Student tries to create student → 403

### 2.3 Read Individual Student

- [ ] **TC-040** (U1) `GET /api/students/{id}` → full student record, no `_id` in response
- [ ] **TC-041** (U8) `GET /api/students/me` → own profile only
- [ ] **TC-042** (U8) `GET /api/students/{other_student_id}` → 403 or empty (isolation)

### 2.4 Update Student

- [ ] **TC-043** (U2) `PATCH /api/students/{id}` update name → 200, name changed
- [ ] **TC-044** (U8) `PATCH /api/students/me` → student can update own profile
- [ ] **TC-045** (U8) `PATCH /api/students/{other_id}` → 403
- [ ] **TC-046** (U7) Teacher patches student → 403

### 2.5 Student Photo

- [ ] **TC-047** (U2) `POST /api/students/{id}/photo` with valid image → 200, photo URL returned
- [ ] **TC-048** (U2) Upload non-image file as photo → 400/422

### 2.6 Guardians

- [ ] **TC-049** (U2) `GET /api/students/{id}/guardians` → guardian list
- [ ] **TC-050** (U2) `PUT /api/students/{id}/guardians` with guardian data → 200, guardian saved
- [ ] **TC-051** (U8) Student cannot view another student's guardians → 403

### 2.7 Consent & Data Erasure

- [ ] **TC-052** (U8) `GET /api/students/me/consent` → consent status
- [ ] **TC-053** (U8) `POST /api/students/me/consent` → consent recorded
- [ ] **TC-054** (U1) `POST /api/students/{id}/erase` → student data erased (GDPR)
- [ ] **TC-055** (U7) Teacher tries erase → 403

### 2.8 Delete Student

- [ ] **TC-056** (U1) `DELETE /api/students/{id}` → 200, student soft-deleted
- [ ] **TC-057** (U7) Teacher tries delete → 403

---

## MODULE 3 — Staff Tracker

**Tool:** StaffTracker.js | **Primary roles:** U1, U2

### 3.1 List & Create Staff

- [ ] **TC-058** (U1) `GET /api/staff/` → all staff with sub_categories
- [ ] **TC-059** (U2) `GET /api/staff/` → staff list visible to principal
- [ ] **TC-060** (U7) Teacher tries list staff → depends on role guard — verify response
- [ ] **TC-061** (U1) `POST /api/staff/` with valid data → staff created
- [ ] **TC-062** (U7) Teacher tries create staff → 403

### 3.2 Read & Update Staff

- [ ] **TC-063** (U1) `GET /api/staff/{id}` → full staff record
- [ ] **TC-064** (U1) `PATCH /api/staff/{id}` → staff updated
- [ ] **TC-065** (U7) Teacher patches own staff record → check allowed fields
- [ ] **TC-066** (U7) Teacher patches another staff's record → 403

### 3.3 Delete Staff

- [ ] **TC-067** (U1) `DELETE /api/staff/{id}` → staff deleted
- [ ] **TC-068** (U2) Principal tries delete staff → 403 (owner only)

---

## MODULE 4 — Attendance Recorder

**Tool:** AttendanceRecorder.js | **Primary roles:** U7 (teacher), U2 (principal), U1 (owner)

### 4.1 Student Attendance

- [ ] **TC-069** (U7) `POST /api/attendance/student/bulk` — mark all Class 9A present → 200
- [ ] **TC-070** (U7) Mark same class+date again → check idempotent / update behavior
- [ ] **TC-071** (U2) `GET /api/attendance/student?class_id=X&date=Y` → class attendance for date
- [ ] **TC-072** (U8) `GET /api/attendance/student` → only own attendance returned
- [ ] **TC-073** (U8) Try to GET another student's attendance by ID → 403 or empty
- [ ] **TC-074** (U7) `GET /api/attendance/student/today/{class_id}` → today's records
- [ ] **TC-075** (U2) `GET /api/attendance/low-attendance` → students below 75%
- [ ] **TC-076** (U1) `GET /api/attendance/export` → CSV/Excel export of attendance

### 4.2 Attendance Corrections

- [ ] **TC-077** (U7) `PATCH /api/attendance/{id}/correct` — change Absent → Present → 200
- [ ] **TC-078** (U7) `GET /api/attendance/{id}/history` → correction audit trail visible
- [ ] **TC-079** (U8) Student tries to correct attendance → 403
- [ ] **TC-080** (U7) `DELETE /api/attendance/{id}` → record deleted (if allowed)

### 4.3 Class-Level & Staff Attendance

- [ ] **TC-081** (U2) `GET /api/attendance/class-summary` → per-class present/absent/late counts
- [ ] **TC-082** (U2) `GET /api/attendance/staff/today` → absent staff list for today
- [ ] **TC-083** (U7) `GET /api/attendance/staff/me` → own attendance history
- [ ] **TC-084** (U2) `POST /api/attendance/staff/bulk` → mark multiple staff attendance
- [ ] **TC-085** (U2) `GET /api/attendance/staff` → full staff attendance list
- [ ] **TC-086** (U3) Accountant tries class-summary → 403

### 4.4 Attendance Stream (SSE)

- [ ] **TC-087** (U7) `GET /api/attendance/stream` → SSE connection opens, events flow
- [ ] **TC-088** (Any) SSE connection drops → frontend reconnects (check DevTools Network)

---

## MODULE 5 — Fee Collection

**Tool:** FeeCollection.js | **Primary roles:** U3 (accountant), U1 (owner), U8 (student read-only)

### 5.1 Fee Structures

- [ ] **TC-089** (U1) `GET /api/fees/structures` → fee structure list
- [ ] **TC-090** (U1) `POST /api/fees/structures` → create structure (Tuition, Exam fee, etc.)
- [ ] **TC-091** (U1) `PATCH /api/fees/structures/{id}` → update amount
- [ ] **TC-092** (U3) Accountant tries to create fee structure → 403 (owner only)

### 5.2 Fee Transactions — Record & Read

- [ ] **TC-093** (U3) `POST /api/fees/transactions` — record ₹5000 tuition for ADM20250001 → 200, transaction ID returned
- [ ] **TC-094** (U3) `GET /api/fees/transactions` → all transactions list, schoolId-scoped
- [ ] **TC-095** (U3) `GET /api/fees/transactions?student_id=X` → only that student's transactions
- [ ] **TC-096** (U8) `GET /api/fees/my` → own fee summary with `total_paid`, `outstanding_balance`, `last_payment_date`
- [ ] **TC-097** (U8) `GET /api/fees/my` → `summary` object present in response
- [ ] **TC-098** (U8) Cannot access `GET /api/fees/transactions` (all) → 403
- [ ] **TC-099** (U3) `GET /api/fees/transactions/{id}/receipt` → JSON receipt with student name, amount, date
- [ ] **TC-100** (U3) `GET /api/fees/status/{student_id}` → fee status for one student
- [ ] **TC-101** (U3) `GET /api/fees/class-summary` → per-class collection totals
- [ ] **TC-102** (U1) `GET /api/fees/summary` → school-wide collection summary
- [ ] **TC-103** (U7) Teacher tries `GET /api/fees/transactions` → 403

### 5.3 Fee Corrections & Deletions

- [ ] **TC-104** (U3) `PATCH /api/fees/transactions/{id}/correct` — change amount → 200
- [ ] **TC-105** (U3) `DELETE /api/fees/transactions/{id}` → transaction removed
- [ ] **TC-106** (U8) Student tries to delete transaction → 403

### 5.4 Discounts

- [ ] **TC-107** (U3) `POST /api/fees/discount-types` → create discount category
- [ ] **TC-108** (U3) `GET /api/fees/discount-types` → list discount types
- [ ] **TC-109** (U3) `PATCH /api/fees/discount-types/{id}` → update discount type
- [ ] **TC-110** (U3) `POST /api/fees/discounts/apply` — small discount (<threshold) → applied directly
- [ ] **TC-111** (U3) `POST /api/fees/discounts/apply` — large discount (>threshold) → status = `pending_approval`
- [ ] **TC-112** (U1) `GET /api/fees/discounts/pending-approvals` → pending discount list
- [ ] **TC-113** (U1) `PATCH /api/fees/discounts/pending-approvals/{id}/approve` → discount approved
- [ ] **TC-114** (U1) `PATCH /api/fees/discounts/pending-approvals/{id}/reject` → discount rejected
- [ ] **TC-115** (U3) Accountant tries to approve own discount → 403

### 5.5 Fee Sync

- [ ] **TC-116** (U3) `POST /api/fees/sync/trigger` → sync job started (or returns existing in-progress)
- [ ] **TC-117** (U3) Trigger sync twice → idempotent, returns existing job not duplicate
- [ ] **TC-118** (U3) `GET /api/fees/stream` → SSE fee update stream opens

### 5.6 Contact Log

- [ ] **TC-119** (U3) `POST /api/fees/contact-log` → contact attempt logged for parent follow-up

---

## MODULE 6 — Teacher Tools & Academics

**Tool:** TeacherTools.js, TimetableBuilder.js | **Primary roles:** U7, U9 (teachers), U2 (principal review/publish)

### 6.1 Assignments

- [ ] **TC-120** (U7) `POST /api/academics/assignments` → assignment created for Class 9A
- [ ] **TC-121** (U8) `GET /api/academics/assignments` → only own class's assignments visible
- [ ] **TC-122** (U7) `PATCH /api/academics/assignments/{id}` → update due date
- [ ] **TC-123** (U7) `DELETE /api/academics/assignments/{id}` → assignment deleted
- [ ] **TC-124** (U9) Sunita Devi cannot patch Rajesh Kumar's assignment → 403

### 6.2 Exams

- [ ] **TC-125** (U2) `POST /api/academics/exams` → exam created
- [ ] **TC-126** (U7) `GET /api/academics/exams` → exams for own class visible
- [ ] **TC-127** (U8) `GET /api/academics/exams` → upcoming exams visible to student
- [ ] **TC-128** (U3) Accountant tries to create exam → 403

### 6.3 Results Entry

- [ ] **TC-129** (U7) `POST /api/academics/results/bulk` — enter marks for 5 students → 200
- [ ] **TC-130** (U7) Enter results for student not in own class → check isolation
- [ ] **TC-131** (U8) `GET /api/academics/results` → no results before publish
- [ ] **TC-132** (U2) `PATCH /api/academics/results/{id}/publish` → result published
- [ ] **TC-133** (U8) `GET /api/academics/results` → results now visible after publish
- [ ] **TC-134** (U8) Cannot see another student's results → isolation check
- [ ] **TC-135** (U7) Teacher cannot publish results (only principal/owner) → 403

### 6.4 Lesson Plans

- [ ] **TC-136** (U7) `POST /api/academics/lesson-plans` → plan created, status = `pending_review`
- [ ] **TC-137** (U7) `GET /api/academics/lesson-plans` → own plans visible
- [ ] **TC-138** (U2) `GET /api/academics/lesson-plans` → all plans visible for review
- [ ] **TC-139** (U2) `PATCH /api/academics/lesson-plans/{id}/review` with `approved` → status changes
- [ ] **TC-140** (U2) Reject with comment → status = `rejected`, comment saved
- [ ] **TC-141** (U7) `PATCH /api/academics/lesson-plans/{id}` → update plan
- [ ] **TC-142** (U7) `DELETE /api/academics/lesson-plans/{id}` → plan deleted
- [ ] **TC-143** (U2) `GET /api/academics/lesson-plan-completion?month=YYYY-MM` → per-class completion %

### 6.5 Question Papers (AI-Generated)

- [ ] **TC-144** (U7) `POST /api/academics/question-papers/generate` → AI generates question paper
- [ ] **TC-145** (U7) `GET /api/academics/question-papers` → list of generated papers
- [ ] **TC-146** (U7) `GET /api/academics/question-papers/{id}` → single paper
- [ ] **TC-147** (U7) `PATCH /api/academics/question-papers/{id}` → edit paper
- [ ] **TC-148** (U7) `DELETE /api/academics/question-papers/{id}` → paper deleted
- [ ] **TC-149** (U8) Student tries to generate question paper → 403

---

## MODULE 7 — Principal Daily Ops

**Tool:** PrincipalDailyOps.js | **Primary roles:** U2 (principal), U1 (owner)

- [ ] **TC-150** (U2) View today's class-wise attendance summary → counts per class displayed
- [ ] **TC-151** (U2) View absent staff today → list from `GET /api/attendance/staff/today`
- [ ] **TC-152** (U2) View pending leave requests → `GET /api/staff/leaves/pending`
- [ ] **TC-153** (U2) View lesson plans awaiting review
- [ ] **TC-154** (U2) View unpublished exam results
- [ ] **TC-155** (U3) Accountant opens Daily Ops → 403 or tool not visible in sidebar
- [ ] **TC-156** (U7) Teacher opens Daily Ops → 403 or not visible

---

## MODULE 8 — Staff Leave Management

**Primary roles:** U7/U9 (apply), U2/U1 (approve/reject)

- [ ] **TC-157** (U7) Apply for 2 days casual leave → request created, status = `pending`
- [ ] **TC-158** (U7) `GET /api/staff/leaves/my` → own leave history and balances
- [ ] **TC-159** (U2) `GET /api/staff/leaves/pending` → pending requests from all staff
- [ ] **TC-160** (U2) `PATCH /api/staff/leaves/{id}` approve → status = `approved`, balance deducted
- [ ] **TC-161** (U2) Reject leave with reason → status = `rejected`
- [ ] **TC-162** (U7) After approval: `GET /api/staff/leaves/my` → balance reduced by 2
- [ ] **TC-163** (U3) Accountant tries to approve leave → 403
- [ ] **TC-164** (U7) Teacher tries to approve another teacher's leave → 403
- [ ] **TC-165** (U7) Apply for leave with zero balance → check error response
- [ ] **TC-166** (U1) `GET /api/staff/{id}/leave-requests` → full leave history for any staff

---

## MODULE 9 — Owner Tools & Reports

**Tool:** OwnerTools.js | **Primary roles:** U1 (owner only for most)

- [ ] **TC-167** (U1) `GET /api/reports/attendance-trends?months=3` → chart data for 3 months
- [ ] **TC-168** (U1) `GET /api/reports/attendance-trends?months=13` → clamped to 12
- [ ] **TC-169** (U1) `GET /api/reports/fee-collection-summary?months=1` → this month's collection
- [ ] **TC-170** (U2) Principal tries fee collection summary → 403 (owner only)
- [ ] **TC-171** (U3) Accountant tries fee collection summary → 403
- [ ] **TC-172** (U2) `GET /api/reports/attendance-trends` → principal can access attendance trends
- [ ] **TC-173** (U1) View School Pulse dashboard → student count, staff count, today's attendance %
- [ ] **TC-174** (U1) `GET /api/operator/platform-health` → platform health data
- [ ] **TC-175** (U2) Principal tries platform health → 403

---

## MODULE 10 — Operations: Visitors

**Tool:** OwnerTools / Operations panel | **Primary roles:** U6 (receptionist), U1/U2

- [ ] **TC-176** (U6) `POST /api/ops/visitors` → visitor logged with name, purpose, host
- [ ] **TC-177** (U6) `GET /api/ops/visitors` → all current visitors
- [ ] **TC-178** (U6) `PATCH /api/ops/visitors/{id}/checkout` → checkout_time set, status = checked_out
- [ ] **TC-179** (U6) `GET /api/ops/visitors/pending-checkout?stale_hours=2` → overdue visitors
- [ ] **TC-180** (U7) Teacher tries to log visitor → 403
- [ ] **TC-181** (U8) Student tries to view visitors → 403

---

## MODULE 11 — Operations: Certificates

**Primary roles:** U6 (receptionist), U2/U1 (approve/reject/escalate)

- [ ] **TC-182** (U6) `POST /api/ops/certificates` → certificate request created
- [ ] **TC-183** (U6) `GET /api/ops/certificates` → list all requests with `is_overdue` flag
- [ ] **TC-184** (U2) `PATCH /api/ops/certificates/{id}/approve` → status = approved
- [ ] **TC-185** (U2) `PATCH /api/ops/certificates/{id}/reject` → rejected with reason
- [ ] **TC-186** (U6) `POST /api/ops/certificates/{id}/escalate` → escalated to owner (SLA exceeded)
- [ ] **TC-187** (U7) Teacher tries approve certificate → 403

---

## MODULE 12 — Operations: Incidents & Complaints

**Tool:** IncidentTracker.js | **Primary roles:** U1/U2 (incidents), U5 (maintenance)

### 12.1 Incidents

- [ ] **TC-188** (U1) `POST /api/ops/incidents` → incident created, status = `open`
- [ ] **TC-189** (U1) `GET /api/ops/incidents` → all incidents list
- [ ] **TC-190** (U2) `GET /api/ops/incidents/{id}` → single incident detail
- [ ] **TC-191** (U2) `PATCH /api/ops/incidents/{id}/assign` → assign to maintenance staff
- [ ] **TC-192** (U2) `POST /api/ops/incidents/{id}/thread` → add comment/update
- [ ] **TC-193** (U2) `PATCH /api/ops/incidents/{id}` → update status to `in_progress`
- [ ] **TC-194** (U5) Maintenance views assigned incident
- [ ] **TC-195** (U5) Maintenance updates to `resolved`
- [ ] **TC-196** (U7) Teacher tries to list incidents → 403
- [ ] **TC-197** (U8) Student tries to list incidents → 403

### 12.2 Complaints

- [ ] **TC-198** (U6) `POST /api/ops/complaints` → complaint logged
- [ ] **TC-199** (U2) `GET /api/ops/complaints` → all complaints list
- [ ] **TC-200** (U2) `PATCH /api/ops/complaints/{id}` → update status
- [ ] **TC-201** (U8) Student tries to create complaint → verify response (should 403 or allowed?)

---

## MODULE 13 — Maintenance Tools

**Tool:** MaintenanceTools.js | **Primary roles:** U5 (maintenance), U1/U2

### 13.1 Facility Requests

- [ ] **TC-202** (U7) Teacher `POST /api/issues/facility` → request created (any staff can raise)
- [ ] **TC-203** (U5) `GET /api/issues/facility` → all facility requests visible
- [ ] **TC-204** (U5) `GET /api/issues/facility/{id}` → single request
- [ ] **TC-205** (U5) `PATCH /api/issues/facility/{id}` update status + cost → 200
- [ ] **TC-206** (U5) `GET /api/issues/facility/cost-summary` → costs grouped by category
- [ ] **TC-207** (U5) `POST /api/issues/facility/{id}/escalate` → escalate to owner
- [ ] **TC-208** (U5) `POST /api/issues/facility/{id}/confirm-resolution` → resolution confirmed
- [ ] **TC-209** (U8) Student tries to create facility request → 403

### 13.2 Tech Issues

- [ ] **TC-210** (U7) `POST /api/issues/tech` → tech issue raised
- [ ] **TC-211** (U4) `GET /api/issues/tech` → IT tech sees all tech tickets
- [ ] **TC-212** (U4) `PATCH /api/issues/tech/{id}` → update status to resolved
- [ ] **TC-213** (U3) Accountant tries to view tech issues → check access

### 13.3 Maintenance Schedule & Vendors

- [ ] **TC-214** (U5) `POST /api/issues/maintenance/schedule` → scheduled task created
- [ ] **TC-215** (U5) `GET /api/issues/maintenance/schedule/upcoming?days=7` → next 7 days
- [ ] **TC-216** (U5) `GET /api/issues/maintenance/schedule` → full schedule
- [ ] **TC-217** (U5) `PATCH /api/issues/maintenance/schedule/{id}` → update task
- [ ] **TC-218** (U5) `POST /api/issues/maintenance/vendors` → vendor created
- [ ] **TC-219** (U5) `GET /api/issues/maintenance/vendors` → vendor list
- [ ] **TC-220** (U5) `GET /api/issues/maintenance/vendors/preferred` → preferred vendors
- [ ] **TC-221** (U5) `PATCH /api/issues/maintenance/vendors/{id}` → mark as preferred
- [ ] **TC-222** (U7) Teacher tries to create vendor → 403

---

## MODULE 14 — Query Section (IT Tickets)

**Tool:** QuerySection.js | **Primary roles:** U4 (IT tech)

- [ ] **TC-223** (Any) `POST /api/queries/` → raise a support ticket
- [ ] **TC-224** (U4) `GET /api/queries/` → all tickets visible to IT tech
- [ ] **TC-225** (U4) `PATCH /api/queries/{id}/resolve` → ticket resolved
- [ ] **TC-226** (U4) `PATCH /api/queries/{id}/assign` → ticket assigned to staff
- [ ] **TC-227** (U4) `PATCH /api/queries/{id}/unresolve` → reopen ticket
- [ ] **TC-228** (U4) `DELETE /api/queries/{id}` → ticket deleted
- [ ] **TC-229** (U4) `GET /api/queries/{id}/attachment` → download attachment

---

## MODULE 15 — Announcements (Ops)

**Primary roles:** U2/U1 (approve), all roles (create based on audience)

- [ ] **TC-230** (U2) Create announcement targeting "teachers" → direct to `active` (principal can self-approve)
- [ ] **TC-231** (U7) Create announcement targeting "all students" → status = `pending_approval`
- [ ] **TC-232** (U2) `GET /api/ops/announcements/pending` → pending list visible
- [ ] **TC-233** (U2) `PATCH /api/ops/announcements/{id}/approve` → status = `active`
- [ ] **TC-234** (U2) `PATCH /api/ops/announcements/{id}/reject` with reason → rejected
- [ ] **TC-235** (U8) Student sees approved announcement in feed
- [ ] **TC-236** (U8) Student cannot see pending announcement
- [ ] **TC-237** (U3) Accountant cannot approve announcement → 403

---

## MODULE 16 — Notifications

**Primary roles:** All (own notifications only)

- [ ] **TC-238** (U7) `GET /api/notifications` → own notifications only
- [ ] **TC-239** (U7) `GET /api/notifications/unread-count` → integer count
- [ ] **TC-240** (U7) `PATCH /api/notifications/{id}/read` → notification marked read, count decreases
- [ ] **TC-241** (U7) `PATCH /api/notifications/mark-all-read` → all notifications read
- [ ] **TC-242** (U8) Student sees notification for published result
- [ ] **TC-243** (U7) Teacher sees notification for approved leave
- [ ] **TC-244** (U8) Cannot access another user's notifications → 403

---

## MODULE 17 — Admin Tools (User Management)

**Tool:** AdminTools.js | **Primary roles:** U4 (IT tech), U1 (owner)

- [ ] **TC-245** (U4) View all users list
- [ ] **TC-246** (U4) Filter users by role
- [ ] **TC-247** (U4) `GET /api/settings/token-usage/admin` → per-user AI usage with `users_over_80_pct`
- [ ] **TC-248** (U4) `PUT /api/settings/token-limits/{user_id}` → update token limit
- [ ] **TC-249** (U1) `GET /api/settings/token-usage/aggregate` → school-wide aggregate
- [ ] **TC-250** (U3) Accountant tries token usage admin → 403
- [ ] **TC-251** (U4) `POST /api/settings/branches` — create branch `{branch_name, branch_code}` → 200
- [ ] **TC-252** (U4) Create duplicate branch_code → check unique constraint error
- [ ] **TC-253** (U4) `GET /api/settings/branches` → all branches
- [ ] **TC-254** (U4) `PUT /api/settings/branches/{id}` → update branch

---

## MODULE 18 — Settings

**Tool:** Settings panel | **Primary roles:** U1/U2/U4

- [ ] **TC-255** (U1) `GET /api/settings/school` → school settings
- [ ] **TC-256** (U1) `PATCH /api/settings/school` → update school info
- [ ] **TC-257** (Any) `GET /api/settings/me` → own user settings
- [ ] **TC-258** (Any) `PATCH /api/settings/me` → update own preferences
- [ ] **TC-259** (U2) `GET /api/settings/classes` → classes list
- [ ] **TC-260** (U2) `GET /api/settings/forms` → custom forms list
- [ ] **TC-261** (U2) `POST /api/settings/forms` → create custom form
- [ ] **TC-262** (Any) `POST /api/settings/forms/{id}/responses` → submit form response
- [ ] **TC-263** (U2) `GET /api/settings/forms/{id}/responses` → view responses
- [ ] **TC-264** (U2) `DELETE /api/settings/forms/{id}` → delete form
- [ ] **TC-265** (U1) `POST /api/settings/year-end-transition` → year end rollover

---

## MODULE 19 — AI Chat Interface

**Tool:** ChatInterface (all roles) | **Risk:** Rate limiting, content filter, confirm-action gate

### 19.1 Chat Basics

- [ ] **TC-266** (U7) Send a message → SSE stream opens, `thinking` event received
- [ ] **TC-267** (U7) Ask read question: *"How many students in Class 9A?"* → answer returned
- [ ] **TC-268** (U7) Check `done` event always last → no spinner stuck in UI
- [ ] **TC-269** (U8) Student asks: *"Show me my attendance"* → own data only returned
- [ ] **TC-270** (U8) Student asks: *"Show all students' fees"* → blocked or 403

### 19.2 Write Tools (Confirm Flow)

- [ ] **TC-271** (U7) Ask: *"Mark Class 9A all present today"* → confirm_action card shown
- [ ] **TC-272** (U7) Click **Confirm** → action executes, success message
- [ ] **TC-273** (U7) Click **Cancel** → action aborted, no data written
- [ ] **TC-274** (U3) Accountant: *"Record fee payment of ₹3000 for ADM20250001"* → confirm card shown

### 19.3 Rate Limiting

- [ ] **TC-275** (U7) Send 25+ messages in quick succession → 429 with `retry_after_seconds`
- [ ] **TC-276** (U1) Override rate limit: `PATCH /api/operator/schools/aaryans-joya/ai-rate-limit` body `{role: "teacher", limit: 200, expires_at: "2027-01-01T00:00:00Z"}` → 200
- [ ] **TC-277** (U7) After override → can send messages again

### 19.4 Content Filter (Student)

- [ ] **TC-278** (U8) Ask harmful question in English → blocked, safe response
- [ ] **TC-279** (U8) Ask harmful question in Hindi (Devanagari) → blocked with Hindi response
- [ ] **TC-280** (U7) Teacher asks same harmful question → check if teacher role also filtered

### 19.5 Token Usage

- [ ] **TC-281** (Any) `GET /api/settings/token-usage` → current session usage
- [ ] **TC-282** (Any) `GET /api/settings/token-usage/me` → own cumulative usage
- [ ] **TC-283** (U1) `GET /api/tokens/balance` → school token balance
- [ ] **TC-284** (U1) `GET /api/tokens/usage` → school-level usage
- [ ] **TC-285** (U1) `GET /api/tokens/packs` → available token packs (Stripe)

---

## MODULE 20 — File Upload

**Tool:** FileUpload.js | **Primary roles:** All authenticated

- [ ] **TC-286** (U7) `POST /api/upload` with PDF → 200, file_id and URL returned
- [ ] **TC-287** (U7) Upload file exceeding size limit → 400/422
- [ ] **TC-288** (U7) `GET /api/upload` → list own uploaded files
- [ ] **TC-289** (U7) `GET /api/upload/serve/{filename}` with valid token → file served
- [ ] **TC-290** (Any) `GET /api/upload/serve/{filename}` without token → 401 (hotfix-1)
- [ ] **TC-291** (U7) `GET /api/upload/serve/other_school_file` → 403 or 404 (schoolId isolation)
- [ ] **TC-292** (U7) `DELETE /api/upload/{file_id}` → file deleted

---

## MODULE 21 — Exports

**Primary roles:** U1/U2/U3

- [ ] **TC-293** (U2) `GET /api/exports/students` → student export (CSV/Excel)
- [ ] **TC-294** (U3) `GET /api/exports/fee-transactions` → fee export
- [ ] **TC-295** (U2) `GET /api/exports/attendance` → attendance export
- [ ] **TC-296** (U2) `GET /api/exports/staff` → staff export
- [ ] **TC-297** (U1) `GET /api/exports/expenses` → expenses export
- [ ] **TC-298** (U8) Student tries any export → 403

---

## MODULE 22 — School Activities (Houses & Sports)

**Tool:** SchoolActivities.js | **Primary roles:** U2/U1

- [ ] **TC-299** (U2) `GET /api/activities/houses` → house list with points
- [ ] **TC-300** (U2) `POST /api/activities/houses/{id}/points` → add points to house
- [ ] **TC-301** (U2) `GET /api/activities/houses/{id}/points-log` → points history
- [ ] **TC-302** (U2) `POST /api/activities/teams` → create sports team
- [ ] **TC-303** (U2) `GET /api/activities/teams` → teams list
- [ ] **TC-304** (U2) `PATCH /api/activities/teams/{id}` → update team
- [ ] **TC-305** (U2) `DELETE /api/activities/teams/{id}` → delete team

---

## MODULE 23 — Transport Optimisation

**Tool:** TransportOptimisation.js | **Primary roles:** transport admin, U1

- [ ] **TC-306** (U1) `GET /api/ops/transport` (via operations) → routes list
- [ ] **TC-307** (U1) Create transport route → route saved
- [ ] **TC-308** (U1) `GET /api/ops/vehicles` → vehicle list
- [ ] **TC-309** (U1) Create vehicle → saved
- [ ] **TC-310** (U1) `GET /api/ops/transport/roster` → student-to-route assignment

---

## MODULE 24 — Operator (School Onboarding & Platform)

**Tool:** SchoolOnboarding.js | **Primary roles:** U1 (owner only)

- [ ] **TC-311** (U1) `POST /api/operator/schools` → create/onboard new school
- [ ] **TC-312** (U1) `GET /api/operator/schools/{school_id}/onboarding-status` → onboarding steps
- [ ] **TC-313** (U1) `PATCH /api/operator/schools/{school_id}/deactivate` → school deactivated
- [ ] **TC-314** (U1) `GET /api/operator/ai-action-counts` → AI usage across all schools
- [ ] **TC-315** (U1) `GET /api/operator/platform-health` → platform health status
- [ ] **TC-316** (U2) Principal tries any operator endpoint → 403

---

## MODULE 25 — Payroll

**Tool:** OwnerTools (payroll section) | **Primary roles:** U3 (create), U1 (process)

- [ ] **TC-317** (U1) `POST /api/payroll/structures` → salary structure created
- [ ] **TC-318** (U1) `GET /api/payroll/structures` → all structures
- [ ] **TC-319** (U3) `GET /api/payroll/disbursements` → disbursements list
- [ ] **TC-320** (U3) `POST /api/payroll/disburse` — staff-007, current month → disbursement created
- [ ] **TC-321** (U3) Disburse same staff + month again → check idempotency (409 or existing returned)
- [ ] **TC-322** (U1) `PATCH /api/payroll/disbursements/{id}/process` → status = `processed`
- [ ] **TC-323** (U7) Teacher tries to view payroll → 403

---

## MODULE 26 — SMS / WhatsApp Messaging

**Tool:** via AI chat or direct | **Primary roles:** U2/U1

- [ ] **TC-324** (U2) `POST /api/sms/send-reminder` → reminder sent (or logged if Twilio unconfigured)
- [ ] **TC-325** (U2) `POST /api/sms/send-bulk` → bulk SMS to parent group
- [ ] **TC-326** (U2) `POST /api/sms/send-parent-message` → targeted parent message
- [ ] **TC-327** (U2) `GET /api/sms/logs` → SMS send history
- [ ] **TC-328** (U2) `GET /api/sms/config-status` → Twilio config active/inactive
- [ ] **TC-329** (U2) `GET /api/sms/whatsapp-defaulters` → fee defaulter WhatsApp list
- [ ] **TC-330** (U8) Student tries SMS → 403

---

## MODULE 27 — Health & Audit

- [ ] **TC-331** (Any) `GET /api/health/ready` with DB connected → 200 `{"status": "ok"}`
- [ ] **TC-332** (Any) `GET /api/health/ready` with DB disconnected → 503
- [ ] **TC-333** (U1) `GET /api/audit/logs` → audit log list
- [ ] **TC-334** (U4) `GET /api/audit/logs` → IT tech can view audit log
- [ ] **TC-335** (U8) Student tries audit log → 403

---

## MODULE 28 — Search

- [ ] **TC-336** (U2) `GET /api/search?q=Rahul` → returns matching students + staff
- [ ] **TC-337** (U2) Search with empty query → 422 or empty results
- [ ] **TC-338** (U8) Student searches for other students → results scoped to own visible data

---

## MODULE 29 — Import Data

- [ ] **TC-339** (U2) `POST /api/import/validate` with valid CSV → validation report returned
- [ ] **TC-340** (U2) `POST /api/import/validate` with invalid CSV → errors listed
- [ ] **TC-341** (U2) `POST /api/import/commit` after validation → data imported
- [ ] **TC-342** (U7) Teacher tries import → 403

---

## MODULE 30 — SchoolPulse (Health Dashboard)

**Tool:** SchoolPulse.js | **Primary roles:** U1 (owner)

- [ ] **TC-343** (U1) View School Pulse → all widgets load (student count, attendance %, fee collection)
- [ ] **TC-344** (U1) Fee collection widget shows today's collection
- [ ] **TC-345** (U1) Attendance widget shows current day %
- [ ] **TC-346** (U2) Principal sees a read-only version of school pulse
- [ ] **TC-347** (U7) Teacher dashboard shows own class widgets only

---

## SECURITY MATRIX — Full Role × Endpoint Isolation

For every row: log in as the "should reject" role, call the endpoint, verify the response code.

| TC | Endpoint | Role that should be REJECTED | Expected |
|---|---|---|---|
| S-001 | `GET /api/reports/fee-collection-summary` | U2, U3, U7, U8 | 403 |
| S-002 | `POST /api/fees/structures` | U3, U7, U8 | 403 |
| S-003 | `PATCH /api/staff/leaves/{id}` (approve) | U3, U7, U8 | 403 |
| S-004 | `GET /api/operator/platform-health` | U2, U3, U7, U8 | 403 |
| S-005 | `POST /api/operator/schools` | U2–U9 | 403 |
| S-006 | `PATCH /api/academics/results/{id}/publish` | U7, U8 | 403 |
| S-007 | `GET /api/settings/token-usage/admin` | U3, U7, U8 | 403 |
| S-008 | `POST /api/auth/admin/users/{id}/reset-password` | U7, U8 | 403 |
| S-009 | `DELETE /api/students/{id}` | U3, U7, U8 | 403 |
| S-010 | `GET /api/fees/transactions` (all) | U8 | 403 |
| S-011 | Any endpoint | No token | 401 + `WWW-Authenticate: Bearer` |
| S-012 | `GET /api/students/{other_id}` | U8 (student) | 403 or empty |
| S-013 | `PATCH /api/payroll/disbursements/{id}/process` | U3, U7, U8 | 403 |
| S-014 | `POST /api/settings/year-end-transition` | U2, U3, U7 | 403 |
| S-015 | `POST /api/import/commit` | U7, U8 | 403 |

---

## Execution Tracker

| Module | Total TCs | Passed | Failed | Skipped |
|---|---|---|---|---|
| 1 — Auth | 28 | | | |
| 2 — Students | 27 | | | |
| 3 — Staff | 11 | | | |
| 4 — Attendance | 20 | | | |
| 5 — Fees | 31 | | | |
| 6 — Academics | 30 | | | |
| 7 — Principal Ops | 7 | | | |
| 8 — Leave | 10 | | | |
| 9 — Owner/Reports | 9 | | | |
| 10 — Visitors | 6 | | | |
| 11 — Certificates | 6 | | | |
| 12 — Incidents/Complaints | 14 | | | |
| 13 — Maintenance | 21 | | | |
| 14 — Queries | 7 | | | |
| 15 — Announcements | 8 | | | |
| 16 — Notifications | 7 | | | |
| 17 — Admin Tools | 11 | | | |
| 18 — Settings | 11 | | | |
| 19 — AI Chat | 20 | | | |
| 20 — File Upload | 7 | | | |
| 21 — Exports | 6 | | | |
| 22 — Activities | 7 | | | |
| 23 — Transport | 5 | | | |
| 24 — Operator | 6 | | | |
| 25 — Payroll | 7 | | | |
| 26 — SMS | 7 | | | |
| 27 — Health/Audit | 5 | | | |
| 28 — Search | 3 | | | |
| 29 — Import | 4 | | | |
| 30 — SchoolPulse | 5 | | | |
| SEC — Security Matrix | 15 | | | |
| **TOTAL** | **~347** | | | |

---

## Quality Gates

| Gate | Threshold | Status |
|---|---|---|
| Auth (TC-001 to TC-028) | 100% pass | |
| P0 Security (S-001 to S-015) | 100% pass | |
| Core data flows (TC-069 to TC-116) | 100% pass | |
| AI Chat basics (TC-266 to TC-280) | 100% pass | |
| All remaining | ≥ 90% pass | |

---

*Generated by Master Test Architect (BMAD TEA) — 2026-05-21*
*Use alongside `manual-dataflow-test-plan.md` for complete coverage*
