"""D.6 — precondition revalidation re-reads INSIDE the transaction (real Mongo).

If the underlying record changed between planning and confirmation, the executor
re-reads it inside the txn and aborts the whole plan with `plan_stale` — and no
partial write is committed.
"""

from __future__ import annotations

import pytest

import database
from ai import plan_executor
from ai.plan_executor import PlanStaleError
from ai.plan_schema import Plan, Step, WRITE
from services.txn_context import session_kwargs

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_stale_precondition_aborts_with_no_partial_write(mongo_real_db, mongo_real_client):
    orig_client = database._client
    database._client = mongo_real_client
    try:
        # Seed with version=5; the plan was built expecting version=3 (data moved).
        await mongo_real_db.fee_structures.insert_one({"_id": "f1", "id": "f1", "version": 5})

        async def runner():
            await mongo_real_db.fee_structures.update_one(
                {"id": "f1"}, {"$set": {"amount": 999}}, **session_kwargs()
            )

        step = Step(
            tool="update_fee_structure", kind=WRITE, idx=0, runner=runner,
            precondition={"collection": "fee_structures", "id": "f1", "field": "version", "version": 3},
        )
        plan = Plan(steps=[step], school_id="s", plan_token="stale-tok")
        with pytest.raises(PlanStaleError):
            await plan_executor.run(plan, db=mongo_real_db)

        # No partial write — the update never applied.
        doc = await mongo_real_db.fee_structures.find_one({"id": "f1"})
        assert "amount" not in doc
        assert await mongo_real_db.ai_write_idempotency.count_documents({}) == 0
    finally:
        database._client = orig_client
