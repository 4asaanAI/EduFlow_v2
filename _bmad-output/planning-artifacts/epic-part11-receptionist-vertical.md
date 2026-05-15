---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 11'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 11
part_name: 'Receptionist Role Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 11: Receptionist Role Vertical

## Context

Part 11 targets the Receptionist sub_category admin vertical end-to-end. The receptionist is the school's front-desk role: they log enquiries, welcome visitors, issue bonafide certificates, file complaints on behalf of parents, and handle support queries. Several backend routes already accept `sub_category=receptionist` in their allow-lists, but the vertical has never been audited holistically — RBAC gaps, missing stage-transition logic, duplicate visitor detection, and SMS-to-parent access are all unverified.

**Entering baseline:** 387 backend tests, 0 skipped. `project-context.md` refreshed at `e260247`.

**Key codebase findings from audit:**
- `GET /api/ops/enquiries` and `POST /api/ops/enquiries` accept `require_role("owner", "admin")` — receptionist IS an admin, so access works, but PATCH `/enquiries/{id}` does a bare `$set` with no stage-transition validation and no notes history.
- `POST /api/ops/visitors` accepts `require_role("owner", "admin")` — receptionist can log, but no duplicate detection (same `visitor_name` same day), no missed-checkout alert.
- `GET /api/queries` has no role filter — receptionist sees ALL school queries (including teacher IT tickets). Query assignment to staff is not implemented.
- `POST /api/ops/certificates` accepts `require_role("admin", "owner")` — any admin (including receptionist) can issue. No approval flow, no approval required sub_category gate.
- `GET /api/search` works for all roles but does not include guardian phone lookup for students.
- `POST /api/ops/complaints` is open to all authenticated users (`get_current_user`). No department routing, no on_behalf_of parent pattern.
- `GET/POST /api/settings/forms` — GET is open, POST requires `require_role("admin", "owner")`. Receptionist can use forms but cannot create them without principal/owner role.
- `POST /api/sms/send-parent-message` requires `require_role("admin", "owner")` — receptionist is admin, so technically accessible, but the SMS tool list in `search.py:TOOLS_BY_ROLE["admin"]` does not include an SMS shortcut for receptionist.

---

## Epic P11: Receptionist Role Vertical Hardening

### Story P11.1: Enquiry stage-transition validation and notes history

**Problem:** `PATCH /api/ops/enquiries/{enquiry_id}` performs a bare `$set` with no constraints — any admin can set `status` to any arbitrary value (e.g. `enrolled` directly from `new`) skipping the `contacted` stage. There is no notes/timeline history on enquiries, so there is no audit trail of follow-up calls or meetings. The `assigned_to` field is set to the creating user at creation but never updated on reassignment.

**Scope:**
- Define the canonical enquiry stage machine in `operations.py`:
  - Valid statuses: `new → contacted → scheduled_visit → enrolled` OR `new → contacted → rejected`
  - Guard `PATCH /api/ops/enquiries/{id}` to only allow valid forward transitions (no backward jumps unless by owner/principal)
  - Reject bare body `$set` that does not match allowed transition map
- Add `notes` array to enquiry documents: each note has `author_id`, `author_name`, `content`, `timestamp`
- `PATCH /api/ops/enquiries/{id}` should accept optional `note` string in body and append to `notes[]`
- Add `assigned_to` update: allow reassigning enquiry to another admin user id, validate the user exists and has `role=admin`
- Add audit log entry on each state change with `from_status`, `to_status`, `note`
- Add integration test: receptionist moves enquiry new→contacted→enrolled, verify intermediate status rejected, verify notes history

**Acceptance Criteria:**
- Invalid status transitions return HTTP 400 with message explaining valid next states
- `GET /api/ops/enquiries/{id}` returns `notes[]` array (may be empty)
- Audit log entry written on each transition
- Backward transition (enrolled→new) returns 403 for receptionist, succeeds for owner
- At least 4 unit tests covering the state machine
- Existing 387 tests still pass

---

### Story P11.2: Visitor duplicate detection and missed-checkout alerts

**Problem:** `POST /api/ops/visitors` does not check for an existing open visitor record with the same `visitor_name` on the same calendar day. A receptionist can log the same person twice without warning. Additionally, there is no mechanism to alert staff when a visitor checked in more than N hours ago has not checked out.

**Scope:**
- Add duplicate detection in `POST /api/ops/visitors`:
  - Before inserting, query `db.visitor_log` for a record with same `visitor_name` (case-insensitive) where `time_out` is null AND `time_in` is within the current calendar day
  - If found, return HTTP 409 with `{"success": false, "duplicate": true, "existing_id": "<id>", "detail": "Visitor already checked in today"}` — caller may force-create by passing `force: true` in body
- Add a `GET /api/ops/visitors/pending-checkout` endpoint:
  - Returns all visitor_log entries where `time_out` is null and `time_in` is older than 4 hours (configurable via query param `stale_hours`, default 4)
  - Requires `require_role("owner", "admin")`
- Add frontend hint: `IncidentTracker.js` visitor log tab should show a badge count of pending checkouts (call the new endpoint)
- Add unit tests: duplicate detection, force override, pending-checkout filter

**Acceptance Criteria:**
- Duplicate visitor same day returns 409 before any DB write
- `force: true` body param bypasses duplicate check and creates the record
- `GET /api/ops/visitors/pending-checkout` returns only unchecked-out visitors older than stale_hours
- At least 4 unit tests
- Existing 387 tests still pass

---

### Story P11.3: Support ticket visibility and staff assignment for receptionist

**Problem:** `GET /api/queries` returns ALL school tickets to any authenticated user (no role-based narrowing). A receptionist front-desk staff can see teachers' private IT complaints and confidential queries. Additionally, the queries schema has no `assigned_to` field — tickets cannot be routed to a specific staff member.

**Scope:**
- Add role-based visibility narrowing to `GET /api/queries`:
  - `it_tech` admin: sees all tickets (current behavior, correct)
  - `owner` / `principal` admin: sees all tickets
  - `receptionist` admin: sees all tickets (front-desk triage role — intentional, document in code comment)
  - `teacher` / `student` / other roles: see only their own tickets (`created_by == user["id"]`)
- Add `assigned_to` and `assigned_to_name` fields to the ticket schema:
  - `POST /api/queries` — `assigned_to` defaults to null
  - New endpoint `PATCH /api/queries/{id}/assign` — requires `it_tech` or `receptionist` admin; accepts `assigned_to` (user_id)
  - `GET /api/queries` — add optional `assigned_to` filter param
- Add at least 5 unit tests: teacher sees own tickets only, receptionist sees all, it_tech can assign, receptionist can assign, student sees own only

**Acceptance Criteria:**
- Teacher/student GET /api/queries returns only own tickets
- Receptionist GET /api/queries returns all school tickets
- `PATCH /api/queries/{id}/assign` succeeds for receptionist and it_tech; returns 403 for teacher
- Existing queries list response shape unchanged (backwards compatible)
- At least 5 unit tests
- Existing 387 tests still pass

---

### Story P11.4: Certificate issuance approval gate for bonafide

**Problem:** `POST /api/ops/certificates` accepts `require_role("admin", "owner")` with no sub_category check — any admin including a receptionist or accountant can issue a bonafide or TC certificate. There is no approval workflow. In most schools, certificate issuance requires principal approval.

**Scope:**
- Add a `cert_type` to approval routing table in `operations.py`:
  - `bonafide`: can be issued directly by `principal` admin or `owner`; a `receptionist` admin must submit for principal approval (`status: "pending_approval"`)
  - `tc` (transfer certificate): requires principal or owner regardless of requester role
  - `character`, `merit`: same as bonafide
- Update `POST /api/ops/certificates`:
  - If requester is `receptionist` admin and cert_type requires approval, set `status: "pending_approval"` (not `"generated"`)
  - If requester is `principal` admin or `owner`, set `status: "generated"` immediately
- Add `PATCH /api/ops/certificates/{cert_id}/approve` — requires `require_owner_or_principal`, moves status from `pending_approval` to `generated`
- Add `PATCH /api/ops/certificates/{cert_id}/reject` — requires `require_owner_or_principal`, moves status to `rejected` with mandatory `reason`
- Add unit tests: receptionist creates → pending, principal creates → generated, owner approves pending, principal rejects with reason

**Acceptance Criteria:**
- Receptionist POST /api/ops/certificates returns `status: "pending_approval"` for bonafide/tc/character
- Principal POST /api/ops/certificates returns `status: "generated"`
- PATCH approve succeeds for principal/owner; returns 403 for receptionist
- PATCH reject requires `reason`; returns 400 if missing
- At least 5 unit tests
- Existing 387 tests still pass

---

### Story P11.5: Student search by guardian phone for front-desk

**Problem:** `GET /api/search?q=<term>` searches students by `name` and `admission_number` only. A receptionist at the front desk needs to look up a student when a parent calls or walks in — typically the parent gives a phone number, not a student name. The `guardian_phone` field exists in student records but is not searchable.

**Scope:**
- Add `guardian_phone` to the student search query in `search.py`:
  - In the student_query `$or` array, add `{"guardian_phone": {"$regex": q_safe, "$options": "i"}}`
  - Also add `{"parent_name": {"$regex": q_safe, "$options": "i"}}` for parent name lookups
- Add `guardian_phone` (last 4 digits masked: `XXXX XXXX 4321`) to the search result subtitle for receptionist role
- For `role=receptionist` admin in `TOOLS_BY_ROLE`, add a front-desk specific tool entry (`visitor-log`, `enquiry-register`, `certificate-generator`, `complaint-tracker`, `query-support`)
- Add unit tests: search by guardian_phone returns correct student, search by parent_name returns match, teacher role does not see guardian_phone in subtitle

**Acceptance Criteria:**
- `GET /api/search?q=9876543210` returns matching student if guardian_phone matches
- `GET /api/search?q=Sharma` returns students whose parent_name matches
- Receptionist-role search result subtitles include masked phone
- `TOOLS_BY_ROLE["admin"]` still works; receptionist sub_category tools are additive
- At least 3 unit tests
- Existing 387 tests still pass

---

### Story P11.6: Complaint on-behalf-of pattern and department routing

**Problem:** `POST /api/ops/complaints` uses `submitted_by: user["id"]` — the receptionist cannot file a complaint on behalf of a parent who walks in or calls. The `category` field exists but there is no routing logic: complaints are not directed to any department or staff. `PATCH /api/ops/complaints/{id}` does a bare `$set` with no status validation.

**Scope:**
- Add `on_behalf_of_name` and `on_behalf_of_phone` optional fields to `POST /api/ops/complaints`:
  - If present, stored verbatim; `submitted_by` remains the logged-in user's id
  - `on_behalf_of_name` is returned in list responses
- Add `routed_to` field (user_id or role label) to complaints:
  - Add routing map in `operations.py`: category → default role
    - `academic` → `principal`
    - `fees` → `accountant`
    - `transport` → `admin` (generic)
    - `facility` → `maintenance`
    - `other` → `principal`
  - On `POST /api/ops/complaints`, auto-populate `routed_to` from routing map
  - Allow override via `routed_to` in request body
- Add complaint status machine: `open → acknowledged → in_progress → resolved → closed`
- Guard `PATCH /api/ops/complaints/{id}` status transitions (only owner/admin can advance; submitter can view but not change status)
- Add unit tests: on_behalf_of fields stored, routing map applied per category, invalid status transition rejected

**Acceptance Criteria:**
- POST /api/ops/complaints with `on_behalf_of_name` stores and returns the field
- `routed_to` is auto-populated based on `category`
- Status backward transition returns 403 for receptionist
- At least 4 unit tests
- Existing 387 tests still pass

---

### Story P11.7: Custom form usage for enquiry intake

**Problem:** `GET /api/settings/forms` is open to all roles; `POST /api/settings/forms` requires `require_role("admin", "owner")`. The receptionist can read and submit forms but cannot create new ones. More importantly, there is no mechanism to link a custom form submission to an enquiry or visitor record — form responses float unattached to any entity.

**Scope:**
- Add `entity_type` and `entity_id` optional fields to `POST /api/settings/forms/{form_id}/responses`:
  - Store in form response document
  - Index on `(form_id, entity_type, entity_id)` for lookup
- Add `GET /api/settings/forms/{form_id}/responses?entity_type=enquiry&entity_id=<id>` filter to list endpoint (already requires `require_role("admin", "owner")`)
- Update `custom_forms` documents to include an optional `use_case` tag (values: `enquiry_intake`, `visitor_registration`, `general`)
- Add a `GET /api/ops/enquiries/{enquiry_id}/forms` convenience endpoint that returns form responses linked to the enquiry
- Verify receptionist can: list forms, submit responses, retrieve linked responses — but cannot create or delete forms (enforce in unit tests)
- Add at least 4 unit tests

**Acceptance Criteria:**
- POST form response with `entity_type=enquiry` and `entity_id` stores linkage
- GET /api/ops/enquiries/{id}/forms returns linked responses
- Receptionist can submit form responses (200), cannot create forms (403)
- At least 4 unit tests
- Existing 387 tests still pass

---

### Story P11.8: Verify SMS-to-parent access for receptionist role

**Problem:** `POST /api/sms/send-parent-message` requires `require_role("admin", "owner")`. The receptionist is an admin, so the route is technically accessible — but the `TOOLS_BY_ROLE` map in `search.py` does not include an SMS shortcut for admin sub_category=receptionist, and there is no test verifying that a receptionist JWT can successfully call the SMS endpoint.

**Scope:**
- Add an explicit test: receptionist admin (`role=admin, sub_category=receptionist`) calling `POST /api/sms/send-parent-message` returns 200 (or the expected Twilio mock response) — not 403
- Add an explicit test: `POST /api/sms/send-fee-reminder` also accessible to receptionist
- Verify `GET /api/sms/config-status` is accessible to receptionist (shows Twilio config state)
- Confirm the SMS rate limiting (if any) does not inadvertently block receptionist sub_category
- If receptionist should NOT have SMS access for any endpoint, document it with a `# rbac: intentional` comment and add a 403 test
- Add 3 unit tests covering the scenarios above

**Acceptance Criteria:**
- Explicit test verifies receptionist can call `POST /api/sms/send-parent-message` without 403
- `GET /api/sms/config-status` accessible to receptionist
- If any SMS endpoint should be blocked for receptionist, it has a documented 403 test and code comment
- At least 3 unit tests
- Existing 387 tests still pass

---

## Epic P11: FR Coverage Map

| FR # | Route / Component | Gap Identified | Story |
|------|-------------------|----------------|-------|
| FR1 | `PATCH /api/ops/enquiries/{id}` | No stage-transition validation, no notes history | P11.1 |
| FR2 | `POST /api/ops/visitors` | No duplicate detection, no pending-checkout endpoint | P11.2 |
| FR3 | `GET /api/queries` | No role-based visibility narrowing, no assignment | P11.3 |
| FR4 | `POST /api/ops/certificates` | No approval gate for receptionist, no approve/reject endpoints | P11.4 |
| FR5 | `GET /api/search` | Missing guardian_phone and parent_name lookup | P11.5 |
| FR6 | `POST /api/ops/complaints` | No on_behalf_of, no department routing, bare status update | P11.6 |
| FR7 | `POST /api/settings/forms/{id}/responses` | No entity linkage, no enquiry-form convenience endpoint | P11.7 |
| FR8 | `POST /api/sms/*` | No explicit receptionist access test | P11.8 |

---

## Epic P11: NFRs

**NFR11.1 — Backward Compatibility:**
All existing API response shapes for `/api/ops/enquiries`, `/api/ops/visitors`, `/api/queries`, `/api/ops/complaints`, and `/api/ops/certificates` must remain backwards-compatible. New fields are additive only; no existing fields may be renamed or removed.

**NFR11.2 — Stage-Transition Auditability:**
Every status change on enquiries, complaints, and certificates must produce an audit log entry in `db.audit_logs` using the existing `_audit_doc()` helper in `operations.py`. Audit entries must include `from_status`, `to_status`, `changed_by`, and `reason` (if applicable).

**NFR11.3 — Test Coverage:**
Each story must add at minimum the number of unit/integration tests stated in its Acceptance Criteria. Total new tests for Part 11 must be at least 32. All new tests must pass alongside the 387 baseline.

**NFR11.4 — RBAC Documentation:**
Every route that has a deliberate RBAC decision (e.g., receptionist sees all queries, receptionist SMS access) must have a `# rbac: intentional — <reason>` comment in the route handler. This prevents future regressions from well-meaning hardening sweeps.

---

## Epic P11: Full Stories with Given/When/Then ACs

### Story P11.S1: Enquiry stage machine prevents invalid transitions

**Given** a school has an enquiry with `status: "new"` logged by a receptionist admin
**When** the receptionist sends `PATCH /api/ops/enquiries/{id}` with body `{"status": "enrolled"}`
**Then** the API returns HTTP 400 with `detail` explaining that `new` can only transition to `contacted`

**Given** the enquiry is now `status: "contacted"`
**When** the receptionist sends `PATCH /api/ops/enquiries/{id}` with `{"status": "enrolled", "note": "Parent confirmed admission"}`
**Then** the API returns HTTP 200, the status is updated to `enrolled`, and the notes array contains the new entry with `author_name` and `timestamp`

**Given** the enquiry is `status: "enrolled"`
**When** a receptionist tries `PATCH` with `{"status": "new"}`
**Then** the API returns HTTP 403 (backward transition forbidden for receptionist)

**Given** an owner user tries the same backward transition
**When** `PATCH` with `{"status": "new"}` is called with owner JWT
**Then** the API returns HTTP 200 (owner bypass allowed)

**Given** a receptionist calls `GET /api/ops/enquiries`
**When** the response is received
**Then** each enquiry includes a `notes` array field (may be empty) in the response body

---

### Story P11.S2: Visitor duplicate detection at check-in

**Given** a visitor named "Rajesh Sharma" was checked in at 9:00 AM today (time_out is null)
**When** a receptionist calls `POST /api/ops/visitors` with `{"visitor_name": "Rajesh Sharma", "purpose": "Meeting"}`
**Then** the API returns HTTP 409 with `{"success": false, "duplicate": true, "existing_id": "<id>", "detail": "Visitor already checked in today"}`

**Given** the receptionist adds `"force": true` to the same request body
**When** `POST /api/ops/visitors` is called with force=true
**Then** the API returns HTTP 200 and creates a second check-in record for Rajesh Sharma

**Given** a visitor checked in 5 hours ago has not checked out
**When** a receptionist calls `GET /api/ops/visitors/pending-checkout` (default stale_hours=4)
**Then** the response includes that visitor's record

**Given** a visitor checked in 2 hours ago has not checked out
**When** `GET /api/ops/visitors/pending-checkout` is called with default stale_hours=4
**Then** that visitor is NOT included in the response

---

### Story P11.S3: Complaint on-behalf-of parent

**Given** a receptionist is logged in and a parent walks in with a fee complaint
**When** the receptionist calls `POST /api/ops/complaints` with `{"subject": "Fee overcharge", "description": "...", "category": "fees", "on_behalf_of_name": "Mrs. Meena Gupta", "on_behalf_of_phone": "9876543210"}`
**Then** the API returns HTTP 200 and the complaint document stores `on_behalf_of_name` and `on_behalf_of_phone`
**And** the `routed_to` field is auto-populated with `"accountant"` based on category routing map

**Given** the same complaint exists
**When** `GET /api/ops/complaints` is called by an accountant admin
**Then** the complaint appears in the list with `on_behalf_of_name` visible

**Given** the complaint has `status: "open"`
**When** the receptionist tries `PATCH /api/ops/complaints/{id}` with `{"status": "resolved"}`
**Then** the response is HTTP 403 (receptionist cannot self-advance complaints past `acknowledged`)

---

### Story P11.S4: Certificate issuance approval gate

**Given** a receptionist admin calls `POST /api/ops/certificates` with `{"student_id": "<id>", "cert_type": "bonafide"}`
**When** the request is processed
**Then** the response returns `{"status": "pending_approval"}` and does NOT set `status: "generated"`

**Given** a principal admin calls `POST /api/ops/certificates` with `{"student_id": "<id>", "cert_type": "bonafide"}`
**When** the request is processed
**Then** the response returns `{"status": "generated"}` immediately (no approval step)

**Given** a certificate has `status: "pending_approval"`
**When** the principal calls `PATCH /api/ops/certificates/{cert_id}/approve`
**Then** the certificate status changes to `"generated"` and an audit log entry is written

**Given** a certificate has `status: "pending_approval"`
**When** the principal calls `PATCH /api/ops/certificates/{cert_id}/reject` with `{"reason": "Student record incomplete"}`
**Then** the certificate status changes to `"rejected"` and the `rejection_reason` is stored

---

### Story P11.S5: Student guardian phone search

**Given** a student record has `guardian_phone: "9876543210"` and `parent_name: "Rajesh Verma"`
**When** a receptionist calls `GET /api/search?q=9876543210`
**Then** the search response includes the student with their name in results

**Given** the same student record
**When** `GET /api/search?q=Rajesh` is called
**Then** the student appears in results (matched via parent_name)

**Given** a teacher calls `GET /api/search?q=9876`
**When** the response is received
**Then** the search result subtitle does NOT include the raw guardian_phone (masked or omitted per role)

---

## Epic P11: Implementation Order

1. P11.3 — Query visibility narrowing (lowest risk, pure read-path change)
2. P11.5 — Guardian phone search (additive only, no write changes)
3. P11.8 — SMS receptionist access verification (test-only, no code changes expected)
4. P11.2 — Visitor duplicate detection (new read + 409 path, new endpoint)
5. P11.1 — Enquiry stage machine (requires schema + logic change)
6. P11.6 — Complaint routing + on_behalf_of (additive fields + status machine)
7. P11.4 — Certificate approval gate (RBAC + new endpoints)
8. P11.7 — Form entity linkage (new fields + convenience endpoint)

---

## Epic P11: Retrospective

A retrospective entry for Part 11 to be completed after all P11.1–P11.8 stories are done.
