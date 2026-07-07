---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 13'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 13
part_name: 'IT-Tech Admin Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 13: IT-Tech Admin Vertical

## Pattern References

Part 9 (Principal) is the pattern-setter for `require_access(role, sub_category)` usage across all role verticals. Before implementing any role gate in this part, read Part 9's implementation to ensure consistency.

---

## Context

Part 13 targets the IT-Tech Admin (`sub_category=it_tech`) vertical end-to-end. The IT-tech role owns tech issue tracking and is the implied system administrator for the school platform. Several critical system-level operations (audit log access, user password reset, AI token budget visibility, import tool access, branch configuration) have inconsistent or undocumented RBAC decisions for this role.

**Entering baseline:** 387 backend tests, 0 skipped.

**Key codebase findings from audit:**
- `POST /api/issues/tech` uses `require_access("owner", "admin", sub_category="it_tech")` — Part 4 hardened this correctly. However, `GET /api/issues/tech` uses a manual `_is_it(user)` check (not `require_access`), creating inconsistency between POST and GET auth patterns.
- `GET /api/audit-log` accepts `owner` and any admin with `sub_category in ("principal", None, "")` — IT-tech is explicitly excluded. This is an intentional decision but undocumented and untested.
- `GET /api/health/ready` (health check endpoint) is public or token-free in most FastAPI setups — no frontend exposes this to IT-tech. No test verifies that IT-tech can see health check output in the UI.
- User management: no password reset endpoint exists. There is no `POST /api/auth/admin-reset-password` or account unlock mechanism in `auth.py`. This is a complete gap for the IT-tech role.
- Token usage: `GET /api/settings/token-usage` returns only the calling user's own usage. There is no endpoint for IT-tech to see aggregated token usage across all users or set a limit for a specific user.
- Integration health: `GET /api/sms/config-status` exists and requires `require_role("admin", "owner")` — accessible to IT-tech. However, S3 connectivity, Azure OpenAI connection status, and database connectivity are not exposed via any API endpoint beyond `/health/ready`.
- Import tool: `POST /api/import/validate` and `POST /api/import/commit` both use `require_owner` — IT-tech is explicitly excluded. This is likely intentional (data import is destructive) but undocumented.
- Branch configuration: `PATCH /api/settings/school` uses `require_owner` — IT-tech cannot manage branch settings. `GET /api/settings/school` is open to all. No branch-add endpoint is documented or accessible to IT-tech.

---

## Epic P13: IT-Tech Admin Vertical Hardening

### Story P13.1: Align GET /api/issues/tech auth with require_access pattern

**Problem:** `POST /api/issues/tech` uses `Depends(require_access("owner", "admin", sub_category="it_tech"))` — the canonical Part 4 pattern. But `GET /api/issues/tech` uses a manual `_is_it(user)` inline check. `PATCH /api/issues/tech/{id}` also uses an inline `_is_it()` check. This inconsistency means future changes to the `require_access` helper would not automatically apply to GET and PATCH, and the intent is not self-documenting.

**Scope:**
- Migrate `GET /api/issues/tech` authentication from inline `_is_it()` to use `Depends(require_access('owner', 'admin', sub_category='it_tech'))` — matching the POST endpoint. The GET handler must use the same `require_access` dependency injection pattern, not an inline check.
  - GET should additionally allow `admin` with `sub_category=principal` (viewing is intentionally broader than creating). Use a second dependency or document this extension with `# rbac: intentional — principals can view all tech requests`.
- Migrate `PATCH /api/issues/tech/{id}` to use the `require_access` pattern for its ownership check (also use `Depends(require_access(...))`)
- Add `# branch-scope: intentional` comment to both GET and PATCH to satisfy the Part 4 P4.5 CI rule
- Add unit tests: it_tech GET returns 200, principal GET returns 200, maintenance admin GET returns 403, it_tech PATCH returns 200, teacher PATCH returns 403; Given an admin+accountant user, When GET /api/issues/tech is called, Then 403 is returned (not 200)

**Acceptance Criteria:**
- `GET /api/issues/tech` uses `Depends(require_access('owner', 'admin', sub_category='it_tech'))` — not a bare inline `_is_it()` check
- `PATCH /api/issues/tech/{id}` uses consistent `require_access`-based auth pattern
- Both handlers have `# rbac: intentional` comments
- Given an admin+accountant user, When `GET /api/issues/tech` is called, Then 403 is returned (not 200)
- At least 4 unit tests (including the accountant 403 case)
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/issues.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.2: System health visibility for IT-tech

**Problem:** `GET /api/health/ready` returns DB/AI/S3 status but is not exposed in the IT-tech UI. IT-tech admins have no in-platform view of system health, S3 connectivity, Azure OpenAI status, or Twilio SMS config. Currently, only `GET /api/sms/config-status` exists and requires admin access — but there is no aggregated system health dashboard endpoint.

**Scope:**
- Add `GET /api/health/system` endpoint (new, distinct from `/health/ready`):
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Returns structured health status:
    ```json
    {
      "database": {"status": "ok|degraded|down", "latency_ms": <float>},
      "ai_service": {"status": "ok|unconfigured|down", "provider": "azure_openai"},
      "sms_service": {"status": "ok|unconfigured|down", "provider": "twilio"},
      "storage": {"status": "ok|unconfigured|down", "provider": "s3"},
      "school_id_configured": true|false,
      "checked_at": "<iso>"
    }
    ```
  - Database check: try a lightweight `ping` or `count_documents` on a small collection
  - AI check: verify `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` env vars are set (do NOT call the API — just check config)
  - SMS check: verify Twilio `ACCOUNT_SID` and `AUTH_TOKEN` env vars are set
  - S3 check: verify `AWS_S3_BUCKET` env var is set
- Add frontend: create a `SystemHealthPanel` component (or add to existing IT-tech tool) that polls `GET /api/health/system` and displays color-coded status cards
- Add unit tests: all services configured returns all `ok`, missing env var returns `unconfigured`, DB error returns `down`

**Acceptance Criteria:**
- `GET /api/health/system` accessible to it_tech admin (200) and returns structured status
- Teacher or student calling `GET /api/health/system` returns 403
- Returns `unconfigured` for each service whose env vars are missing
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/health.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.3: Audit log access — explicit IT-tech decision

**Problem:** `GET /api/audit-log` explicitly excludes `it_tech` admins (the check allows `sub_category in ("principal", None, "")`). This decision is not documented with a code comment explaining why IT-tech is excluded from audit logs. IT-tech is the system administrator role — in most enterprises, system admins have at minimum read access to audit logs for debugging and incident investigation.

**Scope:**
- Document the current decision with a `# rbac: intentional` comment in `audit.py`:
  - Option A (current): IT-tech excluded from audit logs — document why (e.g., privacy: IT-tech can see user records and fee data via audit logs)
  - Option B (recommended): IT-tech can see audit logs filtered to `tech_requests` and `system_events` collections only
- **Implement Option B:**
  - Update `list_audit_log` in `audit.py` to allow `sub_category=it_tech`:
    - It-tech may only query collections: `tech_requests`, `facility_requests`, `users` (login events only), and a new `system_events` collection
    - Block it-tech from: `fee_transactions`, `payroll`, `students` audit entries, `leave_requests`
  - Add `IT_TECH_BLOCKED` collection set to `audit.py` (similar to `PRINCIPAL_BLOCKED`)
  - Add unit tests: it_tech sees tech_request audit entries, it_tech blocked from fee audit entries, principal still blocked from financial collections

**Acceptance Criteria:**
- IT-tech calling `GET /api/audit-log` returns 200 (not 403)
- IT-tech calling `GET /api/audit-log?collection=fee_transactions` returns 403
- IT-tech calling `GET /api/audit-log?collection=tech_requests` returns 200
- `# rbac: intentional` comment explains the it_tech scoping decision
- **EC-13.4:** Given `IT_TECH_BLOCKED` collections list has 5 entries, When `GET /api/audit-log` is called by IT-tech, Then the MongoDB query includes `{'collection': {'$nin': IT_TECH_BLOCKED}}` filter — NOT fetching all documents and filtering in Python
- At least 4 unit tests
- Existing 387 tests still pass

**Implementation note (EC-13.4 — N+1-equivalent filter):** ALWAYS apply collection blocking at the query layer: `query['collection'] = {'$nin': IT_TECH_BLOCKED}` before passing to `db.audit_log.find(query)`. Never fetch all docs and filter in Python — this is both a performance and a data exposure risk (a future Python-level bypass would expose blocked collections).

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/audit.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.4: Admin password reset and account unlock for IT-tech

**Problem:** There is no password reset mechanism in the backend. An IT-tech admin has no way to reset a staff member's password or unlock an account that has been locked due to too many failed login attempts. This is a critical gap for a role designated as the system administrator.

**Scope:**
- Add `POST /api/auth/admin-reset-password` endpoint:
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Body: `{"user_id": "<id>", "new_password": "<plaintext>"}` (backend hashes using existing bcrypt pattern)
  - Validates `user_id` exists in `auth_users` collection
  - Hashes the new password and updates `password_hash`
  - Writes audit log entry: `action: "admin_password_reset"`, `changed_by: it_tech_user_id`, `target_user: user_id`
  - Returns `{"success": true, "message": "Password reset successfully"}`
  - IT-tech cannot reset the `owner` role password (returns 403 with "Cannot reset owner password")
- Add `POST /api/auth/unlock-account` endpoint:
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Body: `{"user_id": "<id>"}`
  - Clears any `locked_at`, `failed_attempts`, `locked_until` fields on the user document
  - Writes audit log entry
- Add unit tests: IT-tech resets staff password, IT-tech cannot reset owner password, unlock clears locked fields, teacher calling reset returns 403

**Acceptance Criteria:**
- IT-tech can reset staff password via POST — returns 200
- IT-tech trying to reset owner password returns 403
- Unlock endpoint clears lockout fields and writes audit log
- Teacher calling either endpoint returns 403
- **EC-13.1 (multi-owner lockout):** Given two owner accounts exist (Owner A and Owner B), When Owner A calls `POST /api/auth/admin-reset-password` for Owner B's account, Then the reset succeeds (owner CAN reset another owner)
- **EC-13.1 (full lockout emergency):** Given Owner A's credentials are lost AND Owner B's credentials are lost (full owner lockout), When IT-tech attempts to reset either owner's password, Then 403 is returned — but the response includes `detail: 'Contact system administrator for emergency recovery'`
- **EC-13.1 (IT-tech resets teacher):** Given IT-tech calls `POST /api/auth/admin-reset-password` for a teacher account, Then the reset succeeds
- At least 5 unit tests
- Existing 387 tests still pass

**Implementation note (EC-13.1 — two-tier reset rules):** IT-tech can reset any role EXCEPT owner. Owner can reset any role INCLUDING other owners. Emergency lockout recovery path: document that full owner lockout requires direct MongoDB access or a separate recovery script — add this as a comment in the route handler: `# RECOVERY: full owner lockout requires direct MongoDB access or a recovery script — see docs/operations.md`.

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/auth.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.5: AI token budget visibility and adjustment for IT-tech

**Problem:** `GET /api/settings/token-usage` returns only the calling user's own token usage. There is no endpoint for IT-tech (or any admin) to see aggregate token usage across all users, identify high consumers, or set a per-user token limit. The `token_usage` collection stores `user_id`, `month`, `tokens`, `sessions` — the data exists but has no admin-visibility layer.

**Scope:**
- Add `GET /api/settings/token-usage/admin` endpoint:
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Returns all token_usage records for current month with user names enriched:
    ```json
    {
      "success": true,
      "data": [
        {"user_id": "...", "user_name": "...", "role": "...", "tokens": 12345, "sessions": 30, "limit": 50000, "percent_used": 24.7}
      ],
      "meta": {"month": "2026-05", "total_tokens": 456789, "users_over_80_pct": 2}
    }
    ```
  - Sort by `tokens` descending
- Add `PATCH /api/settings/token-usage/limits/{user_id}` endpoint:
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Body: `{"limit": 75000}` — stores a per-user limit override in `token_usage_limits` collection (upsert by `user_id`)
  - `GET /api/settings/token-usage` should check `token_usage_limits` for the calling user's custom limit, falling back to 50000 default
- Add unit tests: admin view returns all users, limit override stored and returned in user view, teacher calling admin endpoint returns 403

**Acceptance Criteria:**
- IT-tech calling `GET /api/settings/token-usage/admin` returns all users' usage for current month
- `meta.users_over_80_pct` correctly counts users with > 80% of their limit consumed
- PATCH limit override stored; GET by that user returns the overridden limit
- Teacher/student calling admin endpoint returns 403
- **EC-13.3 (custom limit 80% check):** Given User B has a custom limit of 10,000 tokens and has used 8,500 (85%), When `GET /api/settings/token-usage/admin` is called, Then User B appears in `meta.users_over_80_pct` (85% of their CUSTOM limit, not the default 50,000 limit)
- At least 4 unit tests
- Existing 387 tests still pass

**Implementation note (EC-13.3 — per-user effective limit):** Per-user 80% check must compare against the user's EFFECTIVE limit (custom limit if set, default if not): `effective_limit = user.get('token_limit_override') or DEFAULT_TOKEN_LIMIT; pct = (tokens_used / effective_limit) * 100; if pct >= 80: over_80_users.append(user)`

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/settings.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.6: Import tool RBAC decision and IT-tech access

**Problem:** `POST /api/import/validate` and `POST /api/import/commit` use `require_owner` — IT-tech is excluded. This is a defensible decision (data import is destructive) but it is undocumented. In practice, IT-tech often manages bulk student/staff imports from CSV during onboarding. The import tool supports CSV file upload only.

**Scope:**
- Add explicit documentation of the RBAC decision in `import_data.py`:
  - Add `# rbac: owner-only — data import is destructive; it_tech can validate but not commit` comment
- Implement the split: IT-tech can validate but not commit:
  - `POST /api/import/validate` — change from `require_owner` to `require_access("owner", "admin", sub_category="it_tech")`
  - `POST /api/import/commit` — keep `require_owner` (owner-only, destructive operation)
- Add a `GET /api/import/history` endpoint (new):
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Returns last 20 import audit log entries (from `audit_logs` collection filtered to `action=import_commit`)
- Supported file formats: verify CSV and XLSX are both handled (check `import_data.py` parsing logic); document supported formats in an inline comment
- Add unit tests: it_tech can call validate (200), it_tech calling commit returns 403, owner can call both, import history returns audit entries

**Acceptance Criteria:**
- IT-tech calling `POST /api/import/validate` returns 200 (not 403)
- IT-tech calling `POST /api/import/commit` returns 403
- Owner can call both endpoints
- `GET /api/import/history` returns import audit entries accessible to it_tech
- `# rbac: intentional` comment in `import_data.py`
- At least 4 unit tests
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/import_data.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.7: Branch configuration management for IT-tech

**Problem:** `PATCH /api/settings/school` requires `require_owner` — IT-tech cannot manage school/branch settings. `GET /api/settings/school` is open to all (no auth required). There is no branch-add endpoint accessible to IT-tech. In practice, IT-tech often needs to add or configure branches (name, address, contact) without involving the school owner for routine updates.

**Scope:**
- Add `GET /api/settings/branches` endpoint:
  - Open to all authenticated users (`get_current_user`)
  - Returns list of all branches from `db.branches` collection
- Add `POST /api/settings/branches` endpoint:
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Body: `{"name": "...", "address": "...", "phone": "...", "branch_code": "..."}`
  - Validates `branch_code` is unique within school
  - Returns created branch document
- Add `PATCH /api/settings/branches/{branch_id}` endpoint:
  - Requires `require_access("owner", "admin", sub_category="it_tech")`
  - Updates branch name, address, phone — does NOT allow changing `branch_code` after creation
- Keep `PATCH /api/settings/school` as owner-only (school-level settings like fees, AI context remain owner-gated)
- Add `# rbac: intentional — school-wide settings remain owner-only; branch CRUD available to it_tech` comment
- Add unit tests: it_tech creates branch, it_tech patches branch name, it_tech cannot patch school settings (403), owner can do all

**Acceptance Criteria:**
- IT-tech `POST /api/settings/branches` returns 200 with created branch
- IT-tech `PATCH /api/settings/branches/{id}` returns 200
- IT-tech `PATCH /api/settings/school` returns 403
- `branch_code` uniqueness validated on create (409 if duplicate)
- **EC-13.2 (race condition — concurrent branch creation):** Given two concurrent `POST /api/settings/branches` requests with the same `branch_code`, When both arrive simultaneously, Then exactly ONE succeeds and the other receives 409
- **EC-13.2 (DB-level catch):** Given `POST /api/settings/branches` with duplicate `branch_code`, When the application-level check passes but the DB index catches it, Then 409 (not 500) is returned
- At least 5 unit tests
- Existing 387 tests still pass

**Implementation note (EC-13.2 — unique MongoDB index for branch code):** Add unique MongoDB index: `db.branches.create_index([('schoolId',1),('branch_code',1)], unique=True)` in `database.py _create_indexes()`. Handle the duplicate key error: `except DuplicateKeyError: raise HTTPException(409, 'Branch code already exists')`. The application-level `find_one` check alone is insufficient — the DB index is the only reliable guard against concurrent creation races.

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/settings.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

### Story P13.8: Integration health frontend dashboard for IT-tech

**Problem:** The `GET /api/health/system` endpoint from Story P13.2 provides structured health data, but there is no frontend component surfacing this for IT-tech admins. IT-tech needs a at-a-glance dashboard showing service connectivity status without going to server logs.

**Scope:**
- Create `SystemHealthDashboard.js` component in `frontend/src/components/tools/`:
  - Polls `GET /api/health/system` on mount and on manual refresh
  - Displays a card per service (Database, AI Service, SMS, Storage) with color-coded status: green=ok, yellow=degraded/unconfigured, red=down
  - Shows `checked_at` timestamp for last check
  - Shows `school_id_configured` as a boolean badge
  - Shows token usage summary: pulls from `GET /api/settings/token-usage/admin` and shows top 3 consumers
  - "Refresh Now" button to trigger manual re-check
- Register the new component in the IT-tech admin's tool routing
- No backend changes needed (uses endpoints from P13.2 and P13.5)
- Frontend unit test (or smoke test): component renders without crash, shows service cards, shows refresh button

**Acceptance Criteria:**
- `SystemHealthDashboard.js` renders four service status cards
- Shows `checked_at` timestamp
- Manual refresh triggers API call
- Shows top 3 token consumers from admin usage API
- At least 1 frontend smoke test (render without crash)
- Existing 387 tests still pass

**Scoped-query audit (mandatory before merge):**
- Given: `grep -n "scoped_filter(" backend/routes/health.py`, Then: every result either has `# branch-scope: intentional` comment OR is migrated to `scoped_query(branch_id=user.get("branch_id"))`

---

## Epic P13: FR Coverage Map

| FR # | Route / Component | Gap Identified | Story |
|------|-------------------|----------------|-------|
| FR1 | `GET /api/issues/tech`, `PATCH /api/issues/tech/{id}` | Inconsistent auth pattern vs POST (manual `_is_it()` vs `require_access`) | P13.1 |
| FR2 | `GET /api/health/system` (new) | No IT-tech-gated system health endpoint or frontend panel | P13.2 |
| FR3 | `GET /api/audit-log` | IT-tech excluded with no documentation; should have scoped access | P13.3 |
| FR4 | `POST /api/auth/admin-reset-password` (new) | No password reset or account unlock endpoint | P13.4 |
| FR5 | `GET /api/settings/token-usage/admin` (new) | No aggregate token visibility or per-user limit setting | P13.5 |
| FR6 | `POST /api/import/validate`, `POST /api/import/commit` | IT-tech excluded from validate (should be allowed); no import history | P13.6 |
| FR7 | `POST /api/settings/branches` (new) | No branch CRUD accessible to IT-tech | P13.7 |
| FR8 | `SystemHealthDashboard.js` (new) | No IT-tech frontend health dashboard component | P13.8 |

---

## Epic P13: NFRs

**NFR13.1 — Security for Password Reset:**
`POST /api/auth/admin-reset-password` must use the same password hashing mechanism (bcrypt, same cost factor) as `POST /api/auth/register`. The plaintext password must never be logged. The audit log entry must record that a reset occurred but NOT include the new password in the `changes` field.

**NFR13.2 — Health Check Non-Intrusiveness:**
`GET /api/health/system` must not call external services (Azure OpenAI, Twilio, S3) to determine their status — it must only check that environment variables are configured. A full connectivity test would add latency and could consume rate-limited API credits. Document this constraint with an inline comment.

**NFR13.3 — Import Validation Safety:**
`POST /api/import/validate` being accessible to IT-tech must only read and validate — it must never write to the database. Verify this is already the case in `import_data.py` and add a comment. If any write occurs in the validate path, it must be removed as part of this story.

**NFR13.4 — Test Coverage:**
Each story must add at minimum the number of unit/integration tests stated in its Acceptance Criteria. Total new tests for Part 13 must be at least 35. All new tests must pass alongside the 387 baseline.

**NFR13.5 — Test Data:**
All test data creation must use `tests/backend/factories.py` (created in pre-Part-9 infrastructure story). Do NOT create one-off inline test dicts — they fragment into inconsistent formats across parts.

---

## Epic P13: Full Stories with Given/When/Then ACs

### Story P13.S1: IT-tech auth pattern consistency for tech issues

**Given** an IT-tech admin JWT
**When** `GET /api/issues/tech` is called
**Then** the response returns HTTP 200 with the tech requests list (not 403)

**Given** a maintenance admin JWT
**When** `GET /api/issues/tech` is called
**Then** the response returns HTTP 403 with "Maintenance Admin cannot access tech requests"

**Given** a principal admin JWT
**When** `GET /api/issues/tech` is called
**Then** the response returns HTTP 200 (principals can view tech issues)

**Given** the GET and PATCH handlers in `issues.py`
**When** the source code is audited
**Then** neither handler uses a bare inline `_is_it()` check without a `# rbac: intentional` comment — they use the consistent `require_access` or documented equivalent pattern

---

### Story P13.S2: System health endpoint scoped to IT-tech

**Given** an IT-tech admin JWT and all service env vars are configured
**When** `GET /api/health/system` is called
**Then** the response returns `{"database": {"status": "ok"}, "ai_service": {"status": "ok"}, "sms_service": {"status": "ok"}, "storage": {"status": "ok"}, "school_id_configured": true, "checked_at": "<iso>"}`

**Given** the `TWILIO_ACCOUNT_SID` env var is not set
**When** `GET /api/health/system` is called by IT-tech
**Then** `sms_service.status` is `"unconfigured"` (not `"ok"`)

**Given** a student user JWT
**When** `GET /api/health/system` is called
**Then** the response returns HTTP 403

**Given** a principal admin JWT (not it_tech)
**When** `GET /api/health/system` is called
**Then** the response returns HTTP 403

---

### Story P13.S3: Audit log scoped access for IT-tech

**Given** an IT-tech admin JWT
**When** `GET /api/audit-log` is called with no collection filter
**Then** the response returns HTTP 200 and only includes entries from IT-tech-allowed collections

**Given** an IT-tech admin JWT
**When** `GET /api/audit-log?collection=fee_transactions` is called
**Then** the response returns HTTP 403 with detail explaining access is restricted

**Given** an IT-tech admin JWT
**When** `GET /api/audit-log?collection=tech_requests` is called
**Then** the response returns HTTP 200 with tech_request audit entries

**Given** the `audit.py` source code
**When** it is reviewed
**Then** the IT-tech inclusion and `IT_TECH_BLOCKED` collection set both have `# rbac: intentional` comments

**EC-13.4 — Given** `IT_TECH_BLOCKED` has 5 collection entries
**When** `GET /api/audit-log` is called by an IT-tech user
**Then** the MongoDB query sent to the driver includes `{'collection': {'$nin': IT_TECH_BLOCKED}}` — the filter is NOT applied in Python after fetching all documents

---

### Story P13.S4: Admin password reset and account unlock

**Given** an IT-tech admin and a staff member user_id (not owner)
**When** `POST /api/auth/admin-reset-password` is called with `{"user_id": "<staff_id>", "new_password": "NewSecure123!"}`
**Then** the response returns HTTP 200 and the staff member can log in with the new password
**And** an audit log entry exists with `action: "admin_password_reset"` and `changed_by: <it_tech_user_id>`

**Given** an IT-tech admin and the owner's user_id
**When** `POST /api/auth/admin-reset-password` is called with the owner's user_id
**Then** the response returns HTTP 403 with "Cannot reset owner password"

**Given** a staff member's account has `locked_at` and `failed_attempts: 5` set
**When** IT-tech calls `POST /api/auth/unlock-account` with `{"user_id": "<staff_id>"}`
**Then** the response returns HTTP 200 and `locked_at`, `failed_attempts`, `locked_until` are cleared on the user document

**EC-13.1 — Given** two owner accounts exist (Owner A and Owner B)
**When** Owner A calls `POST /api/auth/admin-reset-password` for Owner B's account
**Then** the reset succeeds (owner CAN reset another owner)

**EC-13.1 — Given** Owner A's credentials are lost AND Owner B's credentials are lost (full owner lockout)
**When** IT-tech attempts to reset either owner's password
**Then** HTTP 403 is returned with `detail: 'Contact system administrator for emergency recovery'`

**EC-13.1 — Given** IT-tech calls `POST /api/auth/admin-reset-password` for a teacher account
**When** the request is processed
**Then** the reset succeeds and HTTP 200 is returned

---

### Story P13.S5: Token budget aggregate view for IT-tech

**Given** three users exist with token usage: User A 45000 tokens, User B 8000, User C 42000 (limit 50000)
**When** IT-tech calls `GET /api/settings/token-usage/admin`
**Then** the response lists all three users sorted by tokens descending (A, C, B)
**And** `meta.users_over_80_pct` is 2 (A and C are above 80% of 50000)

**Given** IT-tech sets User B's limit to 10000 via `PATCH /api/settings/token-usage/limits/<user_b_id>` with `{"limit": 10000}`
**When** User B calls `GET /api/settings/token-usage`
**Then** the response returns `{"limit": 10000, "tokens": 8000, "percent_used": 80.0}`

**Given** a teacher JWT
**When** `GET /api/settings/token-usage/admin` is called
**Then** the response returns HTTP 403

**EC-13.3 — Given** User B has a custom limit of 10,000 tokens and has used 8,500 (85%)
**When** IT-tech calls `GET /api/settings/token-usage/admin`
**Then** User B appears in `meta.users_over_80_pct` because 8,500 is 85% of their CUSTOM limit (10,000) — not 17% of the default 50,000 limit

---

## Epic P13: Implementation Order

1. P13.1 — Auth pattern consistency (refactor only, no feature change — lowest risk)
2. P13.3 — Audit log IT-tech scoped access (adds access rather than removing, safer)
3. P13.6 — Import validate split (change one dependency from `require_owner` to `require_access`)
4. P13.7 — Branch configuration endpoints (new endpoints, no changes to existing)
5. P13.5 — Token budget admin view (new endpoints, additive only)
6. P13.2 — System health endpoint (new endpoint)
7. P13.4 — Password reset and unlock (security-sensitive, do after pattern is established)
8. P13.8 — Frontend health dashboard (pure frontend, depends on P13.2 and P13.5 endpoints)

---

## Epic P13: Retrospective

A retrospective entry for Part 13 to be completed after all P13.1–P13.8 stories are done.
