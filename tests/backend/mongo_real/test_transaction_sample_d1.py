"""D.1 — sample transaction commit/rollback proof on the real-Mongo tier.

Pins the baseline capability AD12 exists to provide: a Motor multi-document
transaction that COMMITS atomically and ROLLS BACK atomically. Later Epic-D
stories (D.3 rollback, D.4 idempotency, D.6 precondition) build on this tier.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_transaction_commits_both_writes(mongo_real_db, mongo_real_client):
    async with await mongo_real_client.start_session() as session:
        async with session.start_transaction():
            await mongo_real_db.a.insert_one({"_id": "1", "v": 1}, session=session)
            await mongo_real_db.b.insert_one({"_id": "1", "v": 2}, session=session)
    assert await mongo_real_db.a.count_documents({}) == 1
    assert await mongo_real_db.b.count_documents({}) == 1


async def test_transaction_rolls_back_both_writes_on_error(mongo_real_db, mongo_real_client):
    with pytest.raises(RuntimeError):
        async with await mongo_real_client.start_session() as session:
            async with session.start_transaction():
                await mongo_real_db.a.insert_one({"_id": "1", "v": 1}, session=session)
                await mongo_real_db.b.insert_one({"_id": "1", "v": 2}, session=session)
                raise RuntimeError("forced mid-transaction failure")
    # Nothing committed — both collections empty.
    assert await mongo_real_db.a.count_documents({}) == 0
    assert await mongo_real_db.b.count_documents({}) == 0
