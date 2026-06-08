"""D.4 — idempotency key derivation, unique-index guard, and REST-key parity.

Concurrency (two confirms → one effect) is proven on the mongo_real tier
(`test_idempotency_concurrency_d4.py`); FakeDb cannot race a unique index.
"""

from __future__ import annotations

import importlib

import pytest

from ai.plan_schema import single_write_plan
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


class _MiniDb:
    """Exposes just the collection the migration touches."""

    def __init__(self):
        self.ai_write_idempotency = FakeCollection()


async def test_migration_025_declares_unique_index():
    mod = importlib.import_module("migrations.025_ai_write_idempotency_index")
    db = _MiniDb()
    await mod.migrate(db)
    # The index that guarantees exactly-once must exist and be unique.
    idx = db.ai_write_idempotency.indexes
    assert any(spec.get("key") == "idempotency_key" and spec.get("unique") for spec in idx.values()), idx


async def test_create_indexes_declares_ai_write_idempotency_unique():
    # Guard that database._create_indexes() declares the same unique index the
    # executor relies on (introspection over a minimal fake db).
    import database

    class _AllCollectionsDb:
        def __getattr__(self, name):
            col = FakeCollection()
            setattr(self, name, col)
            return col

    fake = _AllCollectionsDb()
    orig = database._db
    database._db = fake
    try:
        await database._create_indexes()
    finally:
        database._db = orig
    idx = fake.ai_write_idempotency.indexes
    assert any(spec.get("key") == "idempotency_key" and spec.get("unique") for spec in idx.values()), idx


async def test_idempotency_key_format_is_plan_token_colon_step_idx():
    from ai import plan_executor

    captured = {}

    class _SpyDb:
        class _Col:
            async def insert_one(self, doc, **kwargs):
                captured["key"] = doc["idempotency_key"]
        ai_write_idempotency = _Col()

    async def runner():
        return {"success": True}

    plan = single_write_plan(tool="t", params={}, runner=runner, school_id="s", plan_token="TOK")
    await plan_executor.run(plan, db=_SpyDb())
    assert captured["key"] == "TOK:0"


async def test_ai_fee_key_matches_rest_route_key():
    """AD14: where REST has a content-based idempotency key, the AI path derives the
    SAME key so AI and REST dedupe against one another (not just within a plan token)."""
    from services.fees_service import normalize_fee_key
    from routes.fees import _normalize_fee_key as rest_key

    args = ("stu-1", "2026-Q1", "Tuition")
    assert normalize_fee_key(*args) == rest_key(*args)
