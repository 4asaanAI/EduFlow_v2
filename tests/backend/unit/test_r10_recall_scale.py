"""Epic R10.1 AC2 — indexed/paginated recall (no blind full-collection scans).

Recall reads candidates via the (schoolId, user_id, updated_at_ts) index, paginated
freshest-first, up to a documented + logged ceiling. Memories beyond a single page
stay recallable; the ceiling is never a silent hard wall (XM10).
"""

from __future__ import annotations

import logging

import pytest

pytestmark = pytest.mark.asyncio

from services.actor_context import actor_ctx_from_user
from services.memory import store as memory_store
from tests.backend.conftest import FakeDb


def _ctx(user_id="owner-1", school="aaryans-joya"):
    user = {"id": user_id, "role": "owner", "name": "T", "branch_id": "branch-a"}
    return actor_ctx_from_user(user, school_id=school, branch_id="branch-a")


async def test_recall_pages_beyond_one_page(monkeypatch):
    """With a tiny page size, recall still reaches memories on later pages (AC2)."""
    monkeypatch.setattr(memory_store, "_SWEEP_PAGE", 2)
    db = FakeDb()
    ctx = _ctx()
    for i in range(5):
        await memory_store.add_memory(db, ctx, text=f"owner likes report style {i}")
    # A query that matches all five — they span 3 pages of size 2. All must be scored.
    hits = await memory_store.recall(db, ctx, "owner likes report style", k=10)
    assert len(hits) == 5


async def test_recall_uses_indexed_query_not_full_scan(monkeypatch):
    """The candidate fetch must go through the sort/skip/limit cursor path, never a
    single unbounded .to_list — regression guard that the hot path stays indexed."""
    monkeypatch.setattr(memory_store, "_SWEEP_PAGE", 2)
    db = FakeDb()
    ctx = _ctx()
    for i in range(3):
        await memory_store.add_memory(db, ctx, text=f"fee reminder preference {i}")

    calls = {"to_list_limits": []}
    real_find = db.ai_memories.find

    def spy_find(*args, **kwargs):
        cursor = real_find(*args, **kwargs)
        real_to_list = cursor.to_list

        async def spy_to_list(limit):
            calls["to_list_limits"].append(limit)
            return await real_to_list(limit)

        cursor.to_list = spy_to_list
        return cursor

    db.ai_memories.find = spy_find
    await memory_store.recall(db, ctx, "fee reminder preference", k=5)
    # Every candidate read is a bounded page (== _SWEEP_PAGE), never a 2000 blind scan.
    assert calls["to_list_limits"]
    assert all(limit == 2 for limit in calls["to_list_limits"])


async def test_recall_ceiling_is_logged_not_silent(monkeypatch, caplog):
    """When the scan ceiling is reached, recall logs it (never a silent truncation)."""
    monkeypatch.setattr(memory_store, "_SWEEP_PAGE", 2)
    monkeypatch.setattr(memory_store, "RECALL_SCAN_CEILING", 4)
    db = FakeDb()
    ctx = _ctx()
    for i in range(6):
        await memory_store.add_memory(db, ctx, text=f"note number {i} about fees")
    with caplog.at_level(logging.WARNING, logger="services.memory.store"):
        hits = await memory_store.recall(db, ctx, "note about fees", k=10)
    assert len(hits) <= 4
    assert any("scan ceiling" in r.message for r in caplog.records)


async def test_recall_still_owner_and_tenant_scoped(monkeypatch):
    monkeypatch.setattr(memory_store, "_SWEEP_PAGE", 2)
    db = FakeDb()
    await memory_store.add_memory(db, _ctx("owner-1"), text="owner one fee note")
    await memory_store.add_memory(db, _ctx("owner-2"), text="owner two fee note")
    await memory_store.add_memory(db, _ctx("owner-1", school="other"), text="cross tenant fee note")
    hits = await memory_store.recall(db, _ctx("owner-1"), "fee note", k=10)
    texts = [h["text"] for h in hits]
    assert texts == ["owner one fee note"]
