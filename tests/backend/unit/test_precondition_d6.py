"""D.6 — optimistic-concurrency precondition revalidation.

Each write step may carry a `precondition`; the executor re-reads the target inside
the transaction and aborts the WHOLE plan with `plan_stale` (distinct from
`plan_tampered`) if the value moved since planning. No partial write occurs.
"""

from __future__ import annotations

import pytest

from ai import plan_executor
from ai.plan_executor import PlanStaleError, PLAN_STALE
from ai.plan_schema import Plan, Step, WRITE
from tenant import get_school_id
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _Db:
    def __init__(self):
        self.ai_write_idempotency = FakeCollection()
        self.fee_structures = FakeCollection()


def _seed(db, *, version):
    db.fee_structures.docs.append(
        {"_id": "f1", "id": "f1", "schoolId": get_school_id(), "version": version}
    )


async def test_matching_precondition_proceeds():
    db = _Db()
    _seed(db, version=3)
    ran = []

    async def runner():
        ran.append(1)

    step = Step(
        tool="update_fee_structure", kind=WRITE, idx=0, runner=runner,
        precondition={"collection": "fee_structures", "id": "f1", "field": "version", "version": 3},
    )
    plan = Plan(steps=[step], school_id="s", plan_token="tok")
    result = await plan_executor.run(plan, db=db)
    assert result.status == "committed"
    assert ran == [1]


async def test_changed_precondition_raises_plan_stale_no_write():
    db = _Db()
    _seed(db, version=5)  # data moved: plan expected 3, db now 5
    ran = []

    async def runner():
        ran.append(1)

    step = Step(
        tool="update_fee_structure", kind=WRITE, idx=0, runner=runner,
        precondition={"collection": "fee_structures", "id": "f1", "field": "version", "version": 3},
    )
    plan = Plan(steps=[step], school_id="s", plan_token="tok")
    with pytest.raises(PlanStaleError) as ei:
        await plan_executor.run(plan, db=db)
    assert ei.value.code == PLAN_STALE
    assert ei.value.step_idx == 0
    assert ran == []  # the write never ran — no partial state


async def test_missing_record_raises_plan_stale():
    db = _Db()  # nothing seeded
    step = Step(
        tool="update_fee_structure", kind=WRITE, idx=0, runner=lambda: None,
        precondition={"collection": "fee_structures", "id": "ghost", "field": "version", "version": 1},
    )
    plan = Plan(steps=[step], school_id="s", plan_token="tok")
    with pytest.raises(PlanStaleError):
        await plan_executor.run(plan, db=db)


async def test_plan_stale_is_distinct_from_plan_tampered():
    # plan_stale (data freshness, AD5) must not collide with plan_tampered
    # (token/structure integrity, AD3) — they map to different FE messages (P7).
    assert PLAN_STALE == "plan_stale"
    assert PLAN_STALE != "plan_tampered"
