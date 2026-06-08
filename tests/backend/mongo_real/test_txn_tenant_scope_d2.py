"""D.2 — a write performed INSIDE a real transaction still injects `schoolId`.

Proves there is no tenant-leaking raw write path inside the executor's transaction:
`ScopedCollection` forwards `session=` while injecting the tenant filter, so a
transactional insert lands with the correct `schoolId` and is invisible to other
tenants.
"""

from __future__ import annotations

import pytest

from database import ScopedCollection

pytestmark = [pytest.mark.mongo_real, pytest.mark.asyncio]


async def test_transactional_write_injects_school_id(mongo_real_db, mongo_real_client):
    scoped = ScopedCollection(mongo_real_db.students, "school-a")
    async with await mongo_real_client.start_session() as session:
        async with session.start_transaction():
            await scoped.insert_one({"_id": "s1", "id": "s1", "name": "A"}, session=session)

    # Committed with the injected tenant.
    doc = await mongo_real_db.students.find_one({"id": "s1"})
    assert doc["schoolId"] == "school-a"

    # Another tenant's scoped view cannot see it.
    other = ScopedCollection(mongo_real_db.students, "school-b")
    assert await other.count_documents({"id": "s1"}) == 0


async def test_transactional_write_rolls_back_with_scoping(mongo_real_db, mongo_real_client):
    scoped = ScopedCollection(mongo_real_db.students, "school-a")
    with pytest.raises(RuntimeError):
        async with await mongo_real_client.start_session() as session:
            async with session.start_transaction():
                await scoped.insert_one({"_id": "s1", "id": "s1"}, session=session)
                raise RuntimeError("abort")
    assert await mongo_real_db.students.count_documents({}) == 0
