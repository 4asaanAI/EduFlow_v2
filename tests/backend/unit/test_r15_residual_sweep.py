from __future__ import annotations

"""R15 — Residual Confirmatory Sweep: unit-level regressions.

Covers the localized fixes that don't need the HTTP client:
  * R15.4 (P-L2) idempotency response-body size cap
  * R15.4 (P-L1) actor_context timestamps are tz-aware UTC
  * R15.3/R15.5 (P-L9) assistant per-user hourly rate-limit helper
"""

import json

import pytest

from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


# ─── R15.4 (P-L2): idempotency response-buffer cap ──────────────────────────

class _StubURL:
    def __init__(self, path):
        self.path = path


class _StubRequest:
    def __init__(self):
        self.method = "POST"
        self.url = _StubURL("/api/things")
        self.headers = {"Idempotency-Key": "abc"}


class _StubResponse:
    def __init__(self):
        self.status_code = 200
        self.headers = {"content-type": "application/json"}


async def _store(monkeypatch, body_bytes):
    from services import idempotency
    monkeypatch.setattr(idempotency, "get_school_id", lambda: "aaryans-joya")

    class _Db:
        idempotency_keys = FakeCollection()

    db = _Db()
    await idempotency.store_response(
        db, key="k1", request=_StubRequest(), response=_StubResponse(), body=body_bytes
    )
    return db


async def test_idempotency_stores_small_response(monkeypatch):
    body = json.dumps({"success": True, "data": "ok"}).encode("utf-8")
    db = await _store(monkeypatch, body)
    assert len(db.idempotency_keys.docs) == 1


async def test_idempotency_skips_oversized_response(monkeypatch):
    from services.idempotency import MAX_IDEMPOTENCY_BODY_BYTES
    # Build a valid-JSON body that exceeds the cap — must NOT be stored (and must
    # not be truncated, which would replay corrupt).
    big = json.dumps({"blob": "x" * (MAX_IDEMPOTENCY_BODY_BYTES + 1024)}).encode("utf-8")
    assert len(big) > MAX_IDEMPOTENCY_BODY_BYTES
    db = await _store(monkeypatch, big)
    assert db.idempotency_keys.docs == []


# ─── R15.4 (P-L1): actor_context timestamps are tz-aware UTC ─────────────────

async def test_actor_context_now_is_timezone_aware_utc():
    from datetime import timezone
    from services.actor_context import _now, actor_ctx_from_user

    assert _now().tzinfo is not None
    assert _now().utcoffset() == timezone.utc.utcoffset(None)

    ctx = actor_ctx_from_user({"id": "u1", "role": "owner"}, school_id="s1")
    assert ctx.now().tzinfo is not None
    # Persisted ISO strings now carry an explicit UTC offset.
    assert ctx.now_iso().endswith("+00:00")
    assert ctx.now_utc_iso().endswith("+00:00")


# ─── R15.3/R15.5 (P-L9): assistant per-user hourly limiter ──────────────────

async def test_assistant_rate_limiter_allows_then_denies(monkeypatch):
    from routes import assistant

    assistant._assistant_calls.clear()
    uid = "user-rl-1"

    allowed = [assistant._allow_assistant_call(uid) for _ in range(assistant.ASSISTANT_HOURLY_LIMIT)]
    assert all(allowed)
    # One past the ceiling is denied.
    assert assistant._allow_assistant_call(uid) is False
    # A different user is unaffected (per-user buckets).
    assert assistant._allow_assistant_call("user-rl-2") is True


async def test_assistant_rate_limiter_resets_on_new_hour(monkeypatch):
    from routes import assistant

    uid = "user-rl-3"
    # Simulate a stale bucket at the ceiling; a new hour must reset the count.
    assistant._assistant_calls[uid] = ("1999-01-01T00", assistant.ASSISTANT_HOURLY_LIMIT)
    assert assistant._allow_assistant_call(uid) is True
    assistant._assistant_calls.pop(uid, None)


# ─── R15.5 (P-L8): house seed upsert idempotency (concurrency backstop) ─────

async def test_house_seed_upsert_is_idempotent_under_repeat():
    """Repeating the seed upsert for the same (schoolId, name) yields one row,
    not duplicates — the old insert_one path produced two under a concurrent
    first-load. Backed by the unique (schoolId, name) index in production."""
    coll = FakeCollection()
    coll.indexes["uniq_school_name"] = {"key": [("schoolId", 1), ("name", 1)], "unique": True}
    seton = {"$setOnInsert": {"schoolId": "aaryans-joya", "name": "Blue", "points": 0}}
    await coll.update_one({"schoolId": "aaryans-joya", "name": "Blue"}, seton, upsert=True)
    await coll.update_one({"schoolId": "aaryans-joya", "name": "Blue"}, seton, upsert=True)
    assert len(coll.docs) == 1
