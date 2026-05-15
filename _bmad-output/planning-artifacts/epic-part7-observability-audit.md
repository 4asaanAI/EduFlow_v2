---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 7'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 7
part_name: 'Observability + Audit'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy', 'Part 5 Notifications+SSE', 'Part 6 File Storage']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 7: Observability + Audit

## Context

Part 7 addresses gaps in audit logging coverage, structured logging quality, health endpoint completeness, error response consistency, and slow query observability. Items were identified by auditing `backend/routes/audit.py`, `backend/logging_config.py`, `backend/server.py`, and performing a cross-route grep for unaudited write operations.

Key discoveries from the code audit:

1. **Audit log is not branch-scoped**: `GET /api/audit-log` uses `scoped_filter(query, get_school_id())` which applies only `schoolId`. In a multi-branch school, a principal at branch A can see audit records for branch B. There is no `branch_id` filter. The audit log collection lacks branch isolation.

2. **Settings changes are not audited**: `backend/routes/settings.py` writes to the database (school settings, fee heads, academic year configuration) but has ZERO `db.audit_logs.insert_one()` calls. Changes to fee structures, academic years, and school-level settings are invisible to the audit trail. This is a compliance gap — an accountant can change a fee structure with no record.

3. **Activities route has no audit**: `backend/routes/activities.py` writes activity records (house points, sports events, cultural events) with no audit log entries. House point manipulation by a teacher would be undetectable.

4. **`/api/health/ready` has no S3 check**: The readiness endpoint checks MongoDB, AI endpoint, and optionally biometric. There is no check for S3 connectivity (critical for file upload/serve paths) or Twilio/SMS service (used for OTP and parent notifications). An S3 outage would cause silent upload failures without the health endpoint reflecting degradation.

5. **Global 500 handler returns `{"success": False, "detail": "..."}` while HTTP exception handler returns `{"detail": "..."}` (no `success`)**: This shape inconsistency means the frontend must handle two different error shapes for the same 500 status code. `http_exception_handler` returns `{"detail": exc.detail}`, `global_exception_handler` returns `{"success": False, "detail": "An internal error occurred"}`. The shapes differ.

6. **`request_id` is set in context var but not always present in logs**: `request_id_ctx` is set in `log_requests` middleware. But logs emitted from background tasks (e.g., the SSE keepalive loop, AI dispatch callbacks) do not go through this middleware — their `request_id` will be `None`. There is no mechanism to propagate request_id into async subtasks spawned during a request.

7. **Security events logged at `info` level**: `auth.py` line 196: `logger.info(f"Login success: {username}")`. Login success is a security event that should be at `INFO` (acceptable). However, failed login attempts are not logged at all (no `logger.warning` on 401 from `get_current_user`). A brute-force attack leaves no trace in logs.

8. **`logger.error` used for non-errors in tokens.py**: `tokens.py` lines 49, 74, 90, 124, 151 use `logger.error(f"Token balance error: {e}")` for what are often expected database miss scenarios (e.g. no token document found for a user). These inflate error alert counts in log monitoring systems.

9. **No per-request MongoDB query timing**: `duration_ms` in `logging_config.py` captures total request duration (HTTP middleware). There is no individual MongoDB operation timing. A slow `find().sort().skip().limit()` query (e.g. the fee_transactions list with large datasets) cannot be distinguished from a fast one in logs.

10. **`audit.py` `GET /record/{record_id}` has no page limit**: The endpoint fetches `.to_list(200)` — 200 audit records per entity. For high-churn entities (attendance corrections) this could be 200 large documents in a single response. No pagination is applied.

11. **Audit records lack `branch_id` field**: Existing audit writes in `staff.py`, `fees.py`, `attendance.py`, `academics.py` do NOT include a `branch_id` field in the inserted document. Future branch filtering will be impossible without re-querying the referenced entity to infer the branch. This must be fixed going forward.

**Entering baseline:** 387 backend tests, 0 skipped.

---

## Functional Requirements

**FR7.1 — Branch-scoped audit log queries**: `GET /api/audit-log` MUST accept an optional `branch_id` query parameter. When provided, filter results to records where `doc.branch_id == branch_id`. When not provided, the current behavior is preserved (school-level view for owners). Principals at a specific branch should see only their branch's records.

**FR7.2 — Settings changes audited**: Every write operation in `backend/routes/settings.py` (fee head CRUD, academic year CRUD, school settings update, discount type CRUD) MUST write an `audit_logs` entry with `action`, `entity_id`, `collection`, `changed_by`, `schoolId`, and `branch_id`.

**FR7.3 — Activities changes audited**: Every write operation in `backend/routes/activities.py` (house points, events, achievements) MUST write an `audit_logs` entry.

**FR7.4 — Audit documents include branch_id**: All new `db.audit_logs.insert_one()` calls across all routes MUST include `branch_id` from the current user's `user["branch_id"]` (or from the entity being modified, if applicable). Existing writes without `branch_id` must be fixed.

**FR7.5 — Health endpoint S3 check**: `/api/health/ready` MUST include an `"s3"` status field. The check should attempt a `head_bucket` or `list_objects_v2(MaxKeys=1)` call with a 3 s timeout. Status values: `"ok"` (200 from S3), `"degraded"` (S3 configured but unreachable), `"not_configured"` (no `S3_BUCKET_NAME` env var).

**FR7.6 — Failed login attempts logged**: The authentication middleware or `auth.py` MUST log failed login attempts (wrong password or user not found) at `logger.warning` level with fields: `event: "login_failed"`, `username` (do NOT log password), `ip: request.client.host`. This enables brute-force detection via log monitoring.

**FR7.7 — Error response shape consistency**: ALL error responses (4xx and 5xx) MUST have the shape `{"detail": "..."}`. Remove `success: False` from `global_exception_handler`. The frontend should treat any non-2xx response as an error and read `response.detail`.

**FR7.8 — `GET /api/audit-log/{record_id}` pagination**: The `get_record_history` endpoint must be paginated: accept `page: int = 1` and `limit: int = 50` query params (max 100). Replace `.to_list(200)` with `.skip(skip).limit(limit).to_list(limit)`. Add `meta` to response.

---

## Non-Functional Requirements

**NFR7.1 — Log volume control**: `logger.error` in `tokens.py` for routine "no token document" scenarios MUST be downgraded to `logger.warning` or `logger.info`. Reserve `logger.error` for unexpected exceptions. This prevents alert fatigue in production monitoring.

**NFR7.2 — MongoDB per-operation timing**: Add a `ScopedDatabase` wrapper or a context manager in `database.py` that records elapsed time for every collection operation and logs at `DEBUG` level with `slow_query: true` for operations exceeding 100 ms. Must not impact production performance (DEBUG level only, can be toggled via `LOG_LEVEL`).

**NFR7.3 — request_id propagation to subtasks**: When `asyncio.create_task()` is used to spawn subtasks (e.g. keepalive loop, audit write), the parent request's `request_id` context var value should be copied into the subtask via `contextvars.copy_context().run(...)`. Requires: document the pattern in `logging_config.py` as a usage note.

**NFR7.4 — Audit log index**: The `audit_logs` collection MUST have indexes on `(schoolId, created_at DESC)` and `(schoolId, entity_id)` for the two primary query patterns in `audit.py`. Verify in `database.py`, add if missing.

---

## Architecture Requirements

**AR7.1 — Audit log write helper**: Instead of inline `db.audit_logs.insert_one({...})` with varying field sets across routes, extract a shared `write_audit(db, *, action, entity_id, collection, changed_by, changed_by_role, school_id, branch_id, changes, reason="")` function to `services/audit_service.py`. This ensures all audit records have a consistent schema.

**AR7.2 — Audit coverage matrix**: Maintain a `_bmad-output/parts/observability/audit-coverage-matrix.md` documenting every write endpoint and whether it has audit coverage. Update after each story in this epic.

**AR7.3 — Log level policy**: Document in `logging_config.py` or a companion file the log level policy:
- `logger.debug`: per-operation tracing, query timings
- `logger.info`: normal operations (request completed, startup, login success)
- `logger.warning`: expected degraded conditions (notification write failed, Gemini unavailable, audit write failed, login failed)
- `logger.error`: unexpected exceptions, unhandled errors, data integrity failures
- `logger.critical`: unrecoverable startup failures

---

## FR Coverage Map

| FR | Story | Notes |
|----|-------|-------|
| FR7.1 | P7.1 | branch-scoped audit query |
| FR7.2 | P7.2 | settings audit |
| FR7.3 | P7.3 | activities audit |
| FR7.4 | P7.1 + P7.2 + P7.3 | branch_id in all audit writes |
| FR7.5 | P7.4 | S3 health check |
| FR7.6 | P7.5 | failed login logging |
| FR7.7 | P7.6 | error shape consistency |
| FR7.8 | P7.1 | audit record pagination |
| NFR7.1 | P7.7 | log level fixes |
| NFR7.2 | P7.8 | slow query detection |
| AR7.1 | P7.2 + P7.3 | shared audit write helper |
| NFR7.4 | P7.8 | audit log indexes |

---

## Epic P7: Observability + Audit Hardening

### Story P7.1: Branch-scoped audit log + pagination for record history

**Problem:** `GET /api/audit-log` is scoped to `schoolId` only. In a multi-branch school, a principal at branch A can see all audit records from all branches, including branch B's fee transactions and staff changes. Additionally, `GET /api/audit-log/{record_id}` fetches `.to_list(200)` with no pagination — a high-traffic entity (attendance corrections) could return 200 large documents, causing slow responses and memory spikes.

**Scope:**
- Add `branch_id: str = None` query parameter to `list_audit_log()`
  - If provided: add `query["branch_id"] = branch_id` to the MongoDB filter
  - Principal auto-filter: when `is_principal`, apply `query["branch_id"] = user.get("branch_id")` if no explicit `branch_id` param given
- Add `page: int = 1, limit: int = 50` params to `get_record_history()`
  - `limit = min(max(limit, 1), 100)` cap
  - Replace `.to_list(200)` with `.skip(skip).limit(limit).to_list(limit)`
  - Add `"meta": {"page": page, "limit": limit, "total": total}` to response
  - Add `total = await db.audit_logs.count_documents(scoped_filter(query, get_school_id()))` before the find
- Add unit tests:
  - `branch_id` param filters results
  - Principal without param gets own branch's records auto-filtered
  - Owner without param sees all records
  - Record history returns paginated results

**Acceptance Criteria:**

Given `GET /api/audit-log?branch_id=branch-1` called by an owner,
When the query runs,
Then only audit records with `branch_id == "branch-1"` are returned.

Given a principal user (branch-2) calls `GET /api/audit-log` without a branch_id param,
When the auto-filter applies,
Then only branch-2 audit records are returned.

Given `GET /api/audit-log/{record_id}?page=1&limit=10` with 25 matching records,
When the query runs,
Then 10 records are returned and `meta.total` equals 25.

Given `limit=200` is passed to `get_record_history`,
When the cap is applied,
Then `limit` is capped at 100.

- Branch filter implemented
- Record history paginated
- At least 4 unit tests in `tests/backend/unit/test_audit_routes.py`
- All 387 existing tests still pass

---

### Story P7.2: Settings changes audit coverage + shared audit write helper

**Problem:** `backend/routes/settings.py` writes school-level configuration: fee heads, academic years, school info, discount types. None of these writes have `db.audit_logs.insert_one()` calls. An accountant could create/delete a fee head or change a fee structure, and there would be no audit trail. This is a compliance violation for any regulated school. Additionally, audit `insert_one()` calls across 6 routes (`staff.py`, `fees.py`, `attendance.py`, `academics.py`, `issues.py`, `operations.py`) each build their own dict with varying schemas — no shared helper ensures consistent fields.

**Scope:**
- Create `backend/services/audit_service.py`:
  ```python
  async def write_audit(
      db, *, action: str, entity_id: str, collection: str,
      changed_by: str, changed_by_role: str,
      school_id: str, branch_id: str = "",
      changes: dict = None, reason: str = ""
  ) -> bool:
      """Write audit log entry. Returns True on success, False on failure (fail-open)."""
  ```
  - Builds consistent document with all required fields including `branch_id`
  - Wraps in try/except, logs warning on failure, returns False
  - Never raises (fail-open like `notification_service.py`)
- Add audit calls in `settings.py` for:
  - `POST /api/settings/fee-heads` → action `fee_head_create`
  - `PUT /api/settings/fee-heads/{id}` → action `fee_head_update`
  - `DELETE /api/settings/fee-heads/{id}` → action `fee_head_delete`
  - `POST /api/settings/academic-years` → action `academic_year_create`
  - `PATCH /api/settings` → action `school_settings_update`
  - And any other settings write endpoints identified in `settings.py`
- Optionally migrate existing `db.audit_logs.insert_one()` calls to use `write_audit()` (non-breaking refactor)
- Add unit tests for `write_audit()`:
  - Happy path writes correct document
  - DB error returns False, warning logged, no exception
  - All required fields present

**Acceptance Criteria:**

Given a fee head is created via `POST /api/settings/fee-heads`,
When the request completes,
Then `db.audit_logs` contains a record with `action="fee_head_create"`, `collection="fee_heads"`, `changed_by=<user_id>`, and `branch_id=<user_branch>`.

Given `write_audit()` is called and MongoDB raises an exception,
When the exception is caught,
Then the function returns False, `logger.warning` is emitted, and the parent action is unaffected.

Given an audit document written via `write_audit()`,
When retrieved from the database,
Then it has: `action`, `entity_id`, `collection`, `changed_by`, `changed_by_role`, `schoolId`, `branch_id`, `changes`, `reason`, `created_at` fields.

- `audit_service.py` created
- At least 6 audit calls added to `settings.py`
- 5+ unit tests in `tests/backend/unit/test_audit_service.py`
- All 387 existing tests still pass

---

### Story P7.3: Activities audit coverage

**Problem:** `backend/routes/activities.py` writes house points, sports events, cultural events, and achievement records. None of these writes emit audit log entries. A teacher who inflates a house's points by 500 points leaves no trace. House standings are visible to all students and affect morale — manipulation is a real governance risk.

**Scope:**
- Audit `activities.py` for all write endpoints:
  - `POST /api/activities/house-points` → `write_audit(action="house_points_award", ...)`
  - `POST /api/activities/events` → `write_audit(action="event_create", ...)`
  - `PUT /api/activities/events/{id}` → `write_audit(action="event_update", ...)`
  - `DELETE /api/activities/events/{id}` → `write_audit(action="event_delete", ...)`
  - Any other write endpoints found in `activities.py`
- All audit calls must use `write_audit()` from `audit_service.py` (P7.2)
- All audit records must include `branch_id`
- Add unit tests verifying audit records exist after each operation

**Acceptance Criteria:**

Given `POST /api/activities/house-points` with `points=100` and `student_id=X`,
When the request succeeds,
Then `db.audit_logs` has a record with `action="house_points_award"`, `entity_id=X`, and the requesting user's `changed_by`.

Given `DELETE /api/activities/events/{id}` by an admin,
When the deletion completes,
Then an audit record with `action="event_delete"` exists.

Given any activity write endpoint,
When the audit record is written,
Then `branch_id` equals the acting user's `branch_id`.

- All activity write endpoints have audit calls
- Audit records include `branch_id`
- 4+ unit tests in `tests/backend/unit/test_activities_audit.py`
- All 387 existing tests still pass

---

### Story P7.4: Health endpoint S3 + SMS connectivity checks

**Problem:** `/api/health/ready` checks MongoDB, AI endpoint, and optionally biometric. It returns `"overall": "ready"` as long as MongoDB is up. If S3 is down, all file uploads and serves will fail with 502, but the health endpoint still returns `"ready"`. Similarly, if Twilio/SMS is configured but unreachable, parent SMS notifications will fail silently. A load balancer using `/api/health/ready` for instance routing would keep routing traffic to an unhealthy instance.

**Scope:**
- Add `_check_s3()` async function in `server.py`:
  - If `S3_BUCKET_NAME` env var is not set: return `"not_configured"`
  - Otherwise: attempt `get_s3_client().list_objects_v2(Bucket=bucket, MaxKeys=1)` with 3 s timeout
  - Return `"ok"` on success, `"degraded"` on failure
  - Log warning on failure with `exc_info=True`
- Add `_check_sms()` async function:
  - If `TWILIO_ACCOUNT_SID` is not set: return `"not_configured"`
  - Otherwise: validate credentials via a `requests.get(twilio_url)` with 3 s timeout or use `httpx`
  - Return `"ok"` / `"degraded"` / `"not_configured"`
- Include both in `/api/health/ready` response:
  - `response["s3"] = await _check_s3()`
  - `response["sms"] = await _check_sms()`
- Overall status logic: `"down"` if db is error, `"degraded"` if any non-db check is degraded, `"ready"` if all are ok or not_configured
- Update `tests/backend/api/test_health_ready.py` to cover the new fields
- Add unit tests: S3 ok → status ok; S3 down → status degraded; S3 not configured → not_configured

**Acceptance Criteria:**

Given S3 is configured (`S3_BUCKET_NAME` set) and `list_objects_v2` succeeds,
When `GET /api/health/ready` is called,
Then `response["s3"] == "ok"`.

Given S3 is configured but unreachable (timeout),
When `GET /api/health/ready` is called,
Then `response["s3"] == "degraded"` and `response["overall"] == "degraded"`.

Given `S3_BUCKET_NAME` is not set,
When `GET /api/health/ready` is called,
Then `response["s3"] == "not_configured"` and this does NOT mark the instance as degraded.

Given MongoDB is down and S3 is ok,
When `GET /api/health/ready` is called,
Then `response["overall"] == "down"`.

- `_check_s3()` and `_check_sms()` implemented
- `test_health_ready.py` updated with 4+ new tests
- All 387 existing tests still pass

---

### Story P7.5: Failed login attempt logging

**Problem:** `auth.py` logs successful logins at `logger.info` level (line 196). Failed logins (wrong password, user not found) are handled by raising `HTTPException(401)` with no logging. A brute-force attack attempting thousands of passwords against an admin account leaves no trace in logs. Without login failure logs, security monitoring (e.g. CloudWatch alerts on high error rates) cannot detect this attack pattern. Additionally, the successful login log uses an f-string which bypasses the JSON formatter's structured field approach.

**Scope:**
- In `auth.py` login endpoint, add `logger.warning(...)` for authentication failures:
  - User not found: `logger.warning("login_failed", extra={"event": "login_failed", "username": username, "reason": "user_not_found", "ip": request.client.host if request.client else "unknown"})`
  - Wrong password: `logger.warning("login_failed", extra={"event": "login_failed", "username": username, "reason": "invalid_password", "ip": ...})`
  - Account inactive/locked: `logger.warning(...)` with `reason: "account_inactive"`
- Fix the successful login log to use structured extra fields, not f-string
- Verify that usernames are logged but passwords are NEVER logged (add a test assertion)
- Add the `ip` field to the JSON formatter's known fields (or confirm `extra` dict fields are included)
- Add unit tests:
  - Failed login (wrong password) → warning logged with event=login_failed
  - Failed login (unknown user) → warning logged
  - Successful login → info logged, no password field in log output
  - Log record does not contain the literal password string

**Acceptance Criteria:**

Given a POST to `/api/auth/login` with a wrong password,
When the handler processes the request,
Then `logger.warning` is called with `event="login_failed"` and `reason="invalid_password"`.

Given a POST to `/api/auth/login` with an unknown username,
When the handler processes the request,
Then `logger.warning` is called with `reason="user_not_found"`.

Given a successful login,
When the log record is checked,
Then no field contains the literal password value.

Given any login failure log,
When the log record is serialized,
Then it includes `username`, `event`, `reason`, and `ip` fields.

- `auth.py` logs failures at warning level
- Structured extra fields used (not f-string)
- 4+ unit tests in `tests/backend/unit/test_auth_logging.py`
- Password never appears in any log
- All 387 existing tests still pass

---

### Story P7.6: Error response shape consistency

**Problem:** FastAPI's built-in HTTP exception handler returns `{"detail": "..."}`. The custom `global_exception_handler` in `server.py` returns `{"success": False, "detail": "An internal error occurred"}`. The `RequestValidationError` handler returns `{"detail": [...]}` (list of errors). This means the frontend must handle three different error shapes:
- 4xx (HTTP exceptions): `{"detail": "string"}`
- 422 (validation): `{"detail": [{"msg": ..., "loc": ...}]}`
- 500 (unhandled): `{"success": False, "detail": "string"}`

The `success: False` field in the 500 response is uniquely inconsistent and requires special-casing in the frontend.

**Scope:**
- Remove `"success": False` from `global_exception_handler` response in `server.py`:
  - Change to: `{"detail": "An internal error occurred"}`
- Verify no other exception handler returns a `success` field in error responses
- Document the standardized error shape in a comment above the exception handlers
- Add regression tests in `tests/backend/unit/test_error_shapes.py`:
  - HTTP 404 → `{"detail": "..."}` (no `success` key)
  - HTTP 422 → `{"detail": [...]}` (list format for validation)
  - Unhandled exception → `{"detail": "An internal error occurred"}` (no `success` key)
- Check existing `test_error_message_hygiene.py` for conflicts and update if needed

**Acceptance Criteria:**

Given a route raises `HTTPException(404, "Not found")`,
When the response is returned,
Then the body is exactly `{"detail": "Not found"}` with no `success` field.

Given an unhandled `RuntimeError` is raised in a route,
When the global exception handler catches it,
Then the response body is `{"detail": "An internal error occurred"}` with no `success` field.

Given a validation error (missing required body field),
When the 422 handler fires,
Then `response["detail"]` is a list (not a string).

- `global_exception_handler` response updated
- 3+ regression tests
- `test_error_message_hygiene.py` reviewed and updated
- All 387 existing tests still pass

---

### Story P7.7: Log level audit + tokens.py fix

**Problem:** `tokens.py` uses `logger.error(f"Token balance error: {e}")` for routine scenarios: token document not found, stats query error. These are often expected conditions (a new user has no token document yet) but they fire `error`-level log events, inflating error rates in monitoring dashboards. Log monitoring systems (CloudWatch, Datadog) typically alert on sustained error rates — these false positives can mask real errors. Additionally, the f-string format means the exception is not captured as `exc_info` for stack trace visibility.

**Scope:**
- Audit all `logger.error` calls in `tokens.py`:
  - Downgrade expected scenarios ("no token doc", "stats not available") to `logger.warning`
  - Keep `logger.error` only for unexpected exceptions where the request cannot be fulfilled
  - Add `exc_info=True` to all `logger.error` and `logger.warning` calls (not f-string formatting)
- Audit all `logger.error` calls in `routes/` for similar misuse:
  - `chat.py` lines 1036, 1763: verify these are genuine errors (they are — keep as error)
  - `auth.py` line 297 (password reset email failed): keep as error
- Document the log level policy in `logging_config.py` as a module-level comment (AR7.3)
- Add unit tests:
  - "No token document" path emits `logger.warning`, not `logger.error`
  - Warning calls include `exc_info=True` parameter

**Acceptance Criteria:**

Given a request to `GET /api/tokens/balance` for a user with no token document,
When the handler catches the miss,
Then `logger.warning` is called (not `logger.error`).

Given any log call in `tokens.py`,
When it is `logger.warning` or `logger.error`,
Then `exc_info=True` is present (not f-string exception formatting).

Given the `logging_config.py` file,
When read,
Then a comment block documents the log level policy (debug/info/warning/error/critical with examples).

- All 5 `logger.error` calls in `tokens.py` reviewed and corrected where appropriate
- Log level policy comment added to `logging_config.py`
- 3+ unit tests
- All 387 existing tests still pass

---

### Story P7.8: MongoDB slow query detection + audit log index verification

**Problem:** `logging_config.py` tracks request-level `duration_ms` via middleware, but there is no per-operation MongoDB timing. A slow `find()` with an unindexed query (e.g. `fee_transactions.find({"student_id": x}).sort("created_at", -1)` without an index on `student_id`) can make a request slow without any diagnostic signal pointing to the database. Additionally, `audit_logs` indexes are unverified — the collection may be doing collection scans for every audit log query.

**Scope:**
- Add `SLOW_QUERY_MS = int(os.environ.get("SLOW_QUERY_MS", "100"))` to `database.py`
- Create a `TimedCollection` wrapper (or AsyncIOMotorCollection proxy) that:
  - Wraps `find`, `find_one`, `count_documents`, `insert_one`, `update_one`, `update_many`, `delete_one`, `delete_many`
  - Records wall-clock time for each operation using `time.time()`
  - If elapsed > `SLOW_QUERY_MS`: logs `logger.debug("slow_query", extra={"collection": name, "op": op, "duration_ms": ms, "slow_query": True, "request_id": request_id_ctx.get()})`
  - Normal-speed operations: no log (not even debug — to avoid log volume explosion)
- Integrate into `ScopedDatabase` / `get_db()` (the wrapper applies when `LOG_LEVEL=DEBUG`)
- Verify `database.py` creates indexes for `audit_logs`:
  - `(schoolId, created_at)` descending
  - `(schoolId, entity_id, created_at)`
  - Add if missing; add to migration script
- Add unit tests:
  - Query taking > 100 ms triggers slow query log
  - Query taking < 100 ms does not log
  - `SLOW_QUERY_MS` env var configures the threshold

**Acceptance Criteria:**

Given `SLOW_QUERY_MS=50` is set and a collection operation takes 75 ms,
When the operation completes,
Then a debug log with `slow_query: True` and `duration_ms >= 75` is emitted.

Given `SLOW_QUERY_MS=50` is set and a collection operation takes 30 ms,
When the operation completes,
Then no slow query log is emitted.

Given `database.py` `_create_indexes()` is called,
When it runs,
Then `audit_logs` has indexes on `(schoolId, created_at)` and `(schoolId, entity_id, created_at)`.

Given `request_id_ctx` has a value in the current context,
When a slow query log is emitted,
Then the log record's `request_id` field matches the context value.

- `TimedCollection` or equivalent proxy implemented
- `audit_logs` indexes verified/added
- 3+ unit tests in `tests/backend/unit/test_slow_query.py`
- Slow query logging is DEBUG level (does not appear in INFO output)
- All 387 existing tests still pass

---

## Implementation Order Recommendation

1. **P7.2** — `audit_service.py` shared helper (foundational for P7.3, P7.2 settings coverage)
2. **P7.6** — Error shape consistency (2-line fix, high value, zero risk)
3. **P7.7** — Log level audit in tokens.py (low-risk quality fix)
4. **P7.5** — Failed login logging (security event — implement early)
5. **P7.1** — Branch-scoped audit + pagination (depends on no other story)
6. **P7.3** — Activities audit (depends on P7.2 `audit_service.py`)
7. **P7.4** — Health endpoint S3/SMS checks (infrastructure, can run in parallel)
8. **P7.8** — Slow query detection + index audit (most complex, last)

---

## Audit Coverage Matrix (current state)

| Route File | Has Writes | Has Audit Logs | Gap |
|-----------|-----------|----------------|-----|
| `students.py` | yes | partial (delete only) | create/update not audited |
| `staff.py` | yes | yes (create) | update/delete not audited |
| `fees.py` | yes | yes (partial) | review completeness |
| `attendance.py` | yes | yes (corrections) | bulk mark not audited |
| `academics.py` | yes | yes (exam results) | class/subject CRUD not audited |
| `settings.py` | yes | **NO** | **all writes unaudited** |
| `activities.py` | yes | **NO** | **all writes unaudited** |
| `operations.py` | yes | yes | good coverage |
| `issues.py` | yes | yes | good coverage |
| `import_data.py` | yes | yes | good coverage |
| `notifications.py` | yes | no | low risk, internal only |
| `upload.py` | yes | no | consider for P6 |

> This matrix must be updated after each story in P7 completes.

---

## Epic P7: Retrospective

A retrospective entry for Part 7 to be completed after all P7.1–P7.8 stories are done.
