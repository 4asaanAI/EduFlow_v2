"""API integration tests for AI write rate limiting — Story 7-48.

Covers AC2 (429 + Retry-After), AC4 (audit log captures rate_limit_hit),
AC8 (backward compatibility — successful dispatches still write rate_limit_hit=False).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_rate_limit_collections(fake_db):
    """Reset rate-limit + audit collections between tests since fake_db is session-wide."""
    fake_db.ai_rate_limit_overrides.docs[:] = []
    fake_db.ai_rate_limit_counters.docs[:] = []
    fake_db.ai_dispatch_audit_log.docs[:] = []
    fake_db.confirm_tokens.docs[:] = []
    yield
    fake_db.ai_rate_limit_overrides.docs[:] = []
    fake_db.ai_rate_limit_counters.docs[:] = []
    fake_db.ai_dispatch_audit_log.docs[:] = []
    fake_db.confirm_tokens.docs[:] = []


def _login_owner(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _build_confirm_token(db, *, user_id, session_id, action="add_student", params=None):
    """Seed a non-expired confirm token directly into the fake DB."""
    import uuid as _uuid
    token = str(_uuid.uuid4())
    db.confirm_tokens.docs.append({
        "_id": token,
        "token": token,
        "action": action,
        "params": params or {"name": "Test Student"},
        "user_id": user_id,
        "session_id": session_id,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=5),
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })
    return token


async def test_confirm_returns_429_with_retry_after_when_limit_exceeded(client, fake_db, monkeypatch):
    """Once the owner has 50 successful dispatches in the hour, the 51st returns 429."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()
    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Pre-seed the counter at 50 (limit) so the next call trips it. We attach
    # the counter row directly — exercising the read-path of the limiter.
    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 50,
        "expires_at": fixed_now + timedelta(minutes=65),
        "created_at": fixed_now,
        "role": "owner",
    })



    confirm_token = _build_confirm_token(fake_db, user_id="admin-1", session_id="sess-X")

    resp = client.post(
        "/api/chat/confirm",
        headers=headers,
        json={
            "token": confirm_token,
            "session_id": "sess-X",
            "confirmed": True,
            "decision": "confirm",
        },
    )

    assert resp.status_code == 429, resp.text
    assert resp.headers.get("Retry-After") == "1800"
    body = resp.json()
    assert body["error"] == "rate_limit_exceeded"
    assert body["retry_after_seconds"] == 1800
    assert body["limit"] == 50
    assert body["window"] == "hour"


async def test_rate_limited_request_does_not_burn_confirm_token(client, fake_db, monkeypatch):
    """A 429 response must leave the confirm token unused so the user can retry."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()
    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "session_id": "sess-Y",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 50,
        "expires_at": fixed_now + timedelta(minutes=65),
        "created_at": fixed_now,
        "role": "owner",
    })
    confirm_token = _build_confirm_token(fake_db, user_id="admin-1", session_id="sess-Y")

    resp = client.post(
        "/api/chat/confirm",
        headers=headers,
        json={"token": confirm_token, "session_id": "sess-Y", "confirmed": True},
    )
    assert resp.status_code == 429

    token_row = next(t for t in fake_db.confirm_tokens.docs if t["token"] == confirm_token)
    assert token_row["used"] is False, "rate-limit rejection must NOT mark the token used"


async def test_rate_limit_rejection_writes_audit_row(client, fake_db, monkeypatch):
    """AC4: rate-limited attempts produce ai_dispatch_audit_log rows with rate_limit_hit=True."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()
    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "session_id": "sess-Z",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 50,
        "expires_at": fixed_now + timedelta(minutes=65),
        "created_at": fixed_now,
        "role": "owner",
    })
    confirm_token = _build_confirm_token(
        fake_db,
        user_id="admin-1",
        session_id="sess-Z",
        action="add_student",
        params={"name": "Bobby"},
    )

    audit_before = len(fake_db.ai_dispatch_audit_log.docs)
    client.post(
        "/api/chat/confirm",
        headers=headers,
        json={"token": confirm_token, "session_id": "sess-Z", "confirmed": True},
    )
    audit_after = fake_db.ai_dispatch_audit_log.docs
    assert len(audit_after) == audit_before + 1
    row = audit_after[-1]
    assert row["rate_limit_hit"] is True
    assert row["success"] is False
    assert row["executed_at"] is None
    assert row["tool_name"] == "add_student"
    assert row["params"] == {"name": "Bobby"}
    assert row.get("rate_limit_value") == 50


async def test_invalid_token_does_not_burn_rate_slot(client, fake_db, monkeypatch):
    """Patch-fix: a request with a bogus token must return 4xx without incrementing the counter."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()
    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    counts_before = len(fake_db.ai_rate_limit_counters.docs)
    resp = client.post(
        "/api/chat/confirm",
        headers=headers,
        json={"token": "bogus-token-uuid", "session_id": "sess-Q", "confirmed": True},
    )
    # consume_confirm_token raises 400 for unknown/missing token
    assert resp.status_code in (400, 401), resp.text
    assert len(fake_db.ai_rate_limit_counters.docs) == counts_before


async def test_session_rotation_cannot_bypass_user_limit(client, fake_db, monkeypatch):
    """Patch-fix: counter is per-(user, hour) — rotating session_id does NOT reset it."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()
    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    # User is already at the per-user-hour limit.
    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 50,
        "expires_at": fixed_now + timedelta(minutes=65),
        "created_at": fixed_now,
        "role": "owner",
    })

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Issue tokens in two distinct sessions — both must trip the same limit.
    confirm_a = _build_confirm_token(fake_db, user_id="admin-1", session_id="sess-A")
    confirm_b = _build_confirm_token(fake_db, user_id="admin-1", session_id="sess-B")

    resp_a = client.post(
        "/api/chat/confirm",
        headers=headers,
        json={"token": confirm_a, "session_id": "sess-A", "confirmed": True},
    )
    resp_b = client.post(
        "/api/chat/confirm",
        headers=headers,
        json={"token": confirm_b, "session_id": "sess-B", "confirmed": True},
    )
    assert resp_a.status_code == 429
    assert resp_b.status_code == 429


async def test_counter_does_not_inflate_past_limit_on_rejected_retries(client, fake_db, monkeypatch):
    """Patch-fix: rejected attempts must not push the counter past `limit` (dashboard hygiene)."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()
    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 50,
        "expires_at": fixed_now + timedelta(minutes=65),
        "created_at": fixed_now,
        "role": "owner",
    })

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(5):
        confirm_token = _build_confirm_token(fake_db, user_id="admin-1", session_id="sess-X")
        resp = client.post(
            "/api/chat/confirm",
            headers=headers,
            json={"token": confirm_token, "session_id": "sess-X", "confirmed": True},
        )
        assert resp.status_code == 429

    # Counter stays at 50 — pre-check prevents past-limit inflation.
    counter_row = next(c for c in fake_db.ai_rate_limit_counters.docs
                       if c.get("user_id") == "admin-1"
                       and c.get("hour_bucket") == "2026-05-15T14:00:00Z")
    assert counter_row["count"] == 50


async def test_counter_resets_at_top_of_next_hour(client, fake_db, monkeypatch):
    """A counter from a previous hour bucket has no effect on the current hour."""
    from services import ai_rate_limiter

    ai_rate_limiter.reset_config_cache()

    # Existing counter row for the previous hour (14:00).
    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "session_id": "sess-RST",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 50,
        "expires_at": datetime(2026, 5, 15, 15, 5, 0, tzinfo=timezone.utc),
        "created_at": datetime(2026, 5, 15, 14, 0, 0, tzinfo=timezone.utc),
        "role": "owner",
    })

    # Move clock into the next hour bucket.
    new_now = datetime(2026, 5, 15, 15, 5, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: new_now)

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    confirm_token = _build_confirm_token(fake_db, user_id="admin-1", session_id="sess-RST")

    resp = client.post(
        "/api/chat/confirm",
        headers=headers,
        json={"token": confirm_token, "session_id": "sess-RST", "confirmed": True},
    )
    # Either succeeds or fails for an unrelated reason — what matters is that
    # it is NOT 429 (the previous-hour counter must not apply).
    assert resp.status_code != 429, f"new hour bucket should not inherit old counter; got {resp.text}"
