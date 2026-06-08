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

from pymongo.errors import DuplicateKeyError, OperationFailure

from database import get_txn_session, _NoopSession
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


def _get_nested(doc: dict, path: str):
    """Resolve a dotted field path (e.g. 'meta.version') against a doc; None if absent."""
    node = doc
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


async def _revalidate_precondition(db, step: Step, branch_id: Optional[str]) -> None:
    """Re-read the step's precondition target inside the txn; abort if it moved (D.6)."""
    pre = step.precondition
    if not pre:
        return
    collection = pre.get("collection")
    record_id = pre.get("id")
    if not collection or not record_id:
        # D-review fix: a precondition the planner intended but that is unusable must
        # NOT silently disable the stale-guard — surface it loudly (a planner bug).
        logger.warning(
            "malformed precondition on step=%s (missing collection/id): %r — stale-guard skipped",
            step.idx, pre,
        )
        return
    field_name = pre.get("field", "version")  # prefer a monotonic version over a timestamp string
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
    if expected is not None and _get_nested(current, field_name) != expected:
        raise PlanStaleError(
            f"{collection}/{record_id} changed since the plan was built "
            f"({field_name}: expected {expected!r}, found {_get_nested(current, field_name)!r}).",
            step_idx=step.idx,
        )


def _idempotency_key(plan: Plan, step: Step) -> Optional[str]:
    return f"{plan.plan_token}:{step.idx}" if plan.plan_token else None


async def _claim_idempotency(db, plan: Plan, step: Step, key: str) -> None:
    """Insert the per-step idempotency key inside the txn (D.4).

    DuplicateKey ⇒ this (plan_token, step_idx) already applied (replay or concurrent
    confirm) — propagated so the txn aborts and the caller reports `already_applied`.
    """
    await getattr(db, IDEMPOTENCY_COLLECTION).insert_one(
        {
            "idempotency_key": key,
            "plan_token": plan.plan_token,
            "step_idx": step.idx,
            "tool": step.tool,
        },
        **session_kwargs(),
    )


async def _idempotency_key_committed(db, key: str) -> bool:
    """Has `key` been committed by another confirm? Queried WITHOUT a session so it
    reads committed state even after our own transaction aborted."""
    try:
        doc = await getattr(db, IDEMPOTENCY_COLLECTION).find_one({"idempotency_key": key})
    except Exception:
        return False
    return doc is not None


def _is_write_conflict(exc: OperationFailure) -> bool:
    """A concurrent transaction lost the race for the same contended write."""
    try:
        if exc.has_error_label("TransientTransactionError"):
            return True
    except Exception:
        pass
    return getattr(exc, "code", None) in (112, 11000, 251)  # WriteConflict / dup / NoSuchTransaction


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

            async def _recon(done_idx: int) -> NeedsManualReconciliationError:
                if audit_recon is not None:
                    try:
                        await audit_recon(plan, done_idx, str(exc))
                    except Exception:
                        logger.error("recon audit write failed", exc_info=True)
                return NeedsManualReconciliationError(
                    f"Side effect for step {step.idx} failed and step {done_idx}'s effect "
                    "could not be cleanly reversed; manual reconciliation required."
                )

            for done in reversed(completed):
                # D-review fix: a completed side effect with NO compensator cannot be
                # undone — escalating to needs_manual_reconciliation is correct; silently
                # skipping it while claiming "compensated" is a false success.
                if done.compensate is None:
                    logger.error(
                        "no compensator for completed side-effect step=%s — needs manual reconciliation",
                        done.idx,
                    )
                    raise await _recon(done.idx)
                try:
                    await done.compensate()
                except Exception:
                    logger.error(
                        "compensation_failed step=%s — needs manual reconciliation",
                        done.idx, exc_info=True,
                    )
                    raise await _recon(done.idx)
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
    is_real_txn = not isinstance(session, _NoopSession)
    token = set_current_session(session)
    step_results: list = []
    claimed: list = []  # idempotency keys claimed this run (for noop-path compensation)
    try:
        try:
            async with session.start_transaction():
                for step in write_steps:
                    await _revalidate_precondition(db, step, plan.branch_id)
                    key = _idempotency_key(plan, step)
                    # Skip the claim in dry-run: on the non-transactional (noop) path the
                    # claim would NOT roll back and would poison the key for a later real run.
                    if key and not dry_run:
                        await _claim_idempotency(db, plan, step, key)
                        claimed.append(key)
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
        except OperationFailure as exc:
            # A concurrent confirm may abort this txn with a WriteConflict /
            # TransientTransactionError rather than a surfaced DuplicateKey (the conflict
            # can land on the claim insert itself, before `claimed` is appended). If the
            # first step's key was already committed by the winner, this is an idempotent
            # replay too — map it to already_applied instead of leaking a 500.
            first_key = _idempotency_key(plan, write_steps[0]) if write_steps else None
            if _is_write_conflict(exc) and first_key and await _idempotency_key_committed(db, first_key):
                logger.info("idempotent_replay (write-conflict) plan_token=%s", plan.plan_token)
                return ExecutionResult(status="already_applied", step_results=step_results)
            raise
        except Exception:
            # On the non-transactional (noop) path nothing rolled back the claim
            # inserts; compensate them so a transient failure can't poison the key.
            if not is_real_txn and claimed:
                for k in claimed:
                    try:
                        await getattr(db, IDEMPOTENCY_COLLECTION).delete_one({"idempotency_key": k})
                    except Exception:
                        pass
            raise
    finally:
        reset_current_session(token)
        try:
            await session.end_session()
        except Exception:
            pass

    # Transaction committed. Now run post-commit non-Mongo side effects (saga).
    await _run_side_effects(plan, audit_recon=audit_recon)
    return ExecutionResult(status="committed", step_results=step_results)
