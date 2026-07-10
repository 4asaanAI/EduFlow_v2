# Epic R15 — Residual Confirmatory Sweep — COMPLETED

**Initiative:** Platform Reliability (non-AI) · **Epic:** R15 (final epic of R12–R15) · **Date:** 2026-07-10
**Executing model:** Claude Opus 4.8 (1M) · one-epic-per-run per `EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md`

**Goal:** a final confirmatory line-level pass over the remaining lower-risk route/service files (the high/medium-risk surface was line-audited in R12–R14). Findings fixed in-story if small + safe, else logged in `DEFERRED-AND-DISCOVERIES.md` / appended as tracked stories. Mirrors R11.6.

**Baseline at start:** 1616 passed, 14 deselected, 0 failed.
**At close:** **1632 passed, 14 deselected, 0 failed** (+16 new tests). Branch-scope grep audit clean on every touched file.

---

## R15.1 — Financial & operational routes deep audit + token spend floor

**Files:** `backend/services/token_service.py`; audited `routes/{fees,operations,issues,payroll}.py`, `services/{fees_service,expense_service,incident_service,token_service}.py`.

- **AC2 (P-L6) — FIXED:** `record_usage`'s `personal_topup` debit changed from `$inc: -tokens_used` (could drive a balance negative on a single large turn or a burst of concurrent turns) to an **atomic aggregation-pipeline clamp**: `$set personal_topups.<uid> = $max(0, $ifNull(field,0) - tokens_used)`. Single server-side op → atomic AND floored at 0. The usage-log insert already happens BEFORE the debit (ordering was correct), mirroring R12.3 on the spend side.
- **AC1 — audited with Critical→Low rubric; branch-scope grep clean.** No new unguarded `scoped_filter` introduced. The `operations.py` school-wide `scoped_filter` hits on `leave_requests`/`announcements`/`users` are the documented-intentional cross-branch decisions (see `platform-quality-sweep.md` line 64) — left unchanged.
- Small consistency fix folded in: `academics.py:641` lesson-plan-completion regex now wraps `current_month` in `re.escape(...)` to match line 634 (the value is already strictly validated `^\d{4}-\d{2}` at line 620, so this is defence-in-depth / R13.6-pattern consistency, not a live injection vector).
- **AC3:** residual findings logged in `DEFERRED-AND-DISCOVERIES.md`.

**Tests:** `unit/test_token_service_phase5.py::test_record_usage_personal_topup_floors_at_zero` (200-token debit against a 30-token balance floors at 0, and a subsequent debit stays at 0). The existing debit test (500→460) still passes (clamp preserves normal debits).
**Test-infra:** extended `conftest.FakeCollection.update_one` to interpret aggregation-pipeline (list) updates via a minimal `$max/$min/$subtract/$add/$ifNull` evaluator — additive (only triggers on a list update; dict updates are unchanged), so the shared fake stays green for all 1616 prior tests.

---

## R15.2 — Student/staff/academic routes deep audit

**Files audited:** `routes/{students,staff,academics,attendance,activities,search}.py`, `services/{student_service,staff_service,academic_structure_service}.py`.

- **AC1 (DPDP least-exposure):** student self-view (`/students/me`) already strips guardian `annual_income`/`occupation`/`employer` (EC-15.6). AI-tool guardian phone masking was done in R4.4. The one open product question — whether full guardian contact (`phone`/`email`) should be visible to *teachers*/admins via `get_student`/`list_guardians` — is a product/DPDP judgment call, appended to `HUMAN-VERIFICATION-CHECKLIST.md` (not a code change; over-restricting here would break legitimate staff→guardian contact).
- **AC1 (tenancy):** the audit-agent's "missing schoolId" flags were false positives — `get_db()` returns `ScopedDatabase`, and `ScopedCollection` auto-injects `schoolId` on find/find_one/insert/update/delete/aggregate/find_one_and_*. School isolation is automatic; only branch scoping is explicit (and is present where required). No leak.
- **AC2 (401/403 pairs):** mutating endpoints across these files carry an auth dependency (`require_role`/`require_access`/`require_owner*`/hardcoded role gates) — enumerated in `epic-R15-review.md`. Cross-tenant fixtures exist from R13. No new endpoint was added in R15.2, so no new security-pair was required here.

---

> **POST-R15 FOLLOW-UP (2026-07-10, owner request):** the in-app help chatbot was
> **fully retired** — the floating widget was removed from all profiles and the
> `/api/assistant` endpoint + its tests deleted (redundant with the main AI chat,
> which every dashboard profile already has). The R15.3/R15.5 assistant hardening
> below (rate limit + token accounting) is therefore superseded — a deleted
> endpoint can't overspend. The audit portions of R15.3 (sms/settings/import) stand.
> Suite after retirement: 1625 passed / 0 failed.

## R15.3 — Messaging, settings & import routes deep audit + assistant hardening

**Files audited:** `routes/{sms,settings,notifications,import_data,reports,queries,assistant}.py`, `services/{org_config_service,announcement_service}.py`.

- **AC2 (P-L9) — CONFIRMED FIXED (R1.7):** `POST /api/assistant` returns a real **503** on `result.ok == False` (assistant.py:235–236) — never `success:true` wrapping a failure. Documented + covered by a regression test.
- **AC1 (P-L9) — FIXED:** `POST /api/assistant` had **no rate limit and no token accounting** → uncapped, invisible Azure spend. Added:
  - a **per-user hourly ceiling** (`ASSISTANT_HOURLY_LIMIT = 20`, in-process, attempt-based, checked before the LLM call → 429 when exceeded). Per-worker by design (documented caveat; the DB-backed `ai_rate_limiter` guards the real AI-write dispatch path).
  - **token accounting**: after a successful call, `record_usage(user, branch_id, result.tokens, "assistant")` logs to `token_usage` (source `"assistant"` records spend without debiting a chat budget). Fail-open so accounting never breaks the reply.
- **AC1 (sms/import):** `sms.py` reads Twilio creds from env only (never logged/returned); `import_data.py` bulk path is bounded and tenant-tagged (R13.9). Both use `ScopedCollection` (school auto-scoped). One Low item logged: `settings.py` `token-usage/admin` uses `.to_list(None)` (unbounded) — should aggregate server-side (deferred, Low).

**Tests (shared with R15.5):** `api/test_r15_residual_sweep.py` — accounting records one `source:"assistant"` row; 21st call in an hour → 429; `ok=False` → 503; + the mandatory 401/403 security pair for the endpoint. `unit/test_r15_residual_sweep.py` — the limiter helper (allow→deny, per-user isolation, hour rollover reset).

---

## R15.4 — Datetime & config hygiene sweep (P-L1–P-L5)

- **AC1 (P-L1) — FIXED (key files):**
  - `services/actor_context.py` `_now()` now returns `datetime.now(timezone.utc)` (was naive `datetime.now()`), unifying it with `_now_utc()`. This is THE persisted-timestamp source for ~40 service write sites (`now_iso()`). On our UTC servers this preserves the same instant and only tags the timezone, fixing the naive/aware BSON-comparison ambiguity flagged in R11.6. **Full suite green after the change** — no timestamp-format assertions broke.
  - `services/notification_service.py:45` `created_at` → `datetime.now(timezone.utc).isoformat()`.
  - The remaining ~120 naive `datetime.now()` calls across 16 route files are a large-scale migration — logged in `DEFERRED-AND-DISCOVERIES.md` (pragmatic scope: the persisted-timestamp *source of record* and the notification write are fixed).
- **AC2 (P-L2) — FIXED:** `services/idempotency.py` caps the stored response body at `MAX_IDEMPOTENCY_BODY_BYTES = 512 KB`. An oversized body is **not stored** (never truncated — a truncated JSON body would replay corrupt); the retry re-executes normally. Prevents an unbounded idempotency doc from blowing past MongoDB's 16 MB BSON limit.
- **AC2 (P-L5) — FIXED:** `GET /api/auth/seed-status` (returned row counts unauthenticated) is now gated: in **production** it requires an authenticated **owner** (401 unauth / 403 non-owner); in dev/staging it stays open as a bootstrap/diagnostic convenience (seed scripts run before any login exists).
- **AC2 (P-L3) — DOCUMENTED (deferred, safe):** `server.py:_check_ai` collapses "AI not configured" and "AI endpoint unreachable" both into `"degraded"` — a diagnostic blind-spot (readiness still fails correctly when AI is down; it just can't distinguish the two). Logged against R9.1; not a correctness bug.

**Tests:** `unit/test_r15_residual_sweep.py` (idempotency small stored / oversized skipped; actor_context tz-aware `now()`/`now_iso()`); `api/test_r15_residual_sweep.py` (seed-status open in dev, 401/403/200 matrix in production).

---

## R15.5 — Confirmatory-pass Low fixes (P-L7, P-L8, P-L9)

- **AC1 (P-L7) — FIXED:** manual attendance entry (`routes/attendance.py`) now catches `DuplicateKeyError` on the `(student_id, date)` unique index. A byte-for-byte replay (same status) is **idempotent** → returns the existing record (200); a differing status is a **genuine conflict** → 409 with a message pointing to the `/correct` endpoint (which keeps an audit trail). Previously this surfaced as a 500.
- **AC2 (P-L8) — FIXED:** house seeding (`routes/activities.py::list_houses`) moved from `insert_one` (two concurrent first-loads → duplicate houses) to an **idempotent upsert** keyed on `(schoolId, name)` with `$setOnInsert` (+ `DuplicateKeyError` swallow + authoritative re-read). Backed by a new **unique `(schoolId, name)` index** on `houses` in `database.py::_create_indexes()`. `schoolId` is set explicitly in `$setOnInsert` (belt-and-suspenders alongside `ScopedCollection` injection). Timestamp is tz-aware UTC (R15.4).
- **AC3 (P-L9):** assistant rate-limit + token accounting + R1.7 `ok=False` confirmation — implemented under R15.3 (single implementation covers both stories).

**Tests:** `api/test_r15_residual_sweep.py` (attendance idempotent-replay / conflict-409 / no duplicate row; house seed → 4 distinct tenant-tagged houses, second load no duplicate); `unit/test_r15_residual_sweep.py` (house upsert idempotent under repeat).

---

## Files touched
- `backend/services/token_service.py` — atomic personal_topup floor
- `backend/services/notification_service.py` — tz-aware created_at
- `backend/services/actor_context.py` — tz-aware `_now`
- `backend/services/idempotency.py` — response-body size cap
- `backend/routes/auth.py` — seed-status production gate (+ `import os`)
- `backend/routes/attendance.py` — DuplicateKeyError → idempotent/409
- `backend/routes/activities.py` — idempotent house seed
- `backend/routes/academics.py` — re.escape consistency (line 641)
- `backend/routes/assistant.py` — rate limit + token accounting
- `backend/database.py` — unique `(schoolId, name)` houses index
- `tests/backend/conftest.py` — FakeCollection pipeline-update support
- `tests/backend/unit/test_token_service_phase5.py` — floor regression
- `tests/backend/unit/test_r15_residual_sweep.py` (new)
- `tests/backend/api/test_r15_residual_sweep.py` (new)
