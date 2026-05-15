---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 10'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 10
part_name: 'Accountant Role Vertical'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy', 'Part 8 Frontend Foundation', 'Part 9 Principal Vertical']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 10: Accountant Role Vertical

## Context

Part 10 targets the completeness and correctness of the accountant (admin + sub_category=accounts) role vertical. The accountant is the primary operator for fee management, discount applications, payment corrections, expense tracking, and financial exports. Auditing `FeeCollection.js`, `FeeSync.js`, `backend/routes/fees.py`, `backend/routes/operations.py`, `backend/routes/exports.py`, and migration `009_add_payroll.py` reveals: the fee workflows are largely implemented but have notable gaps — the discount application has no approval gate for large amounts, the export is missing `receipt_number` and `corrected` flag fields, the expense workflow is accessible to ALL admin sub-categories (not gated to accountant/owner), and the payroll data model from migration 009 has zero route coverage.

**Entering baseline:** 387 backend tests, 0 skipped.

---

## Epic P10: Accountant Role Vertical

### Story P10.1: FeeCollection.js — partial payment support and receipt generation audit

**Problem:** `FeeCollection.js` supports recording a payment via `POST /api/fees/transactions`. The `status` field can be set to `paid`, `pending`, or `overdue`. However:

1. There is no partial payment concept — a fee entry is either fully paid or pending. If a parent pays Rs 3,000 of a Rs 5,000 fee, the accountant must either record the full amount as paid (incorrect) or leave it pending (loses the payment record).
2. Receipt generation (`downloadReceipt` at line 7) calls `GET /api/fees/transactions/{id}/receipt` but there is no corresponding backend route for this — the endpoint does not exist in `fees.py`. The download will fail with a 404 for every transaction.
3. The receipt download is only shown for transactions with `status === 'paid'` (line 432). Partial payments, if implemented, would need their own receipt format.

**Scope:**
- Add a `partial` payment status to the `FeeTransaction` schema model and `status` enum in `fees.py`.
- Add a `paid_amount` field to `FeeTransaction` (defaults to `amount` for full payments). For partial payments, `paid_amount < amount` and `status = "partial"`.
- Update `POST /api/fees/transactions` to accept `paid_amount` in the body; if `paid_amount` is provided and is less than `amount`, set `status = "partial"`.
- Add `GET /api/fees/transactions/{id}/receipt` endpoint in `fees.py`: returns a simple PDF or structured JSON receipt with fields: `receipt_number`, `student_name`, `fee_type`, `amount`, `paid_amount`, `payment_mode`, `transaction_ref`, `paid_date`, `status`. Auth: `require_role("owner", "admin")`. For now, return JSON with `Content-Type: application/json` (PDF generation is a future enhancement — return a structured receipt document).
- Update `downloadReceipt` in `FeeCollection.js` to handle JSON receipts (open in a new tab or show in a modal) until PDF is available.
- Add backend tests: partial payment → `status=partial`, `paid_amount < amount`; receipt endpoint returns correct fields including `receipt_number`.

**Acceptance Criteria:**
- `POST /api/fees/transactions` with `paid_amount` < `amount` creates a `partial` status transaction
- `GET /api/fees/transactions/{id}/receipt` endpoint exists and returns `receipt_number`, `student_name`, `paid_amount`, `payment_mode`
- Receipt download in `FeeCollection.js` does not 404
- At least 3 new backend tests (partial payment, receipt fields, receipt 404 for non-existent id)
- Existing 387 tests still pass

---

### Story P10.2: FeeSync.js — idempotency, external system context, and conflict resolution audit

**Problem:** `FeeSync.js` triggers `POST /api/fees/sync/trigger` via `triggerFeeSync()`. Looking at the sync flow:

1. The sync endpoint in `fees.py` calls an external fee software API via `httpx` (import visible at line 17 of `fees.py`). The sync is triggered ad-hoc by clicking a button — there is no idempotency protection. If the accountant clicks "Trigger sync" twice in quick succession, two sync jobs run concurrently and both write to `db.fee_sync_jobs`, potentially creating duplicate conflict records.
2. `FeeSync.js` shows `job.status` from the API response but never polls for job completion — the "Trigger sync" button returns the initial job record (likely `status: "in_progress"`) and the UI does not update to show `completed` unless the user manually clicks "Refresh".
3. Conflict resolution (`resolve()` function at line 43) calls `PATCH /api/fees/sync/{job_id}/conflicts/{conflict_id}` but the UI shows `Ours: Rs {amount}` and `Theirs: Rs {amount}` — there is no explanation of WHICH system is "ours" and which is "theirs", making the decision meaningless to an accountant.

**Scope:**
- In the sync trigger endpoint (`POST /api/fees/sync/trigger`), add an idempotency check: if a sync job with `status = "in_progress"` already exists, return the existing job rather than creating a new one.
- Add auto-polling in `FeeSync.js`: after triggering a sync, poll `GET /api/fees/sync/{job_id}` every 3 seconds until `status` is `completed` or `failed` (max 10 polls, then show "Taking longer than expected — click Refresh").
- Update the conflict display in `FeeSync.js` to label "Ours" as "EduFlow" and "Theirs" as "Fee Software (external)" with the external system name from `job.source_system` (or a fallback of "External System").
- Add backend test: trigger sync twice in quick succession → only one job created (second call returns existing in-progress job).

**Acceptance Criteria:**
- Two rapid sync trigger calls result in exactly one sync job
- `FeeSync.js` auto-polls until sync job completes or fails
- Conflict display labels "EduFlow" vs "External System (Fee Software)" clearly
- At least 2 new backend tests
- Existing 387 tests still pass

---

### Story P10.3: Fee structure management — accountant can view but should not create structures

**Problem:** `GET /api/fees/structures` is accessible to `require_role("owner", "admin")` (line 98 of `fees.py`). This means the accountant (admin + sub_category=accounts) can view fee structures. However:

1. There is no `POST /api/fees/structures` endpoint for creating fee structures. Fee structures are presumably created at the start of a school year and should only be editable by owner or principal.
2. The frontend `FeeCollection.js` does not show fee structures at all — the accountant can see transactions and apply discounts but cannot see what the base fee amounts are supposed to be.
3. There is no `PATCH /api/fees/structures/{id}` endpoint. If a fee structure was entered incorrectly, there is no way to correct it.

**Scope:**
- Add `POST /api/fees/structures` endpoint in `fees.py`: creates a fee structure with `{name, class_id, fee_heads: [{name, amount, due_date, frequency}]}`. Auth: `require_role("owner")` only (principal and accountant should not create structures).
- Add `PATCH /api/fees/structures/{id}` endpoint: updates an existing fee structure. Auth: `require_owner` (owner-only update).
- Add a "Fee Structures" read-only tab to `FeeCollection.js`: lists all fee structures with class, fee heads, and amounts. Accountant can view (calls `GET /api/fees/structures`), owner sees edit buttons. This makes the fee collection panel self-documenting — the accountant knows what should be collected.
- Add backend tests: owner creates structure → 201; accountant tries to create → 403; accountant reads structures → 200.

**Acceptance Criteria:**
- `POST /api/fees/structures` returns 201 for owner, 403 for accountant
- `PATCH /api/fees/structures/{id}` returns 200 for owner, 403 for accountant
- Accountant can `GET /api/fees/structures` (200)
- Fee Structures read-only tab visible in `FeeCollection.js` for accountant
- At least 3 new backend tests
- Existing 387 tests still pass

---

### Story P10.4: Discount application — approval flow for large discounts

**Problem:** `POST /api/fees/discounts/apply` (line 396 of `fees.py`) requires `require_role("owner", "admin")` — any admin can apply any discount of any size without a secondary approval. This is a financial control gap:

1. A discount type can have `value_type = "flat"` and `value = 50000` (Rs 50,000 flat discount). An accountant could apply this to any student with no second pair of eyes.
2. There is no `threshold` concept — no maximum discount amount that an accountant can apply unilaterally.
3. The frontend `FeeCollection.js` has a free-text "Approval note" field in the discount apply form but the backend does not validate or use it beyond storing it in the record.

**Scope:**
- Add a configurable threshold to the school settings (or hard-code `DISCOUNT_APPROVAL_THRESHOLD = 10000` as an env var / DB setting): any discount with a calculated discount amount exceeding the threshold requires owner approval.
- When a discount application would exceed the threshold:
  - Instead of inserting directly to `db.fee_discounts`, insert to `db.pending_discount_approvals` with `status = "pending"`.
  - Return `{"success": True, "pending_approval": true, "message": "Discount requires owner approval due to amount threshold"}` with HTTP 202.
- Add `GET /api/fees/discounts/pending-approvals` (owner-only): lists discounts pending approval.
- Add `PATCH /api/fees/discounts/pending-approvals/{id}/approve` (owner-only): approves the discount and moves it to `db.fee_discounts`.
- Add `PATCH /api/fees/discounts/pending-approvals/{id}/reject` (owner-only): rejects the discount.
- Update `FeeCollection.js` to show a "Pending approval" state when the API returns 202.
- Add backend tests: discount below threshold → immediate approval; discount above threshold → 202 pending; owner approves pending → discount created; owner rejects → discount removed.

**Acceptance Criteria:**
- Discount amounts exceeding the threshold return HTTP 202 and create a pending approval record
- Owner can list, approve, and reject pending discount approvals
- `FeeCollection.js` handles 202 response and shows "Pending approval" state
- At least 4 new backend tests
- Existing 387 tests still pass

---

### Story P10.5: Fee transaction correction — original record preservation and role restriction

**Problem:** `PATCH /api/fees/transactions/{id}/correct` (line 226 of `fees.py`):

1. Uses `require_role("owner", "admin")` — any admin sub-category can correct fee records. An accountant correcting their own records with no oversight is a financial control risk.
2. The original record IS preserved in `db.fee_transaction_corrections` (line 250) — this is correctly implemented. However, the original `db.fee_transactions` document is mutated in place — there is no `original_snapshot` field added to the transaction itself to make the correction visible at a glance without querying the corrections collection.
3. The `corrected: True` flag IS set on the transaction (line 251) — but `GET /api/fees/transactions` does not include `corrected` in its response filtering, so the frontend cannot highlight corrected records.

**Scope:**
- Tighten the correction endpoint auth: allow accountant (admin + sub_category=accounts) to correct their own-created transactions; require owner for corrections to transactions created by other users. Implement this as: if `user["role"] == "admin"` and `user.get("sub_category") == "accounts"`, check `original["created_by"] == user["id"]`; if mismatch, raise 403.
- Add `original_snapshot` embedded field to the transaction document on first correction: `original_snapshot = {amount, status, payment_mode, ...}` set only if not already present (preserves the first-ever state).
- Update `GET /api/fees/transactions` to include `corrected` and `correction_count` fields (count from `db.fee_transaction_corrections` where `transaction_id` matches).
- Update `FeeCollection.js` overdue records table to highlight corrected transactions (amber badge or strikethrough on original value with corrected value inline).
- Add backend tests: accountant corrects own transaction → 200; accountant corrects another user's transaction → 403; correction sets `original_snapshot` once and does not overwrite it on subsequent corrections.

**Acceptance Criteria:**
- Accountant can correct only their own transactions (403 for others' transactions)
- Owner can correct any transaction
- `original_snapshot` field is set on first correction and preserved on subsequent corrections
- `GET /api/fees/transactions` returns `corrected` flag and `correction_count`
- `FeeCollection.js` highlights corrected transactions with an amber badge
- At least 4 new backend tests
- Existing 387 tests still pass

---

### Story P10.6: Expense tracking — restrict to accountant/owner; add category budget

**Problem:** `GET /api/ops/expenses` and `POST /api/ops/expenses` (lines 275–298 of `operations.py`) use `require_role("owner", "admin")`. This means:

1. A principal, transport head, maintenance admin, or any other admin sub-category can view and create expenses — which is not appropriate. Expense creation and viewing should be restricted to owner and accountant.
2. There is no budget concept — expenses are free-form with no limit per category. An accountant creating a "maintenance" expense category with no cap is a financial risk.
3. The expense export (`GET /api/export/expenses`) uses `require_owner` only — the accountant cannot export expenses despite being the person responsible for them.

**Scope:**
- Create a shared auth helper `_is_owner_or_accountant(user)` in `operations.py` (similar to `_is_owner_or_principal`): `user.get("role") == "owner" or (user.get("role") == "admin" and user.get("sub_category") == "accounts")`.
- Change `GET /api/ops/expenses`, `POST /api/ops/expenses`, `PATCH /api/ops/expenses/{id}`, and `DELETE /api/ops/expenses/{id}` to use `_is_owner_or_accountant` (inline guard, same pattern as `attendance.py`).
- Change `GET /api/export/expenses` to use `require_role("owner", "admin")` with an inline `_is_owner_or_accountant` check, or define a `require_owner_or_accountant` dependency in `middleware/auth.py`.
- Add `GET /api/ops/expenses/summary` endpoint: returns total expenses by category for the current month and year-to-date. Auth: owner or accountant.
- Update `FeeCollection.js` (or add a dedicated `ExpenseTracker` component) to show the expense summary and allow creating expenses from the accountant vertical.
- Add backend tests: principal tries to create expense → 403; accountant creates expense → 201; accountant exports expenses → 200; expense summary returns correct category totals.

**Acceptance Criteria:**
- Principal, transport head, maintenance admin receive 403 from all expense endpoints
- Accountant can CRUD expenses and export them
- `GET /api/ops/expenses/summary` returns monthly and YTD totals by category
- At least 4 new backend tests
- Existing 387 tests still pass

---

### Story P10.7: Export completeness — fee-transactions CSV missing receipt_number and corrected flag

**Problem:** `GET /api/export/fee-transactions` (line 36 of `exports.py`) exports: Student, Fee Type, Amount, Status, Due Date, Paid Date, Payment Mode. It is missing:

1. `receipt_number` — the unique receipt identifier that an accountant needs for reconciliation.
2. `corrected` flag — whether the transaction was amended after the fact.
3. `transaction_ref` — the external payment reference (UPI/bank transfer ID).
4. `fee_period` — the billing period the payment belongs to.
5. Student scoping — the export iterates `db.fee_transactions` and fetches `db.students` per transaction in a loop (N+1 query). For 5,000 transactions this could take 30+ seconds.

**Scope:**
- Add `receipt_number`, `corrected` (boolean), `transaction_ref`, `fee_period`, and `class_name` to the exported CSV columns.
- Update the CSV headers array to: `["Student", "Class", "Fee Type", "Period", "Amount", "Status", "Due Date", "Paid Date", "Payment Mode", "Transaction Ref", "Receipt No", "Corrected"]`.
- Fix the N+1 query: pre-fetch all students in a single `db.students.find({"id": {"$in": student_ids}})` call before the row-building loop.
- Add the `fee_period` filter parameter: `GET /api/export/fee-transactions?fee_period=2026-04` filters to a specific month.
- Add backend tests: exported CSV includes `receipt_number` column; exported CSV includes `corrected` column; N+1 fix verified (mock: students fetched once, not per row).

**Acceptance Criteria:**
- CSV headers include `Receipt No`, `Corrected`, `Transaction Ref`, `Period`, `Class`
- CSV rows populate `receipt_number` and `corrected` fields correctly
- Students pre-fetched in single query (no N+1)
- `fee_period` filter parameter works
- At least 3 new backend tests
- Existing 387 tests still pass

---

### Story P10.8: Payroll access — data model exists but zero route coverage

**Problem:** Migration `009_add_payroll.py` creates `db.salary_structures` and `db.salary_disbursements` collections. `db.audit_logs` lists `payroll` in `FINANCIAL_COLLECTIONS` (line 9 of `audit.py`). However:

1. There are zero HTTP routes for payroll — no `GET /api/payroll`, no `POST /api/payroll/disburse`, no `GET /api/payroll/staff/{id}`.
2. The accountant has no way to view or manage payroll data via the API or frontend.
3. This is an unfulfilled data model promise: migrations created the collections, but the business logic layer is absent.

**Scope (this story creates the foundational payroll routes — not a full payroll system):**
- Add `backend/routes/payroll.py` with:
  - `GET /api/payroll/structures` — list all salary structures. Auth: owner or accountant.
  - `POST /api/payroll/structures` — create a salary structure `{staff_id, base_salary, allowances: {}, deductions: {}}`. Auth: owner only.
  - `GET /api/payroll/disbursements?month={yyyy-mm}` — list salary disbursements for a month. Auth: owner or accountant.
  - `POST /api/payroll/disburse` — create a disbursement record `{staff_id, month, gross, deductions, net, status: "pending"|"processed"}`. Auth: owner only.
- Register `payroll.router` in `main.py` (or equivalent).
- Add a "Payroll" read-only panel to the accountant's tool view: shows this month's disbursements with staff name, gross, deductions, net, status. Owner sees an additional "Mark as Processed" button.
- Add backend tests: owner creates salary structure → 201; accountant reads structures → 200; accountant tries to create structure → 403; disbursement list returns correct month filter.

**Acceptance Criteria:**
- `GET /api/payroll/structures` returns 200 for owner and accountant
- `POST /api/payroll/structures` returns 201 for owner, 403 for accountant
- `GET /api/payroll/disbursements` returns 200 for owner and accountant
- `POST /api/payroll/disburse` returns 201 for owner, 403 for accountant
- Payroll read-only panel visible in accountant frontend view
- At least 4 new backend tests
- `payroll.router` registered in main app
- Existing 387 tests still pass

---

## FR Coverage Map

| FR ID | Story | Description |
|-------|-------|-------------|
| FR-P10.1 | P10.1 | Partial payment support (paid_amount < amount, status=partial) |
| FR-P10.2 | P10.1 | Receipt endpoint exists and returns required fields |
| FR-P10.3 | P10.2 | Fee sync trigger is idempotent (no duplicate jobs) |
| FR-P10.4 | P10.2 | FeeSync.js auto-polls until job completion |
| FR-P10.5 | P10.3 | Accountant can view fee structures (owner creates/edits) |
| FR-P10.6 | P10.4 | Large discounts require owner approval (threshold-based) |
| FR-P10.7 | P10.5 | Accountant can correct only their own transactions |
| FR-P10.8 | P10.5 | original_snapshot preserved on first correction |
| FR-P10.9 | P10.6 | Expense CRUD restricted to owner/accountant |
| FR-P10.10 | P10.6 | Expense summary by category available to accountant |
| FR-P10.11 | P10.7 | Fee export includes receipt_number, corrected flag, transaction_ref |
| FR-P10.12 | P10.8 | Payroll routes exist and return correct RBAC responses |

---

## NFRs

| NFR ID | Category | Requirement |
|--------|----------|-------------|
| NFR-P10.1 | Performance | `GET /api/export/fee-transactions` must not issue N+1 DB queries; students must be batch-fetched in a single query |
| NFR-P10.2 | Financial control | No discount exceeding the configured threshold may be applied without owner approval |
| NFR-P10.3 | Audit | Every fee correction must preserve the original record snapshot; correction audit log must include `reason` and `corrected_by` |
| NFR-P10.4 | Security | Expense, payroll, and fee-structure write endpoints must return 403 for all non-owner, non-accountant admin sub-categories |

---

## Implementation Order

1. **P10.7** (export completeness) — backend-only, fixes an obvious data gap with N+1 fix included
2. **P10.5** (correction role restriction + original_snapshot) — closes a financial control gap
3. **P10.6** (expense auth tightening) — closes a privilege overreach with minimal scope
4. **P10.1** (partial payments + receipt endpoint) — fills the 404 gap; moderate scope
5. **P10.3** (fee structure management) — adds missing create/edit endpoints + read-only accountant view
6. **P10.4** (discount approval gate) — adds new workflow (pending_approvals); depends on stable fees.py from P10.5
7. **P10.2** (FeeSync idempotency + polling) — polish; low regression risk
8. **P10.8** (payroll routes) — new file, largest scope; last to avoid blocking other stories

---

## Epic P10: Retrospective

A retrospective entry for Part 10 to be completed after all P10.1–P10.8 stories are done.
