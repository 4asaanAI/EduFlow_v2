# API Contracts - Backend

_Generated: 2026-05-15 | Scan: deep | Part: backend_

---

## Base URL

All endpoints are prefixed with `/api`. In local dev the server runs on `http://localhost:8000`.

---

## Authentication

All protected endpoints require:

```
Authorization: Bearer <access_token>
```

Access tokens are short-lived JWTs (60 min). Use `POST /api/auth/refresh` (httpOnly cookie) to get a new one.

JWT payload fields: `user_id`, `role`, `name`, `initials`, `sub_category?`, `branch_id?`, `phone?`

---

## Roles

| Role | sub_category | Description |
|------|-------------|-------------|
| `owner` | - | Full school owner |
| `admin` | `principal` | Principal (school head) |
| `admin` | `accountant` | Finance staff |
| `admin` | `receptionist` | Front-desk staff |
| `admin` | `it_tech` | IT/Tech support |
| `admin` | `maintenance` | Facilities staff |
| `teacher` | - | Class teacher |
| `student` | - | Student self-service |

---

## Endpoints by Domain

### Auth - `/api/auth`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/login` | No | Login with username+password. Returns access token + sets refresh cookie. |
| `POST` | `/refresh` | Cookie | Exchange refresh token for new access token. |
| `POST` | `/logout` | Bearer | Revoke refresh token + clear cookie. |
| `POST` | `/forgot-password` | No | Send password reset email. Rate-limited (3/hr). |
| `POST` | `/reset-password` | No | Reset password via token from email. |
| `GET` | `/me` | Bearer | Get current user's profile. |
| `GET` | `/seed-status` | No | Check seed data counts (public debug endpoint). |

### Chat / Conversations - `/api/chat`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/conversations` | Bearer | List user's conversations. |
| `POST` | `/conversations` | Bearer | Create a new conversation. |
| `PATCH` | `/conversations/{conv_id}` | Bearer | Update conversation title/metadata. |
| `DELETE` | `/conversations/{conv_id}` | Bearer | Delete a conversation. |
| `GET` | `/conversations/{conv_id}/messages` | Bearer | Fetch messages for a conversation. |
| `POST` | `/conversations/{conv_id}/messages` | Bearer | Send a message (streaming SSE response). |
| `POST` | `/conversations/{conv_id}/action` | Bearer | Execute a suggested action from AI response. |
| `POST` | `/confirm` | Bearer | Confirm a pending AI action (legacy). |
| `POST` | `/conversations/{conv_id}/confirm` | Bearer | Confirm a pending AI action. |

### Chat Uploads - `/api/chat`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/upload` | Bearer | Upload file attachment for chat context. |

### Students - `/api/students`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List all students (paginated, filtered). |
| `POST` | `/` | Bearer | Create a new student record. |
| `GET` | `/me` | Bearer (student) | Get own student profile. |
| `GET` | `/classes/all` | Bearer | List all classes with student counts. |
| `GET` | `/{student_id}` | Bearer | Get a student's full profile. |
| `PATCH` | `/{student_id}` | Bearer | Update student record. |
| `DELETE` | `/{student_id}` | Bearer | Delete student. |
| `POST` | `/{student_id}/photo` | Bearer | Upload student photo. |
| `GET` | `/{student_id}/guardians` | Bearer | Get guardian contacts for a student. |
| `PUT` | `/{student_id}/guardians` | Bearer | Replace guardian contacts. |
| `POST` | `/{student_id}/guardians/{guardian_id}/photo` | Bearer | Upload guardian photo. |
| `POST` | `/{student_id}/erase` | Bearer | GDPR-style data erasure request. |

### Staff - `/api/staff`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List all staff members. |
| `POST` | `/` | Bearer | Create a staff member. |
| `GET` | `/{staff_id}` | Bearer | Get staff profile. |
| `PATCH` | `/{staff_id}` | Bearer | Update staff record. |
| `DELETE` | `/{staff_id}` | Bearer | Delete staff member. |
| `GET` | `/{staff_id}/leave-requests` | Bearer | Get leave requests for a staff member. |
| `GET` | `/leaves/my` | Bearer | Get own leave requests. |
| `GET` | `/leaves/pending` | Bearer | Get pending leave requests (principal/owner). |
| `PATCH` | `/leaves/{leave_id}` | Bearer | Approve/reject a leave request. |

### Fees - `/api/fees`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/structures` | Bearer | Get fee structures for school. |
| `GET` | `/transactions` | Bearer | List fee transactions (filterable). |
| `GET` | `/class-summary` | Bearer | Fee summary by class. |
| `GET` | `/my` | Bearer (student) | Get own fee history. |
| `POST` | `/transactions` | Bearer | Record a fee payment. |
| `PATCH` | `/transactions/{transaction_id}/correct` | Bearer | Correct a fee transaction. |
| `POST` | `/contact-log` | Bearer | Log a payment contact attempt. |
| `GET` | `/summary` | Bearer | Overall fee collection summary. |
| `GET` | `/stream` | Bearer | SSE stream for real-time fee updates. |
| `GET` | `/status/{student_id}` | Bearer | Get fee status for a student. |
| `DELETE` | `/transactions/{transaction_id}` | Bearer | Delete a fee transaction (owner only). |
| `POST` | `/discount-types` | Bearer | Create a discount type. |
| `GET` | `/discount-types` | Bearer | List discount types. |
| `PATCH` | `/discount-types/{discount_type_id}` | Bearer | Update a discount type. |
| `POST` | `/discounts/apply` | Bearer | Apply discount to a student's fee. |

### Attendance - `/api/attendance`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/` | Bearer | Record attendance (single). |
| `PATCH` | `/{attendance_id}/correct` | Bearer | Correct an attendance record. |
| `GET` | `/{attendance_id}/history` | Bearer | Get correction history. |
| `DELETE` | `/{attendance_id}` | Bearer | Delete attendance record. |
| `POST` | `/student/bulk` | Bearer | Bulk-record student attendance for a class. |
| `GET` | `/student` | Bearer | Query student attendance records. |
| `GET` | `/student/today/{class_id}` | Bearer | Today's attendance for a class. |
| `POST` | `/staff/bulk` | Bearer | Bulk-record staff attendance. |
| `GET` | `/stream` | Bearer | SSE stream for attendance updates. |
| `GET` | `/low-attendance` | Bearer | Students with attendance below threshold. |
| `GET` | `/export` | Bearer | Export attendance as CSV. |
| `GET` | `/staff` | Bearer | Query staff attendance records. |

### Academics - `/api/academics`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/assignments` | Bearer | List assignments (filtered by class). |
| `POST` | `/assignments` | Bearer | Create an assignment. |
| `PATCH` | `/assignments/{assignment_id}` | Bearer | Update an assignment. |
| `DELETE` | `/assignments/{assignment_id}` | Bearer | Delete an assignment. |
| `GET` | `/exams` | Bearer | List exams. |
| `POST` | `/exams` | Bearer | Create/schedule an exam. |
| `GET` | `/results` | Bearer | Query exam results. |
| `POST` | `/results/bulk` | Bearer | Bulk-enter exam results. |
| `POST` | `/lesson-plans` | Bearer | Create a lesson plan. |
| `GET` | `/lesson-plans` | Bearer | List lesson plans. |
| `PATCH` | `/lesson-plans/{plan_id}` | Bearer | Update a lesson plan. |
| `DELETE` | `/lesson-plans/{plan_id}` | Bearer | Delete a lesson plan. |
| `POST` | `/question-papers/generate` | Bearer | AI-generate a question paper. |
| `GET` | `/question-papers` | Bearer | List question papers. |
| `GET` | `/question-papers/{paper_id}` | Bearer | Get a specific question paper. |

### Operations - `/api/ops`, `/api/operations`, `/api/transport`

| Method | Prefix | Path | Description |
|--------|--------|------|-------------|
| `GET` | `/api/ops` | `/certificates` | List certificates. |
| `POST` | `/api/ops` | `/certificates` | Issue a certificate. |
| `GET` | `/api/ops` | `/expenses` | List school expenses. |
| `POST` | `/api/ops` | `/expenses` | Record an expense. |
| `GET` | `/api/ops` | `/complaints` | List complaints. |
| `POST` | `/api/ops` | `/complaints` | File a complaint. |
| `PATCH` | `/api/ops` | `/complaints/{complaint_id}` | Update complaint status. |
| `GET` | `/api/ops` | `/incidents` | List incidents. |
| `POST` | `/api/ops` | `/incidents` | Report an incident. |
| `GET` | `/api/ops` | `/incidents/{incident_id}` | Get incident detail. |
| `POST` | `/api/ops` | `/incidents/{incident_id}/thread` | Add a thread reply. |
| `PATCH` | `/api/ops` | `/incidents/{incident_id}/assign` | Assign incident to staff. |
| `GET` | `/api/ops` | `/visitors` | List visitor logs. |
| `POST` | `/api/ops` | `/visitors` | Log a visitor. |
| `PATCH` | `/api/ops` | `/visitors/{visitor_id}/checkout` | Check out a visitor. |
| `GET` | `/api/ops` | `/enquiries` | List admission enquiries. Returns `meta.total` beside `meta.count`, so a page shorter than the register is visible as one. A page size below 1 is refused with a 400, never turned into 1. Each row carries a `journey` block, which is the family's ONE position worked out from the enquiry and its application together. |
| `POST` | `/api/ops` | `/enquiries` | Log an admission enquiry. |
| `PATCH` | `/api/ops` | `/enquiries/{enquiry_id}` | Move an enquiry along its stages. **`enrolled` is refused here**, see the Admissions section below. |

### Admissions - `/api/admissions`, `/api/commercial/crm`

Two prefixes, one funnel. `/api/commercial/crm` is the enquiry half (leads, calls,
opportunity values); `/api/admissions` is the application half, through to a child on the
roll. Since 2026-08-14 both are shown on ONE screen, "Admissions", with tabs.

**Enrolment has exactly one source: `POST /applications/{id}/enroll`.** It creates the
student and the guardians in a single transaction and marks the application and the
enquiry enrolled. No other route, and no AI tool, may set a status of `enrolled`; every
one of them refuses with the same message. Before 2026-08-14 an enquiry could be moved to
`enrolled` by hand, so the funnel could report a child who did not exist.

| Method | Prefix | Path | Auth | Description |
|--------|--------|------|------|-------------|
| `GET` | `/api/admissions` | `/applications` | Bearer (owner/admin) | List applications, each with its `journey` position. |
| `GET` | `/api/admissions` | `/applications/{id}` | Bearer (owner/admin) | One application. |
| `POST` | `/api/admissions` | `/applications` | Bearer (owner/admin) | Start an application. Pass `enquiry_id` to carry the family across (name, both parents, phone, date of birth, gender, previous school). A second attempt for the same enquiry returns the FIRST application with `meta.existing = true` rather than creating a duplicate. |
| `PATCH` | `/api/admissions` | `/applications/{id}/status` | Bearer (owner/admin) | Move a stage. Refuses submission without a guardian name and phone, `assessed` without an assessment, `accepted` without an offer, and `enrolled` always. |
| `POST` | `/api/admissions` | `/applications/{id}/documents` | Bearer (owner/admin) | Attach an uploaded document. |
| `POST` | `/api/admissions` | `/applications/{id}/assessment` | Bearer (owner/admin) | Record an entrance score. |
| `POST` | `/api/admissions` | `/applications/{id}/offer` | Bearer, **owner or principal** | Issue an offer for a class, valid until a date that cannot be in the past. |
| `POST` | `/api/admissions` | `/applications/{id}/enroll` | Bearer, **owner or principal** | Create the child and the guardians. The only route that enrols anybody. |
| `GET` | `/api/commercial` | `/crm/leads` | Bearer (owner/principal/receptionist) | Enquiries as CRM leads, scoped to a legal entity. |
| `POST` | `/api/commercial` | `/crm/leads` | Bearer (owner/principal/receptionist) | Create a lead. Refuses a phone or email already used by an active enquiry. |
| `PATCH` | `/api/commercial` | `/crm/leads/{id}` | Bearer (owner/principal/receptionist) | Update a lead. A lost lead needs a reason. |
| `DELETE` | `/api/commercial` | `/crm/leads/{id}` | Bearer (owner/principal/receptionist) | Delete an enquiry entered in error. Blocked once it has become an application or a student. |
| `GET` | `/api/commercial` | `/crm/leads/{id}/activities` | Bearer (owner/principal/receptionist) | The call and visit log for one family. |
| `POST` | `/api/commercial` | `/crm/leads/{id}/activities` | Bearer (owner/principal/receptionist) | Log a call, visit, meeting or note. A `next_follow_up` date on it is written onto the enquiry and is what drives the worklist below. |
| `GET` | `/api/commercial` | `/crm/follow-ups` | Bearer (owner/principal/receptionist) | **Who to call today.** See below. |
| `POST` | `/api/commercial` | `/crm/leads/{id}/opportunities` | Bearer, owner or principal | Attach a pipeline value to a lead. |
| `GET` | `/api/commercial` | `/crm/opportunities` | Bearer (owner/principal/receptionist) | List opportunities. |
| `PATCH` | `/api/commercial` | `/crm/opportunities/{id}` | Bearer, owner or principal | Move an opportunity's stage. A lost one needs a reason. |
| `GET` | `/api/commercial` | `/crm/pipeline` | Bearer (owner/principal/receptionist) | Stage counts and weighted values. |

#### Entrance tests, `/api/admissions/tests` (added 2026-08-15)

Before this, `assessment_scheduled` was a status on an application and nothing else, so the
school could not pull a list for a given day. A test is now a record with a date, a time, a
place and a total, and a list of who is sitting it.

Every route below carries `require_role("owner", "admin")`, **the same gate the assessment
route above has always had**. Running the list and entering the marks from it are the same
job, so this grants nobody anything new. Issuing an offer and enrolling stay narrower.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/tests` | List tests, newest first, each with its counts. Optional `status` filter. |
| `POST` | `/tests` | Create one. `title`, `scheduled_for` (YYYY-MM-DD), `place` and `maximum_marks` are required; `start_time` (HH:MM), `class_applying` and `notes` are optional. **A test with no place is refused**: a list of children with a date and no place is not something the office can hand to a parent. |
| `GET` | `/tests/{id}` | The list for that test: every applicant with their guardian's name and phone, whether they turned up, and their mark. Names are read from the application each time, never copied, so a corrected spelling shows up. |
| `PATCH` | `/tests/{id}` | Change the date, time, place, title, notes or `status` (`planned`, `held`, `cancelled`). |
| `POST` | `/tests/{id}/seats` | Put applicants on the test. Takes `application_ids`. |
| `PATCH` | `/tests/{id}/seats/{seat_id}` | Record `attendance` (`present` or `absent`) and/or a `score`. |
| `DELETE` | `/tests/{id}/seats/{seat_id}` | Take somebody off the list. |

**The two rules the endpoints exist to hold.**

1. **"Not yet marked" is a third state and is never the same as absent.** `attendance` is
   `null` until a person says otherwise, and every response carries `not_yet_marked` as its
   own count alongside `present` and `absent`. A register nobody filled in and a test nobody
   came to are opposite facts, and the second is a reason to ring twelve families.
2. **A mark reaches the application in the same call.** The score goes through
   `admissions_service.record_assessment`, the same function the application screen uses. If
   that refuses (for example the application is still a draft), the request is refused and
   **nothing at all is stored, including the attendance sent with it**. There is one
   assessment per application; this is not a second one.

**The total lives on the test and freezes at the first mark.** `record_assessment` takes a
`maximum` per call, so before this two children sitting one paper could be recorded out of
different totals with their percentages silently disagreeing. Changing `maximum_marks` after
any mark exists is refused with a 409.

Other refusals, each with a 400 or 409 that says why: a score for somebody not marked
present, a score outside the paper's total, removing an applicant whose mark is already on
their application, cancelling a test that has already been marked, and anything at all on a
cancelled test. **Seating returns both halves**: `seated` and `refused`, the latter naming
each applicant and the reason, so a partly refused request cannot read as a complete one.

#### `GET /api/commercial/crm/follow-ups`

Optional `entity_id`, `today` (defaults to the real one) and `upcoming_days` (0 to 90,
default 7). A nonsense value is refused with a 400 rather than quietly adjusted.

Returns three lists, `overdue`, `due_today` and `upcoming`, each row carrying the family,
the phone, how many days late the call is, and the last activity anybody recorded. It also
returns `counts`, and **the counts are the point of the endpoint**:

| Count | Why it is there |
|---|---|
| `active_enquiries` | How many families are actually open. |
| `no_follow_up_date_set` | How many of those nobody has scheduled a call with. **Without this an empty worklist reads as "the office is up to date" when the truth may be "nobody has planned anything".** |
| `scheduled_beyond_the_window` | Families due after the window, so nothing is silently outside the answer. |

A follow-up date that cannot be read is refused at the point of writing, on all three
entrances (lead create, lead update, activity). Dates already in the records that cannot
be read are shown in `overdue` with `date_is_readable: false` rather than dropped, because
a row in no list at all is the same silent short answer this platform keeps fixing.

### Settings - `/api/settings`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/token-usage` | Bearer | Record AI token usage. |
| `GET` | `/token-usage` | Bearer | Get token usage stats. |
| `POST` | `/year-end-transition` | Bearer (owner) | Trigger year-end class promotion. |
| `PATCH` | `/school` | Bearer (owner) | Update school settings. |
| `GET` | `/me` | Bearer | Get own user settings. |
| `PATCH` | `/me` | Bearer | Update own user settings. |
| `GET` | `/school` | Bearer | Get school info. |
| `GET` | `/classes` | Bearer | List class definitions. |
| `GET` | `/forms` | Bearer | List custom forms. |
| `POST` | `/forms` | Bearer | Create a custom form. |
| `GET` | `/forms/{form_id}` | Bearer | Get a form definition. |
| `POST` | `/forms/{form_id}/responses` | Bearer | Submit a form response. |
| `GET` | `/forms/{form_id}/responses` | Bearer | List form responses. |
| `DELETE` | `/forms/{form_id}` | Bearer | Delete a form. |

### Exports - `/api/export`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/students` | Bearer | Export students as CSV/Excel. |
| `GET` | `/fee-transactions` | Bearer | Export fee transactions. |
| `GET` | `/attendance` | Bearer | Export attendance records. |
| `GET` | `/staff` | Bearer | Export staff directory. |
| `GET` | `/expenses` | Bearer | Export expense records. |
| `GET` | `/enquiries` | Bearer | Export enquiry records. |
| `GET` | `/exam-results` | Bearer | Export exam results. |
| `GET` | `/school-workbook` | Bearer, **owner or principal** | The whole school as ONE Excel file, a sheet per area (children, staff, fees, attendance, exam results, classes, transport, expenses, enquiries). Returns the per-sheet counts on an `X-Export-Row-Counts` header. |
| `POST` | `/table` | Bearer | Package rows a screen already holds (`{title, headers, rows, format}`) into a CSV or Excel file. **Reads nothing** - it formats what the caller sent back to the caller, which they could only have obtained by passing the gate on the endpoint the rows came from. |

**Three rules govern all of these (Release 3, 2026-08-12).**

1. **Complete or refused, never short.** Each read asks for one row more than it will
   accept, so it can tell "that is all of them" from "there were more". Past
   `EXPORT_MAX_ROWS` (100,000) the request fails with a **413 that says no file was
   produced**. Nothing is ever silently dropped. `POST /table` refuses over 50,000 rows
   and over 60 columns the same way.
2. **The permission gate comes from the Release 2 table**, not from hand-written role
   checks. `require_export(key)` derives it from `services/profile_matrix.py` by asking
   whether the caller may open a screen that shows that data; `may_export(user, key)` is
   the same rule asked as a plain question, for Flo. **Dormant profiles are refused even
   where the table grants them the screen.** A download is not a way around who may see
   what. `/school-workbook` uses `require_owner_or_principal`, which is Aman and Adesh
   exactly.
3. **No confirm step and no approval window**, on a screen or through Flo (Abhimanyu,
   2026-08-12). Reading what you may already read is not the thing that needs guarding.

The queries live in `EXPORT_BUILDERS` (nine entries, each returning
`(headers, rows, title)`). The routes are three lines each. **Add a new data set to that
dictionary, never beside a route**, and give it an `EXPORT_SCREENS` entry or `may_export`
default-denies it and the feature reads as broken.

### AI Tools - `/api/tools`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/{tool_id}/execute` | Bearer | Execute a named AI tool. |

> **Removed (2026-07-10):** the standalone in-app help assistant (`POST /api/assistant`)
> was retired - it duplicated the main AI chat (`/api/chat`), which every dashboard
> profile already has. Use `/api/chat` for all assistant interactions.

### Tokens / AI Budget - `/api/tokens`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/balance` | Bearer | Get branch token balance. |
| `GET` | `/usage` | Bearer | Get aggregate token usage. |
| `GET` | `/usage/me` | Bearer | Get own token usage. |
| `POST` | `/purchase` | Bearer (owner) | Purchase token pack. |
| `PUT` | `/limits` | Bearer (owner) | Set per-user token limits. |
| `GET` | `/packs` | Bearer | List available token packs. |

### Operator (Super-admin) - `/api/operator`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `PATCH` | `/schools/{school_id}/ai-rate-limit` | Bearer (owner) | Override AI rate limit for a school. |
| `GET` | `/ai-action-counts` | Bearer (owner) | Get AI action usage counts. |

### Reports - `/api/reports`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/attendance-trends` | Bearer | Attendance trend data for charts. |
| `GET` | `/fee-collection-summary` | Bearer | Fee collection chart data. |

### Notifications - `/api/notifications`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List notifications for current user. |
| `GET` | `/unread-count` | Bearer | Get count of unread notifications. |
| `PATCH` | `/{notification_id}/read` | Bearer | Mark a notification read. |
| `PATCH` | `/mark-all-read` | Bearer | Mark all notifications read. |
| `POST` | `/` | Bearer | Create a notification (internal). |

### Queries (Support Tickets) - `/api/queries`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List support queries. |
| `POST` | `/` | Bearer | Create a query/ticket. |
| `PATCH` | `/{ticket_id}/resolve` | Bearer | Resolve a ticket. |
| `PATCH` | `/{ticket_id}/unresolve` | Bearer | Reopen a ticket. |
| `DELETE` | `/{ticket_id}` | Bearer | Delete a ticket. |
| `GET` | `/{ticket_id}/attachment` | Bearer | Download ticket attachment. |

### Search - `/api/search`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | Full-text search across students, staff, etc. |

### SMS - `/api/sms`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/send-reminder` | Bearer | Send fee reminder SMS. |
| `POST` | `/send-bulk` | Bearer | Send bulk SMS. |
| `POST` | `/send-parent-message` | Bearer | Send SMS to parent. |
| `GET` | `/logs` | Bearer | Get SMS send logs. |
| `GET` | `/config-status` | Bearer | Check SMS config (Twilio). |

### Uploads - `/api/uploads`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/` | Bearer | Upload a file (S3-backed). |
| `GET` | `/serve/{filename}` | Bearer | Serve a file (legacy local path). |
| `GET` | `/` | Bearer | List uploads. |
| `DELETE` | `/{file_id}` | Bearer | Delete an uploaded file. |

### Import - `/api/import`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/validate` | Bearer | Validate import CSV before committing. |
| `POST` | `/commit` | Bearer | Commit validated import. |

### Issues (Facility/Tech/Maintenance) - `/api/issues`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/facility` | Bearer | Report a facility issue. |
| `GET` | `/facility` | Bearer | List facility issues. |
| `PATCH` | `/facility/{request_id}` | Bearer | Update facility issue. |
| `POST` | `/facility/{request_id}/confirm-resolution` | Bearer | Confirm facility issue resolved. |
| `POST` | `/tech` | Bearer | Report a tech support issue. |
| `GET` | `/tech` | Bearer | List tech support issues. |
| `PATCH` | `/tech/{request_id}` | Bearer | Update tech issue. |
| `GET` | `/` | Bearer | Combined issues list. |
| `GET` | `/maintenance/schedule` | Bearer | Get maintenance schedule. |
| `POST` | `/maintenance/schedule` | Bearer | Create maintenance schedule entry. |
| `PATCH` | `/maintenance/schedule/{entry_id}` | Bearer | Update schedule entry. |
| `GET` | `/maintenance/vendors` | Bearer | List vendors. |
| `POST` | `/maintenance/vendors` | Bearer | Add vendor. |
| `PATCH` | `/maintenance/vendors/{vendor_id}` | Bearer | Update vendor. |

### Audit Log - `/api/audit-log`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List audit log entries. |
| `GET` | `/{record_id}` | Bearer | Get audit log entry. |
| `GET` | `/record/{record_id}` | Bearer | Get full audit record (alternative path). |

### Activities (Houses/Positions/Teams) - `/api/activities`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/houses` | Bearer | List school houses. |
| `POST` | `/houses/{house_id}/points` | Bearer | Award points to a house. |
| `GET` | `/houses/{house_id}/points-log` | Bearer | Get points history. |
| `GET` | `/positions` | Bearer | List positions (captain, prefect, etc.). |
| `POST` | `/positions` | Bearer | Create a position. |
| `DELETE` | `/positions/{position_id}` | Bearer | Delete a position. |
| `GET` | `/teams` | Bearer | List teams. |
| `POST` | `/teams` | Bearer | Create a team. |
| `PATCH` | `/teams/{team_id}` | Bearer | Update a team. |
| `DELETE` | `/teams/{team_id}` | Bearer | Delete a team. |

### Image Generation - `/api/image-gen`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/certificate` | Bearer | AI-generate certificate image. |
| `POST` | `/id-cards` | Bearer | AI-generate student ID cards. |

### Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/health` | No | Liveness check. Returns `{"status": "ok"}`. |
| `GET` | `/api/health/ready` | No | Readiness check. Probes DB + AI + (optional) biometric. |

---

## Common Response Shapes

**Success:**
```json
{ "success": true, "data": { ... } }
```

**Error:**
```json
{ "detail": "Error message" }
```

**Validation error (422):**
```json
{ "detail": [{ "loc": [...], "msg": "...", "type": "..." }] }
```

---

## SSE Streams

Several endpoints stream Server-Sent Events:
- `GET /api/fees/stream` - real-time fee update stream
- `GET /api/attendance/stream` - real-time attendance stream  
- `POST /api/chat/conversations/{conv_id}/messages` - AI response stream

Client must set `X-SSE-Session-ID` header for SSE connections.
