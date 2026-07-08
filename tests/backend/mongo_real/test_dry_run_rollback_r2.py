"""R2.3 AC2 — dry-run/shadow mode commits NOTHING on a real session.

Shadow mode runs the writes inside a real transaction and then aborts it, so the
would-be effect can be reported without persisting anything. FakeDb's no-op session
cannot prove real rollback, so this lives on the mongo_real tier alongside the D.3
rollback proof.
"""

from __future__ import annotations

import pytest

import database
from ai import plan_executor
from ai.plan_schema import Plan, Step, WRITE
from services.txn_context import session_kwargs

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_dry_run_persists_nothing(mongo_real_db, mongo_real_client):
    orig_client = database._client
    database._client = mongo_real_client
    try:
        ran = []

        async def write_a():
            ran.append("a")
            await mongo_real_db.col_a.insert_one({"_id": "dr1", "id": "dr1"}, **session_kwargs())
            return {"success": True}

        plan = Plan(
            steps=[Step(tool="a", kind=WRITE, idx=0, runner=write_a)],
            school_id="s", plan_token="tok-dryrun",
        )
        result = await plan_executor.run(plan, db=mongo_real_db, dry_run=True)

        assert result.status == "dry_run"
        assert result.dry_run is True
        assert ran == ["a"]  # the write ran inside the txn...
        # ...but the txn was aborted, so nothing persisted, and the idempotency
        # claim was skipped (never poisoned for a later real run).
        assert await mongo_real_db.col_a.count_documents({}) == 0
        assert await mongo_real_db.ai_write_idempotency.count_documents({}) == 0
    finally:
        database._client = orig_client
