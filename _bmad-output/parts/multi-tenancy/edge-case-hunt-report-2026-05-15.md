# Edge Case Hunt Report — EduFlow Parts 5-16

**Date:** 2026-05-15
**Reviewer:** BMad Edge Case Hunter (automated, codebase-read)
**Scope:** All 12 epic files (Parts 5-16) + codebase audit

---

## Top 10 Most Critical Edge Cases (Cross-Part)

**Rank 1 — EC-6.1 (Part 6): S3 upload succeeds + DB insert fails + S3 rollback fails → orphaned S3 object (DPDP risk)**
Silent data divergence — file exists in S3 but not in DB. At scale, storage costs grow silently; student documents beyond their intended lifecycle with no DB record to support DPDP deletion requests.
→ New AC required: double-failure rollback path must write orphaned key to `orphaned_s3_keys` collection.

**Rank 2 — EC-15.1 (Part 15): `SKIP_CONSENT_CHECK=true` leaked to staging bypasses DPDP compliance gate**
If this env var is in staging `.env`, ALL student data access bypasses parental consent. India DPDP Act 2023 violation.
→ New AC required: startup `ValueError` if `SKIP_CONSENT_CHECK=true` when `ENVIRONMENT=production|staging`.

**Rank 3 — EC-9.3 (Part 9): Leave approved twice — double notification + double audit entry → payroll processing error**
Two rapid clicks or two admins approve the same leave: staff gets two "approved" notifications; double audit entry falsifies governance record; payroll may count leave twice.
→ New AC required: `update_one` with conditional filter `{status: "pending"}` to make approval idempotent.

**Rank 4 — EC-13.2 (Part 13): Branch code uniqueness is application-level only — concurrent POST creates duplicate branch codes, breaking tenant isolation**
No MongoDB unique index on `(schoolId, branch_code)`. Two simultaneous branch creation requests bypass the `find_one` check.
→ New AC required: `db.branches.create_index([("schoolId",1),("branch_code",1)], unique=True)`.

**Rank 5 — EC-5.4 (Part 5): Notification digest queries `leave_requests` / `facility_requests` without explicit `scoped_filter` — latent cross-school exposure**
`db.leave_requests.count_documents({"status": "pending"})` relies entirely on ScopedCollection auto-injection. Any future refactor bypassing ScopedCollection would expose cross-school data.

**Rank 6 — EC-10.4 (Part 10): Concurrent payroll disbursements — no unique index on `(staff_id, month)` → double salary**
Two simultaneous owner clicks disburse salary twice for same staff member/month. No idempotency guard, no unique index.
→ New AC required: unique index on `(schoolId, staff_id, month)` in `salary_disbursements`.

**Rank 7 — EC-12.3 (Part 12): Concurrent photo PATCH exceeds max-5 guard — non-atomic read-then-write**
Two technicians appending photos simultaneously both read count=4, both push, result: 6 photos.
→ New AC required: use `$size` in the update filter for atomic conditional append.

**Rank 8 — EC-8.1 (Part 8): SSE retry (P8.1) re-issues AI POST → duplicate conversation messages + double token debit**
P8.1 adds retry but the epic notes chat streams must NOT auto-reconnect (duplicate AI calls). Contradiction must be resolved.

**Rank 9 — EC-14.2 (Part 14): HoD teacher `scope.type="subject"` causes `AttributeError` on assignment class_id check**
`scope.class_ids` on a subject-scope object fails. HoD teachers creating cross-class assignments are silently blocked.

**Rank 10 — EC-7.3 (Part 7): Failed login logging captures ALB private IP, not real client IP — defeats brute-force detection**
Behind AWS ALB, `request.client.host = 10.x.x.x`. Must use `X-Forwarded-For` header. All CloudWatch brute-force alarms become useless.

---

## Edge Cases Requiring New Story ACs

| AC Target | Edge Case | Required Fix |
|-----------|-----------|-------------|
| P5.4a/P5.7 | `gather(return_exceptions=True)` swallows `False` returns | Count failures by `is False`, not `isinstance(r, Exception)` |
| P6.1 | Double-failure rollback (DB insert fails + S3 delete fails) | Write orphan to `orphaned_s3_keys` collection |
| P10.2 | FeeSync job hung indefinitely in `in_progress` | Add `SYNC_JOB_TIMEOUT_MINUTES` dead-job recovery |
| P10.4 | Discount threshold exact-value float precision | Use `Decimal`/integer paise comparison |
| P13.4 | Multi-owner lockout — IT-tech can't reset owner password | Owner can reset other owner; document recovery path |
| P15.1 | `SKIP_CONSENT_CHECK=true` in non-dev | Startup `ValueError` guard |
| P15.4 | `partial` status fee transactions not in `total_paid` | Sum `paid_amount` from partial-status rows |
| P16.3 | `fee_head` normalisation conflates distinct fee types | Pre-check collision before normalising |

---

## New Stories Required

| Story | Part | Description |
|-------|------|-------------|
| P11.9 | 11 | DPDP: mask `on_behalf_of_phone` from complaint responses for non-owner roles |
| P16.X | 16 | localStorage draft cleanup: TTL + purge for attendance drafts (7-day expiry) |

---

## Full Edge Case List (by Part)

### Part 5: SSE + Notifications

**EC-5.1:** `defaultdict` `_connections` creates ghost entries when `publish()` accesses a non-existent channel. Empty channel buckets linger after all queues drain.

**EC-5.2:** Concurrent `POST /notifications` + `PATCH /mark-all-read` race — new notification born already-read with no `read_at` explanation.

**EC-5.3:** `X-SSE-Session-ID: "   "` (whitespace-only) bypasses empty check (`if not session_id` is False), corrupts `_connections` key.

**EC-5.4:** Notification digest sub-queries (`leave_requests`, `facility_requests`) use bare dicts, relying entirely on ScopedCollection auto-injection — latent cross-school exposure.

**EC-5.5:** `asyncio.gather(return_exceptions=True)` in P5.7 fan-out: `create_notification()` returns `False` on failure (not raises), so `isinstance(r, Exception)` count is always 0.

### Part 6: File Storage

**EC-6.1:** S3 upload succeeds + DB insert fails + S3 delete raises `ClientError` → original exception replaced, file orphaned in S3 permanently.

**EC-6.2:** PDFs with BOM prefix (`EF BB BF`) before `%PDF` magic bytes rejected by `content[:4] == b'%PDF'` check.

**EC-6.3:** `DELETE /api/uploads/{file_id}` on pre-migration record deletes the legacy S3 key path (unscoped), not the school-namespaced path added by P6.2.

**EC-6.4:** `payload.exe.pdf` (final extension `.pdf`) passes MIME check; `.pdf.exe` is caught. Double-extension not covered.

**EC-6.5:** `GET /api/uploads` caps at 100 results with no pagination — school with 500 uploads gets silent truncation, no `meta.total`.

### Part 7: Observability + Audit

**EC-7.1:** `page=0` in `GET /api/audit-log` → `skip = max(-1,0) * limit = 0`, same as page 1, silently returns wrong page with no error.

**EC-7.2:** `write_audit()` fail-open: when persistent (Atlas disk full), settings changes proceed un-audited with no operator alert.

**EC-7.3:** `request.client.host` behind AWS ALB returns `10.x.x.x` — brute-force login detection logs useless internal IP, not real attacker IP. Must use `X-Forwarded-For`.

**EC-7.4:** `TimedQuery` uses wall-clock `time.time()` which includes event-loop queue wait time — busy-loop spikes cause false slow-query warnings for fast queries.

### Part 8: Frontend Foundation

**EC-8.1:** P8.1 SSE retry re-issues the AI POST — epic explicitly warns against this (duplicate messages, duplicate token debit). Contradiction in the same epic.

**EC-8.2:** `localStorage["attendance_draft_{class_id}_{date}"]` accumulates 1,000+ keys per teacher per year — no TTL, 5MB limit eventually hit.

**EC-8.3:** `DOMPurify` with `FORBID_ATTR: ['style']` strips inline style but not `class` attributes referencing themed CSS variables (`.danger { color: red }`).

**EC-8.4:** `useRef`-based singleton 401 refresh: if the shared promise rejects, all N concurrent callers receive the rejection and may trigger N browser navigations simultaneously.

### Part 9: Principal Vertical

**EC-9.1:** Principal can post announcement with `audience_roles: ["owner"]`, spoofing owner communications.

**EC-9.2:** `GET /api/attendance/class-summary` naive implementation: N×3 MongoDB queries per class (present/absent/not_marked counts separately) — 120 queries for 40 classes.

**EC-9.3:** Leave approved twice — double notification + double audit + potential payroll double-count.

**EC-9.4:** Principal `PATCH /api/staff/{id}` — story says "another admin's role", implying self-update may be allowed. Principal could change their own `sub_category` to `owner`.

### Part 10: Accountant Vertical

**EC-10.1:** FeeSync job hung in `in_progress` → permanent 409 for all subsequent sync triggers, no recovery path.

**EC-10.2:** Discount threshold `float` precision: `10000.000000000001 > 10000` → incorrect approval routing for exact-threshold amounts.

**EC-10.3:** Fee correction second time: `original_snapshot` correctly NOT overwritten, but `correction_count` increment not verified in any AC.

**EC-10.4:** Payroll disbursement: two concurrent owner clicks create two disbursements for same `{staff_id, month}` — no unique index, no idempotency guard.

### Part 11: Receptionist Vertical

**EC-11.1:** Visitor `force: true` bypass has no rate limit — 50 forced check-ins for the same visitor same day, polluting visitor log.

**EC-11.2:** Enquiry backward transition (`enrolled→new`) when a student record already exists — DB inconsistency (student in `db.students`, enquiry shows `new`).

**EC-11.3:** `on_behalf_of_phone` stored verbatim without DPDP consent — accountants see parent PII without consent record.

**EC-11.4:** Certificate `pending_approval` has no timeout — principal on leave = parent waiting indefinitely for university deadline with no escalation path.

### Part 12: Maintenance Vertical

**EC-12.1:** `recurrence_rule` title whitespace: `"Generator Service" ≠ "Generator Service "` — duplicate next-occurrence created on retry.

**EC-12.2:** `escalated_at` set to future timestamp (clock skew) → 429 rate limit applied permanently, escalation permanently blocked.

**EC-12.3:** Concurrent photo `$push` — both technicians read count=4, both push → 6 photos (exceeds max-5 guard).

**EC-12.4:** `GET /api/issues/facility/cost-summary` — Python `sum()` over fetched documents with `None` values → `TypeError`. Must use MongoDB `$sum` aggregation (ignores null).

### Part 13: IT-Tech Vertical

**EC-13.1:** Multi-owner lockout: IT-tech can't reset owner, and if ALL owners lose credentials, no recovery path exists.

**EC-13.2:** Branch code uniqueness: application-level `find_one` check + two concurrent `POST` → duplicate `branch_code` → broken tenant isolation.

**EC-13.3:** `meta.users_over_80_pct` uses default limit (50,000 tokens) for users with custom limits — under-reports high-usage users with low custom caps.

**EC-13.4:** IT-tech audit filter applied in Python after fetching all documents — N+1-equivalent pattern, potential data exposure on refactor.

### Part 14: Teacher Vertical

**EC-14.1:** Bulk attendance audit entry: per-student granularity vs per-class granularity not specified — `write_audit()` designed for single-entity operations.

**EC-14.2:** HoD subject-scope: `scope.class_ids` on `type="subject"` scope → `AttributeError` or empty list — HoD blocked from creating cross-class assignments.

**EC-14.3:** `POST /api/academics/results/bulk` partial failure: mixed-success response shape not defined (`{"success": "partial", "saved": N, "errors": [...]}` not in API conventions).

**EC-14.4:** `force_password_change` redirect — teacher navigates directly to `/#attendance`, bypassing the password-change screen. Route guard must be applied to ALL tool panels.

### Part 15: Student Vertical

**EC-15.1:** `SKIP_CONSENT_CHECK=true` in staging `.env` bypasses DPDP legal gate for ALL students — needs production/staging startup guard.

**EC-15.2:** `GET /api/fees/my` `total_paid` sums `status="paid"` only — excludes `paid_amount` from `status="partial"` transactions (P10.1 introduced `partial`).

**EC-15.3:** `PATCH /api/students/me` writes audit log with `changed_by=student_id` but no `purpose` or `lawful_basis` field — "DPDP-aware audit" is not concretely defined.

**EC-15.4:** Daily AI message cap `STUDENT_AI_DAILY_MESSAGES` — no timezone specified for "daily" reset. IST vs UTC difference creates a 5.5-hour gaming window.

### Part 16: Platform Integration

**EC-16.1:** `fee_head` normalisation to lowercase collapses "Tuition" (annual) and "TUITION" (monthly supplement) → incorrect idempotency match.

**EC-16.2:** Owner with explicit `branch_id` query param — does the endpoint filter by it or use JWT branch_id (undefined for owner)? Cross-branch data exposure risk.

**EC-16.3:** Locust load test: Motor connection pool (default 100) + 50 concurrent Locust users on Atlas M0 (500 connection limit) — pool exhaustion misattributed to slow queries.

**EC-16.4:** Playwright `localStorage["attendance_draft_*"]` from previous test run persists into next run — "Restore Draft?" dialog interferes with clean attendance test flow.
