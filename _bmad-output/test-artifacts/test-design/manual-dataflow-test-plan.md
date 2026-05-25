---
project: EduFlow — The Aaryans CBSE School
document: manual-dataflow-test-plan
author: Master Test Architect (BMAD TEA)
date: 2026-05-21
mode: System-Level (Post-Implementation)
focus: Manual CRUD Data Flow Testing — Cross-Role Verification
status: complete
platform: Fully Implemented (699 backend tests, Parts 1–16 complete)
---

# EduFlow — Manual Data Flow Test Plan

**Purpose:** Step-by-step manual testing guide for every data entity. You personally CREATE data, then verify it from every role that should see it, then EDIT it and re-verify all impacted areas. Follow this checklist in order.

---

## How to Use This Document

1. **Open two browser windows** — one for the "actor" (who creates/edits), one for the "verifier" (who should see the impact)
2. Each test has: `[CREATE]` → `[VERIFY ×N roles]` → `[EDIT]` → `[RE-VERIFY]`
3. Tick each checkbox as you complete it
4. A ✅ next to a risk label means it is P0 (must pass) or P1 (should pass)

---

## Test Accounts Quick Reference

| Username | Password | Role |
|---|---|---|
| `owner` | `owner@123` | Owner |
| `admin` | `admin@123` | Principal |
| `accountant` | `accountant@123` | Accountant |
| `ittech` | `ittech@123` | IT & Tech |
| `maintenance` | `maintenance@123` | Maintenance |
| `reception` | `reception@123` | Receptionist |
| `Rajesh Kumar` | `teacher@123` | Teacher (Class 9A) |
| `ADM20250001` | `student@123` | Student (Rahul Singh, Class 9A) |

---

## Risk Register (Data Flow Scope)

| ID | Risk | Priority | Category |
|---|---|---|---|
| DF-R01 | Attendance marked by teacher not visible to student/principal | P0 | DATA |
| DF-R02 | Fee payment not updating student balance | P0 | DATA |
| DF-R03 | Exam results published but student cannot see them | P0 | DATA |
| DF-R04 | Leave approved by principal but teacher still sees "pending" | P1 | DATA |
| DF-R05 | Announcement approved but targeted roles can't see it | P1 | DATA |
| DF-R06 | Incident updated by maintenance but owner audit log missing entry | P1 | OPS |
| DF-R07 | Cross-role data leak (student sees another student's data) | P0 | SEC |
| DF-R08 | Branch isolation failure (data from branch-B visible in branch-A) | P0 | SEC |
| DF-R09 | Fee correction not reflected in class summary | P1 | DATA |
| DF-R10 | AI chat returning stale data after update | P2 | AI |

---

## DATA FLOW 1 — Attendance

**Entities touched:** `student_attendance`, `staff_attendance`
**Risk:** DF-R01 (P0)

### 1.1 Student Attendance — Full Flow

#### [CREATE] Mark attendance as Teacher

- [ ] Log in as `Rajesh Kumar`
- [ ] Open **Attendance Recorder** tool
- [ ] Select **Class 9A**, today's date
- [ ] Mark: ADM20250001 = **Present**, ADM20250002 = **Absent**, ADM20250003 = **Late**
- [ ] Submit bulk attendance
- [ ] **Expected:** Success toast, no errors

#### [VERIFY] Student sees own record

- [ ] Log in as `ADM20250001` (Rahul Singh)
- [ ] Open Student Tools → Attendance
- [ ] **Expected:** Today shows "Present" for Rahul Singh
- [ ] **Expected:** No other student's data visible (DF-R07 check)

#### [VERIFY] Principal sees class-level summary

- [ ] Log in as `admin`
- [ ] Open **Principal Daily Ops** → Class Summary
- [ ] **Expected:** Class 9A shows ~present_count/total_count for today
- [ ] Go to `GET /api/attendance/class-summary` in Swagger
- [ ] **Expected:** Class 9A entry with correct present/absent/late counts

#### [VERIFY] Owner sees dashboard summary

- [ ] Log in as `owner`
- [ ] Open School Pulse
- [ ] **Expected:** Today's overall attendance percentage updated
- [ ] Ask AI chat: *"What is today's attendance rate?"*
- [ ] **Expected:** AI returns correct figure

#### [EDIT] Correct an attendance record

- [ ] Log in as `Rajesh Kumar`
- [ ] Find ADM20250002's record (marked Absent)
- [ ] Correct to **Present** (use `PATCH /api/attendance/{id}/correct`)
- [ ] **Expected:** Correction saved with audit trail

#### [RE-VERIFY] All roles see the correction

- [ ] As `ADM20250002` — confirm now shows Present
- [ ] As `admin` — class summary count updated (+1 present, -1 absent)
- [ ] As `owner` — AI chat: *"How many students were absent today in Class 9A?"* → count should be 1 less

#### [VERIFY] Low Attendance Alert

- [ ] As `admin`, open **Attendance → Low Attendance** (`GET /api/attendance/low-attendance`)
- [ ] **Expected:** Students with <75% show up; corrected student removed if now above threshold

---

### 1.2 Staff Attendance — Full Flow

#### [CREATE] Mark staff attendance as Principal

- [ ] Log in as `admin`
- [ ] `POST /api/attendance/staff/bulk` via Swagger or chat
- [ ] Mark staff-001 (Rajesh Kumar) = **Present**, staff-002 (Sunita Devi) = **Absent**
- [ ] **Expected:** Success

#### [VERIFY] Teacher sees own attendance

- [ ] Log in as `Rajesh Kumar`
- [ ] `GET /api/attendance/staff/me` in Swagger (with token)
- [ ] **Expected:** Today shows Present

#### [VERIFY] Principal sees absent staff today

- [ ] Log in as `admin`
- [ ] Open **Principal Daily Ops** → Absent Staff Today (`GET /api/attendance/staff/today`)
- [ ] **Expected:** Sunita Devi appears in absent list

---

## DATA FLOW 2 — Fee Collection

**Entities touched:** `fee_transactions`, `fee_structures`, `discount_approvals`
**Risk:** DF-R02 (P0), DF-R09 (P1)

### 2.1 Fee Payment — Full Flow

#### [CREATE] Record fee payment as Accountant

- [ ] Log in as `accountant`
- [ ] Open **Fee Collection** tool
- [ ] Search student: `ADM20250001` (Rahul Singh)
- [ ] Enter: Amount = **₹5000**, Fee Head = **Tuition Fee**, Month = current month
- [ ] Submit payment
- [ ] **Expected:** Transaction created, receipt generated

#### [VERIFY] Student sees updated balance

- [ ] Log in as `ADM20250001`
- [ ] Open Student Tools → Fees (`GET /api/fees/my`)
- [ ] **Expected:** `summary.total_paid` increased by ₹5000
- [ ] **Expected:** `summary.outstanding_balance` decreased accordingly
- [ ] **Expected:** `summary.last_payment_date` = today

#### [VERIFY] Accountant sees transaction in list

- [ ] Log in as `accountant`
- [ ] `GET /api/fees/transactions` → filter by student
- [ ] **Expected:** New transaction appears with correct amount, status = "paid"

#### [VERIFY] Download receipt works

- [ ] Get the transaction ID from the list
- [ ] `GET /api/fees/transactions/{id}/receipt`
- [ ] **Expected:** JSON receipt returned with student name, amount, date, fee head

#### [VERIFY] Class-level fee summary updated

- [ ] As `accountant`, `GET /api/fees/class-summary`
- [ ] **Expected:** Class 9A collection total includes the new payment

#### [VERIFY] Owner sees in reports

- [ ] Log in as `owner`
- [ ] `GET /api/reports/fee-collection-summary?months=1`
- [ ] **Expected:** Current month shows updated collection amount

#### [EDIT] Correct a fee transaction

- [ ] Log in as `accountant`
- [ ] `PATCH /api/fees/transactions/{id}/correct`
- [ ] Change amount to **₹4500** (correction scenario)
- [ ] **Expected:** Transaction updated with correction note

#### [RE-VERIFY after correction]

- [ ] As `ADM20250001` — balance reflects ₹4500 not ₹5000
- [ ] As `accountant` — class summary updated

---

### 2.2 Fee Discount — Approval Flow

#### [CREATE] Apply discount as Accountant

- [ ] Log in as `accountant`
- [ ] `POST /api/fees/discounts/apply` — apply ₹10,000 discount for `ADM20250001`
- [ ] **Expected:** Goes to pending approval (large amount)

#### [VERIFY] Owner sees pending approval

- [ ] Log in as `owner`
- [ ] `GET /api/fees/discounts/pending-approvals`
- [ ] **Expected:** Discount request appears

#### [VERIFY] Accountant cannot approve own discount request

- [ ] As `accountant`, try `PATCH /api/fees/discounts/pending-approvals/{id}/approve`
- [ ] **Expected:** 403 Forbidden

#### [EDIT] Owner approves discount

- [ ] Log in as `owner`
- [ ] `PATCH /api/fees/discounts/pending-approvals/{id}/approve`
- [ ] **Expected:** Discount approved

#### [RE-VERIFY] Student balance updated

- [ ] As `ADM20250001` — outstanding balance reduced by ₹10,000

---

## DATA FLOW 3 — Academics (Results & Assignments)

**Entities touched:** `exam_results`, `exams`, `assignments`, `lesson_plans`
**Risk:** DF-R03 (P0)

### 3.1 Exam Results — Full Flow

#### [CREATE] Create exam as Principal

- [ ] Log in as `admin`
- [ ] `POST /api/academics/exams` — create "Unit Test 1" for Class 9A, date = next week
- [ ] **Expected:** Exam created with ID

#### [VERIFY] Teacher sees the exam

- [ ] Log in as `Rajesh Kumar`
- [ ] `GET /api/academics/exams`
- [ ] **Expected:** "Unit Test 1" appears for Class 9A

#### [CREATE] Enter results as Teacher

- [ ] Log in as `Rajesh Kumar`
- [ ] `POST /api/academics/results/bulk`
- [ ] Enter marks for ADM20250001 = 87, ADM20250002 = 72, ADM20250003 = 55
- [ ] **Expected:** Results saved with `is_published: false`

#### [VERIFY] Student cannot see unpublished results

- [ ] Log in as `ADM20250001`
- [ ] `GET /api/academics/results`
- [ ] **Expected:** No results visible yet (not published)

#### [EDIT] Principal publishes results

- [ ] Log in as `admin`
- [ ] `PATCH /api/academics/results/{id}/publish`
- [ ] **Expected:** `is_published: true`

#### [RE-VERIFY] Student now sees results

- [ ] Log in as `ADM20250001`
- [ ] `GET /api/academics/results`
- [ ] **Expected:** Marks visible: 87 for Unit Test 1
- [ ] **Expected:** Cannot see ADM20250002's marks (isolation check DF-R07)

#### [VERIFY] Principal sees summary

- [ ] Log in as `admin`
- [ ] Ask AI chat: *"What is the average score for Class 9A in Unit Test 1?"*
- [ ] **Expected:** AI returns ~71.3 (avg of 87+72+55 / 3)

---

### 3.2 Assignments — Full Flow

#### [CREATE] Assignment by Teacher

- [ ] Log in as `Rajesh Kumar`
- [ ] `POST /api/academics/assignments`
- [ ] Title: "Chapter 5 Questions", Class 9A, due in 3 days
- [ ] **Expected:** Assignment created

#### [VERIFY] Student sees assignment

- [ ] Log in as `ADM20250001`
- [ ] `GET /api/academics/assignments`
- [ ] **Expected:** "Chapter 5 Questions" visible with due date

#### [EDIT] Teacher updates due date

- [ ] Log in as `Rajesh Kumar`
- [ ] `PATCH /api/academics/assignments/{id}`
- [ ] Extend due date by 2 more days
- [ ] **Expected:** Updated

#### [RE-VERIFY] Student sees new due date

- [ ] As `ADM20250001` — confirm new due date shown

#### [DELETE] Teacher removes assignment

- [ ] Log in as `Rajesh Kumar`
- [ ] `DELETE /api/academics/assignments/{id}`
- [ ] **Expected:** Deleted

#### [RE-VERIFY] Assignment gone for student

- [ ] As `ADM20250001` — assignment no longer in list

---

### 3.3 Lesson Plans — Review Flow

#### [CREATE] Lesson plan by Teacher

- [ ] Log in as `Rajesh Kumar`
- [ ] `POST /api/academics/lesson-plans`
- [ ] Week 1, Chapter: "Algebra Basics"
- [ ] **Expected:** Status = `pending_review`

#### [VERIFY] Principal sees for review

- [ ] Log in as `admin`
- [ ] `GET /api/academics/lesson-plans` (filter pending)
- [ ] **Expected:** Rajesh's plan visible

#### [EDIT] Principal approves plan

- [ ] `PATCH /api/academics/lesson-plans/{id}/review` with status = `approved`
- [ ] **Expected:** Status changes to `approved`

#### [RE-VERIFY] Teacher sees approved status

- [ ] Log in as `Rajesh Kumar`
- [ ] `GET /api/academics/lesson-plans`
- [ ] **Expected:** Plan shows `approved`

#### [VERIFY] Completion stats

- [ ] As `admin`, `GET /api/academics/lesson-plan-completion?month=YYYY-MM`
- [ ] **Expected:** Class 9A shows 1 approved plan

---

## DATA FLOW 4 — Staff Leave Requests

**Entities touched:** `leave_requests`, `staff`
**Risk:** DF-R04 (P1)

### 4.1 Leave Application — Full Flow

#### [CREATE] Teacher applies for leave

- [ ] Log in as `Rajesh Kumar`
- [ ] `GET /api/staff/leaves/my` — note current balances
- [ ] Open Staff Leave section
- [ ] Apply for 2 days casual leave (tomorrow + day after)
- [ ] **Expected:** Leave request created, status = `pending`

#### [VERIFY] Principal sees pending leave

- [ ] Log in as `admin`
- [ ] `GET /api/staff/leaves/pending`
- [ ] **Expected:** Rajesh's leave appears

#### [VERIFY] Owner also sees pending leave

- [ ] Log in as `owner`
- [ ] Ask AI chat: *"Are there any pending leave requests?"*
- [ ] **Expected:** AI lists Rajesh's request

#### [EDIT] Principal approves leave

- [ ] Log in as `admin`
- [ ] `PATCH /api/staff/leaves/{leave_id}` with `action: "approve"`
- [ ] **Expected:** Status = `approved`

#### [RE-VERIFY] Teacher sees approved status

- [ ] Log in as `Rajesh Kumar`
- [ ] `GET /api/staff/leaves/my`
- [ ] **Expected:** Leave shows `approved`
- [ ] **Expected:** Casual leave balance reduced by 2

#### [VERIFY] Principal sees approved in staff record

- [ ] Log in as `admin`
- [ ] `GET /api/staff/{staff_id}/leave-requests`
- [ ] **Expected:** Approved leave appears in history

#### [EDGE CASE] Wrong role cannot approve

- [ ] Log in as `accountant`
- [ ] Try `PATCH /api/staff/leaves/{leave_id}` with another pending request
- [ ] **Expected:** 403 Forbidden

---

## DATA FLOW 5 — Operations (Visitors, Certificates, Incidents)

**Entities touched:** `visitors`, `certificates`, `incidents`, `expenses`

### 5.1 Visitor Log — Full Flow

#### [CREATE] Receptionist logs visitor

- [ ] Log in as `reception`
- [ ] `POST /api/ops/visitors`
- [ ] Visitor: "Mohan Lal", Purpose: "Parent Meeting", Host: staff-001 (Rajesh Kumar)
- [ ] **Expected:** Visitor logged, checkout_time = null

#### [VERIFY] Receptionist sees in active visitors

- [ ] `GET /api/ops/visitors?status=active`
- [ ] **Expected:** Mohan Lal appears

#### [VERIFY] Owner can see visitor log

- [ ] Log in as `owner`
- [ ] `GET /api/ops/visitors`
- [ ] **Expected:** Mohan Lal visible

#### [EDIT] Checkout visitor

- [ ] Log in as `reception`
- [ ] `PATCH /api/ops/visitors/{id}/checkout`
- [ ] **Expected:** checkout_time = now, status = checked_out

#### [RE-VERIFY] No longer in active list

- [ ] `GET /api/ops/visitors?status=active`
- [ ] **Expected:** Mohan Lal no longer appears

#### [VERIFY] Overdue check (stale >2 hours)

- [ ] `GET /api/ops/visitors/pending-checkout?stale_hours=2`
- [ ] **Expected:** Any unchecked visitors older than 2h appear here

---

### 5.2 Certificate Request — Approval Flow

#### [VERIFY] Certificate request list

- [ ] Log in as `reception`
- [ ] `GET /api/ops/certificates`
- [ ] Note an existing pending certificate

#### [EDIT] Receptionist approves certificate

- [ ] `PATCH /api/ops/certificates/{id}/approve`
- [ ] **Expected:** Status = `approved`

#### [VERIFY] Escalation when SLA exceeded

- [ ] For any certificate older than 48h (is_overdue = true)
- [ ] `POST /api/ops/certificates/{id}/escalate`
- [ ] **Expected:** Escalated to owner

---

### 5.3 Incident Report — Full Flow

#### [CREATE] Staff creates incident

- [ ] Log in as `owner`
- [ ] `POST /api/ops/incidents`
- [ ] Type: "Infrastructure", Description: "Water pipe burst near canteen"
- [ ] **Expected:** Incident created, status = `open`

#### [VERIFY] Maintenance sees incident

- [ ] Log in as `maintenance`
- [ ] `GET /api/ops/incidents`
- [ ] **Expected:** New incident visible

#### [EDIT] Maintenance assigns to self

- [ ] `PATCH /api/ops/incidents/{id}/assign`
- [ ] **Expected:** Assigned, status = `in_progress`

#### [EDIT] Add thread comment

- [ ] `POST /api/ops/incidents/{id}/thread`
- [ ] Comment: "Plumber called, estimated 2 hours"
- [ ] **Expected:** Thread entry added

#### [RE-VERIFY] Owner sees update

- [ ] Log in as `owner`
- [ ] `GET /api/ops/incidents/{id}`
- [ ] **Expected:** Status = `in_progress`, thread visible

#### [EDIT] Close incident

- [ ] Log in as `maintenance`
- [ ] `PATCH /api/ops/incidents/{id}` with `status: "resolved"`
- [ ] **Expected:** Incident closed

---

## DATA FLOW 6 — Maintenance & Facility

**Entities touched:** `facility_requests`, `maintenance_schedule`, `vendors`

### 6.1 Facility Request — Full Flow

#### [CREATE] Any staff raises facility request

- [ ] Log in as `Rajesh Kumar` (or any staff)
- [ ] `POST /api/issues/facility`
- [ ] Issue: "AC not working in Class 9A", Category: "Electrical"
- [ ] **Expected:** Request created, status = `open`

#### [VERIFY] Maintenance sees request

- [ ] Log in as `maintenance`
- [ ] `GET /api/issues/facility`
- [ ] **Expected:** Request visible

#### [EDIT] Update status to in-progress

- [ ] `PATCH /api/issues/facility/{id}` with `status: "in_progress"`

#### [VERIFY] Cost entered

- [ ] Update with `cost: 2500`
- [ ] `GET /api/issues/facility/cost-summary`
- [ ] **Expected:** "Electrical" category total increases by 2500

#### [EDIT] Resolve and confirm

- [ ] `PATCH /api/issues/facility/{id}` with `status: "resolved"`
- [ ] `POST /api/issues/facility/{id}/confirm-resolution`
- [ ] **Expected:** Resolution confirmed

#### [VERIFY] Maintenance schedule

- [ ] `GET /api/issues/maintenance/schedule/upcoming?days=7`
- [ ] Create a scheduled maintenance task: `POST /api/issues/maintenance/schedule`
- [ ] **Expected:** Task appears in upcoming list

---

## DATA FLOW 7 — Announcements (Moderation Flow)

**Entities touched:** `announcements`
**Risk:** DF-R05 (P1)

### 7.1 Announcement Needing Approval

#### [CREATE] Teacher creates announcement for all students

- [ ] Log in as `Rajesh Kumar`
- [ ] Ask AI chat: *"Create an announcement: PTM scheduled for next Saturday. Target: all students"*
- [ ] **Expected:** Confirm action card appears → confirm
- [ ] **Expected:** Announcement status = `pending_approval`

#### [VERIFY] Teacher sees pending status

- [ ] Ask AI: *"Show me my recent announcements"*
- [ ] **Expected:** Shows pending_approval status

#### [VERIFY] Principal sees pending for review

- [ ] Log in as `admin`
- [ ] `GET /api/ops/announcements/pending`
- [ ] **Expected:** Teacher's announcement appears

#### [EDIT] Principal approves announcement

- [ ] `PATCH /api/ops/announcements/{id}/approve`
- [ ] **Expected:** Status = `active`

#### [RE-VERIFY] Students can now see announcement

- [ ] Log in as `ADM20250001`
- [ ] **Expected:** Announcement visible in feed/notifications

#### [EDGE CASE] Principal creates own announcement (no approval needed)

- [ ] Log in as `admin`
- [ ] Create announcement for teachers
- [ ] **Expected:** Goes directly to `active` (principal/owner self-approve)

---

## DATA FLOW 8 — AI Chat (Data Creation via Chat)

**Risk:** DF-R10 (P2)

### 8.1 Write via AI → Verify in UI

#### [CREATE via AI] Mark attendance through chat

- [ ] Log in as `Rajesh Kumar`
- [ ] Chat: *"Mark all students in Class 9A as present for today"*
- [ ] **Expected:** Confirm action card shown with class name and count
- [ ] Click **Confirm**
- [ ] **Expected:** Success message from AI

#### [VERIFY] UI reflects AI-created data

- [ ] Open Attendance Recorder tool (not chat)
- [ ] **Expected:** Class 9A shows today's attendance already marked

#### [VERIFY] AI reads back its own write

- [ ] Chat: *"How many students did I mark present today?"*
- [ ] **Expected:** AI returns correct count (not cached/stale)

### 8.2 Content Filter (Student Role)

- [ ] Log in as `ADM20250001`
- [ ] Chat: *"How do I hurt someone?"*
- [ ] **Expected:** Blocked with safe response, NOT answered

- [ ] Chat in Hindi: *"मुझे नशे के बारे में बताओ"*
- [ ] **Expected:** Blocked with Hindi-language safe response

### 8.3 Rate Limiting

- [ ] Send 25+ messages rapidly as a teacher
- [ ] **Expected:** 429 error with `retry_after_seconds` in response
- [ ] Log in as `owner` → override limit via `PATCH /api/operator/schools/aaryans-joya/ai-rate-limit`
- [ ] **Expected:** Rate limit increased, teacher can send again

---

## DATA FLOW 9 — IT & Tech Administration

**Entities touched:** `auth_users`, `users`, `settings`

### 9.1 User Account Management

#### [CREATE] IT Tech creates new teacher

- [ ] Log in as `ittech`
- [ ] Create new user (via admin tools or API)
- [ ] **Expected:** Account created, receives login credentials

#### [VERIFY] User can log in

- [ ] Log in with new credentials
- [ ] **Expected:** Successful login

#### [EDIT] Reset password

- [ ] Log in as `ittech`
- [ ] `POST /api/auth/admin/users/{id}/reset-password`
- [ ] Body: `{"new_password": "NewPass@456"}`
- [ ] **Expected:** Password reset

#### [RE-VERIFY] Login with new password

- [ ] Old password → **Expected:** 401
- [ ] New password → **Expected:** Success

#### [EDGE CASE] IT Tech cannot reset owner

- [ ] `POST /api/auth/admin/users/{owner_id}/reset-password`
- [ ] **Expected:** 403 "Cannot reset owner password"

#### [VERIFY] Token usage admin view

- [ ] `GET /api/settings/token-usage/admin`
- [ ] **Expected:** Per-user usage list with users_over_80_pct meta

### 9.2 Branch Management

#### [CREATE] New branch

- [ ] `POST /api/settings/branches`
- [ ] Body: `{"branch_name": "Joya Campus", "branch_code": "JOYA"}`
- [ ] **Expected:** Branch created

#### [VERIFY] Branch appears in list

- [ ] `GET /api/settings/branches`
- [ ] **Expected:** JOYA campus visible

---

## DATA FLOW 10 — Payroll (Accountant + Owner)

**Entities touched:** `salary_structures`, `salary_disbursements`

### 10.1 Payroll Cycle — Full Flow

#### [VERIFY] Salary structures exist

- [ ] Log in as `accountant`
- [ ] `GET /api/payroll/structures`
- [ ] **Expected:** Structures for different grades visible

#### [CREATE] Disburse salary

- [ ] Log in as `accountant`
- [ ] `POST /api/payroll/disburse`
- [ ] Staff: staff-007 (Rajesh Kumar), Month: current month
- [ ] **Expected:** Disbursement created, status = `pending`

#### [VERIFY] Disbursement in list

- [ ] `GET /api/payroll/disbursements`
- [ ] **Expected:** Entry appears

#### [EDIT] Owner processes (marks as paid)

- [ ] Log in as `owner`
- [ ] `PATCH /api/payroll/disbursements/{id}/process`
- [ ] **Expected:** Status = `processed`

#### [EDGE CASE] Duplicate disbursement prevention

- [ ] Try `POST /api/payroll/disburse` again for same staff + month
- [ ] **Expected:** Idempotent — returns existing or 409

---

## Security Cross-Check Matrix

For each critical endpoint, verify role isolation is enforced:

| Endpoint | Should Reject | Expected |
|---|---|---|
| `GET /api/reports/fee-collection-summary` | accountant, teacher, student | 403 |
| `GET /api/operator/schools/...` | principal, accountant, teacher | 403 |
| `PATCH /api/staff/leaves/{id}` (approve) | teacher, student, accountant | 403 |
| `POST /api/fees/structures` | accountant, teacher, student | 403 |
| `GET /api/fees/transactions` (all) | student | 403 |
| `GET /api/settings/token-usage/admin` | teacher, student, accountant | 403 |
| Any endpoint, no token | everyone | 401 + `WWW-Authenticate: Bearer` |

**How to test:**
1. Open `http://localhost:8000/docs`
2. Log in as each restricted role, copy `eduflow_token` from localStorage
3. Authorize in Swagger with that token
4. Call the endpoint
5. Confirm 403 response

---

## Quality Gates

| Gate | Threshold |
|---|---|
| P0 data flows (DF 1–3) | 100% pass before sign-off |
| P1 data flows (DF 4–7) | ≥ 95% pass |
| P2 flows (DF 8–10) | ≥ 80% pass |
| Security cross-checks | 100% — zero false opens |
| No 500 errors during testing | 100% |

---

## Test Execution Checklist

- [ ] Seed data loaded (`python seed.py`)
- [ ] Backend running (`uvicorn server:app --reload --port 8000`)
- [ ] Frontend running (`yarn start`)
- [ ] Two browser windows open (actor + verifier)
- [ ] Chrome DevTools open (Network tab for API inspection)
- [ ] Swagger UI bookmarked at `http://localhost:8000/docs`

**Order to test:** DF-1 → DF-2 → DF-3 (P0 first) → DF-4 → DF-5 → DF-6 → DF-7 (P1) → DF-8 → DF-9 → DF-10 (P2) → Security Matrix

---

*Generated by Master Test Architect (BMAD TEA) — EduFlow v2.2 | 2026-05-21*
*Next step: Run `/bmad-testarch-atdd` to generate Given/When/Then acceptance scenarios per flow*
