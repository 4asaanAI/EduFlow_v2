---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 12'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 12
part_name: 'Maintenance Admin Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 12: Maintenance Admin Vertical

## Pattern References

Part 9 (Principal) is the pattern-setter for `require_access(role, sub_category)` usage across all role verticals. Before implementing any role gate in this part, read Part 9's implementation to ensure consistency.

---

## Context

Part 12 targets the Maintenance Admin (`sub_category=maintenance`) vertical end-to-end. The backend routes in `issues.py` are broadly complete for facility requests, maintenance schedule, and vendor management. However, several operational gaps remain: no cost tracking on work orders, missing SLA/priority logic, incomplete lifecycle verification, and frontend coverage that diverges from available backend routes.

**Entering baseline:** 387 backend tests, 0 skipped.

**Key codebase findings from audit:**
- `MaintenanceTools.js` exports: `MaintenanceFacilityTracker`, `ITTechIssueTracker`, `MaintenanceDashboard`, `MaintenanceWorkOrders`, `MaintenanceSchedule`, `VendorLog`, `RaiseMaintenanceRequest`, `AllIssuesView`. Coverage is strong for facility/schedule/vendor. Missing: cost tracking, SLA display, escalation to owner button.
- Facility request lifecycle in `issues.py`: `open → accepted → in_progress → pending_parts → pending_owner_confirmation → done → closed`. The `accepted` status IS in `VALID_STATUSES` but `IssuePanel`/`MaintenanceWorkOrders` status options for maintenance only show `['open', 'in_progress', 'pending_owner_confirmation']` — the `accepted`, `pending_parts`, and `done` states are unreachable from the UI.
- Maintenance schedule supports `recurrence: one_time | weekly | monthly | quarterly | annual` in the backend but the UI supports it — however there is no auto-generation of next occurrence when a recurring schedule entry is marked `done`.
- Vendor management: the backend stores `category`, `rating`, `gst_number`, `tags`, `is_active`. The frontend `VendorLog.js` does not display `rating` or `tags`, and there is no preferred-vendor-per-category query endpoint.
- Photo attachments: `PhotoUploader` component exists in `MaintenanceTools.js` and uploads to `POST /api/uploads` via S3. Photos are stored as URL strings in `facility_requests.photos[]`. This works but is not tested.
- Work order costing: the `facility_requests` schema has no `estimated_cost`, `actual_cost`, or `vendor_id` fields. Vendor assignment to a specific request is not implemented at the document level.
- Priority/SLA: `VALID_PRIORITIES = {"low", "medium", "high", "urgent"}` are defined and stored, but there is no SLA calculation, no `due_date` field on facility requests, and no overdue flag.
- Escalation to owner: the only owner interaction is `POST /api/issues/facility/{id}/confirm-resolution` (which requires `pending_owner_confirmation` status). There is no proactive escalation endpoint or notification trigger for long-overdue requests.

---

## Epic P12: Maintenance Admin Vertical Hardening

### Story P12.1: Complete facility request lifecycle — missing UI states

**Problem:** The backend `VALID_STATUSES` includes `accepted`, `pending_parts`, and `done`, but `MaintenanceWorkOrders` (the primary maintenance UI) only shows `['open', 'in_progress', 'pending_owner_confirmation']` as selectable next statuses. Maintenance staff cannot mark a request as `accepted` (taking ownership) or `pending_parts` (waiting for materials) from the UI. The `done` state (pre-confirmation) is also inaccessible.

**Scope:**
- Update `RequestCard` in `MaintenanceTools.js` status options for maintenance sub_category:
  - Change `statusOptions` for `isMaint` from `['open', 'in_progress', 'pending_owner_confirmation']` to the full lifecycle: `['open', 'accepted', 'in_progress', 'pending_parts', 'pending_owner_confirmation', 'done']`
  - Guard: maintenance cannot set `closed` (already enforced in backend `PATCH /api/issues/facility/{id}`)
- Add a lifecycle progress bar or stepper UI in `RequestCard` to visualize the current stage
- Add backend unit test: maintenance admin can PATCH facility request to `accepted`, `pending_parts`, and `done` status via the API
- Add integration test: full lifecycle walk-through `open → accepted → in_progress → pending_parts → pending_owner_confirmation`, then owner calls `confirm-resolution` → `closed`

**Acceptance Criteria:**
- Maintenance admin can select `accepted`, `pending_parts`, `done` from the UI dropdown
- Backend PATCH to each status by maintenance admin returns 200
- PATCH to `closed` by maintenance admin returns 403 (existing backend rule)
- Integration test walks full lifecycle to `closed`
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P12.2: Recurring maintenance schedule auto-generation

**Problem:** The maintenance schedule supports `recurrence: weekly | monthly | quarterly | annual` in the backend, but when a recurring entry is marked `done` or `skipped`, no next occurrence is automatically created. A truly recurring preventive maintenance system requires the next scheduled entry to appear when the current one is completed.

**Scope:**
- Use a `recurrence_rule` string field following simplified iCal RRULE syntax: `FREQ=WEEKLY;BYDAY=MO,WE,FR`. When a scheduled entry is marked complete, the system auto-creates the next occurrence based on the RRULE. The next-occurrence creation is synchronous (not async) for Part 12 — async job queue is Part 16.
- Update `PATCH /api/issues/maintenance/schedule/{entry_id}` in `issues.py`:
  - When `status` is set to `done` or `skipped` AND `recurrence != "one_time"`:
    - Calculate next `scheduled_date` based on recurrence type:
      - `weekly`: +7 days
      - `monthly`: +1 month (same day)
      - `quarterly`: +3 months
      - `annual`: +1 year
    - Create a new maintenance schedule document with status `"scheduled"` and same `title`, `description`, `category`, `assigned_to`, `vendor_id`, `recurrence`, `recurrence_rule`
    - Return `{"next_occurrence": {"id": ..., "scheduled_date": ...}}` in the PATCH response
  - For `one_time` recurrence: no next occurrence created (current behavior)
- Add `GET /api/issues/maintenance/schedule/upcoming?days=30` endpoint: returns all scheduled entries with `scheduled_date` within next N days and `status == "scheduled"`
- Add unit tests: weekly recurrence creates next entry 7 days forward, monthly creates +1 month, one_time does not create next, upcoming filter returns correct entries

**Acceptance Criteria:**
- Marking a weekly recurring entry as `done` creates a new entry with `scheduled_date` +7 days
- Marking a one_time entry as `done` does NOT create a next occurrence
- `GET /api/issues/maintenance/schedule/upcoming?days=14` returns entries due within 14 days
- PATCH response includes `"next_occurrence"` key when a next entry was created (null otherwise)
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P12.3: Vendor rating and preferred-vendor-per-category

**Problem:** The vendor schema stores `rating` (0–5) and `category` fields, but there is no endpoint to retrieve the preferred (highest-rated) vendor for a given maintenance category. The frontend `VendorLog.js` does not display `rating` or `tags`. When creating a maintenance schedule entry or facility request, there is no way to suggest a preferred vendor.

**Scope:**
- Add `GET /api/issues/maintenance/vendors/preferred?category=plumbing` endpoint:
  - Returns the vendor with highest `rating` for the given category (among `is_active: true` vendors)
  - If multiple vendors tie, return all tied vendors sorted by name
  - Requires `require_role("owner", "admin")` (maintenance or principal)
- Update `VendorLog.js` to display `rating` (show as star count 0–5 using text or simple CSS) and `tags` (as small badges)
- Add `rating` input field to the `VendorLog` create form (number 0–5, optional)
- Update `PATCH /api/issues/maintenance/vendors/{id}` to allow updating `rating` independently via a dedicated `PUT /api/issues/maintenance/vendors/{id}/rate` endpoint (rating-only update, logs audit entry)
- Add unit tests: preferred endpoint returns highest-rated vendor, tie returns multiple, inactive vendor not returned

**Acceptance Criteria:**
- `GET /api/issues/maintenance/vendors/preferred?category=electrical` returns the top-rated active vendor
- Tie case returns all tied vendors
- `PUT /api/issues/maintenance/vendors/{id}/rate` with `{"rating": 4}` updates rating and writes audit log
- Frontend `VendorLog` displays rating stars and tags for each vendor
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P12.4: Work order cost tracking

**Problem:** The `facility_requests` schema has no cost fields. Maintenance admins cannot record estimated or actual cost for a work order, making it impossible to budget or report on maintenance spend. There is no vendor assignment at the request level (separate from the schedule).

**Scope:**
- Add optional fields to facility request documents:
  - `vendor_id` (string, FK to `maintenance_vendors.id`)
  - `estimated_cost` (float, optional)
  - `actual_cost` (float, optional)
  - `cost_currency` (string, default "INR")
- Update `PATCH /api/issues/facility/{id}` to accept and update these fields (maintenance admin or owner/principal only)
- Add a `GET /api/issues/facility/cost-summary` endpoint (owner/principal only):
  - Returns total estimated_cost, total actual_cost, count of requests with cost data, breakdown by category
- Add unit tests: PATCH with cost fields stores them, cost-summary returns correct totals, maintenance admin can set cost, teacher cannot set cost

**Acceptance Criteria:**
- PATCH facility request with `{"estimated_cost": 2500.00, "vendor_id": "<id>"}` stores fields
- `GET /api/issues/facility/cost-summary` returns `{total_estimated, total_actual, by_category}`
- Teacher/student PATCH to set cost returns 403
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P12.5: Priority SLA tracking and overdue flagging

**Problem:** Facility requests have `priority` (low/medium/high/urgent) but there is no `due_date`, no SLA window, and no `overdue` flag. An `urgent` request from two weeks ago looks identical to a fresh one in the list. There is no alerting mechanism for overdue work orders.

**Scope:**
- Define SLA windows by priority (configurable via school settings in future; hardcoded for now):
  - `urgent`: 4 hours
  - `high`: 24 hours
  - `medium`: 72 hours
  - `low`: 168 hours (7 days)
- On `POST /api/issues/facility`:
  - Compute and store `due_at` = `created_at` + SLA_HOURS[priority] as ISO string
- Add a computed `is_overdue` field in `GET /api/issues/facility` response:
  - `true` if `status` is not `closed` AND current time > `due_at`
  - Computed at query time (not stored — avoid stale data)
- Add `GET /api/issues/facility?overdue=true` filter to list endpoint
- Update `MaintenanceWorkOrders` and `MaintenanceDashboard` to show overdue badge (red highlight) for overdue items
- Add `overdue` count to `MaintenanceDashboard` stat cards
- Add unit tests: urgent request has due_at 4h from creation, is_overdue true after SLA window, overdue filter returns correct results

**Acceptance Criteria:**
- POST facility request response includes `due_at` field
- GET facility requests response includes `is_overdue` boolean per item
- `GET /api/issues/facility?overdue=true` returns only overdue items
- Dashboard stat card shows overdue count
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P12.6: Photo attachment backend verification

**Problem:** The `PhotoUploader` component in `MaintenanceTools.js` uploads images to `POST /api/uploads` and stores URLs in `facility_requests.photos[]`. The backend `create_facility_request` accepts `photos: [url1, url2, ...]` from the JSON body. However, there is no test verifying: (1) that photos URLs stored in a facility request are accessible S3 URLs, (2) that the frontend correctly passes the `entity_type=maintenance_request` to the uploads API, and (3) that the photos array is correctly stored and returned.

**Scope:**
- Add integration tests for photo attachment flow:
  - POST /api/issues/facility with `photos: ["https://s3.../photo1.jpg"]` stores URL
  - GET /api/issues/facility returns the `photos[]` array in each item
  - PATCH /api/issues/facility/{id} can append additional photos (not overwrite) — add `photos_append` field to PATCH body that pushes to the array rather than replacing it
- Add backend validation: photos array items must be valid URLs (start with `http://` or `https://`)
- Add `photos_append` parameter to `PATCH /api/issues/facility/{id}` that does `$push` into the `photos` array (max 5 total)
- Verify `entity_type=maintenance_request` is correctly tagged in uploads (add a check for this in existing upload integration test)
- Add unit tests: invalid URL in photos returns 400, photos_append adds to array, max 5 photos enforced

**Acceptance Criteria:**
- POST with invalid URL in photos returns 400
- PATCH with `photos_append` adds URLs to existing array
- Photos array never exceeds 5 items (6th photo returns 400)
- GET returns photos array with all stored URLs
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P12.7: Escalation to owner for long-overdue requests

**Problem:** Maintenance admins have no way to proactively escalate an unresolved request to the school owner. The only owner touchpoint is the `confirm-resolution` endpoint (pull model). There is no push escalation: a 3-day-old urgent request sitting in `in_progress` with no update cannot be flagged to the owner without manual intervention.

**Scope:**
- Add `POST /api/issues/facility/{id}/escalate` endpoint:
  - Allowed by: maintenance admin, principal, or owner
  - Validates that status is not `closed` or `done`
  - Writes a notification to all users with `role=owner` using the existing `_notify()` helper in `issues.py`
  - Stores escalation record in facility request: `escalated_at`, `escalated_by`, `escalation_reason`
  - Prevents re-escalation within 1 hour (returns 429 if `escalated_at` is less than 1 hour ago)
- Add `GET /api/issues/facility/{id}` single-record endpoint (currently missing — only list exists):
  - Returns full facility request by id with all fields including `notes[]`, `photos[]`, `escalated_at`
- Add unit tests: escalation creates notification for owner, re-escalation within 1 hour returns 429, single-record GET returns correct data, non-maintenance/principal cannot escalate (403)

**Acceptance Criteria:**
- POST escalate writes owner notification and stores escalation metadata
- Re-escalation within 1 hour returns HTTP 429
- `GET /api/issues/facility/{id}` returns single record with full detail
- Teacher calling escalate returns 403
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

## Epic P12: FR Coverage Map

| FR # | Route / Component | Gap Identified | Story |
|------|-------------------|----------------|-------|
| FR1 | `MaintenanceWorkOrders.js` status options | `accepted`, `pending_parts`, `done` unreachable from UI | P12.1 |
| FR2 | `PATCH /api/issues/maintenance/schedule/{id}` | No recurring next-occurrence generation | P12.2 |
| FR3 | `GET /api/issues/maintenance/vendors` | No preferred-vendor-by-category endpoint, rating/tags not in UI | P12.3 |
| FR4 | `PATCH /api/issues/facility/{id}` | No cost fields (`estimated_cost`, `actual_cost`, `vendor_id`) | P12.4 |
| FR5 | `POST /api/issues/facility` + list | No SLA `due_at`, no `is_overdue` flag | P12.5 |
| FR6 | `POST /api/issues/facility` photo flow | No validation on photo URLs, no `photos_append` PATCH | P12.6 |
| FR7 | `POST /api/issues/facility/{id}/escalate` | No escalation endpoint, no single-record GET | P12.7 |

---

## Epic P12: NFRs

**NFR12.1 — Schema Additivity:**
All new fields added to `facility_requests` documents (`due_at`, `vendor_id`, `estimated_cost`, `actual_cost`, `escalated_at`, `escalated_by`) must be optional with sensible null defaults. Existing documents without these fields must continue to work — the `is_overdue` field is computed, not stored.

**NFR12.2 — SLA Configurability Path:**
SLA windows must be defined as a named constant dict `FACILITY_SLA_HOURS` in `issues.py` at module level (not inline), so they can later be made configurable via school settings. A code comment must note this upgrade path.

**NFR12.3 — Recurring Schedule Idempotency:**
The next-occurrence creation on schedule completion must be idempotent if called twice (e.g., a retry). Check for an existing future entry with the same `title` and `scheduled_date` before inserting; if found, return the existing entry rather than creating a duplicate.

**NFR12.4 — Test Coverage:**
Each story must add at minimum the number of unit/integration tests stated in its Acceptance Criteria. Total new tests for Part 12 must be at least 28. All new tests must pass alongside the 387 baseline.

**NFR12.5 — Test Data:**
All test data creation must use `tests/backend/factories.py` (created in pre-Part-9 infrastructure story). Do NOT create one-off inline test dicts — they fragment into inconsistent formats across parts.

---

## Epic P12: Full Stories with Given/When/Then ACs

### Story P12.S1: Full facility request lifecycle walk-through

**Given** a maintenance admin logs a new facility request (`POST /api/issues/facility`) with priority `high`
**When** the request is created
**Then** the response includes `status: "open"` and `due_at` set to 24 hours from `created_at`

**Given** the request is `status: "open"`
**When** the maintenance admin sends `PATCH /api/issues/facility/{id}` with `{"status": "accepted"}`
**Then** the response returns HTTP 200 with `status: "accepted"`

**Given** the request is `status: "in_progress"`
**When** the maintenance admin sends `PATCH` with `{"status": "pending_parts", "note": "Waiting for pipes from vendor"}`
**Then** the status is updated and the `notes` array includes the new entry

**Given** the request is `status: "pending_owner_confirmation"`
**When** the owner calls `POST /api/issues/facility/{id}/confirm-resolution`
**Then** the status moves to `"closed"` and the maintenance admin receives a notification

---

### Story P12.S2: Recurring maintenance schedule auto-generates next occurrence

**Given** a monthly recurring schedule entry for "Generator Service" exists with `scheduled_date: 2026-05-01` and `status: "scheduled"`
**When** the maintenance admin patches the entry with `{"status": "done"}`
**Then** the API response includes `"next_occurrence": {"scheduled_date": "2026-06-01", "id": "<new_id>"}` and a new `scheduled` entry is visible in the schedule list

**Given** the same scenario for a `one_time` recurrence entry
**When** it is marked as `done`
**Then** the response includes `"next_occurrence": null` and no new entry is created

**Given** a network error causes the PATCH to be retried and a next-occurrence entry was already created
**When** the retry attempts to create the same next-occurrence
**Then** the API returns the existing next-occurrence without creating a duplicate

---

### Story P12.S3: Work order cost tracking by maintenance admin

**Given** a facility request `id` exists with `status: "in_progress"`
**When** the maintenance admin sends `PATCH /api/issues/facility/{id}` with `{"estimated_cost": 3500.00, "vendor_id": "<vendor_id>"}`
**Then** the facility request document stores `estimated_cost: 3500.00` and `vendor_id`

**Given** multiple facility requests with `estimated_cost` values exist
**When** an owner calls `GET /api/issues/facility/cost-summary`
**Then** the response returns `{"total_estimated": <sum>, "total_actual": <sum>, "by_category": {...}}`

**Given** a teacher user attempts `PATCH /api/issues/facility/{id}` with cost fields
**When** the request is processed
**Then** the API returns HTTP 403

---

### Story P12.S4: Escalation to owner for overdue request

**Given** a facility request has been `in_progress` for 48 hours past its `due_at` SLA
**When** the maintenance admin sends `POST /api/issues/facility/{id}/escalate` with `{"reason": "Vendor not responding"}`
**Then** the API returns HTTP 200 and the owner receives a notification
**And** the facility request document stores `escalated_at` and `escalated_by`

**Given** the same request was escalated 30 minutes ago
**When** `POST /api/issues/facility/{id}/escalate` is called again
**Then** the API returns HTTP 429 with message "Already escalated within the last hour"

**Given** a teacher user calls `POST /api/issues/facility/{id}/escalate`
**When** the request is processed
**Then** the API returns HTTP 403

---

### Story P12.S5: Vendor preferred selection for maintenance category

**Given** three vendors exist for category `plumbing` with ratings 3, 5, 4 (all active)
**When** `GET /api/issues/maintenance/vendors/preferred?category=plumbing` is called
**Then** the API returns the vendor with `rating: 5`

**Given** two vendors exist for category `electrical` with equal rating 4 (both active)
**When** `GET /api/issues/maintenance/vendors/preferred?category=electrical` is called
**Then** the API returns both vendors sorted by name

**Given** a vendor has `is_active: false`
**When** `GET /api/issues/maintenance/vendors/preferred?category=plumbing` is called
**Then** the inactive vendor is NOT included in results even if its rating is highest

---

## Epic P12: Implementation Order

1. P12.1 — Complete lifecycle UI states (frontend + backend unit tests, low risk)
2. P12.5 — SLA and overdue flag (additive fields on POST, computed on GET)
3. P12.6 — Photo attachment verification (test coverage + validation hardening)
4. P12.4 — Cost tracking fields (additive schema change + new summary endpoint)
5. P12.3 — Vendor rating and preferred endpoint (new GET endpoint + frontend update)
6. P12.7 — Escalation + single-record GET (new endpoints)
7. P12.2 — Recurring schedule auto-generation (logic change in PATCH handler — highest risk, do last)

---

## Epic P12: Retrospective

A retrospective entry for Part 12 to be completed after all P12.1–P12.7 stories are done.
