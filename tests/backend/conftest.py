"""
pytest Configuration — EduFlow Backend Tests

Shared fixtures for all backend tests:
  - `client` — FastAPI TestClient (sync, no real DB)
  - `async_client` — httpx AsyncClient (async tests)
  - `auth_headers` — pre-authenticated admin Bearer token headers
  - `db` — async Motor test database (isolated per test session)

Usage:
    from tests.backend.conftest import ...  # fixtures auto-discovered by pytest
"""

import os
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator

# ─── Override environment before importing app ─────────────────────────────
# Set test environment variables before any app import
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGODB_URL", "mongodb://localhost:27017/eduflow_test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

# ─── App imports (after env setup) ─────────────────────────────────────────
try:
    from fastapi.testclient import TestClient
    import httpx
    # Import the FastAPI app — adjust path if needed
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
    from server import app
    APP_AVAILABLE = True
except ImportError as e:
    APP_AVAILABLE = False
    _import_error = str(e)


# ─── Event loop (for async tests) ─────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop shared across the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── FastAPI test clients ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client() -> Generator:
    """
    Sync FastAPI TestClient.
    Use for simple request/response tests where async is not needed.
    """
    if not APP_AVAILABLE:
        pytest.skip(f"App not importable: {_import_error}")
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator:
    """
    Async httpx client for async test functions.
    Use with `pytest.mark.asyncio`.
    """
    if not APP_AVAILABLE:
        pytest.skip(f"App not importable: {_import_error}")
    base_url = os.environ.get("API_URL", "http://localhost:8000")
    async with httpx.AsyncClient(app=app, base_url=base_url) as ac:
        yield ac


# ─── Auth helpers ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def auth_token(client) -> str:
    """
    Log in as the test admin and return the JWT token.
    Cached for the session so login only happens once.
    """
    username = os.environ.get("TEST_ADMIN_USERNAME", "admin")
    password = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        pytest.fail(
            f"Auth fixture: login failed with status {response.status_code}: {response.text}"
        )
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """
    Pre-built Authorization headers for authenticated requests.

    Usage:
        def test_something(client, auth_headers):
            resp = client.get("/api/students", headers=auth_headers)
    """
    return {"Authorization": f"Bearer {auth_token}"}


# ─── Test data factories ───────────────────────────────────────────────────

@pytest.fixture
def student_data() -> dict:
    """Build a minimal student payload for POST /api/students."""
    import random
    suffix = random.randint(1000, 9999)
    return {
        "name": f"Test Student {suffix}",
        "class_name": "Class 5",
        "section": "A",
        "roll_number": f"ROLL{suffix}",
        "parent_name": f"Parent {suffix}",
        "parent_phone": f"9{suffix:09d}",
        "gender": "M",
    }


@pytest.fixture
def staff_data() -> dict:
    """Build a minimal staff payload for POST /api/staff."""
    import random
    suffix = random.randint(1000, 9999)
    return {
        "name": f"Test Teacher {suffix}",
        "role": "teacher",
        "subject": "Mathematics",
        "phone": f"8{suffix:09d}",
        "email": f"teacher{suffix}@testschool.edu",
        "employee_id": f"EMP{suffix}",
    }
