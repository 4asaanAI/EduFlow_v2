---
workflowType: 'stories'
project_name: 'EduFlow Enterprise Upgrade'
user_name: 'Abhimanyu'
date: '2026-05-12'
status: 'ready-for-implementation'
inputDocuments:
  - '_bmad-output/planning-artifacts/prd.md'
  - '_bmad-output/planning-artifacts/architecture.md'
  - '_bmad-output/project-context.md'
totalStories: 28
phases:
  - phase: 1
    name: 'Foundation & Infrastructure'
    stories: [1, 2, 3, 4]
  - phase: 2
    name: 'Core CRUD Completeness'
    stories: [5, 6, 7, 8, 9, 10]
  - phase: 3
    name: 'New Capabilities'
    stories: [11, 12, 13, 14, 15, 16, 17]
  - phase: 4
    name: 'AI & Safety Hardening'
    stories: [18, 19, 20]
  - phase: 5
    name: 'Observability & Quality'
    stories: [21, 22, 23, 24, 25, 26, 27, 28]
---

# Implementation Stories — EduFlow Enterprise Upgrade

**Total stories:** 28 across 5 phases
**Sequence:** Complete each phase before starting the next — later phases depend on earlier ones.
**PRD references:** Each story maps to the Functional Requirements (FR) from `prd.md`.

---

## Implementation Order Rationale

1. **Foundation first** — S3 and auth gaps are preconditions for data integrity and security; fix before adding features
2. **CRUD next** — Close the 40% → 100% CRUD gap before building new capability on top of incomplete foundations
3. **New capability** — Maintenance profile, approvals, issue tracker, timetable, leave management, discount engine
4. **AI hardening** — Dispatch table, idempotency tokens, confirmation token security (depends on CRUD being solid)
5. **Quality baseline** — Tests, observability, UX states, mobile fixes (can run in parallel with Phase 4)

---

## Phase 1 — Foundation & Infrastructure

### Story 1: S3-Backed File Storage Migration

**Priority:** Critical — data loss blocker
**Effort:** Medium
**PRD:** FR63, FR64, FR65

**As** the operator (Abhimanyu),
**I want** all file uploads to be stored in S3 and all existing files to be migrated,
**so that** no files are lost when the Elastic Beanstalk instance is replaced or redeployed.

**Acceptance Criteria:**
- [ ] `routes/upload.py` writes files directly to S3 using boto3; nothing is written to local disk
- [ ] All file reads generate a time-limited pre-signed S3 URL (expiry ≤ 1 hour)
- [ ] S3 bucket is not publicly accessible; no public-read ACL
- [ ] Failed uploads surface a clear error to the caller; no partial file records are created
- [ ] All uploads include S3 checksum verification (ETag or SHA256)
- [ ] A migration script (`backend/migrations/012_migrate_uploads_to_s3.py`) is written and run against a copy of production data first
- [ ] After migration, existing file URLs resolve correctly
- [ ] `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` are documented in `.env.example`
- [ ] File upload accepts files ≤ 10MB and surfaces a clear error for oversized files; upload confirmation renders within 5 seconds

**Technical Notes:**
- S3 bucket should be in `ap-south-1` (Mumbai) for DPDP data residency
- Use `boto3.client('s3').generate_presigned_url()` for read URLs — never expose the raw S3 key to the frontend
- Migration script must be idempotent — safe to run twice

---

### Story 2: Auth Hardening — Short-Lived Tokens + Session Invalidation

**Priority:** Critical — security gap
**Effort:** Medium
**PRD:** NFR Security, FR3, FR6

**As** the system,
**I want** access tokens to expire in ≤1 hour and user deactivation to immediately invalidate all sessions,
**so that** the platform meets its security requirements.

**Acceptance Criteria:**
- [ ] JWT access token expiry reduced from 7 days to 1 hour
- [ ] A refresh token (7-day expiry, revocable) is issued alongside the access token
- [ ] `POST /api/auth/refresh` endpoint validates the refresh token and issues a new access token
- [ ] When an Owner deactivates a user account (FR3), all active refresh tokens for that user are invalidated immediately — subsequent refresh attempts return 401
- [ ] Frontend `api.js` handles 401 on any API call by attempting one token refresh; if refresh fails, clears auth and redirects to login
- [ ] Refresh tokens are stored in `httpOnly`, `Secure`, `SameSite=Strict` cookies (not localStorage)
- [ ] Access tokens remain in memory (not persisted in localStorage)
- [ ] `JWT_SECRET` absent in production environment causes startup failure with a clear error message (removes the weak fallback)

**Technical Notes:**
- Store active refresh tokens in a `refresh_tokens` MongoDB collection with TTL index on `expires_at`
- Deactivation: `is_active = false` on the user record + purge all matching `refresh_tokens` documents
- Frontend: store access token in React state/context only (lost on page reload → triggers refresh flow)

---

### Story 3: `schoolId` Forward-Compatibility Backfill

**Priority:** High — Phase 2 precondition
**Effort:** Small
**PRD:** Technical Constraints — Multi-tenancy, Phase 2 Scalability NFR

**As** the system,
**I want** all existing data records to have a `schoolId` field,
**so that** the authorization matrix tests are valid and multi-tenancy can be activated in Phase 2 without a breaking migration.

**Acceptance Criteria:**
- [ ] Migration `013_add_school_id.py` adds `schoolId: "aaryans-joya"` to all existing documents in every collection
- [ ] All new Pydantic models include a `schoolId` field with a default value pulled from the `SCHOOL_ID` env var
- [ ] All new MongoDB queries include `schoolId` in their filter (not enforced as a hard constraint yet, but present)
- [ ] `SCHOOL_ID` is documented in `.env.example`
- [ ] Migration is idempotent — does not re-add the field if already present

---

### Story 4: `/api/health/ready` Endpoint + Structured Logging

**Priority:** High — go-live prerequisite
**Effort:** Medium
**PRD:** FR66, FR67, FR68, FR70

**As** the operator (Abhimanyu),
**I want** a readiness endpoint and structured logs shipped to a queryable destination,
**so that** I know when something breaks before Aman does.

**Acceptance Criteria:**
- [ ] `GET /api/health/ready` returns a JSON object with per-component status: `{ db: "ok"|"error", ai: "ok"|"degraded", overall: "ready"|"degraded"|"down" }`
- [ ] Endpoint performs an active liveness check on MongoDB (ping command) on each call
- [ ] Endpoint performs an active reachability check on Azure OpenAI (lightweight call or endpoint probe) on each call — if AI is unreachable, `ai: "degraded"` but `overall` remains `"ready"` (AI degradation is not a platform outage)
- [ ] All `logger.info/warning/error` calls output valid JSON with fields: `timestamp`, `level`, `service`, `method`, `path`, `status_code`, `duration_ms`, `request_id` — no PII fields (student names, phone numbers, fee amounts, addresses)
- [ ] Logs are shipped to AWS CloudWatch (or equivalent queryable destination) in real time
- [ ] At least one CloudWatch alarm fires when error rate on any route group exceeds a threshold (e.g. >10 errors/5min)
- [ ] An alert fires when daily Azure OpenAI spend exceeds a configured threshold (`OPENAI_SPEND_ALERT_INR` env var)
- [ ] A `X-Request-ID` header is accepted from the client and echoed in the response and all log entries for that request; if absent, a UUID is generated server-side
- [ ] Log schema is validated in a CI step that rejects entries containing any of the following field names: `student_name`, `phone`, `address`, `fee_amount`, `biometric`

---

## Phase 2 — Core CRUD Completeness

### Story 5: Student Profile — Full CRUD

**Priority:** High
**Effort:** Medium
**PRD:** FR77, FR58, FR59, FR60

**As** an Owner or Principal,
**I want** to create, view, edit, and deactivate student profiles,
**so that** the full school database is manageable within EduFlow.

**Acceptance Criteria:**
- [ ] `GET /api/students/:id` returns the full student profile
- [ ] `POST /api/students` creates a student profile with schema validation + referential integrity check (class must exist, academic year must be current)
- [ ] `PATCH /api/students/:id` performs a partial update; every field change is logged in the audit trail with previous value, new value, changed by, and timestamp
- [ ] `DELETE /api/students/:id` is a soft deactivation (`is_active: false`); hard delete only available to Owner via a separate `POST /api/students/:id/erase` endpoint gated behind DPDP two-step (FR61)
- [ ] Deactivated students do not appear in default list views; a `?include_inactive=true` query param surfaces them for Owner
- [ ] Student list view has pagination (≤ 20 per page) and at minimum one sort option (name, class)
- [ ] Frontend `StudentDatabase.js` renders loading, empty, and error states
- [ ] All fields respect the student's `schoolId`
- [ ] DPDP erasure (`/erase`) requires Owner role, a mandatory reason field, generates an irreversible pre-deletion audit record, pseudonymizes attendance records (replaces name/contact fields with a non-reversible token), and hard-deletes PII fields across all collections for that student

---

### Story 6: Staff Profile — Full CRUD

**Priority:** High
**Effort:** Medium
**PRD:** FR78, FR59, FR60

**As** an Owner or Principal,
**I want** to create, view, edit, and deactivate staff profiles,
**so that** all staff records are manageable within EduFlow.

**Acceptance Criteria:**
- [ ] `GET /api/staff/:id` returns full staff profile including role, sub_category, leave balances
- [ ] `POST /api/staff` creates a staff profile; user account is created or linked
- [ ] `PATCH /api/staff/:id` partial update with full audit trail (previous value, new value, changed by, timestamp)
- [ ] `DELETE /api/staff/:id` soft deactivation — immediately invalidates the staff member's active sessions (ties into Story 2 session invalidation)
- [ ] Staff list supports pagination (≤ 20/page) and sort by name, staff_type, department
- [ ] Frontend `StaffTracker.js` renders loading, empty, and error states
- [ ] Leave balance fields are readable but only editable by Owner or Principal (not self-editable)

---

### Story 7: Attendance — Correction with Audit Trail + Manual Entry Fallback

**Priority:** High
**Effort:** Medium
**PRD:** FR14, FR17, FR59

**As** a Principal,
**I want** to correct attendance records with a mandatory reason and manually mark attendance when biometric is unavailable,
**so that** records are always accurate and auditable.

**Acceptance Criteria:**
- [ ] `PATCH /api/attendance/:id/correct` accepts `{ correction_type, reason }` — original record is preserved, a new correction record is inserted with `corrected_by`, `corrected_at`, `reason`, and a reference to the original
- [ ] Manual attendance entry (`POST /api/attendance`) is available to Principal when the biometric flag is not set; manually-entered records include a `source: "manual"` flag visible in the audit trail
- [ ] `GET /api/attendance/:id/history` returns the full correction history for a record
- [ ] A hard delete of attendance records is rejected at the API layer (405 response) under normal operations
- [ ] Frontend `AttendanceRecorder.js` renders loading, empty, and error states; the correction form requires a reason field (client-side validation + server-side enforcement)

---

### Story 8: Fee Management — Full CRUD + Idempotency

**Priority:** Critical
**Effort:** Large
**PRD:** FR21, FR22, FR23, FR24, FR25, FR26, FR27, FR28, FR29, FR30, FR31, FR32, FR88

**As** an Accountant,
**I want** to record payments, apply discounts, log contact events, and correct fee records with full auditability,
**so that** the fee workflow is complete and trustworthy.

**Acceptance Criteria:**
- [ ] `POST /api/fees/transactions` creates a fee payment; accepts an `Idempotency-Key` header; duplicate submissions with the same key return the original record (HTTP 200) without creating a duplicate
- [ ] The idempotency key format is `{student_id}:{fee_period}:{fee_head}` — enforced server-side
- [ ] Idempotency window is 24 hours from first submission
- [ ] `PATCH /api/fees/transactions/:id/correct` requires a mandatory `reason` field; original record is preserved in the audit trail; no silent overwrites
- [ ] `GET /api/fees/transactions?overdue_days=30` returns students with fees overdue by ≥ N days
- [ ] `POST /api/fees/contact-log` logs a contact event (call, message, visit) against a student's fee record with `date`, `contact_type`, `outcome`, `notes`
- [ ] Fee collection summary (`GET /api/fees/summary`) returns: total collected, total outstanding, number of defaulters for a selected period; updates within 30 seconds of a payment event
- [ ] Principal can view per-student fee status via `GET /api/fees/status/:student_id` (paid/unpaid/overdue only — no financial aggregates)
- [ ] Frontend `FeeCollection.js` renders loading, empty, and error states including partial-write recovery guidance
- [ ] Fee records cannot be hard deleted (405 response at API layer)

---

### Story 9: Discount Policy Engine

**Priority:** High
**Effort:** Medium
**PRD:** FR25, FR26, FR27, FR92, FR93

**As** an Accountant,
**I want** to configure reusable discount types and apply multiple discounts to a student's fee profile with full breakdown visibility,
**so that** all discount applications are transparent and auditable.

**Acceptance Criteria:**
- [ ] `POST /api/fees/discount-types` creates a discount type with: `name`, `value` (flat or percentage), `recurrence` (one-time/per-term), `reason_note`
- [ ] `GET /api/fees/discount-types` returns all active discount types (reusable catalogue)
- [ ] `PATCH /api/fees/discount-types/:id` renames or deactivates a discount type; deactivation does not remove existing applied discounts
- [ ] `POST /api/fees/discounts/apply` applies a discount type to a student's fee profile; records `applied_by`, `applied_at`, `effective_from`
- [ ] `GET /api/fees/discounts/:student_id` returns: original fee amount, each applied discount (label, value, type), and calculated payable amount — no black-box totals
- [ ] Multiple discounts on the same student are stacked and all shown individually
- [ ] Owner discount impact summary (`GET /api/fees/discount-summary`) returns: total expected revenue, total discount value committed, per-discount-type count and aggregate value
- [ ] All discount application and catalogue management actions appear in the audit log
- [ ] Frontend renders the full discount breakdown (original → each discount → payable) as a line-by-line calculation

---

### Story 10: Operations — Leave Requests + Approvals Workflow

**Priority:** High
**Effort:** Medium
**PRD:** FR40–FR45, FR91

**As** a staff member and as Owner/Principal,
**I want** to submit, review, approve, and reject leave requests and general approval requests,
**so that** all operational decisions have an audit trail.

**Acceptance Criteria:**
- [ ] `POST /api/operations/leave-requests` creates a leave request with: `date_range`, `leave_type` (sick/casual/planned), `reason`; only the requesting staff member's own user ID is accepted (cannot submit on behalf of another)
- [ ] `PATCH /api/operations/leave-requests/:id/decide` — Principal approves or rejects with a mandatory `reason`; approved leave is reflected in the staff member's availability for substitution queries
- [ ] `POST /api/operations/approval-requests` — any Admin submits an approval request with: `title`, `description`, `estimated_impact`, `note`, `routing` (owner_only | owner_and_principal)
- [ ] Submitted approval requests appear in Owner's dashboard with an unread-count badge; requests with `routing: owner_and_principal` also appear in Principal's dashboard
- [ ] `PATCH /api/operations/approval-requests/:id/decide` — Owner (all) or Principal (academic-routed only) approves or rejects with a mandatory `reason`
- [ ] Submitting Admin receives an in-app notification on decision (Story 16 — notifications — must be implemented or stubbed)
- [ ] Every submission, routing decision, and decision is recorded in the audit log
- [ ] Leave request list supports pagination and filter by status (pending/approved/rejected)

---

## Phase 3 — New Capabilities

### Story 11: Maintenance Admin Profile — Full Build

**Priority:** Critical — new profile, go-live requirement
**Effort:** Large
**PRD:** FR52, FR53, FR54, FR55, FR2, FR4, FR5

**As** a Maintenance Admin,
**I want** a dedicated profile with a facility request queue,
**so that** facility issues are logged, tracked, and resolved with full owner confirmation.

**Acceptance Criteria:**
- [ ] `maintenance` sub_category added to the `admin` role in `scope_resolver.py` and `require_role` usage
- [ ] Maintenance Admin can only read and write `facility_request` type records — API returns 403 for any `tech_request` query
- [ ] `POST /api/issues/facility` creates a facility request with: `description`, `location`, `logged_by`, `category`
- [ ] `PATCH /api/issues/facility/:id` updates status (`open` → `in_progress` → `pending_owner_confirmation`) and adds a note; Maintenance Admin cannot set status to `closed`
- [ ] `POST /api/issues/facility/:id/confirm-resolution` — Owner-only endpoint; sets status to `closed`; notifies Maintenance Admin
- [ ] Owner sees all facility requests regardless of status via `GET /api/issues?type=facility`
- [ ] Frontend tool panel `MaintenanceTools.js` is created with: request queue, status update form, note thread; renders loading, empty, and error states
- [ ] Maintenance Admin is routable via login (user with `role: admin`, `sub_category: maintenance`)
- [ ] Authorization matrix test suite covers Maintenance Admin × all sensitive endpoints

---

### Story 12: IT/Tech Admin — Issue Tracker Namespace Isolation

**Priority:** High
**Effort:** Small-Medium
**PRD:** FR51, FR53, FR54, FR55

**As** an IT/Tech Admin,
**I want** a tech request tracker isolated from facility requests,
**so that** each namespace is only visible to its owning profile.

**Acceptance Criteria:**
- [ ] `POST /api/issues/tech` creates a tech request; only IT/Tech Admin (`sub_category: it_tech`) can write to this endpoint
- [ ] IT/Tech Admin is denied access to `GET /api/issues/facility` (403); Maintenance Admin is denied access to `GET /api/issues/tech` (403)
- [ ] IT/Tech Admin can update status and add notes to tech requests
- [ ] Owner and Principal can view all open issues across both namespaces via `GET /api/issues?type=all` — returns merged list with `type` field
- [ ] Category selector at intake (`tech` vs `facility`) routes to the correct collection; reassignment allowed before first action
- [ ] Frontend tool panel for IT/Tech Admin renders loading, empty, and error states

---

### Story 13: Incident, Complaint & Visitor Management

**Priority:** High
**Effort:** Medium
**PRD:** FR33–FR39, FR38a, FR38b

**As** a Receptionist, Owner, or Principal,
**I want** to log, track, and resolve complaints, incidents, and visitor entries,
**so that** nothing slips through and every issue has a documented resolution thread.

**Acceptance Criteria:**
- [ ] `POST /api/operations/visitors` logs a visitor entry: `name`, `purpose`, `student_or_staff_involved`, `outcome`
- [ ] `POST /api/operations/incidents` logs a complaint or incident: `description`, `severity` (low/medium/high), `involved_parties`
- [ ] High-severity incidents trigger in-app notifications to Owner and Principal immediately on creation (Story 16 dependency)
- [ ] `POST /api/operations/incidents/:id/thread` adds a follow-up entry; each entry stores `author_id`, `timestamp`, `content`; original record is not modified
- [ ] `GET /api/operations/incidents/:id` returns the full thread in reverse-chronological order with author and timestamp on each entry
- [ ] `PATCH /api/operations/incidents/:id/assign` — Owner or Principal assigns a follow-up to a staff member with a `due_date`
- [ ] `GET /api/operations/incidents?status=open` returns all open complaints, incidents across all types for Owner; Principal sees the same minus financial records
- [ ] Full-text search across `description` and `involved_parties` fields
- [ ] Frontend renders a thread view (scrollable, reverse-chronological), status badge, and assignment info; renders loading, empty, and error states

---

### Story 14: Announcements

**Priority:** Medium
**Effort:** Small
**PRD:** FR56, FR57

**As** a Receptionist,
**I want** to create announcements targeted at specific role groups,
**so that** information reaches the right people without WhatsApp.

**Acceptance Criteria:**
- [ ] `POST /api/operations/announcements` creates an announcement: `content`, `target_roles` (all | [role1, role2])
- [ ] Only users whose role is in `target_roles` see the announcement in their notification feed
- [ ] Announcements appear in the notification history drawer (Story 16 dependency)
- [ ] `GET /api/operations/announcements` returns announcements targeted at the calling user's role, sorted by `created_at` descending
- [ ] Announcement list supports pagination (≤ 20/page)

---

### Story 15: Transport Management

**Priority:** High
**Effort:** Medium
**PRD:** FR46–FR50

**As** a Transport Head,
**I want** to manage vehicles, route zones, and student assignments,
**so that** the transport roster is always current and visible to Owner and Principal.

**Acceptance Criteria:**
- [ ] `POST /api/transport/vehicles` creates a vehicle: `vehicle_id`, `capacity`
- [ ] `POST /api/transport/zones` creates a route zone: `name`, `description`
- [ ] `PATCH /api/students/:id` accepts a `route_zone_id` field update (Transport Head scope only)
- [ ] `GET /api/transport/roster?zone_id=X` returns all students assigned to that zone with: name, class, parent contact details
- [ ] `GET /api/transport/roster` (Owner/Principal) returns full roster across all zones: student count, zone breakdown, vehicle assignments
- [ ] Student schema includes a nullable `coordinates` field (Phase 2 route optimisation groundwork — no data collection in Phase 1)
- [ ] Transport tool panel renders loading, empty, and error states

---

### Story 16: In-App Notifications

**Priority:** High
**Effort:** Medium
**PRD:** FR80, FR37, FR44

**As** any authenticated user,
**I want** to receive in-app notifications for high-severity incidents, approval decisions, and assigned follow-ups,
**so that** I am informed without relying on WhatsApp.

**Acceptance Criteria:**
- [ ] `POST /api/notifications` (internal) creates a notification: `user_id`, `type`, `message`, `source_record_id`, `source_record_type`
- [ ] `GET /api/notifications` returns the calling user's notifications in reverse-chronological order; supports pagination
- [ ] `PATCH /api/notifications/:id/read` marks a notification as read
- [ ] Unread count is included in `GET /api/notifications/unread-count` — called on mount and after each SSE event
- [ ] Tapping a notification navigates to the source record (frontend `navigate` event or deep link)
- [ ] Notification drawer renders correctly on mobile (375px viewport)
- [ ] High-severity incident → notification to Owner and Principal
- [ ] Approval request submitted → notification to Owner (and Principal if academic-routed)
- [ ] Approval request decided → notification to submitting Admin
- [ ] Facility request resolved (owner-confirmed) → notification to Maintenance Admin
- [ ] No push notifications required for Phase 1 — in-app only

---

### Story 17: Timetable Management

**Priority:** High — required for substitution workflow
**Effort:** Medium
**PRD:** FR90, FR18

**As** a Principal or Owner,
**I want** to create and manage the school timetable,
**so that** the substitution workflow knows which staff are free during each period.

**Acceptance Criteria:**
- [ ] `POST /api/academics/timetable` creates a timetable entry: `class_id`, `period_number`, `day_of_week`, `subject_id`, `teacher_id`
- [ ] `PUT /api/academics/timetable/import` accepts a bulk import payload (array of timetable entries); validates referential integrity before committing (class exists, teacher exists, no conflicting periods for the same teacher)
- [ ] `GET /api/academics/timetable?teacher_id=X&date=Y` returns all periods for a teacher on a given day — the availability check endpoint used by the substitution workflow
- [ ] `PATCH /api/academics/timetable/:id` edits a timetable entry; full audit trail
- [ ] Timetable view in the frontend renders a weekly grid (class × period × day); renders loading, empty, and error states

---

## Phase 4 — AI & Safety Hardening

### Story 18: AI Dispatch Table — Formal Implementation

**Priority:** Critical
**Effort:** Large
**PRD:** FR8, FR9, FR10, FR86, FR87, Appendix A Dispatch Table

**As** the system,
**I want** the AI dispatch table to be formally implemented with confirm-action enforcement and an audit log,
**so that** no AI-executed mutation bypasses the safety gate.

**Acceptance Criteria:**
- [ ] All 9 write dispatches from Appendix A are implemented in `tool_functions_v2.py` with their exact parameter schemas
- [ ] Every write dispatch emits a `confirm` SSE event before executing — even if the LLM concludes the intent is obvious
- [ ] Confirmation tokens are UUID4, stored in MongoDB `confirm_tokens` collection with: `token`, `action`, `params`, `user_id`, `session_id`, `expires_at` (5 minutes from issue), `used: false`
- [ ] `POST /api/chat/confirm` accepts the token and executes the action; returns 400 if token is expired, already used, or belongs to a different session
- [ ] Confirmation tokens are bound to the issuing session — cross-session replay returns 401
- [ ] `POST /api/chat/confirm` with a valid token sets `used: true` atomically before executing the action (prevents double-execution on retry)
- [ ] Every AI-dispatched mutation is recorded in `ai_dispatch_audit_log` collection: `tool_name`, `params`, `user_id`, `session_id`, `confirmed_at`, `executed_at`
- [ ] If confirmation token validation is unavailable (DB unreachable), all write operations are rejected (fail-closed)
- [ ] All 8 query dispatches from Appendix A are implemented and do not require confirm-action

---

### Story 19: Fee Idempotency + Confirmation Token Hardening

**Priority:** Critical
**Effort:** Small
**PRD:** FR22, FR10, FR87, FR88

**As** the system,
**I want** all data-mutating endpoints to accept and honour idempotency tokens,
**so that** double-taps, network retries, and duplicate submissions cannot create duplicate records.

**Acceptance Criteria:**
- [ ] Every data-mutating API endpoint accepts an `Idempotency-Key` header
- [ ] Idempotency keys are stored in MongoDB with a TTL index of 24 hours
- [ ] Submitting the same `Idempotency-Key` within 24 hours returns the original response (HTTP 200) without re-executing the operation
- [ ] Fee payment idempotency key format `{student_id}:{fee_period}:{fee_head}` is enforced at the API layer (Story 8 extends this)
- [ ] Confirmation tokens (from Story 18) are covered by the same idempotency guarantee — replaying a `POST /api/chat/confirm` with an already-used token returns the original result, not a 400 error, so retries on network failure are safe

---

### Story 20: AI Graceful Degradation

**Priority:** High
**Effort:** Small
**PRD:** FR11, FR69

**As** any user,
**I want** the platform to continue working when Azure OpenAI is unavailable,
**so that** fee collection and attendance marking are never blocked by an AI outage.

**Acceptance Criteria:**
- [ ] When Azure OpenAI returns a timeout (>30 seconds) or connection error, `llm_client.chat()` returns a structured `{ degraded: true, message: "AI temporarily unavailable" }` result — it does not raise an exception or return a generic error string
- [ ] The SSE chat endpoint catches this result and emits a specific `{ type: "ai_unavailable" }` event to the frontend
- [ ] Frontend `ChatInterface.js` renders a clear "AI is temporarily unavailable" banner when it receives this event; the chat input is disabled
- [ ] All tool panels remain fully functional when the AI is unavailable — no tool panel endpoint calls `llm_client`
- [ ] `/api/health/ready` returns `ai: "degraded"` but `overall: "ready"` when AI is unreachable (Story 4 extension)
- [ ] If a third-party integration (biometric, fee sync) is unavailable, its SSE channel remains open and shows a "last updated X ago" indicator instead of an error state

---

## Phase 5 — Observability & Quality

### Story 21: Authorization Matrix Test Suite

**Priority:** Critical — go-live gate
**Effort:** Large
**PRD:** Testing Success, FR4, FR5, FR53

**As** the team,
**I want** automated tests that verify every role × sensitive endpoint combination,
**so that** no RBAC regression ships to production.

**Acceptance Criteria:**
- [ ] `tests/test_auth_matrix.py` covers the full matrix: Owner, Principal, Accountant, Receptionist, Transport Head, IT/Tech Admin, Maintenance Admin, Staff (teacher), Student
- [ ] For each role, tests assert: correct data is returned for permitted endpoints; 403 is returned for denied endpoints
- [ ] Tests use `httpx.AsyncClient` with the FastAPI test app (no live server required)
- [ ] MongoDB is mocked using `mongomock` or `motor-mock` — no live DB required
- [ ] Test covers namespace isolation: IT/Tech cannot read facility requests; Maintenance cannot read tech requests
- [ ] Test covers Principal fee scope: can read per-student status, cannot read aggregate financial summaries
- [ ] All tests pass in CI before any deployment

---

### Story 22: AI Tool Dispatch Tests

**Priority:** Critical — go-live gate
**Effort:** Medium
**PRD:** Testing Success — AI tool-dispatch tests

**As** the team,
**I want** automated tests for every AI-dispatched mutation,
**so that** the confirm-action gate is provably enforced.

**Acceptance Criteria:**
- [ ] `tests/test_ai_dispatch.py` covers all 9 write dispatches from Appendix A
- [ ] For each dispatch, tests assert: (1) correct execution on clear instruction with confirmed token, (2) safe rejection on ambiguous or missing parameters, (3) the confirm-action step fires and the mutation is NOT executed without it
- [ ] Tests verify that replaying an expired confirmation token returns an appropriate error without executing the mutation
- [ ] Tests verify cross-session token replay is rejected
- [ ] LLM client is mocked — tests never call Azure OpenAI

---

### Story 23: Core Route Tests

**Priority:** High
**Effort:** Medium
**PRD:** Testing Success — core route tests

**As** the team,
**I want** happy-path and auth-failure tests for all core routes,
**so that** basic regressions are caught in CI.

**Acceptance Criteria:**
- [ ] `tests/test_routes.py` covers: auth, attendance, fee collection, student CRUD, staff CRUD
- [ ] For each route: 1 happy-path test (authenticated, correct role, valid payload) + 1 auth-failure test (no token → 401, wrong role → 403)
- [ ] Fee idempotency test: two identical POST requests with the same `Idempotency-Key` → second returns original result, not a duplicate record
- [ ] Attendance correction test: hard delete attempt returns 405

---

### Story 24: Scope Resolver Unit Tests

**Priority:** High
**Effort:** Small
**PRD:** Testing Success

**As** the team,
**I want** unit tests for `scope_resolver.py` covering every role/sub-category,
**so that** RBAC policy is verified independently of the route layer.

**Acceptance Criteria:**
- [ ] `tests/test_scope_resolver.py` has one test per role/sub-category combination from the RBAC matrix
- [ ] Each test asserts the correct MongoDB filter is produced (e.g. owner → no filter, student → `{user_id: X}`)
- [ ] Unrecognised role/sub-category → scope defaults to "self only" (deny-by-default)
- [ ] Token service tests in `tests/test_token_service.py`: limit enforcement per role, graceful fallback when no balance document exists, monthly reset logic

---

### Story 25: UX States — Loading, Empty, Error on All Tool Panels

**Priority:** High
**Effort:** Medium
**PRD:** FR71, FR72, FR73

**As** any user,
**I want** every tool panel to show loading, empty, and error states,
**so that** I always understand what the platform is doing.

**Acceptance Criteria:**
- [ ] All tool panels in `frontend/src/components/tools/` render a skeleton/spinner during data fetch
- [ ] All tool panels render an empty state with contextual guidance text when the API returns zero records
- [ ] All tool panels render an error state with a retry button and recovery guidance when a fetch fails
- [ ] Write operations that fail partway through show an error state that explains what was and was not written (no silent partial write)
- [ ] No hardcoded loading text — empty and error states use language appropriate to the context (e.g. "No students found in Class 6-A" not "No data")
- [ ] All new tool panels created in Phase 3 stories include these states from day one

---

### Story 26: Theme Coherence — Dark/Light on All Panels

**Priority:** High
**Effort:** Small-Medium
**PRD:** FR74

**As** any user,
**I want** every tool panel to render correctly in both light and dark themes,
**so that** the UI is consistent and professional.

**Acceptance Criteria:**
- [ ] A grep for hardcoded colour values (`#[0-9a-fA-F]{3,6}`, `rgb(`, `hsl(`) in all tool panel `.js` files returns zero matches — all colours use Tailwind classes or CSS variables from `theme.css`
- [ ] All shadcn/ui components inherit theme correctly — no `className` overrides that hardcode colours
- [ ] Tested manually in both light and dark themes across all tool panels
- [ ] Colour contrast ratio ≥ 4.5:1 for all body text in both themes (spot-checked with a contrast checker)

---

### Story 27: Mobile Responsiveness — Owner + Principal Views

**Priority:** Critical — go-live constraint
**Effort:** Medium
**PRD:** FR75, FR76, FR83

**As** Owner (Aman) or Principal (Adesh),
**I want** all primary views to be fully usable on my phone,
**so that** I can run the school from anywhere.

**Acceptance Criteria:**
- [ ] All Owner and Principal views render without horizontal scrolling at 375px viewport width
- [ ] All touch targets are ≥ 44 × 44px
- [ ] Priority surfaces (dashboard, chat, incident log, approvals, pending actions) are accessible in the top 75% of a 375px portrait viewport
- [ ] Chat input area and confirm-action card remain visible and correctly positioned when the mobile keyboard is open (iOS Safari and Android Chrome tested)
- [ ] Owner dashboard (FR83) renders in this exact mobile priority order: open high-severity incidents → pending approvals → today's staff attendance → fee collection summary
- [ ] SSE chat reconnects automatically when a tab regains visibility on mobile (Background → Foreground)
- [ ] No overflow, no truncated action buttons, no non-tappable elements in any Owner or Principal view

---

### Story 28: SSE Real-Time — Staff Attendance + Fee Summary

**Priority:** High
**Effort:** Medium
**PRD:** NFR Real-Time Communication (SSE), FR14, FR15, FR30

**As** a Principal or Owner,
**I want** real-time staff attendance updates and fee summary updates via SSE,
**so that** I never need to refresh to see the current state.

**Acceptance Criteria:**
- [ ] `GET /api/attendance/stream` is a persistent SSE endpoint that emits an event when a staff attendance record is created or updated
- [ ] `GET /api/fees/stream` is a persistent SSE endpoint that emits an event when a fee payment is recorded; fee summary reflects the new payment within 30 seconds
- [ ] Server sends a keepalive event every 30 seconds on all SSE channels
- [ ] When a browser tab regains visibility, the client reconnects and fetches a fresh state snapshot before resuming the event stream
- [ ] Multiple tabs for the same user receive the same events but do not process them twice (session deduplication via `session_id` header)
- [ ] If the upstream data source is unavailable, the SSE channel remains open and silent; the frontend shows "last updated X ago"
- [ ] SSE route timeout configured to ≥ 300 seconds in CloudFront/ALB (deployment configuration documented and verified)

---

## Story Dependency Map

```
Story 1 (S3)              → Story 5 (student photos), Story 6 (staff photos)
Story 2 (Auth)            → All subsequent stories (auth is foundation)
Story 3 (schoolId)        → Story 21 (auth matrix tests — tests need schoolId in data)
Story 4 (health/logging)  → Story 20 (AI degradation), Story 28 (SSE)

Story 5 (Student CRUD)    → Story 7 (attendance), Story 8 (fees), Story 15 (transport)
Story 6 (Staff CRUD)      → Story 7 (attendance), Story 10 (leave requests), Story 17 (timetable)
Story 8 (Fee CRUD)        → Story 9 (discount engine)
Story 10 (Leave/Approvals)→ Story 17 (timetable — leave affects availability)
Story 16 (Notifications)  → Story 10 (approval notifications), Story 11 (maintenance notifications), Story 13 (incident notifications)
Story 17 (Timetable)      → Story 18 (AI dispatch — substitution tool)

Story 11 (Maintenance)    → Story 21 (auth matrix)
Story 12 (IT/Tech)        → Story 21 (auth matrix)
Story 18 (Dispatch table) → Story 22 (AI dispatch tests)
```

---

## Go-Live Checklist

The following stories are **hard go-live gates** — the platform must not go live without them:

- [ ] Story 1 — S3 file storage (data loss risk)
- [ ] Story 2 — Auth hardening (security risk)
- [ ] Story 4 — Health endpoint + logging (operator blind without it)
- [ ] Story 8 — Fee CRUD + idempotency (financial data integrity)
- [ ] Story 11 — Maintenance admin profile (committed to client)
- [ ] Story 18 — AI dispatch table formal implementation (safety architecture)
- [ ] Story 21 — Authorization matrix tests (RBAC verification)
- [ ] Story 22 — AI dispatch tests (confirm-action gate verification)
- [ ] Story 27 — Mobile responsiveness (Aman and Adesh use mobile daily)
