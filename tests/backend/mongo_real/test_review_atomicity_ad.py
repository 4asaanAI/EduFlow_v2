"""A–D review — atomicity proofs that need a real transaction (mongo_real tier).

Pins the fix for the review's top finding: notification/audit Mongo writes performed
by a service INSIDE the executor's transaction must roll back with it (AD14 — "a
rolled-back plan sends nothing"). FakeDb cannot prove rollback, so it lives here.
"""

from __future__ import annotations

import pytest

import database
from ai import plan_executor
from ai.plan_schema import Plan, Step, WRITE
from services.notification_service import create_notification
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_notification_and_audit_roll_back_with_aborted_txn(mongo_real_db, mongo_real_client):
    orig = database._client
    database._client = mongo_real_client
    try:
        async def runner():
            # A real write + a notification + a domain audit, all expected to enlist.
            await mongo_real_db.fee_transactions.insert_one({"id": "t1"}, **session_kwargs())
            await create_notification(mongo_real_db, user_id="u1", notification_type="x", message="paid")
            await write_audit_doc(mongo_real_db, {"action": "pay", "entity_id": "t1", "entity_type": "fee"})
            raise RuntimeError("force abort after the notification/audit writes")

        plan = Plan(steps=[Step(tool="pay", kind=WRITE, idx=0, runner=runner)],
                    school_id="s", plan_token="tok-atomic")
        with pytest.raises(RuntimeError):
            await plan_executor.run(plan, db=mongo_real_db)

        # Everything rolled back — no torn state, no phantom notification/audit.
        assert await mongo_real_db.fee_transactions.count_documents({}) == 0
        assert await mongo_real_db.notifications.count_documents({}) == 0
        assert await mongo_real_db.audit_logs.count_documents({}) == 0
    finally:
        database._client = orig


async def test_notification_and_audit_persist_on_commit(mongo_real_db, mongo_real_client):
    orig = database._client
    database._client = mongo_real_client
    try:
        async def runner():
            await mongo_real_db.fee_transactions.insert_one({"id": "t1"}, **session_kwargs())
            await create_notification(mongo_real_db, user_id="u1", notification_type="x", message="paid")
            await write_audit_doc(mongo_real_db, {"action": "pay", "entity_id": "t1", "entity_type": "fee"})

        plan = Plan(steps=[Step(tool="pay", kind=WRITE, idx=0, runner=runner)],
                    school_id="s", plan_token="tok-commit")
        result = await plan_executor.run(plan, db=mongo_real_db)
        assert result.status == "committed"
        assert await mongo_real_db.fee_transactions.count_documents({}) == 1
        assert await mongo_real_db.notifications.count_documents({}) == 1
        assert await mongo_real_db.audit_logs.count_documents({}) == 1
    finally:
        database._client = orig
