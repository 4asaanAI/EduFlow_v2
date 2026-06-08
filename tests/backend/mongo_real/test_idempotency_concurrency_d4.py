"""D.4 — two concurrent confirms of the same plan produce exactly ONE effect.

The unique index on `ai_write_idempotency.idempotency_key` makes one of two racing
confirm transactions win; the loser hits DuplicateKey and aborts, so the write
applies exactly once and the executor reports `already_applied` for the loser.
"""

from __future__ import annotations

import asyncio

import pytest

import database
from ai import plan_executor
from ai.plan_schema import single_write_plan
from services.txn_context import session_kwargs

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_two_concurrent_confirms_apply_exactly_once(mongo_real_db, mongo_real_client):
    await mongo_real_db.ai_write_idempotency.create_index("idempotency_key", unique=True)

    orig_client = database._client
    database._client = mongo_real_client
    try:
        async def make_run():
            async def runner():
                await mongo_real_db.effects.insert_one({"id": "e", "marked": True}, **session_kwargs())
                return {"success": True}

            plan = single_write_plan(
                tool="t", params={}, runner=runner, school_id="s", plan_token="race-token",
            )
            return await plan_executor.run(plan, db=mongo_real_db)

        results = await asyncio.gather(make_run(), make_run(), return_exceptions=True)

        statuses = sorted(
            r.status for r in results if not isinstance(r, Exception)
        )
        # Exactly one committed; the other either already_applied or aborted (raised).
        assert statuses.count("committed") == 1
        # The write landed exactly once.
        assert await mongo_real_db.effects.count_documents({}) == 1
        assert await mongo_real_db.ai_write_idempotency.count_documents({"idempotency_key": "race-token:0"}) == 1
    finally:
        database._client = orig_client


async def test_sequential_replay_reports_already_applied(mongo_real_db, mongo_real_client):
    await mongo_real_db.ai_write_idempotency.create_index("idempotency_key", unique=True)
    orig_client = database._client
    database._client = mongo_real_client
    try:
        runs = []

        async def runner():
            runs.append(1)
            await mongo_real_db.effects.insert_one({"id": "e"}, **session_kwargs())

        plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="seq-token")
        first = await plan_executor.run(plan, db=mongo_real_db)
        second = await plan_executor.run(plan, db=mongo_real_db)
        assert first.status == "committed"
        assert second.status == "already_applied"
        assert runs == [1]
        assert await mongo_real_db.effects.count_documents({}) == 1
    finally:
        database._client = orig_client
