# Story D.3 — Single-step atomic executor + length-1 plan path

**Epic:** D. **Status:** DONE (4 new FakeDb tests + 1 mongo_real rollback test; 102 confirm/chat/attendance E2E tests green through the new path; baseline 25-fail unchanged).
**ADs:** AD4 (transaction-first), P3 (plan schema). **FRs/NFRs:** FR9, NFR10.

## Acceptance Criteria
1. `_execute_confirmed_dispatch` builds a length-1 Plan and calls `plan_executor.run()`
   **unconditionally** (no `len==1` fork) — DONE.
2. An existing single write tool still works end-to-end (regression) — DONE: the 102
   existing confirm/chat/attendance tests (incl. `api/test_phase4_idempotency_sse.py`,
   `test_chat_confirm_rate_limit.py`, `test_audit_gate.py`) pass through the executor.
3. A forced mid-write failure leaves zero committed changes — DONE
   (`mongo_real/test_executor_rollback_d3.py`).

## What shipped
- `ai/plan_schema.py` — `Step`/`Plan` dataclasses (P3) + `single_write_plan(...)` builder.
  Epic E's planner will reuse this exact schema for multi-step plans + preconditions.
- `ai/plan_executor.py` — `run(plan, *, db, session_factory=get_txn_session, dry_run, audit_recon)`:
  opens one txn via `get_txn_session()`, binds the ambient session contextvar, runs each
  write step's `runner()` inside the txn, commits on clean exit / aborts on any exception.
  (Idempotency D.4, precondition D.6, saga D.5 layered in the same module.)
- `routes/chat.py::_execute_confirmed_dispatch` — replaced the direct
  `tool_def["fn"](...)` call with a length-1 plan whose `runner` wraps that same call;
  the confirm token is the `plan_token`. Maps `PlanStaleError`→409 `plan_stale`,
  `NeedsManualReconciliationError`→409, `SagaCompensatedError`→502, preserving the
  existing `HTTPException`/opaque-500 handling and write-ahead audit finalize.
- `tests/backend/conftest.py` — added `ai_write_idempotency` FakeCollection to `FakeDb`.

## Design note
The tool fn is unchanged and session-unaware; it enlists in the transaction purely via
the ambient `txn_context` session (D.2). This is what lets "an existing single write
tool still works end-to-end" be literally true — the tool code didn't change, only its
execution envelope did.
