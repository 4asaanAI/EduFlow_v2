"""Story F.4 (kill-switch) + F.5 (shadow/dry-run) — flag resolution + caching."""

from __future__ import annotations

import pytest

from services import ai_kill_switch, ai_shadow_mode

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.system_flags.docs[:] = []
    ai_kill_switch.reset_cache()
    ai_shadow_mode.reset_cache()
    yield
    fake_db.system_flags.docs[:] = []
    ai_kill_switch.reset_cache()
    ai_shadow_mode.reset_cache()


async def test_kill_switch_defaults_enabled_fail_open(fake_db):
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is True


async def test_kill_switch_off_blocks(fake_db):
    await ai_kill_switch.set_ai_writes_enabled(fake_db, enabled=False, actor_id="owner-1")
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is False


async def test_kill_switch_reenable(fake_db):
    await ai_kill_switch.set_ai_writes_enabled(fake_db, enabled=False)
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is False
    await ai_kill_switch.set_ai_writes_enabled(fake_db, enabled=True)
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is True


async def test_kill_switch_cache_ttl_bounds_staleness(monkeypatch, fake_db):
    # Flip OFF directly in the DB (no set_ helper → cache not invalidated). The
    # cached True persists until TTL expiry, then the fresh OFF is read (≤60s).
    clock = {"t": 1000.0}
    monkeypatch.setattr(ai_kill_switch, "_monotonic", lambda: clock["t"])
    ai_kill_switch.reset_cache()
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is True  # caches True
    await fake_db.system_flags.update_one(
        {"key": ai_kill_switch.FLAG_KEY}, {"$set": {"key": ai_kill_switch.FLAG_KEY, "enabled": False}}, upsert=True
    )
    clock["t"] += 5  # within TTL — still cached True
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is True
    clock["t"] += ai_kill_switch.CACHE_TTL_SECONDS + 1  # past TTL — re-reads OFF
    assert await ai_kill_switch.ai_writes_enabled(fake_db) is False


async def test_dry_run_defaults_off(fake_db):
    assert await ai_shadow_mode.ai_dry_run_enabled(fake_db) is False


async def test_dry_run_on(fake_db):
    await ai_shadow_mode.set_ai_dry_run(fake_db, enabled=True, actor_id="owner-1")
    assert await ai_shadow_mode.ai_dry_run_enabled(fake_db) is True
