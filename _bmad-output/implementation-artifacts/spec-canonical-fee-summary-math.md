---
title: 'Use canonical fee summary math on every screen'
type: 'bugfix'
created: '2026-08-05'
status: 'done'
baseline_commit: 'f82f685c244504d053baa383b77586d1410ea111'
context:
  - '{project-root}/_bmad-output/project-context.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The student fee summary and class summary omit overdue, unpaid, and partial balances that the canonical overall summary includes. The same ledger can therefore display different paid/outstanding totals depending on the screen.

**Approach:** Reuse the canonical status definitions and per-transaction balance rules from `ai/fee_metrics.py` in both REST summaries while preserving existing response fields and routes.

## Boundaries & Constraints

**Always:** Exclude soft-deleted transactions; count paid transactions at full amount; count partial payments by `paid_amount`; count overdue/pending/unpaid at full outstanding amount; clamp partial remaining balance to zero; preserve response keys and authorization.

**Ask First:** Any change to fee statuses, currency handling, or historical transaction data.

**Never:** Mutate fee transactions during a read, change receipt/payment workflows, touch live data, or change frontend branding/theme.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Mixed ledger | paid 100, pending 80, overdue 60, unpaid 40, partial 100/30 | paid 130; outstanding 250 | N/A |
| Overpaid partial | amount 100, paid_amount 120 | remaining contributes zero | Clamp to zero |
| Deleted row | outstanding row with `deleted=true` | excluded from totals | N/A |

</frozen-after-approval>

## Code Map

- `backend/ai/fee_metrics.py` -- canonical status constants and per-student balance math.
- `backend/routes/fees.py` -- student and per-class summary endpoints.
- `tests/backend/api/test_fee_summary_consistency.py` -- regression matrix.

## Tasks & Acceptance

**Execution:**
- [x] `backend/routes/fees.py` -- apply canonical collected/outstanding rules to `/my` and `/class-summary`.
- [x] `tests/backend/api/test_fee_summary_consistency.py` -- prove mixed, deleted and overpaid-partial cases.

**Acceptance Criteria:**
- Given the same transaction ledger, when overall, class and student summaries are read, then their paid/outstanding arithmetic agrees.
- Given existing clients, when responses are read, then all existing response keys remain available.

## Spec Change Log

## Verification

**Commands:**
- `python -m pytest tests/backend/api/test_fee_summary_consistency.py tests/backend/api/test_fees_crud.py -q` -- expected: all pass.

**Results:**
- New consistency suite: 2 passed.
- Existing fee CRUD and student vertical suites: 16 passed.

## Suggested Review Order

**Canonical arithmetic**

- One pure helper defines paid, partial and outstanding status behavior.
  [`fee_metrics.py:26`](../../backend/ai/fee_metrics.py#L26)

- Class summaries consume the same arithmetic instead of a status subset.
  [`fees.py:317`](../../backend/routes/fees.py#L317)

- Student summaries exclude deleted rows and include every outstanding status.
  [`fees.py:352`](../../backend/routes/fees.py#L352)

**Regression proof**

- Mixed ledgers prove overall, class and student totals agree.
  [`test_fee_summary_consistency.py:44`](../../tests/backend/api/test_fee_summary_consistency.py#L44)
