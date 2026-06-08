"""Epic E.5/E.3 — multi-step plan execution + round-counter separation.

`plan_from_steps` builds an executable multi-step Plan from the resolved step
dicts stored on a confirm token; the executor runs every WRITE step in order
through the one atomic path. Read steps carry no runner and never re-run.
"""

from __future__ import annotations

import pytest

from ai import plan_executor, planner
from ai.plan_schema import plan_from_steps, WRITE, READ
from tests.backend.conftest import FakeCollection
from routes import chat

pytestmark = pytest.mark.asyncio


class _FakeDb:
    def __init__(self):
        self.ai_write_idempotency = FakeCollection()


async def test_multistep_plan_runs_all_write_steps_in_order():
    db = _FakeDb()
    order: list[str] = []

    def runner_factory(raw):
        async def _r():
            order.append(raw["tool"])
            return {"success": True, "tool": raw["tool"]}
        return _r

    steps = [
        {"idx": 0, "tool": "get_leave_requests", "kind": READ, "params": {}},
        {"idx": 1, "tool": "approve_leave", "kind": WRITE,
         "params": {"leave_id": "lv-1"}, "precondition": None},
        {"idx": 2, "tool": "create_announcement", "kind": WRITE,
         "params": {"title": "T"}},
    ]
    plan = plan_from_steps(
        steps=steps, runner_factory=runner_factory,
        school_id="sch", branch_id="b1", plan_token="tok-multi",
    )
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    # Only the two WRITE steps run; the READ step is not re-executed.
    assert order == ["approve_leave", "create_announcement"]
    assert len(result.step_results) == 2


async def test_multistep_failure_propagates_for_rollback():
    db = _FakeDb()

    def runner_factory(raw):
        async def _r():
            if raw["tool"] == "create_announcement":
                raise RuntimeError("boom")
            return {"success": True}
        return _r

    steps = [
        {"idx": 0, "tool": "approve_leave", "kind": WRITE, "params": {"leave_id": "lv-1"}},
        {"idx": 1, "tool": "create_announcement", "kind": WRITE, "params": {"title": "T"}},
    ]
    plan = plan_from_steps(
        steps=steps, runner_factory=runner_factory, school_id="sch", plan_token="tok-x",
    )
    with pytest.raises(RuntimeError):
        await plan_executor.run(plan, db=db)


def test_round_and_plan_budgets_are_distinct_constants():
    # E.3: planning/read rounds and plan size are bounded SEPARATELY.
    assert chat.MAX_TOOL_ROUNDS == 3
    assert chat.MAX_PLAN_STEPS == planner.MAX_PLAN_STEPS == 8
