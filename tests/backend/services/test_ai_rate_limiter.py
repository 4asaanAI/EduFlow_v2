"""Unit tests for backend/services/ai_rate_limiter.py — Story 7-48."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio


def _now_at(hour: int, minute: int = 0, second: int = 0):
    return datetime(2026, 5, 15, hour, minute, second, tzinfo=timezone.utc)


def _import_module():
    """Import the rate limiter, ensuring conftest path setup ran."""
    from tests.backend.conftest import APP_AVAILABLE  # noqa: F401
    from services import ai_rate_limiter
    ai_rate_limiter.reset_config_cache()
    return ai_rate_limiter


# ─── Time helpers ──────────────────────────────────────────────────────────


async def test_hour_bucket_truncates_to_clock_hour():
    rl = _import_module()
    bucket = rl.hour_bucket(_now_at(14, 37, 12))
    assert bucket == "2026-05-15T14:00:00Z"


async def test_hour_bucket_handles_naive_datetime_as_utc():
    rl = _import_module()
    naive = datetime(2026, 5, 15, 14, 37, 12)
    bucket = rl.hour_bucket(naive)
    assert bucket == "2026-05-15T14:00:00Z"


async def test_seconds_until_next_hour_at_top_of_hour_is_full_hour():
    rl = _import_module()
    # 00:00:00.000 → exactly 3600s until next hour
    assert rl.seconds_until_next_hour(_now_at(14, 0, 0)) == 3600


async def test_seconds_until_next_hour_mid_hour():
    rl = _import_module()
    # 14:30:00 → 1800s remaining
    assert rl.seconds_until_next_hour(_now_at(14, 30, 0)) == 1800


async def test_seconds_until_next_hour_near_boundary_returns_at_least_one():
    rl = _import_module()
    # 14:59:59.99... should yield >= 1s (never zero/negative)
    assert rl.seconds_until_next_hour(_now_at(14, 59, 59)) >= 1


# ─── resolve_limit ─────────────────────────────────────────────────────────


class _FakeOverrideDb:
    """Minimal stand-in for the override collection lookup path."""

    def __init__(self, rows=None, raise_on_find=False):
        self._rows = list(rows or [])
        self._raise = raise_on_find
        self.ai_rate_limit_overrides = _FakeOverridesCollection(self._rows, raise_on_find)


class _FakeOverridesCollection:
    def __init__(self, rows, raise_on_find):
        self._rows = rows
        self._raise = raise_on_find

    def find(self, query):
        if self._raise:
            raise RuntimeError("simulated DB error")

        def _matches(doc):
            if doc.get("school_id") != query.get("school_id"):
                return False
            if doc.get("role") != query.get("role"):
                return False
            # honour $or expires_at filter
            for clause in query.get("$or", [{}]):
                if "expires_at" in clause:
                    expected = clause["expires_at"]
                    actual = doc.get("expires_at")
                    if expected is None and actual is None:
                        return True
                    if isinstance(expected, dict) and "$gt" in expected:
                        if actual and actual > expected["$gt"]:
                            return True
            return False

        return _Cursor([d for d in self._rows if _matches(d)])


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def sort(self, key_or_list, direction=None):
        """Accept both pymongo single-field and compound-sort list forms."""
        if isinstance(key_or_list, list):
            # Compound sort: apply in reverse order so first key wins
            for k, d in reversed(key_or_list):
                self._rows.sort(key=lambda r, _k=k: r.get(_k) or datetime.min.replace(tzinfo=timezone.utc), reverse=d < 0)
        else:
            self._rows.sort(key=lambda r: r.get(key_or_list) or datetime.min.replace(tzinfo=timezone.utc), reverse=direction < 0)
        return self

    async def to_list(self, limit):
        return self._rows[:limit]


async def test_resolve_limit_returns_yaml_default_when_no_override():
    rl = _import_module()
    db = _FakeOverrideDb([])
    assert await rl.resolve_limit(role="owner", school_id="school-1", db=db) == 50


async def test_resolve_limit_zero_for_role_not_in_yaml():
    rl = _import_module()
    db = _FakeOverrideDb([])
    assert await rl.resolve_limit(role="parent", school_id="school-1", db=db) == 0


async def test_resolve_limit_returns_override_when_unexpired():
    rl = _import_module()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    db = _FakeOverrideDb([
        {"school_id": "school-1", "role": "owner", "limit": 200, "expires_at": future, "created_at": datetime.now(timezone.utc)}
    ])
    assert await rl.resolve_limit(role="owner", school_id="school-1", db=db) == 200


async def test_resolve_limit_ignores_expired_override():
    rl = _import_module()
    past = datetime.now(timezone.utc) - timedelta(days=1)
    db = _FakeOverrideDb([
        {"school_id": "school-1", "role": "owner", "limit": 200, "expires_at": past, "created_at": datetime.now(timezone.utc)}
    ])
    assert await rl.resolve_limit(role="owner", school_id="school-1", db=db) == 50


async def test_resolve_limit_falls_back_on_db_error():
    rl = _import_module()
    db = _FakeOverrideDb(raise_on_find=True)
    # YAML default for owner is 50 — error path must not throw.
    assert await rl.resolve_limit(role="owner", school_id="school-1", db=db) == 50


# ─── increment_and_check ───────────────────────────────────────────────────


def _build_full_fake_db(override_rows=None):
    from tests.backend.conftest import FakeCollection, FakeDb
    db = FakeDb()
    db.ai_rate_limit_overrides = FakeCollection(list(override_rows or []))
    return db


async def test_increment_and_check_zero_limit_rejects_first_attempt():
    rl = _import_module()
    db = _build_full_fake_db()

    fixed_time = _now_at(14, 0, 0)
    result = await rl.increment_and_check(
        user_id="user-x",
        role="student",  # YAML default = 0
        school_id="school-1",
        db=db,
        now_fn=lambda: fixed_time,
    )
    assert result.allowed is False
    assert result.limit == 0
    assert result.retry_after_seconds == 3600


async def test_increment_and_check_allows_under_limit_then_rejects_over():
    rl = _import_module()
    db = _build_full_fake_db()
    fixed_time = _now_at(14, 30, 0)

    # Owner default = 50. Burn through 50 → allowed, 51st → rejected.
    for n in range(1, 51):
        result = await rl.increment_and_check(
            user_id="owner-1",
            role="owner",
            school_id="school-1",
            db=db,
            now_fn=lambda: fixed_time,
        )
        assert result.allowed is True, f"call #{n} should be allowed"
        assert result.count == n

    result = await rl.increment_and_check(
        user_id="owner-1",
        role="owner",
        school_id="school-1",
        db=db,
        now_fn=lambda: fixed_time,
    )
    assert result.allowed is False
    # Counter is intentionally NOT incremented past the limit (avoids skewing
    # dashboards). count stays at the limit value on rejection.
    assert result.count == 50
    assert result.limit == 50
    assert result.retry_after_seconds == 1800  # half-hour remaining


async def test_counter_resets_at_next_hour_bucket():
    rl = _import_module()
    db = _build_full_fake_db()

    # 50 calls at 14:30 — owner's full budget for that hour.
    for _ in range(50):
        await rl.increment_and_check(
            user_id="owner-1",
            role="owner",
            school_id="school-1",
            db=db,
            now_fn=lambda: _now_at(14, 30, 0),
        )

    # Next call at 15:01 should be allowed — new bucket, fresh count.
    result = await rl.increment_and_check(
        user_id="owner-1",
        role="owner",
        school_id="school-1",
        db=db,
        now_fn=lambda: _now_at(15, 1, 0),
    )
    assert result.allowed is True
    assert result.count == 1
    assert result.bucket == "2026-05-15T15:00:00Z"


async def test_sessions_share_a_single_counter_per_user_hour():
    """Counter is per-(user_id, hour_bucket) — session_id rotation must NOT bypass."""
    rl = _import_module()
    db = _build_full_fake_db()
    fixed_time = _now_at(14, 0, 0)

    for _ in range(50):
        await rl.increment_and_check(
            user_id="owner-1", role="owner", school_id="school-1",
            db=db, now_fn=lambda: fixed_time,
        )
    # A 51st request — even after the caller "rotates session" — is rejected.
    result = await rl.increment_and_check(
        user_id="owner-1", role="owner", school_id="school-1",
        db=db, now_fn=lambda: fixed_time,
    )
    assert result.allowed is False
    assert result.count == 50  # not incremented past limit


async def test_payload_shape_matches_spec():
    rl = _import_module()
    db = _build_full_fake_db()
    result = await rl.increment_and_check(
        user_id="u", role="student", school_id="school-1",
        db=db, now_fn=lambda: _now_at(14, 30, 0),
    )
    payload = result.to_response_payload()
    assert payload["success"] is False
    assert payload["error"] == "rate_limit_exceeded"
    assert payload["window"] == "hour"
    assert payload["limit"] == 0
    assert payload["retry_after_seconds"] == 1800
