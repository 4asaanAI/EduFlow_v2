---
title: 'Richer fee history + full-size fee overlay on student profile'
type: 'feature'
created: '2026-09-24'
status: 'in-review'
context: []
baseline_commit: 'e982128d9bff05203faa0ec877ad3c891615322c'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `StudentFeePanel.js` (the fee panel opened from a student's profile) shows only Period/Head/Amount/Status/Due, hides `paid_amount` entirely, and is a narrow 640px centered modal — too small to hold the extra detail finance staff need to see per record.

**Approach:** Add Total Fees, Fees Paid, Created At, Last Edited, Discount and Fine columns to the history table plus a non-editable Total row; grow the panel into a large full-viewport overlay; no backend schema change (all new columns derive from data that already exists).

## Boundaries & Constraints

**Always:**
- `amount` = Total Fees, `paid_amount` = Fees Paid — both already exist on the fee-transaction doc; no new persisted fields.
- Discount stays read from the existing student-level discount system (`GET /api/fees/discounts/{student_id}` → `total_discount`) — never a typed input on the payment/correction form.
- Fine stays calculate-only, never persisted — reuse `services/late_fine_service.compute_late_fine`, never write a `fine`/`late_fee` field to `fee_transactions`.
- Created At = existing `created_at`; Last Edited = existing `updated_at` (render "—" when absent, i.e. never corrected).
- Keep the `require_finance_profile` gate and `getFeeTransactions`/`recordFeePayment`/`correctFeeTransaction` API functions as-is — this is a display/read addition, not a new write surface.

**Ask First:** none — no undecided fork remains (discount/fine sourcing was settled with the human before this spec was written).

**Never:**
- Do not add `discount` or `fine` as typed fields on the payment form or the correction form.
- Do not persist a computed fine anywhere.
- Do not touch `FeeCollection.js` (the separate accountant-wide tool) — scope is `StudentFeePanel.js` and its backend support only.
- Do not introduce a new route/page for this — grow the existing overlay in place (avoids router/deep-link surface, lowest blast radius for a modal-heavy codebase).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Normal row | txn with amount, paid_amount, created_at, no correction | Total Fees, Fees Paid, Created At shown; Last Edited shows "—" | N/A |
| Corrected row | txn has `updated_at` from a correction | Last Edited shows `updated_at` | N/A |
| No discount on file | `total_discount` is 0 or student has no `fee_discounts` | Discount column shows ₹0 on every row and in Total row | 404/empty from discount endpoint → treat as ₹0, don't block table render |
| Fine calc fails | `fee_period` isn't `YYYY-MM` or `due_date` missing | Fine cell shows "—" for that row, not an error | Catch `LateFineError` per-row; never blocks the table |
| Total row | ≥1 transaction loaded | Sums Total Fees and Fees Paid across all rows; Fine cell sums the per-row computed fines; Discount cell shows the single `total_discount` figure (not summed — it's one student-level value, summing per-row would multiply it) | N/A |

</frozen-after-approval>

## Code Map

- `frontend/src/components/ui/StudentFeePanel.js` -- history table, payment form, overlay wrapper — main file
- `backend/routes/fees.py` -- `get_fee_transactions` (line ~371), `_discount_breakdown` (~859) — reuse, no signature change
- `backend/services/late_fine_service.py` -- `compute_late_fine` — reuse for per-row fine calc
- `frontend/src/lib/api.js` -- `getFeeTransactions`, add `getStudentDiscounts(studentId)` if not already exported

## Tasks & Acceptance

**Execution:**
- [x] `frontend/src/lib/api.js` -- `getFeeDiscounts(studentId)` already wraps `GET /api/fees/discounts/{student_id}`; reuse it, no new wrapper needed -- history table needs `total_discount`
- [x] `frontend/src/components/ui/StudentFeePanel.js` -- fetch discount breakdown alongside transactions in `load()`; compute fine per (session year, quarter) group (sum outstanding across every transaction in that quarter, one `calculateLateFine` call per session year covering all its distinct quarters, `settled_on` = latest `paid_date` only when the whole group is `paid`) -- source the new columns, avoiding `late_fine_service`'s per-quarter-not-per-fee-head invariant
- [x] `frontend/src/components/ui/StudentFeePanel.js` -- add columns Total Fees, Fees Paid, Discount, Fine, Created At, Last Edited to the `<thead>`/`<tbody>`; relabel current "Amount" as "Total Fees" -- matches the intent
- [x] `frontend/src/components/ui/StudentFeePanel.js` -- add a non-editable `<tfoot>` Total row per the matrix above -- explicit ask
- [x] `frontend/src/components/ui/StudentFeePanel.js` -- widen `panelStyle`/`overlayStyle` to a large full-viewport layout (e.g. `width: min(1200px, 96vw)`, `maxHeight: 94vh`, inner table area scrolls) -- "large overlay, not a small popup"
- [x] `tests/backend/api/test_fee_history_detail_fields.py` (new) -- asserts `GET /api/fees/transactions` returns `amount`, `paid_amount`, `created_at` on a fresh record and `updated_at` after a correction
- [x] `frontend/src/components/__tests__/StudentFeeCollectionCTA.test.js` -- added fixtures + tests asserting all six new cells, the Total row, the shared-quarter fine, a second distinct quarter summed separately, and the load-failure path
- [x] `frontend/src/components/ui/StudentFeePanel.js` -- reset `fineByTxnId`/`fineByGroup` when `getFeeTransactions` fails; derive `colSpan` from `HISTORY_COLUMN_LABELS`; fine is now grouped by (session year, quarter) instead of per transaction -- closes the loopback-1 findings

**Acceptance Criteria:**
- Given a student with 3 fee transactions and a 10% discount on file, when the fee panel opens, then Total Fees/Fees Paid/Discount/Fine/Created At/Last Edited all render, and the Total row sums Total Fees and Fees Paid correctly.
- Given a transaction with `fee_period` not matching `YYYY-MM`, when the panel renders, then the Fine cell shows "—" and no error is thrown.
- Given the panel is open, when compared to before, then the overlay occupies a clearly larger area of the viewport (not the previous 640px-wide modal).

## Spec Change Log

- **2026-09-24, loopback 1 (bad_spec).** Three parallel reviews (blind adversarial, edge-case hunter, acceptance auditor) all converged on the same finding: the original Design Notes' "per transaction as if it were its own quarter's whole outstanding bill" approach directly contradicts `late_fine_service.py`'s own documented rule — "one fine per child per quarter, never one per fee head" — and its enforced invariant (`assess_quarters` raises `LateFineError` when the same quarter appears more than once as still-accruing in one batch). Any student with two fee records due in the same quarter (a normal case — e.g. tuition + transport) would trigger that guard and silently blank the Fine column for every row in that request, not just one row. **Amended:** Fine is now computed once per **(session year, quarter)** group — outstanding is summed across every transaction sharing that quarter, `settled_on` is only set when every transaction in the group is `paid` (using the latest `paid_date` among them), and the resulting single total is displayed on every contributing row (same convention already used for Discount) and counted once in the Total row. This avoids the duplicate-quarter guard structurally instead of hoping it doesn't fire. **KEEP:** everything else from the original implementation is unchanged and correct — the Total Fees/Fees Paid/Discount/Created At/Last Edited columns, the non-editable Total row, the widened overlay, `feesPaidFor`/`deriveQuarter` helpers, reuse of `getFeeDiscounts`/`calculateLateFine`, and the existing test fixtures/structure (extended, not replaced). Also folding in, as trivial patches surfaced by the same reviews: reset `fineByTxnId`/`totalDiscount` when `getFeeTransactions` fails (previously stale data could linger next to an error banner); broaden `settled_on` to use `paid_date` whenever present rather than gating on `status === 'paid'` only within a group's all-paid check; derive the table's `colSpan` from the column list instead of a hardcoded `11`; and correct a false claim in this file's own Tasks & Acceptance checklist (see below) by writing the backend regression test that was wrongly marked as "already covered."

## Design Notes

Fine is computed **once per (session year, quarter) group**, not per transaction: every fee record sharing a quarter (e.g. tuition + transport both due in Q1) has its `amount - feesPaid` summed into one `outstanding_amount`, and `compute_late_fine` is called once per quarter — matching `late_fine_service.py`'s own rule that a fine is charged on the whole outstanding bill, never per fee head. `settled_on` for a group is the latest `paid_date` among its transactions, but only when every transaction in that group is `paid` (otherwise the quarter isn't cleared, so it's left unsettled and dated `as_of` today). The resulting total is shown on every row in that quarter (the same convention as Discount, which is also one figure repeated per row) and summed once per distinct group in the Total row. It is display-only and never persisted, consistent with `late_fine_service.py`'s explicit "writes nothing" invariant.

## Verification

**Commands:**
- `python -m pytest tests/backend/ -q` -- expect 0 failed
- `cd frontend && CI=true npx jest` -- expect 0 failed
- `cd frontend && npm run build` -- expect lint + build to pass (lint runs first, fails on any warning)

**Manual checks (if no CLI):**
- Open a student profile, click "Fee Collection", confirm the overlay is visibly large and all six new columns + Total row render correctly for a student with existing fee history.
