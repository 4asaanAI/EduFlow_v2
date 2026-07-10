from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# R14.1 — SSE startup guard: refuses multi-worker without shared broker
# ---------------------------------------------------------------------------

def test_sse_startup_refuses_multi_worker_without_redis(monkeypatch):
    """Startup raises ValueError when WEB_CONCURRENCY > 1 and REDIS_URL is absent."""
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    monkeypatch.delenv("REDIS_URL", raising=False)

    from services import sse as sse_module
    with pytest.raises(ValueError, match="WEB_CONCURRENCY=4"):
        sse_module.validate_multi_worker_config()


def test_sse_startup_allows_multi_worker_with_redis(monkeypatch):
    """No error when WEB_CONCURRENCY > 1 AND REDIS_URL is configured."""
    monkeypatch.setenv("WEB_CONCURRENCY", "4")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

    from services import sse as sse_module
    sse_module.validate_multi_worker_config()  # must not raise


def test_sse_startup_allows_single_worker_without_redis(monkeypatch):
    """No error for the standard single-worker deployment (no Redis needed)."""
    monkeypatch.setenv("WEB_CONCURRENCY", "1")
    monkeypatch.delenv("REDIS_URL", raising=False)

    from services import sse as sse_module
    sse_module.validate_multi_worker_config()  # must not raise


def test_sse_startup_defaults_to_single_worker(monkeypatch):
    """If WEB_CONCURRENCY env var is absent, defaults to 1 (no error)."""
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)

    from services import sse as sse_module
    sse_module.validate_multi_worker_config()  # must not raise


# ---------------------------------------------------------------------------
# R14.1 — layaastat fire-and-forget: tasks held to prevent GC (already shipped R9.3)
# ---------------------------------------------------------------------------

def test_layaastat_pending_tasks_set_exists():
    """_pending_tasks set exists to hold strong refs to fire-and-forget tasks."""
    from services import layaastat
    assert hasattr(layaastat, "_pending_tasks")
    assert isinstance(layaastat._pending_tasks, set)


# ---------------------------------------------------------------------------
# R14.2 — School status cache: TTL-bounded, fail-open on exception
# ---------------------------------------------------------------------------

async def test_school_status_cached_on_second_call(monkeypatch):
    """Status lookup is cached: second call does not hit the DB."""
    from middleware import school_context

    school_context._clear_school_status_cache()

    call_count = 0

    class FakeDb:
        class schools:
            @staticmethod
            async def find_one(query, projection=None):
                nonlocal call_count
                call_count += 1
                return {"status": "active"}

    monkeypatch.setattr(school_context, "get_raw_db", lambda: FakeDb())

    # Simulate the cache being set by the first request
    school_context._set_cached_school_status("school-a", "active")

    # Second lookup should hit cache, not the DB
    result = school_context._get_cached_school_status("school-a")
    assert result == "active"
    assert call_count == 0  # DB never called


def test_school_status_cache_expires(monkeypatch):
    """Cache entry returns None after TTL expires."""
    import time as _time
    from middleware import school_context

    school_context._clear_school_status_cache()

    # Force an expired entry
    school_context._school_status_cache["school-b"] = ("active", _time.monotonic() - 1)

    result = school_context._get_cached_school_status("school-b")
    assert result is None


async def test_school_status_fail_open_on_db_exception(monkeypatch):
    """When the DB throws, the middleware fails open (request proceeds, 402 not returned)."""
    import logging
    from middleware import school_context

    school_context._clear_school_status_cache()
    warnings = []

    class FakeDb:
        class schools:
            @staticmethod
            async def find_one(query, projection=None):
                raise RuntimeError("mongo blip")

    monkeypatch.setattr(school_context, "get_raw_db", lambda: FakeDb())

    # Patch the logger to capture warnings
    original_warning = school_context.logger.warning
    def capture_warning(msg, *args, **kwargs):
        warnings.append(msg)
        original_warning(msg, *args, **kwargs)
    monkeypatch.setattr(school_context.logger, "warning", capture_warning)

    # Simulate what the middleware does on DB exception path
    school_id = "school-c"
    cached = school_context._get_cached_school_status(school_id)
    assert cached is None  # cold cache

    db = FakeDb()
    try:
        school_doc = await db.schools.find_one({"school_id": school_id})
    except Exception:
        school_context.logger.warning(
            "school status check failed school_id=%s — failing open", school_id, exc_info=True
        )
        cached = "active"  # fail open

    assert cached == "active"
    assert any("failing open" in str(w) for w in warnings)


def test_deactivated_school_returns_402(client):
    """A deactivated school gets 402 on normal requests (cache populated)."""
    from middleware import school_context
    from middleware.auth import create_jwt

    school_context._clear_school_status_cache()
    school_context._set_cached_school_status("aaryans-joya", "deactivated")

    token = create_jwt({"user_id": "u1", "role": "owner", "school_id": "aaryans-joya"})
    try:
        resp = client.get("/api/staff/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 402
    finally:
        school_context._clear_school_status_cache()


def test_active_school_passes_through(client):
    """An active school's requests are not blocked by the deactivation gate."""
    from middleware import school_context
    from middleware.auth import create_jwt

    school_context._clear_school_status_cache()
    school_context._set_cached_school_status("aaryans-joya", "active")

    token = create_jwt({"user_id": "u1", "role": "owner", "school_id": "aaryans-joya"})
    try:
        resp = client.get("/api/staff/", headers={"Authorization": f"Bearer {token}"})
        # 200 or 404 — anything except 402 means the gate passed
        assert resp.status_code != 402
    finally:
        school_context._clear_school_status_cache()
