# API Contracts — Backend

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
| `owner` | — | Full school owner |
| `admin` | `principal` | Principal (school head) |
| `admin` | `accountant` | Finance staff |
| `admin` | `receptionist` | Front-desk staff |
| `admin` | `it_tech` | IT/Tech support |
| `admin` | `maintenance` | Facilities staff |
| `teacher` | — | Class teacher |
| `student` | — | Student self-service |

---

## Endpoints by Domain

### Auth — `/api/auth`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/login` | No | Login with username+password. Returns access token + sets refresh cookie. |
| `POST` | `/refresh` | Cookie | Exchange refresh token for new access token. |
| `POST` | `/logout` | Bearer | Revoke refresh token + clear cookie. |
| `POST` | `/forgot-password` | No | Send password reset email. Rate-limited (3/hr). |
| `POST` | `/reset-password` | No | Reset password via token from email. |
| `GET` | `/me` | Bearer | Get current user's profile. |
| `GET` | `/seed-status` | No | Check seed data counts (public debug endpoint). |

### Chat / Conversations — `/api/chat`

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

### Chat Uploads — `/api/chat`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/upload` | Bearer | Upload file attachment for chat context. |

### Students — `/api/students`

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

### Staff — `/api/staff`

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

### Fees — `/api/fees`

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

### Attendance — `/api/attendance`

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

### Academics — `/api/academics`

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

### Operations — `/api/ops`, `/api/operations`, `/api/transport`

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

### Settings — `/api/settings`

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

### Exports — `/api/export`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/students` | Bearer | Export students as CSV/Excel. |
| `GET` | `/fee-transactions` | Bearer | Export fee transactions. |
| `GET` | `/attendance` | Bearer | Export attendance records. |
| `GET` | `/staff` | Bearer | Export staff directory. |
| `GET` | `/expenses` | Bearer | Export expense records. |
| `GET` | `/enquiries` | Bearer | Export enquiry records. |
| `GET` | `/exam-results` | Bearer | Export exam results. |

### AI Tools — `/api/tools`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/{tool_id}/execute` | Bearer | Execute a named AI tool. |

> **Removed (2026-07-10):** the standalone in-app help assistant (`POST /api/assistant`)
> was retired — it duplicated the main AI chat (`/api/chat`), which every dashboard
> profile already has. Use `/api/chat` for all assistant interactions.

### Tokens / AI Budget — `/api/tokens`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/balance` | Bearer | Get branch token balance. |
| `GET` | `/usage` | Bearer | Get aggregate token usage. |
| `GET` | `/usage/me` | Bearer | Get own token usage. |
| `POST` | `/purchase` | Bearer (owner) | Purchase token pack. |
| `PUT` | `/limits` | Bearer (owner) | Set per-user token limits. |
| `GET` | `/packs` | Bearer | List available token packs. |

### Operator (Super-admin) — `/api/operator`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `PATCH` | `/schools/{school_id}/ai-rate-limit` | Bearer (owner) | Override AI rate limit for a school. |
| `GET` | `/ai-action-counts` | Bearer (owner) | Get AI action usage counts. |

### Reports — `/api/reports`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/attendance-trends` | Bearer | Attendance trend data for charts. |
| `GET` | `/fee-collection-summary` | Bearer | Fee collection chart data. |

### Notifications — `/api/notifications`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List notifications for current user. |
| `GET` | `/unread-count` | Bearer | Get count of unread notifications. |
| `PATCH` | `/{notification_id}/read` | Bearer | Mark a notification read. |
| `PATCH` | `/mark-all-read` | Bearer | Mark all notifications read. |
| `POST` | `/` | Bearer | Create a notification (internal). |

### Queries (Support Tickets) — `/api/queries`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List support queries. |
| `POST` | `/` | Bearer | Create a query/ticket. |
| `PATCH` | `/{ticket_id}/resolve` | Bearer | Resolve a ticket. |
| `PATCH` | `/{ticket_id}/unresolve` | Bearer | Reopen a ticket. |
| `DELETE` | `/{ticket_id}` | Bearer | Delete a ticket. |
| `GET` | `/{ticket_id}/attachment` | Bearer | Download ticket attachment. |

### Search — `/api/search`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | Full-text search across students, staff, etc. |

### SMS — `/api/sms`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/send-reminder` | Bearer | Send fee reminder SMS. |
| `POST` | `/send-bulk` | Bearer | Send bulk SMS. |
| `POST` | `/send-parent-message` | Bearer | Send SMS to parent. |
| `GET` | `/logs` | Bearer | Get SMS send logs. |
| `GET` | `/config-status` | Bearer | Check SMS config (Twilio). |

### Uploads — `/api/uploads`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/` | Bearer | Upload a file (S3-backed). |
| `GET` | `/serve/{filename}` | Bearer | Serve a file (legacy local path). |
| `GET` | `/` | Bearer | List uploads. |
| `DELETE` | `/{file_id}` | Bearer | Delete an uploaded file. |

### Import — `/api/import`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/validate` | Bearer | Validate import CSV before committing. |
| `POST` | `/commit` | Bearer | Commit validated import. |

### Issues (Facility/Tech/Maintenance) — `/api/issues`

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

### Audit Log — `/api/audit-log`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | Bearer | List audit log entries. |
| `GET` | `/{record_id}` | Bearer | Get audit log entry. |
| `GET` | `/record/{record_id}` | Bearer | Get full audit record (alternative path). |

### Activities (Houses/Positions/Teams) — `/api/activities`

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

### Image Generation — `/api/image-gen`

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
- `GET /api/fees/stream` — real-time fee update stream
- `GET /api/attendance/stream` — real-time attendance stream  
- `POST /api/chat/conversations/{conv_id}/messages` — AI response stream

Client must set `X-SSE-Session-ID` header for SSE connections.
