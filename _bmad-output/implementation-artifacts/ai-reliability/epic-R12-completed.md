# Epic R12 — Onboarding, Billing & Payroll Integrity — COMPLETED

**Date:** 2026-07-10
**Epic:** R12 (Platform Reliability initiative, epics-platform-reliability.md)
**Baseline:** 1552 tests passing
**Final:** 1568 tests passing (+16 net new)
**Deferred/skipped:** 14 (baseline pinned failures, unchanged)

---

## Stories shipped

### R12.1 — Onboarding: owner auth record completeness
**Audit finding:** P-H1 — newly provisioned owner accounts lacked `username_lower` (case-insensitive login fails) and `user_info` sub-doc (JWT population fails → AI context empty).

**Changes:**
- `backend/routes/operator.py` — `create_school()` now derives `owner_name` (from email prefix, capitalized) and `owner_initials`; inserts `username_lower: owner_email.lower()` and `user_info: {id, role, name, initials}` into the `auth_users` row at provision time.

**ACs met:**
- AC1: `username_lower` present and lowercase-normalized.
- AC2: `user_info.role`, `user_info.id`, `user_info.name`, `user_info.initials` all populated.
- AC3: test `test_create_school_success` asserts all four fields.

---

### R12.2 — Billing: webhook tenant isolation (ContextVar approach)
**Audit finding:** P-C1 — Razorpay webhook handlers called `_scoped_billing_db()` which captured a stale ScopedDatabase; cross-tenant notes could credit wrong school.

**Changes:**
- `backend/services/razorpay_service.py` — Added `_resolve_school_for_branch(raw_db, branch_id) -> str | None` (looks up `branches` collection, unscoped). Removed `_scoped_billing_db()` helper. All four webhook handlers (`handle_payment_link_paid`, `handle_subscription_activated`, `handle_subscription_charged`, `handle_subscription_cancelled`) now:
  1. Call `get_raw_db()` to resolve branch → `schoolId` from `raw_db.branches`.
  2. Set `_school_id_var.set(school_id)` to establish correct per-request school context.
  3. Call `get_db()` which returns a properly scoped database.
  4. Reset the ContextVar in `finally`.
  5. Log and early-return if `school_id` is unresolvable (AC4 fail-closed).

**ACs met:**
- AC1: school resolved via `branches` lookup before any billing op.
- AC2: unresolvable branch → logged + return (no writes).
- AC3: cross-tenant isolation — school-b webhook credits school-b only; school-a untouched.
- AC4: `test_payment_link_unresolvable_branch_rejected` asserts no purchase inserted.

---

### R12.3 — Billing: top-up atomicity and `$setOnInsert` path conflict
**Audit finding:** P-C2 — `purchase_topup_razorpay` had a MongoDB path conflict: `"personal_topups": {}` in `$setOnInsert` and `personal_topups.{user_id}` in `$inc` → WriteConflict on first top-up.

**Changes:**
- `backend/services/razorpay_service.py` — `purchase_topup_razorpay()`:
  - Removed `"personal_topups": {}` from `$setOnInsert` (MongoDB `$inc` on dotted path auto-creates nested object).
  - Wrapped `token_purchases.insert_one` + `token_balances.update_one` in `get_txn_session()` transaction (atomic, idempotent on replay via `razorpay_reference_id` unique index guard).
- `handle_subscription_charged`: also wrapped its insert + update pair in a transaction.

**ACs met:**
- AC1: first top-up for a new branch (no balance doc) succeeds without WriteConflict.
- AC2: replayed webhook doesn't double-credit (idempotency via purchase lookup).
- AC3: `test_subscription_charged_cross_tenant_credits_correct_school` verifies.

---

### R12.4 — Onboarding: atomic provisioning + partial-failure resume
**Audit finding:** P-H2 — `create_school()` issued three separate inserts (schools, school_settings, auth_users); a crash between inserts left a stub school with no owner. Re-calling the endpoint returned 409 (duplicate) instead of resuming.

**Changes:**
- `backend/routes/operator.py` — `create_school()`:
  - Duplicate check now distinguishes: if `schools` row exists **but no owner** `auth_users` row → delete the stub (schools + school_settings) and proceed with fresh provisioning (resume).
  - All three inserts (`schools`, `school_settings`, `auth_users`) wrapped in `get_txn_session()` transaction with `session=session` passed to each `insert_one`.

**ACs met:**
- AC1: successful first-call inserts all three docs atomically.
- AC2: partial failure (schools stub, no auth_users) → clean resume on retry → 200 + full owner account created.
- AC3: fully complete (both rows exist) → 409.

---

### R12.5 — Payroll: canonical sub_category and idempotent disbursement
**Audit finding:** P-M4 — payroll routes accepted legacy `"accounts"` sub_category (fee domain compat leak) and lacked idempotent disbursement (double-submit created two rows, misreporting payroll total).

**Changes:**
- `backend/services/payroll_service.py` (new file):
  - `is_owner_or_accountant(user)` — canonical check: owner OR `(admin AND sub_category == "accountant")`. `"accounts"` is NOT accepted.
  - `disburse_salary(db, *, staff_id, month, base_salary, ...)` — checks for existing row by (staff_id, month) first; returns `(doc, True)` if already exists. Inserts canonical schema (`base_salary`, `allowances`, `deductions`, `net_amount`, `paid_by`, `paid_at`). Catches `DuplicateKeyError` for concurrent double-submit.
  - `upsert_salary_structure(db, *, staff_id, base_salary, ...)` — idempotent by staff_id (replaces if exists).
- `backend/routes/payroll.py` — imports `is_owner_or_accountant` and both service functions from `payroll_service`. `create_disbursement` now accepts canonical `"accountant"` AND the legacy `"accounts"` field names (`gross`/`net`) for backward compat with the API client, but delegates to canonical service.
- `backend/routes/fees.py` — `_is_accounts(user)` reverted to accept BOTH `"accounts"` and `"accountant"` (fee domain backward compat; canonical enforcement is payroll-service-only). Route handlers renamed (`fees_upsert_salary_structure`, `fees_create_salary_disbursement`) to avoid collision with imported service functions. Both delegate to `payroll_service.*`.

**ACs met:**
- AC1: disbursement doc uses canonical field names (`base_salary`, `net_amount`, `paid_by`).
- AC2: double-submit returns existing row + `idempotent: true`; only one DB row.
- AC3: payroll routes require `"accountant"` sub_category; `"accounts"` returns 403.

---

## Test files added / updated

| File | Tests | What they cover |
|------|-------|-----------------|
| `tests/backend/unit/test_school_onboarding.py` | Updated 2 + added 1 | R12.1 username_lower/user_info assertions; R12.4 duplicate/resume semantics |
| `tests/backend/unit/test_razorpay_checkout.py` | Updated fixture | R12.2 `branches` collection on `TokenDb`; `get_raw_db` patch |
| `tests/backend/unit/test_r12_billing.py` (new) | 5 | R12.2 cross-tenant isolation, unresolvable branch, R12.3 path-conflict fix, idempotency |
| `tests/backend/unit/test_r12_payroll.py` (new) | 11 | R12.5 service-layer unit tests + route auth policy (owner, accountant, legacy-403, 401) |

---

## Grep audit — scoped_filter in modified routes

```
grep -n "scoped_filter(" backend/routes/operator.py backend/routes/payroll.py backend/routes/fees.py
```

- `operator.py` — no `scoped_filter` calls (uses `raw_db` directly, pre-school-context; intentional).
- `payroll.py` — 0 calls; uses `get_db()` (ScopedDatabase handles schoolId injection).
- `fees.py` — existing calls all have `# branch-scope: intentional` comments; unchanged.

---

## No regressions

Full suite: **1568 passed, 14 deselected** (pinned baseline failures, unchanged).
