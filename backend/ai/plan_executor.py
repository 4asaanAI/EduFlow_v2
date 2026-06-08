"""Atomic plan executor (AI Layer Hardening, AD4/AD5/AD6 — Epics D).

`_execute_confirmed_dispatch` (routes/chat.py) builds a Plan (length-1 for a single
confirmed write) and calls `run()` **unconditionally** — one execution path, no
`len==1` fork. Strategy:

- **Transaction-first (D.3):** every Mongo write runs inside ONE Motor multi-document
  transaction via `database.get_txn_session()`. The session is bound into the ambient
  `txn_context` contextvar so the existing session-unaware tools/services enlist in it.
  A failure anywhere aborts the whole transaction → zero committed changes.
- **Idempotency (D.4):** before each write step the executor claims
  `idempotency_key = f"{plan_token}:{step_idx}"` in `ai_write_idempotency` (unique
  index). A replay/concurrent confirm hits DuplicateKey → the txn aborts and the
  executor reports `already_applied` (exactly-once).
- **Precondition revalidation (D.6):** each write step may carry a `precondition`;
  the executor re-reads inside the txn and aborts the whole plan with `plan_stale`
  (distinct from `plan_tampered`) if the underlying data moved since planning.
- **Saga (D.5):** non-Mongo side effects (SMS/email) run AFTER commit; on failure the
  executor compensates completed side effects in reverse. If a compensation itself
  fails, the plan halts in `needs_manual_reconciliation` with an audit row.

Never uses `get_raw_db()` (tenant leak); all reads/writes go through the scoped db.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pymongo.errors import DuplicateKeyError, PyMongoError

from database import get_txn_session
from services.txn_context import set_current_session, reset_current_session, session_kwargs
from tenant import scoped_query
from ai.plan_schema import Plan, Step, WRITE

logger = logging.getLogger(__name__)

IDEMPOTENCY_COLLECTION = "ai_write_idempotency"

# 409 taxonomy (P7) — distinct codes the frontend maps to distinct messages.
PLAN_STALE = "plan_stale"
NEEDS_MANUAL_RECONCILIATION = "needs_manual_reconciliation"


class PlanStaleError(Exception):
    """A write step's precondition changed between planning and confirmation (D.6).
    Maps to HTTP 409 {code: 'plan_stale'} — 'data changed, re-plan'."""

    code = PLAN_STALE

    def __init__(self, message: str, *, step_idx: int):
        super().__init__(message)
        self.step_idx = step_idx


class NeedsManualReconciliationError(Exception):
    """A saga compensation itself failed — the plan is in an indeterminate state
    requiring an operator (D.5). Never a silent partial success."""

    code = NEEDS_MANUAL_RECONCILIATION


class SagaCompensatedError(Exception):
    """A post-commit side effect failed but its prior side effects were cleanly
    compensated. DB writes remain committed (they are the source of truth); the
    caller surfaces a failure message (UX-DR2)."""

    def __init__(self, message: str, *, failed_step_idx: int):
        super().__init__(message)
        self.failed_step_idx = failed_step_idx


@dataclass
class ExecutionResult:
    status: str  # committed | dry_run | already_applied
    step_results: list = field(default_factory=list)
    dry_run: bool = False
    diff: Optional[list] = None


class _DryRunAbort(Exception):
    """Internal sentinel: forces the transaction to abort after running writes so
    dry-run commits nothing (full shadow behavior is Story F.5)."""


async def _revalidate_precondition(db, step: Step, branch_id: Optional[str]) -> None:
    """Re-read the step's precondition target inside the txn; abort if it moved (D.6)."""
    pre = step.precondition
    if not pre:
        return
    collection = pre.get("collection")
    record_id = pre.get("id")
    if not collection or not record_id:
        return
    field_name = pre.get("field", "updated_at")
    expected = pre.get("version", pre.get("expected"))
    current = await getattr(db, collection).find_one(
        scoped_query({"id": record_id}, branch_id=branch_id),
        {"_id": 0, field_name: 1, "id": 1},
        **session_kwargs(),
    )
    if current is None:
        raise PlanStaleError(
            f"Record {record_id} in {collection} no longer exists.", step_idx=step.idx
        )
    if expected is not None and current.get(field_name) != expected:
        raise PlanStaleError(
            f"{collection}/{record_id} changed since the plan was built "
            f"({field_name}: expected {expected!r}, found {current.get(field_name)!r}).",
            step_idx=step.idx,
        )


async def _claim_idempotency(db, plan: Plan, step: Step) -> None:
    """Insert the per-step idempotency key inside the txn (D.4).

    DuplicateKey ⇒ this (plan_token, step_idx) already applied (replay or concurrent
    confirm) — propagated so the txn aborts and the caller reports `already_applied`.
    """
    if not plan.plan_token:
        return
    key = f"{plan.plan_token}:{step.idx}"
    await getattr(db, IDEMPOTENCY_COLLECTION).insert_one(
        {
            "_id": key,
            "idempotency_key": key,
            "plan_token": plan.plan_token,
            "step_idx": step.idx,
            "tool": step.tool,
        },
        **session_kwargs(),
    )


async def _run_side_effects(plan: Plan, audit_recon: Optional[Callable] = None) -> None:
    """Run non-Mongo side effects AFTER commit; compensate in reverse on failure (D.5)."""
    completed: list[Step] = []
    for step in plan.steps:
        if step.side_effect is None:
            continue
        try:
            await step.side_effect()
            completed.append(step)
        except Exception as exc:  # the side effect failed → compensate prior ones
            logger.warning("side_effect_failed step=%s tool=%s", step.idx, step.tool, exc_info=True)
            for done in reversed(completed):
                if done.compensate is None:
                    continue
                try:
                    await done.compensate()
                except Exception:
                    logger.error(
                        "compensation_failed step=%s — needs manual reconciliation",
                        done.idx, exc_info=True,
                    )
                    if audit_recon is not None:
                        try:
                            await audit_recon(plan, done.idx, str(exc))
                        except Exception:
                            logger.error("recon audit write failed", exc_info=True)
                    raise NeedsManualReconciliationError(
                        f"Compensation for step {done.idx} failed after step {step.idx} "
                        "errored; manual reconciliation required."
                    )
            raise SagaCompensatedError(
                f"Side effect for step {step.idx} failed; prior side effects were "
                "compensated. No further changes applied.",
                failed_step_idx=step.idx,
            )


async def run(
    plan: Plan,
    *,
    db,
    session_factory: Optional[Callable] = None,
    dry_run: bool = False,
    audit_recon: Optional[Callable] = None,
) -> ExecutionResult:
    """Execute a Plan atomically. See module docstring for the strategy."""
    session_factory = session_factory or get_txn_session
    write_steps = plan.write_steps
    session = await session_factory()
    token = set_current_session(session)
    step_results: list = []
    try:
        try:
            async with session.start_transaction():
                for step in write_steps:
                    await _revalidate_precondition(db, step, plan.branch_id)
                    await _claim_idempotency(db, plan, step)
                    result = await step.runner() if step.runner else None
                    step_results.append({"step": step.idx, "tool": step.tool, "status": "ok", "result": result})
                if dry_run:
                    # Abort the txn so a shadow run commits nothing (F.5 builds the diff).
                    raise _DryRunAbort()
        except _DryRunAbort:
            return ExecutionResult(status="dry_run", step_results=step_results, dry_run=True)
        except DuplicateKeyError:
            # Idempotency claim lost → exactly-once. Nothing committed this round.
            logger.info("idempotent_replay plan_token=%s — already applied", plan.plan_token)
            return ExecutionResult(status="already_applied", step_results=step_results)
    finally:
        reset_current_session(token)
        try:
            await session.end_session()
        except Exception:
            pass

    # Transaction committed. Now run post-commit non-Mongo side effects (saga).
    await _run_side_effects(plan, audit_recon=audit_recon)
    return ExecutionResult(status="committed", step_results=step_results)
