# Story D.5 — Saga fallback + needs-manual-reconciliation

**Epic:** D. **Status:** DONE (4 FakeDb fault-injection tests; baseline unchanged).
**ADs:** AD4 (saga), AD14 (side effects fire after commit). **FRs/NFRs:** FR10, NFR22.

## Acceptance Criteria
1. A plan whose steps include a non-Mongo side effect (e.g. SMS): when a later step
   fails, the executor runs compensating actions in reverse — DONE
   (`_run_side_effects`; `test_side_effect_failure_compensates_in_reverse`).
2. The DB ends fully-applied or fully-compensated — DONE: Mongo writes commit in the
   transaction (D.3) BEFORE any side effect runs; on side-effect failure the side
   effects are compensated (`test_db_writes_committed_before_side_effects_run`).
3. If a compensation itself fails → plan halts in `needs_manual_reconciliation` with an
   audit row + specific message (no silent partial success) — DONE
   (`NeedsManualReconciliationError`, `audit_recon` callback;
   `test_compensation_failure_yields_needs_manual_reconciliation_with_audit`).

## What shipped
- `ai/plan_executor._run_side_effects(plan, audit_recon)` — runs each step's
  `side_effect` after commit; on failure compensates completed side effects in reverse.
  Compensation success → `SagaCompensatedError` (DB committed, side effects undone, caller
  surfaces a failure message — UX-DR2). Compensation failure → `NeedsManualReconciliationError`
  + `audit_recon(plan, step_idx, err)` audit hook.
- `routes/chat.py` maps `NeedsManualReconciliationError`→409 `{code: needs_manual_reconciliation}`
  and `SagaCompensatedError`→502 `{code: side_effect_failed}`.

## Note on Epic-D scope
The length-1 legacy plans built by `_execute_confirmed_dispatch` declare NO
`side_effect`/`compensate` steps yet — existing tools fire notifications as Mongo writes
that enlist in the transaction (AD14: roll back on abort). The saga path is the
capability Epic E's planner will populate for genuine non-Mongo side effects; D.5 builds
and proves it in isolation.
