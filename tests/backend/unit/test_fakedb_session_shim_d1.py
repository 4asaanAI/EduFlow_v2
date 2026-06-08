"""D.1 — FakeDb session shim: FakeCollection tolerates `session=` and ignores it.

The transaction executor threads `session=` through the shared service layer. On
the FakeDb tier there is no real transaction, so the shim must ACCEPT the kwarg on
every op WITHOUT asserting anything about atomicity (real rollback is mongo_real only).
"""

from __future__ import annotations

import pytest

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


async def test_all_ops_accept_session_kwarg():
    col = FakeCollection()
    sentinel = object()  # stands in for a Motor session — must be ignored

    await col.insert_one({"_id": "1", "id": "1", "v": 1}, session=sentinel)
    assert await col.find_one({"id": "1"}, session=sentinel) is not None
    assert await col.count_documents({"id": "1"}, session=sentinel) == 1
    assert await col.find({"id": "1"}, session=sentinel).to_list(10)

    res = await col.update_one({"id": "1"}, {"$set": {"v": 2}}, session=sentinel)
    assert res.modified_count == 1
    await col.update_many({"id": "1"}, {"$set": {"v": 3}}, session=sentinel)

    await col.delete_one({"id": "1"}, session=sentinel)
    assert await col.count_documents({}) == 0


async def test_session_shim_does_not_assert_atomicity():
    """A 'rolled back' (errored) sequence still leaves writes — FakeDb is NOT
    transactional. This documents that atomicity must be proven on mongo_real."""
    col = FakeCollection()
    sentinel = object()
    await col.insert_one({"_id": "1", "id": "1"}, session=sentinel)
    # No transaction semantics: the write persists regardless of any later error.
    assert await col.count_documents({}) == 1


async def test_unique_index_enforcement_is_opt_in():
    col = FakeCollection()
    await col.insert_one({"_id": "1", "id": "k1"})
    # No index registered → duplicates allowed (baseline behavior preserved).
    await col.insert_one({"_id": "2", "id": "k1"})
    assert await col.count_documents({"id": "k1"}) == 2

    col2 = FakeCollection()
    await col2.create_index("key", unique=True)
    await col2.insert_one({"_id": "1", "key": "v"})
    from pymongo.errors import DuplicateKeyError

    with pytest.raises(DuplicateKeyError):
        await col2.insert_one({"_id": "2", "key": "v"})
