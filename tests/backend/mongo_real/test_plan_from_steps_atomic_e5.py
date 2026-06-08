"""E.5 — a multi-step plan built via `plan_from_steps` commits all-or-nothing.

Proves the Epic E multi-step builder feeds the SAME atomic executor path as the
length-1 plan: every WRITE step commits together, or a later failure rolls them
all back. FakeDb cannot prove real atomicity, so this lives on the mongo_real tier.
"""

from __future__ import annotations

import pytest

import database
from ai import plan_executor
from ai.plan_schema import plan_from_steps
from services.txn_context import session_kwargs

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


def _runner_factory_for(db, fail_on=None):
    def factory(raw):
        async def _r():
            await db.plan_writes.insert_one(
                {"_id": raw["tool"], "id": raw["tool"]}, **session_kwargs()
            )
            if raw["tool"] == fail_on:
                raise RuntimeError("forced failure")
            return {"success": True}
        return _r
    return factory


_STEPS = [
    {"idx": 0, "tool": "step_one", "kind": "write", "params": {}},
    {"idx": 1, "tool": "step_two", "kind": "write", "params": {}},
]


async def test_multistep_plan_commits_all_steps(mongo_real_db, mongo_real_client):
    orig = database._client
    database._client = mongo_real_client
    try:
        plan = plan_from_steps(
            steps=_STEPS, runner_factory=_runner_factory_for(mongo_real_db),
            school_id="s", plan_token="tok-commit",
        )
        result = await plan_executor.run(plan, db=mongo_real_db)
        assert result.status == "committed"
        assert await mongo_real_db.plan_writes.count_documents({}) == 2
    finally:
        database._client = orig


async def test_multistep_plan_rolls_back_on_later_failure(mongo_real_db, mongo_real_client):
    orig = database._client
    database._client = mongo_real_client
    try:
        plan = plan_from_steps(
            steps=_STEPS,
            runner_factory=_runner_factory_for(mongo_real_db, fail_on="step_two"),
            school_id="s", plan_token="tok-roll",
        )
        with pytest.raises(RuntimeError):
            await plan_executor.run(plan, db=mongo_real_db)
        # step_one's write rolled back with step_two's — nothing committed.
        assert await mongo_real_db.plan_writes.count_documents({}) == 0
        assert await mongo_real_db.ai_write_idempotency.count_documents({}) == 0
    finally:
        database._client = orig
