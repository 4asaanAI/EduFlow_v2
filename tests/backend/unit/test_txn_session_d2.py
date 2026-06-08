"""D.2 — tenant-safe transaction sessions.

Covers the FakeDb-tier guarantees:
- `txn_context.session_kwargs` resolves the AMBIENT session when none is passed.
- `ScopedCollection` forwards `session=` AND still injects `schoolId` (no raw,
  tenant-leaking write path inside a transaction).
- `get_txn_session()` returns a usable no-op session when no replica set exists.

The real all-or-nothing / tenant-leak proof under a genuine transaction lives on
the mongo_real tier (`test_txn_tenant_scope_d2.py`).
"""

from __future__ import annotations

import pytest

from database import ScopedCollection, get_txn_session, _NoopSession
from services import txn_context

pytestmark = pytest.mark.asyncio


class _SpyCollection:
    """Records the filter/document and kwargs each op was called with."""

    def __init__(self):
        self.calls = []

    async def insert_one(self, document, *args, **kwargs):
        self.calls.append(("insert_one", document, kwargs))
        return type("R", (), {"inserted_id": document.get("_id")})()

    async def update_one(self, filter, update, *args, **kwargs):
        self.calls.append(("update_one", filter, kwargs))
        return type("R", (), {"modified_count": 1})()

    def find(self, filter=None, *args, **kwargs):
        self.calls.append(("find", filter, kwargs))
        return []


async def test_session_kwargs_explicit_wins():
    s = object()
    assert txn_context.session_kwargs(s) == {"session": s}


async def test_session_kwargs_empty_when_no_session():
    assert txn_context.session_kwargs(None) == {}
    assert txn_context.session_kwargs() == {}


async def test_session_kwargs_resolves_ambient_session():
    ambient = object()
    token = txn_context.set_current_session(ambient)
    try:
        assert txn_context.session_kwargs() == {"session": ambient}
        # explicit None still resolves to ambient (that is the whole point)
        assert txn_context.session_kwargs(None) == {"session": ambient}
    finally:
        txn_context.reset_current_session(token)
    # reset restores the no-session state
    assert txn_context.session_kwargs() == {}


async def test_scoped_collection_forwards_session_and_injects_school_id():
    spy = _SpyCollection()
    col = ScopedCollection(spy, "school-x")
    sess = object()

    await col.insert_one({"id": "1"}, session=sess)
    op, doc, kwargs = spy.calls[-1]
    assert doc["schoolId"] == "school-x"   # tenant injected
    assert kwargs.get("session") is sess   # session forwarded

    await col.update_one({"id": "1"}, {"$set": {"v": 1}}, session=sess)
    op, flt, kwargs = spy.calls[-1]
    # scoped_filter wraps a non-empty filter as {"$and": [base, {"schoolId": ...}]}
    assert {"schoolId": "school-x"} in flt["$and"]
    assert kwargs.get("session") is sess


async def test_get_txn_session_returns_noop_without_replica_set():
    # In the test process database._client is None → no-op session usable as a
    # transaction context manager (one code path, no env branching in executor).
    session = await get_txn_session()
    assert isinstance(session, _NoopSession)
    async with session.start_transaction():
        pass  # must not raise
    await session.end_session()
