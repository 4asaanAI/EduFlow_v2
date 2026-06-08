"""D.3 — single-step atomic executor + length-1 plan path (FakeDb tier).

Proves the executor's control flow on FakeDb: a length-1 plan runs its step, a
failing step propagates (so the txn would abort), and the idempotent-replay path
returns `already_applied`. Real all-or-nothing rollback is on the mongo_real tier
(`test_executor_rollback_d3.py`).
"""

from __future__ import annotations

import pytest

from ai import plan_executor
from ai.plan_schema import single_write_plan, Plan, Step, WRITE
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _FakeDb:
    def __init__(self):
        self.ai_write_idempotency = FakeCollection()


async def test_length_1_plan_runs_step_and_commits():
    db = _FakeDb()
    calls = []

    async def runner():
        calls.append("ran")
        return {"success": True, "message": "done"}

    plan = single_write_plan(
        tool="mark_attendance", params={"x": 1}, runner=runner,
        school_id="s", branch_id=None, plan_token="tok-1",
    )
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    assert calls == ["ran"]
    assert result.step_results[0]["result"]["success"] is True


async def test_failing_step_propagates_and_runs_no_side_effects():
    db = _FakeDb()

    async def runner():
        raise RuntimeError("boom")

    plan = single_write_plan(
        tool="t", params={}, runner=runner, school_id="s", plan_token="tok-2",
    )
    with pytest.raises(RuntimeError):
        await plan_executor.run(plan, db=db)


async def test_idempotent_replay_returns_already_applied():
    db = _FakeDb()
    # Register the unique index so the FakeDb claim collides on replay.
    await db.ai_write_idempotency.create_index("idempotency_key", unique=True)
    runs = []

    async def runner():
        runs.append(1)
        return {"success": True}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="tok-3")
    first = await plan_executor.run(plan, db=db)
    assert first.status == "committed"
    # Same plan token replayed → claim hits DuplicateKey → already_applied, no re-run.
    second = await plan_executor.run(plan, db=db)
    assert second.status == "already_applied"
    assert runs == [1]


async def test_multi_write_runs_in_order():
    db = _FakeDb()
    order = []

    def mk(i):
        async def r():
            order.append(i)
        return r

    plan = Plan(
        steps=[Step(tool=f"t{i}", kind=WRITE, idx=i, runner=mk(i)) for i in range(3)],
        school_id="s", plan_token="tok-4",
    )
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    assert order == [0, 1, 2]
