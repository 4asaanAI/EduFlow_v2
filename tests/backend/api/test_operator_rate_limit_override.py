"""Operator endpoint tests for AI rate limit overrides + counts — Story 7-48 AC#6/#7."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_rate_limit_collections(fake_db):
    """Reset rate-limit collections between tests since fake_db is session-wide."""
    fake_db.ai_rate_limit_overrides.docs[:] = []
    fake_db.ai_rate_limit_counters.docs[:] = []
    yield
    fake_db.ai_rate_limit_overrides.docs[:] = []
    fake_db.ai_rate_limit_counters.docs[:] = []


def _login(client, username, password):
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _login_owner(client):
    return _login(client, "admin", "admin123")


async def test_override_endpoint_requires_owner_role(client, fake_db):
    # Seed a non-owner user to exercise the 403 path.
    from middleware.auth import hash_password
    fake_db.auth_users.docs.append({
        "id": "teacher-1",
        "username": "teacher",
        "username_lower": "teacher",
        "password_hash": hash_password("teach123"),
        "is_active": True,
        "user_info": {"id": "teacher-1", "role": "teacher", "name": "T"},
    })

    token = _login(client, "teacher", "teach123")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.patch(
        "/api/operator/schools/school-1/ai-rate-limit",
        headers=headers,
        json={"role": "owner", "limit": 200, "reason": "bump"},
    )
    assert resp.status_code == 403
    # Part 1 hardening: error message is sanitized; no role-list leak.
    assert resp.json()["detail"] == "Forbidden"


async def test_override_validates_role(client, fake_db):
    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.patch(
        "/api/operator/schools/school-1/ai-rate-limit",
        headers=headers,
        json={"role": "parent", "limit": 10, "reason": "test"},
    )
    assert resp.status_code == 400
    assert "Invalid role" in resp.json()["detail"]


async def test_override_requires_reason(client):
    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.patch(
        "/api/operator/schools/school-1/ai-rate-limit",
        headers=headers,
        json={"role": "owner", "limit": 200, "reason": ""},
    )
    assert resp.status_code == 400


async def test_override_rejects_negative_limit(client):
    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.patch(
        "/api/operator/schools/school-1/ai-rate-limit",
        headers=headers,
        json={"role": "owner", "limit": -1, "reason": "x"},
    )
    assert resp.status_code == 400


async def test_override_persists_and_takes_effect(client, fake_db):
    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.patch(
        "/api/operator/schools/school-1/ai-rate-limit",
        headers=headers,
        json={"role": "owner", "limit": 200, "reason": "pilot scale-up"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["limit"] == 200
    assert body["data"]["effective_limit"] == 200

    # Override row landed in DB with required forensic fields.
    rows = [r for r in fake_db.ai_rate_limit_overrides.docs if r["school_id"] == "school-1"]
    assert len(rows) == 1
    assert rows[0]["reason"] == "pilot scale-up"
    assert rows[0]["created_by"] == "admin-1"


async def test_override_supersedes_previous_active_rows(client, fake_db):
    """Patch-fix: a fresh PATCH marks prior unexpired overrides as superseded."""
    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}

    # First override.
    client.patch(
        "/api/operator/schools/school-X/ai-rate-limit",
        headers=headers,
        json={"role": "owner", "limit": 100, "reason": "first"},
    )
    # Second override for same (school, role).
    client.patch(
        "/api/operator/schools/school-X/ai-rate-limit",
        headers=headers,
        json={"role": "owner", "limit": 300, "reason": "second"},
    )

    rows = [r for r in fake_db.ai_rate_limit_overrides.docs
            if r.get("school_id") == "school-X" and r.get("role") == "owner"]
    # Two rows total — both kept for history — but exactly one is active.
    assert len(rows) == 2
    active = [r for r in rows if not r.get("superseded")]
    assert len(active) == 1
    assert active[0]["limit"] == 300

    # Resolver returns the active limit.
    from services import ai_rate_limiter
    effective = await ai_rate_limiter.resolve_limit(role="owner", school_id="school-X", db=fake_db)
    assert effective == 300


async def test_override_expired_row_is_ignored(client, fake_db):
    """An expired override should not be returned by resolve_limit."""
    past = datetime.now(timezone.utc) - timedelta(days=1)
    fake_db.ai_rate_limit_overrides.docs.append({
        "id": "old-override",
        "school_id": "school-expired",
        "role": "owner",
        "limit": 999,
        "reason": "old",
        "expires_at": past,
        "created_at": past - timedelta(days=2),
        "created_by": "admin-1",
    })
    from services import ai_rate_limiter

    effective = await ai_rate_limiter.resolve_limit(role="owner", school_id="school-expired", db=fake_db)
    assert effective == 50  # YAML default — expired override ignored.


async def test_ai_action_counts_endpoint_owner_only(client, fake_db):
    from middleware.auth import hash_password
    fake_db.auth_users.docs.append({
        "id": "principal-1",
        "username": "principal",
        "username_lower": "principal",
        "password_hash": hash_password("p123"),
        "is_active": True,
        "user_info": {"id": "principal-1", "role": "principal", "name": "P"},
    })
    token = _login(client, "principal", "p123")
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(
        "/api/operator/ai-action-counts",
        headers=headers,
        params={"user_id": "admin-1", "session_id": "sess-X"},
    )
    assert resp.status_code == 403


async def test_ai_action_counts_returns_current_hour_count(client, fake_db, monkeypatch):
    from services import ai_rate_limiter

    fixed_now = datetime(2026, 5, 15, 14, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(ai_rate_limiter, "_now", lambda: fixed_now)

    fake_db.ai_rate_limit_counters.docs.append({
        "user_id": "admin-1",
        "hour_bucket": "2026-05-15T14:00:00Z",
        "count": 7,
        "expires_at": fixed_now + timedelta(minutes=65),
        "created_at": fixed_now,
        "role": "owner",
    })

    token = _login_owner(client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get(
        "/api/operator/ai-action-counts",
        headers=headers,
        params={"user_id": "admin-1", "session_id": "sess-Q"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["count"] == 7
    assert body["limit"] == 50  # YAML default for owner
    assert body["hour_bucket"] == "2026-05-15T14:00:00Z"


async def test_override_rejects_subcategory_as_role(client, fake_db):
    """Part 1.5 Patch O: principal/accountant are sub_categories, not roles.

    Permitting them as `role` in an override silently creates a dead row that
    never matches because no auth user has role=principal. Reject at PATCH.
    """
    token = _login_owner(client)
    resp = client.patch(
        "/api/operator/schools/school-x/ai-rate-limit",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "principal", "limit": 5, "reason": "ignored"},
    )
    assert resp.status_code == 400
    assert "Invalid role" in resp.text
