"""Canonical Plan / Step schema for the atomic executor (AI Layer Hardening, P3).

Epic D introduces the executor and runs it on **length-1** plans built from a single
confirmed write token (`_execute_confirmed_dispatch`). Epic E's planner (`ai/planner.py`)
will populate multi-step plans + per-write `precondition`s using this SAME schema — the
executor is intentionally agnostic to who built the plan.

A `Step` carries enough for the executor to be safe:
- `kind` ∈ {read, write} — only write steps run inside the transaction.
- `precondition` (AD5/D.6) — re-read-and-compare inside the txn; mismatch ⇒ plan_stale.
- `destructive` (AD15/F.10) — flagged for the two-step destructive gate (Epic F).
- `runner` — the async callable that performs the write (the chat adapter wraps the
  existing tool fn; tests pass a closure). The executor never imports tools directly.
- `side_effect` / `compensate` (AD4/D.5) — a NON-Mongo side effect (SMS/email) run
  AFTER commit, with a compensating action for saga rollback.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

READ = "read"
WRITE = "write"


@dataclass
class Step:
    tool: str
    params: dict = field(default_factory=dict)
    kind: str = WRITE
    idx: int = 0
    precondition: Optional[dict] = None
    destructive: bool = False
    # Forward action — performs the Mongo write(s). Enlists in the txn via the
    # ambient session contextvar (services/txn_context.py).
    runner: Optional[Callable[[], Awaitable[Any]]] = None
    # Non-Mongo side effect run AFTER commit + its compensating action (D.5 saga).
    side_effect: Optional[Callable[[], Awaitable[Any]]] = None
    compensate: Optional[Callable[[], Awaitable[Any]]] = None


@dataclass
class Plan:
    steps: list
    school_id: str
    branch_id: Optional[str] = None
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # The confirm-token string; idempotency keys derive from it as
    # f"{plan_token}:{step_idx}" (P5). None ⇒ idempotency claim is skipped.
    plan_token: Optional[str] = None

    @property
    def write_steps(self) -> list:
        return [s for s in self.steps if s.kind == WRITE]


def single_write_plan(
    *,
    tool: str,
    params: dict,
    runner: Callable[[], Awaitable[Any]],
    school_id: str,
    branch_id: Optional[str] = None,
    plan_token: Optional[str] = None,
    destructive: bool = False,
) -> Plan:
    """Build the length-1 plan used by `_execute_confirmed_dispatch` (D.3).

    This is the ONE execution path for a confirmed single write — there is no
    `len==1` fork; a single legacy write is just a one-step plan.
    """
    step = Step(tool=tool, params=params, kind=WRITE, idx=0, runner=runner, destructive=destructive)
    return Plan(steps=[step], school_id=school_id, branch_id=branch_id, plan_token=plan_token)
