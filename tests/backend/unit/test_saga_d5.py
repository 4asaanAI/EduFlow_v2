"""D.5 — saga fallback for non-Mongo side effects + needs-manual-reconciliation.

Mongo writes commit atomically in the transaction (D.3). NON-Mongo side effects
(SMS/email) run AFTER commit; if a later side effect fails the executor compensates
the completed ones in reverse. If a compensation itself fails, the plan halts in
`needs_manual_reconciliation` with an audit row — never a silent partial success.
"""

from __future__ import annotations

import pytest

from ai import plan_executor
from ai.plan_executor import SagaCompensatedError, NeedsManualReconciliationError
from ai.plan_schema import Plan, Step, WRITE
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _Db:
    def __init__(self):
        self.ai_write_idempotency = FakeCollection()


async def test_all_side_effects_succeed_status_committed():
    db = _Db()
    fired = []

    def step(i, fail=False):
        async def runner():
            pass
        async def side():
            fired.append(("se", i))
        async def comp():
            fired.append(("comp", i))
        return Step(tool=f"t{i}", kind=WRITE, idx=i, runner=runner, side_effect=side, compensate=comp)

    plan = Plan(steps=[step(0), step(1)], school_id="s", plan_token="tok")
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    assert fired == [("se", 0), ("se", 1)]  # no compensation ran


async def test_side_effect_failure_compensates_in_reverse():
    db = _Db()
    order = []

    async def runner():
        pass

    async def se0():
        order.append("se0")

    async def comp0():
        order.append("comp0")

    async def se1_fail():
        order.append("se1")
        raise RuntimeError("sms gateway down")

    plan = Plan(
        steps=[
            Step(tool="t0", kind=WRITE, idx=0, runner=runner, side_effect=se0, compensate=comp0),
            Step(tool="t1", kind=WRITE, idx=1, runner=runner, side_effect=se1_fail),
        ],
        school_id="s", plan_token="tok",
    )
    with pytest.raises(SagaCompensatedError) as ei:
        await plan_executor.run(plan, db=db)
    assert ei.value.failed_step_idx == 1
    # step 0's side effect was compensated after step 1 failed (reverse order).
    assert order == ["se0", "se1", "comp0"]


async def test_compensation_failure_yields_needs_manual_reconciliation_with_audit():
    db = _Db()
    audited = []

    async def audit_recon(plan, step_idx, err):
        audited.append((step_idx, err))

    async def runner():
        pass

    async def se0():
        pass

    async def comp0_fail():
        raise RuntimeError("compensation also failed")

    async def se1_fail():
        raise RuntimeError("primary side effect failed")

    plan = Plan(
        steps=[
            Step(tool="t0", kind=WRITE, idx=0, runner=runner, side_effect=se0, compensate=comp0_fail),
            Step(tool="t1", kind=WRITE, idx=1, runner=runner, side_effect=se1_fail),
        ],
        school_id="s", plan_token="tok",
    )
    with pytest.raises(NeedsManualReconciliationError) as ei:
        await plan_executor.run(plan, db=db, audit_recon=audit_recon)
    assert ei.value.code == "needs_manual_reconciliation"
    assert "reconciliation" in str(ei.value).lower()
    assert audited and audited[0][0] == 0  # audit row written for the failed compensation


async def test_db_writes_committed_before_side_effects_run():
    """Fault injection: even when a side effect fails, the Mongo write already
    committed (it ran inside the transaction) — DB ends fully-applied."""
    db = _Db()
    committed = []

    async def runner():
        committed.append("write")

    async def se_fail():
        raise RuntimeError("boom")

    plan = Plan(
        steps=[Step(tool="t", kind=WRITE, idx=0, runner=runner, side_effect=se_fail)],
        school_id="s", plan_token="tok",
    )
    with pytest.raises(SagaCompensatedError):
        await plan_executor.run(plan, db=db)
    assert committed == ["write"]  # the write ran (and on real Mongo, committed)
