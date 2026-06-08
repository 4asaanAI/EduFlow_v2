# EduFlow — Complete Manual Testing Guide

> **Date:** 2026-05-21 | **Stack:** React 19 SPA + FastAPI + MongoDB Atlas

---

## 1. Setup — Start the App

### Step 1 — Start the Backend
```bash
cd backend
uvicorn server:app --reload --port 8000
```
Confirm: `http://localhost:8000/docs` opens FastAPI Swagger UI

### Step 2 — Start the Frontend
```bash
cd frontend
yarn start
```
Confirm: `http://localhost:3000` opens the EduFlow login screen

### Step 3 — Seed the Database (first time only)
```bash
cd backend
python seed.py
```
This creates all demo users, classes, students, staff, fee structures.

---

## 2. Test Accounts (All Roles)

| Username | Password | Role | Sub-Category |
|---|---|---|---|
| `owner` | `owner@123` | owner | — |
| `admin` | `admin@123` | admin | principal |
| `accountant` | `accountant@123` | admin | accountant |
| `transport` | `transport@123` | admin | transport_head |
| `reception` | `reception@123` | admin | receptionist |
| `ittech` | `ittech@123` | admin | it_tech |
| `maintenance` | `maintenance@123` | admin | maintenance |
| `Rajesh Kumar` | `teacher@123` | teacher | class_teacher |
| `Sunita Devi` | `teacher@123` | teacher | class_teacher |
| `Vikash Singh` | `hod@123` | teacher | hod |
| `ADM20250001` | `student@123` | student | — |
| `ADM20250002` | `student@123` | student | — |

---

## 3. Tools You Need

| Tool | Purpose | Where |
|---|---|---|
| **Browser (Chrome)** | Test the full UI | `http://localhost:3000` |
| **FastAPI Swagger** | Test individual API endpoints with auth | `http://localhost:8000/docs` |
| **Bruno** (recommended) or **Postman** | Save & replay API requests | Download: usebruno.com |
| **MongoDB Compass** | View/verify DB state directly | Download: mongodb.com/compass |
| **Chrome DevTools → Network** | Inspect SSE/API calls in real time | F12 → Network tab |

---

## 4. Testing Flows — Each Role

---

### 4.1 Authentication (All Roles)

**A. Login**
1. Go to `http://localhost:3000`
2. Enter username/password from table above
3. Confirm redirect to dashboard with correct role
4. Open DevTools → Application → Local Storage → verify `eduflow_token` is set

**B. Wrong password / lockout**
1. Enter correct username, wrong password 5 times
2. Expect: account locked message on 5th attempt
3. Log in as `ittech` → unlock the user via IT tools

**C. Change password**
1. Log in as any user
2. Go to Profile / Settings
3. Change password, re-login with new password

**D. Logout**
1. Click logout
2. Verify redirect to login screen
3. Verify back-button doesn't restore session

---

### 4.2 Owner Role

Login: `owner` / `owner@123`

**School Dashboard**
1. Check School Pulse widget — student count, staff count, fee collection summary
2. Open the AI chat box at the bottom — ask: *"Show me today's attendance summary"*
3. Ask: *"How many students are in Class 10?"*

**Owner Tools Panel**
1. Open Owner Tools from sidebar
2. View fee collection summary
3. View pending discount approvals
4. Approve or reject one discount

**Announcements**
1. Create an announcement targeted to "all" (requires approval since owner = auto-approve)
2. Verify it appears for other roles

**Reports**
1. Open Reports → Attendance Trends (1 month)
2. Open Reports → Fee Collection Summary (3 months)
3. Verify charts render

**Operator: Rate Limit Override**
1. Via Swagger: `PATCH /api/operator/schools/aaryans-joya/ai-rate-limit`
   - Body: `{"role": "teacher", "limit": 100, "expires_at": "2027-01-01T00:00:00Z"}`
2. Verify teacher AI chat has new limit

---

### 4.3 Principal Role

Login: `admin` / `admin@123`

**Daily Ops Panel**
1. Open Principal Daily Ops from sidebar
2. Check today's class-wise attendance summary
3. Check absent staff list for today

**Attendance**
1. Open Attendance Recorder
2. Record bulk attendance for a class
3. Verify low-attendance alert shows student with <75%

**Academics**
1. Open assignments list — create a new assignment for Class 9
2. Create an exam for Class 10
3. Bulk-enter results for 5 students
4. Publish exam results → verify students can see them

**Leave Approval**
1. As a teacher (in another browser tab), apply for leave
2. Back as principal: open pending leaves → approve one, reject another
3. Verify teacher sees updated leave status

**Announcements**
1. Create announcement for teachers — check it shows pending approval
2. Log in as `owner` → approve the announcement
3. Log back in as teacher → verify announcement is visible

**Lesson Plan Review**
1. Open lesson plans list
2. Review a pending plan (approve/reject with comment)

---

### 4.4 Accountant Role

Login: `accountant` / `accountant@123`

**Fee Collection**
1. Open Fee Collection tool
2. Search for student "Rahul Singh" (ADM20250001)
3. Record a fee payment (enter amount, select fee head, add receipt)
4. Download receipt — verify `GET /api/fees/transactions/{id}/receipt` works

**Fee Structures**
1. View current fee structures
2. Note: only Owner can create/edit fee structures

**Apply Discount**
1. Search a student
2. Apply a discount (large amount) → should go to pending approval
3. Log in as `owner` → approve the discount

**Payroll**
1. Open payroll section
2. View salary structures
3. Disburse salary for a staff member for current month
4. Process (mark as paid) the disbursement

**Fee Summary / Class Summary**
1. View `GET /api/fees/class-summary` — fee collection per class
2. View `GET /api/fees/summary` — overall collection stats

---

### 4.5 IT & Tech Role

Login: `ittech` / `ittech@123`

**User Management**
1. View all users in Admin Tools
2. Reset password for a teacher (not owner)
3. Attempt to reset owner's password → expect 403
4. Unlock a locked-out account

**Token Usage**
1. Open token usage admin view
2. Check which users are over 80% of their limit
3. Update a user's token limit

**Branch Management**
1. Create a new branch: `POST /api/settings/branches`
   - Body: `{"branch_name": "Joya Campus", "branch_code": "JOYA"}`
2. Verify it appears in branches list

**Tech Issue Tickets**
1. Raise a tech issue (as any user via chat: *"raise a tech issue: projector not working in Class 10A"*)
2. Log in as ittech → resolve the ticket

---

### 4.6 Maintenance Role

Login: `maintenance` / `maintenance@123`

**Facility Requests**
1. Open Maintenance Tools
2. View all open facility requests
3. Update one request status to "in_progress"
4. Mark another as "resolved"
5. Confirm resolution on a resolved request

**Maintenance Schedule**
1. View upcoming schedule (next 7 days)
2. Create a new maintenance task
3. Update an existing task

**Vendors**
1. View vendor list
2. Add a new vendor
3. Mark a vendor as preferred

**Cost Summary**
1. View `GET /api/issues/facility/cost-summary`
2. Verify costs are grouped by category

---

### 4.7 Receptionist Role

Login: `reception` / `reception@123`

**Visitor Log**
1. Open Operations → Visitors
2. Log a new visitor (name, purpose, host teacher)
3. Check them out (checkout time)
4. View overdue checkouts (stale > 2 hours)

**Certificates**
1. View certificate requests
2. Approve a certificate request
3. If overdue (>48h), escalate to owner
4. Reject one with a reason

**Complaints**
1. Log a new complaint
2. Update complaint status
3. View all complaints list

---

### 4.8 Teacher Role

Login: `Rajesh Kumar` / `teacher@123`

**Teacher Tools**
1. Open Teacher Tools panel
2. View your assigned classes

**Attendance**
1. Mark today's attendance for your class (bulk attendance)
2. Check your own attendance record (`GET /api/attendance/staff/me`)

**Assignments**
1. Create a new assignment for your class
2. Edit it
3. Delete it

**Lesson Plans**
1. Create a lesson plan for this week
2. View review status (pending/approved/rejected)

**Results**
1. Enter bulk exam results for your class
2. Note: only principal/owner can publish results

**Leave Application**
1. Apply for 2 days casual leave
2. Check leave balance
3. View leave history

**AI Chat (Teacher-specific)**
1. Open chat: ask *"Show me Class 9A's attendance for this week"*
2. Ask: *"Who has low attendance in my class?"*
3. Ask: *"Draft a WhatsApp message to parents about tomorrow's exam"*
4. Try a write action: *"Mark Class 9A attendance for today"* → confirm the action card

---

### 4.9 Student Role

Login: `ADM20250001` / `student@123`

**Student Portal**
1. Open Student Tools
2. View my profile
3. View my fee status (total paid, outstanding balance)
4. Download fee receipt

**Academics**
1. View assignments for my class
2. View exam schedule
3. View published results

**Attendance**
1. View my own attendance history

**AI Chat (Student)**
1. Ask: *"Show me my attendance for this month"*
2. Ask: *"When is my next exam?"*
3. Ask: *"What are my due fees?"*
4. Try asking something inappropriate — verify content filter blocks it
5. Try Devanagari: *"मेरी fees कितनी है?"* — verify Hindi response works

**Consent**
1. Check `GET /api/students/me/consent`
2. Post consent: `POST /api/students/me/consent`

---

### 4.10 Transport Head Role

Login: `transport` / `transport@123`

**Transport Optimisation**
1. Open Transport Optimisation tool
2. View route list
3. View vehicle assignments
4. Check transport tool via AI chat: *"Show me route details"*

---

## 5. AI Chat — End-to-End Test Flows

> Chat box is always visible at bottom of screen (pinned). Works for all roles.

### 5.1 Read Tools (no confirmation required)
| What to ask | Expected |
|---|---|
| "How many students are absent today?" | Count + class breakdown |
| "Show me fee defaulters" | List of students with overdue fees |
| "Who has less than 75% attendance?" | Low attendance list |
| "Show me pending leave requests" | Leave list (principal/owner) |
| "What's the upcoming exam schedule?" | Events list |
| "Show me Class 9A timetable" | Period-by-period schedule |

### 5.2 Write Tools (confirmation card required)
| What to ask | Confirm card expected |
|---|---|
| "Mark attendance for Class 9A — all present" | Yes → confirm → attendance marked |
| "Record fee payment of ₹5000 for ADM20250001" | Yes → confirm |
| "Create an announcement: School closed tomorrow" | Yes → confirm |

**Confirm flow:**
1. AI shows a confirm action card with details
2. Click "Confirm" → action executes
3. Click "Cancel" → action aborted

### 5.3 Rate Limiting
1. Send 20+ AI messages rapidly as a teacher
2. Expect `429 rate_limit_exceeded` with `retry_after_seconds` shown
3. Wait for the hour to reset OR owner overrides the limit

### 5.4 SSE Streaming
1. Open DevTools → Network → filter by `EventStream`
2. Send a chat message
3. Watch events: `thinking` → `text_delta` → `done`
4. Verify no spinner stuck after `done` event

---

## 6. File Upload Flow

1. Log in as any staff role
2. Go to File Upload tool
3. Upload a PDF or image
4. Verify upload succeeds (file stored in S3 or local)
5. Download/view the uploaded file via the serve endpoint
6. Test unauthenticated access to file → must return 401 (not serve the file)

---

## 7. Search

1. Log in as owner or principal
2. Use global search: type "Rahul" → should return students, staff
3. Search for a class name
4. Verify results are scoped to current school

---

## 8. Notifications

1. Trigger an action that creates a notification (fee payment, attendance marked)
2. Check notification bell icon — unread count should increase
3. Open notifications list — verify body/title are correct
4. Mark as read

---

## 9. Audit Log

1. Log in as `owner` or `ittech`
2. Open Audit Log tool
3. Verify actions like login, fee payment, attendance are logged
4. Filter by user or action type

---

## 10. School Onboarding (Owner Only)

1. Log in as `owner`
2. Open School Onboarding tool
3. Step through: school info → branches → academic year → classes
4. Verify settings saved (`GET /api/settings/school`)

---

## 11. Health Check

```bash
curl http://localhost:8000/api/health/ready
```
- Should return `200 OK` with `{"status": "ok"}` when DB connected
- Returns `503` when DB is down

---

## 12. Security Spot-Checks

| Test | Expected |
|---|---|
| API call without token | `401 Unauthorized` + `WWW-Authenticate: Bearer` header |
| Student tries to access `GET /api/fees/transactions` (accountant only) | `403 Forbidden` |
| Accountant tries to access `GET /api/reports/fee-collection-summary` (owner only) | `403 Forbidden` |
| Teacher tries to approve leave | `403 Forbidden` |
| Any role tries `GET /api/operator/schools/...` without owner | `403 Forbidden` |

---

## 13. Quick Swagger API Tests (No UI)

Go to `http://localhost:8000/docs`

1. Click **Authorize** → enter:
   ```
   Bearer <paste token from localStorage eduflow_token>
   ```
2. Test individual endpoints without the frontend:
   - `GET /api/students/` — list students
   - `GET /api/auth/me` — verify current user
   - `GET /api/fees/summary` — fee totals
   - `GET /api/reports/attendance-trends?months=3`

---

## 14. What Requires External Services (Skip if not configured)

| Feature | Requires |
|---|---|
| SMS notifications | Twilio credentials in `.env` |
| AI Chat responses | Azure OpenAI API key |
| File uploads | AWS S3 credentials (or runs locally without S3) |
| Razorpay billing | Razorpay key id/secret + webhook secret |
| Password reset emails | SMTP credentials |
| Transport coordinates | Google Maps API key |
| AI image generation (certificates) | Gemini API key |

---

## 15. Common Issues & Fixes

| Problem | Fix |
|---|---|
| Backend won't start — `SCHOOL_ID` error | Add `SCHOOL_ID=aaryans-joya` to `backend/.env` |
| Login returns 401 — "User not found" | Run `python seed.py` to create users |
| AI chat shows no response | Check Azure OpenAI keys in `.env` |
| File upload fails | S3 credentials missing — check AWS keys |
| Tests skipping silently | Missing `from __future__ import annotations` in a route file |
| Frontend blank screen | Check `REACT_APP_BACKEND_URL=http://localhost:8000` in `frontend/.env` |
