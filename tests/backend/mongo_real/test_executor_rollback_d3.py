"""D.3 — a forced mid-write failure leaves ZERO committed changes (real txn).

The executor wraps a multi-write plan in one transaction; if a later step raises,
the earlier writes must roll back. FakeDb cannot prove this (no real transaction),
so it lives on the mongo_real tier.
"""

from __future__ import annotations

import pytest

import database
from ai import plan_executor
from ai.plan_schema import Plan, Step, WRITE
from services.txn_context import session_kwargs

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_forced_mid_write_failure_rolls_back_everything(mongo_real_db, mongo_real_client):
    # Point get_txn_session at the real replica-set client for this test.
    orig_client = database._client
    database._client = mongo_real_client
    try:
        async def write_a():
            await mongo_real_db.col_a.insert_one({"_id": "a1", "id": "a1"}, **session_kwargs())

        async def write_b_then_fail():
            await mongo_real_db.col_b.insert_one({"_id": "b1", "id": "b1"}, **session_kwargs())
            raise RuntimeError("forced mid-write failure")

        plan = Plan(
            steps=[
                Step(tool="a", kind=WRITE, idx=0, runner=write_a),
                Step(tool="b", kind=WRITE, idx=1, runner=write_b_then_fail),
            ],
            school_id="s", plan_token="tok-rollback",
        )
        with pytest.raises(RuntimeError):
            await plan_executor.run(plan, db=mongo_real_db)

        # Nothing committed — both writes rolled back, idempotency claim rolled back.
        assert await mongo_real_db.col_a.count_documents({}) == 0
        assert await mongo_real_db.col_b.count_documents({}) == 0
        assert await mongo_real_db.ai_write_idempotency.count_documents({}) == 0
    finally:
        database._client = orig_client
