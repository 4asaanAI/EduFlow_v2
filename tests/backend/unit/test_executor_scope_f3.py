"""Story F.3 — per-step re-scoping in the executor.

A plan is bound to one (school_id, branch_id) derived from the authenticated actor.
A later step that names a different branch/school must abort the WHOLE plan
(no partial write) — step 3 cannot widen scope vs step 1.
"""

from __future__ import annotations

import pytest

from ai import plan_executor
from ai.plan_executor import PlanScopeViolationError
from ai.plan_schema import Plan, Step

pytestmark = pytest.mark.asyncio


def _make_plan(steps, *, school_id="aaryans-joya", branch_id="branch-a"):
    return Plan(steps=steps, school_id=school_id, branch_id=branch_id, plan_token="tok-1")


async def _ok_runner():
    return {"success": True}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.ai_write_idempotency.docs[:] = []
    yield
    fake_db.ai_write_idempotency.docs[:] = []


async def test_step_widening_branch_aborts_whole_plan(fake_db):
    ran = []

    async def _record():
        ran.append("step0")
        return {"success": True}

    steps = [
        Step(tool="mark_attendance", params={"branch_id": "branch-a"}, idx=0, runner=_record),
        Step(tool="record_fee_payment", params={"branch_id": "branch-b"}, idx=1, runner=_ok_runner),
    ]
    with pytest.raises(PlanScopeViolationError) as exc:
        await plan_executor.run(_make_plan(steps), db=fake_db)
    assert exc.value.step_idx == 1


async def test_step_widening_school_aborts(fake_db):
    steps = [
        Step(tool="mark_attendance", params={"schoolId": "other-school"}, idx=0, runner=_ok_runner),
    ]
    with pytest.raises(PlanScopeViolationError):
        await plan_executor.run(_make_plan(steps), db=fake_db)


async def test_in_scope_plan_runs(fake_db):
    steps = [
        Step(tool="mark_attendance", params={"branch_id": "branch-a"}, idx=0, runner=_ok_runner),
        Step(tool="record_fee_payment", params={}, idx=1, runner=_ok_runner),
    ]
    result = await plan_executor.run(_make_plan(steps), db=fake_db)
    assert result.status == "committed"


async def test_owner_plan_branch_none_allows_any_branch_step(fake_db):
    # Owner authority (branch_id=None) is school-wide — a step may target a branch.
    steps = [Step(tool="mark_attendance", params={"branch_id": "branch-c"}, idx=0, runner=_ok_runner)]
    plan = _make_plan(steps, branch_id=None)
    result = await plan_executor.run(plan, db=fake_db)
    assert result.status == "committed"
