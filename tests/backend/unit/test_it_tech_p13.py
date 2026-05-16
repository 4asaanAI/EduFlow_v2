from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection


def _it_tech_h():
    t = create_jwt({"user_id": "it1", "role": "admin", "name": "IT", "sub_category": "it_tech"})
    return {"Authorization": f"Bearer {t}"}


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def test_it_tech_cannot_reset_owner_password(client, fake_db):
    """IT-tech gets 403 when trying to reset owner password."""
    original_docs = fake_db.auth_users.docs[:]
    fake_db.auth_users.docs = [
        {
            "id": "owner-user",
            "user_info": {"id": "owner-user", "role": "owner", "name": "Owner"},
            "password_hash": "x",
        }
    ]
    try:
        resp = client.post(
            "/api/auth/admin/users/owner-user/reset-password",
            json={"new_password": "NewPass123"},
            headers=_it_tech_h(),
        )
        assert resp.status_code == 403
    finally:
        fake_db.auth_users.docs = original_docs


def test_owner_can_reset_non_owner_password(client, fake_db):
    """Owner can reset a non-owner user's password; response has no plaintext password."""
    original_docs = fake_db.auth_users.docs[:]
    original_refresh = fake_db.refresh_tokens.docs[:]
    fake_db.auth_users.docs = [
        {
            "id": "teacher-user",
            "user_info": {"id": "teacher-user", "role": "teacher", "name": "Teacher"},
            "password_hash": "x",
        }
    ]
    fake_db.refresh_tokens.docs = []
    try:
        resp = client.post(
            "/api/auth/admin/users/teacher-user/reset-password",
            json={"new_password": "NewPass456!"},
            headers=_owner_h(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert "temporary_password" not in body, "plaintext password must not be returned"
    finally:
        fake_db.auth_users.docs = original_docs
        fake_db.refresh_tokens.docs = original_refresh


def test_admin_unlock_clears_lockout_fields(client, fake_db):
    """admin_unlock_user clears locked_at, failed_attempts, locked_until and returns success."""
    original_docs = fake_db.auth_users.docs[:]
    original_attempts = fake_db.login_attempts.docs[:]
    fake_db.auth_users.docs = [
        {
            "id": "locked-user",
            "username": "locked",
            "username_lower": "locked",
            "user_info": {"id": "locked-user", "role": "teacher", "name": "Locked"},
            "is_active": False,
            "locked_at": "2026-01-01T00:00:00",
            "failed_attempts": 5,
            "locked_until": "2026-01-01T00:15:00",
        }
    ]
    fake_db.login_attempts.docs = [
        {"key": "login:locked"}
    ]
    try:
        resp = client.post(
            "/api/auth/admin/users/locked-user/unlock",
            headers=_owner_h(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        # Check that lockout fields were cleared
        updated = fake_db.auth_users.docs[0]
        assert updated.get("is_active") is True
        assert "locked_at" not in updated
        assert "failed_attempts" not in updated
        assert "locked_until" not in updated
    finally:
        fake_db.auth_users.docs = original_docs
        fake_db.login_attempts.docs = original_attempts


def test_token_usage_admin_returns_users_over_80_pct(client, fake_db):
    """GET /api/settings/token-usage/admin returns users_over_80_pct in meta."""
    original_usage = fake_db.token_usage.docs[:]
    original_limits = fake_db.token_limits.docs[:]
    fake_db.token_usage.docs = [
        {"user_id": "u1", "tokens": 45000, "schoolId": "aaryans-joya"},
        {"user_id": "u2", "tokens": 10000, "schoolId": "aaryans-joya"},
    ]
    fake_db.token_limits.docs = []
    try:
        resp = client.get("/api/settings/token-usage/admin", headers=_owner_h())
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        meta = body.get("meta", {})
        assert "users_over_80_pct" in meta
        # u1 has 45000/50000 = 90% — should appear; u2 has 20% — should not
        over_80_ids = [r["user_id"] for r in meta["users_over_80_pct"]]
        assert "u1" in over_80_ids
        assert "u2" not in over_80_ids
    finally:
        fake_db.token_usage.docs = original_usage
        fake_db.token_limits.docs = original_limits


def test_create_branch_endpoint_exists(client, fake_db):
    """POST /api/settings/branches creates a branch and returns success."""
    original_branches = fake_db.branches.docs[:]
    fake_db.branches.docs = []
    try:
        resp = client.post(
            "/api/settings/branches",
            json={"name": "North Campus", "branch_code": "NC01", "location": "North Side"},
            headers=_owner_h(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("success") is True
        assert body["data"]["name"] == "North Campus"
        assert body["data"]["branch_code"] == "NC01"
    finally:
        fake_db.branches.docs = original_branches
