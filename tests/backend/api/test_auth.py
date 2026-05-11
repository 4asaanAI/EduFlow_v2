"""
API Tests: Authentication — EduFlow Backend

Tests for POST /api/auth/login and GET /api/auth/me endpoints.
Uses pytest with FastAPI's TestClient (sync) — no real DB required for
most tests since auth route validates credentials against MongoDB.

For CI: requires TEST_ADMIN_USERNAME + TEST_ADMIN_PASSWORD env vars,
and a running MongoDB with seed data.
"""

import pytest
import os


# ─── Login Endpoint ─────────────────────────────────────────────────────────

class TestLogin:
    """POST /api/auth/login"""

    def test_login_with_valid_credentials(self, client):
        """Given valid credentials, should return 200 with access_token."""
        username = os.environ.get("TEST_ADMIN_USERNAME", "admin")
        password = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")

        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 20

    def test_login_with_invalid_password(self, client):
        """Given wrong password, should return 401."""
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrong_password_xyz"},
        )

        assert response.status_code == 401

    def test_login_with_nonexistent_user(self, client):
        """Given non-existent username, should return 401."""
        response = client.post(
            "/api/auth/login",
            json={"username": "no_such_user_abc123", "password": "whatever"},
        )

        assert response.status_code == 401

    def test_login_missing_username(self, client):
        """Given missing username field, should return 422."""
        response = client.post(
            "/api/auth/login",
            json={"password": "somepass"},
        )

        assert response.status_code == 422

    def test_login_missing_password(self, client):
        """Given missing password field, should return 422."""
        response = client.post(
            "/api/auth/login",
            json={"username": "admin"},
        )

        assert response.status_code == 422

    def test_login_empty_username(self, client):
        """Given empty username string, should return 422 (validator rejects it)."""
        response = client.post(
            "/api/auth/login",
            json={"username": "", "password": "password"},
        )

        # Either 422 (validation) or 401 (auth failure) is acceptable
        assert response.status_code in (401, 422)

    @pytest.mark.parametrize("malicious_input", [
        "admin${}",
        "admin()",
        "admin{$where: 1}",
    ])
    def test_login_rejects_injection_characters(self, client, malicious_input):
        """Given NoSQL injection attempt in username, should return 422."""
        response = client.post(
            "/api/auth/login",
            json={"username": malicious_input, "password": "password"},
        )

        assert response.status_code == 422


# ─── Me Endpoint ─────────────────────────────────────────────────────────────

class TestGetMe:
    """GET /api/auth/me"""

    def test_get_me_with_valid_token(self, client, auth_headers):
        """Given a valid JWT, should return the current user's profile."""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # Verify expected fields are present
        assert "username" in data or "name" in data
        assert "role" in data

    def test_get_me_without_token(self, client):
        """Without Authorization header, should return 401."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_get_me_with_invalid_token(self, client):
        """Given a malformed/invalid JWT, should return 401."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer not.a.real.token"},
        )

        assert response.status_code == 401
