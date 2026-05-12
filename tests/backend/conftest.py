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
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/eduflow_test")
os.environ.setdefault("DB_NAME", "eduflow_test")
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
    import server
    import routes.auth as auth_routes
    import routes.students as student_routes
    import routes.staff as staff_routes
    import routes.attendance as attendance_routes
    import routes.fees as fees_routes
    from middleware.auth import hash_password
    APP_AVAILABLE = True
except ImportError as e:
    APP_AVAILABLE = False
    _import_error = str(e)


def _get_nested(doc, key):
    value = doc
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(doc, query):
    for key, expected in (query or {}).items():
        if key == "$and":
            if not all(_matches(doc, option) for option in expected):
                return False
            continue
        if key == "$or":
            if not any(_matches(doc, option) for option in expected):
                return False
            continue
        actual = _get_nested(doc, key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$in" and actual not in value:
                    return False
                if op == "$gte" and actual < value:
                    return False
                if op == "$lte" and actual > value:
                    return False
                if op == "$gt" and actual <= value:
                    return False
                if op == "$lt" and actual >= value:
                    return False
                if op == "$exists":
                    exists = actual is not None
                    if exists is not bool(value):
                        return False
                if op == "$regex":
                    import re
                    flags = re.I if expected.get("$options") == "i" else 0
                    if re.search(value, str(actual or ""), flags) is None:
                        return False
                if op == "$options":
                    continue
            continue
        if actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction):
        self.docs.sort(key=lambda doc: doc.get(key) or "", reverse=direction < 0)
        return self

    def skip(self, count):
        self.docs = self.docs[count:]
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    async def to_list(self, _limit):
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in self.docs]


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query=None, projection=None):
        for doc in self.docs:
            if _matches(doc, query or {}):
                return {k: v for k, v in doc.items() if k != "_id"} if projection else doc
        return None

    def find(self, query=None, projection=None):
        return FakeCursor([doc for doc in self.docs if _matches(doc, query or {})])

    async def count_documents(self, query=None):
        return sum(1 for doc in self.docs if _matches(doc, query or {}))

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("Result", (), {"inserted_id": doc.get("_id")})()

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                doc.update({k: doc.get(k, 0) + v for k, v in update.get("$inc", {}).items()})
                return type("Result", (), {"modified_count": 1})()
        if upsert:
            doc = {**query, **update.get("$setOnInsert", {}), **update.get("$set", {})}
            for key, value in update.get("$inc", {}).items():
                doc[key] = value
            self.docs.append(doc)
            return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()

    async def update_many(self, query, update):
        count = 0
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                count += 1
        return type("Result", (), {"modified_count": count})()

    async def delete_one(self, query):
        before = len(self.docs)
        self.docs[:] = [doc for doc in self.docs if not _matches(doc, query)]
        return type("Result", (), {"deleted_count": before - len(self.docs)})()

    async def delete_many(self, query):
        before = len(self.docs)
        self.docs[:] = [doc for doc in self.docs if not _matches(doc, query)]
        return type("Result", (), {"deleted_count": before - len(self.docs)})()


class FakeDb:
    def __init__(self):
        self.auth_users = FakeCollection([
            {
                "id": "admin-1",
                "username": "admin",
                "username_lower": "admin",
                "password_hash": hash_password("admin123"),
                "is_active": True,
                "user_info": {"id": "admin-1", "role": "owner", "name": "Admin User"},
            }
        ])
        self.login_attempts = FakeCollection()
        self.refresh_tokens = FakeCollection()
        self.students = FakeCollection([
            {
                "id": "student-1",
                "schoolId": "aaryans-joya",
                "name": "Demo Student",
                "class_id": "class-1",
                "admission_number": "ADM1",
                "is_active": True,
                "status": "active",
                "created_at": "2026-01-01T00:00:00",
            }
        ])
        self.academic_years = FakeCollection([
            {"id": "year-1", "schoolId": "aaryans-joya", "name": "2026-27", "is_current": True}
        ])
        self.classes = FakeCollection([
            {"id": "class-1", "schoolId": "aaryans-joya", "academic_year_id": "year-1", "name": "Class 5", "section": "A"},
            {"id": "class-2", "schoolId": "aaryans-joya", "academic_year_id": "year-1", "name": "5", "section": "A"},
        ])
        self.guardians = FakeCollection()
        self.staff = FakeCollection()
        self.leave_requests = FakeCollection()
        self.audit_logs = FakeCollection()
        self.file_uploads = FakeCollection()
        self.student_attendance = FakeCollection()
        self.attendance_corrections = FakeCollection()
        self.fee_transactions = FakeCollection()
        self.fee_idempotency_keys = FakeCollection()
        self.fee_transaction_corrections = FakeCollection()
        self.fee_contact_logs = FakeCollection()
        self.fee_structures = FakeCollection()


if APP_AVAILABLE:
    _fake_db = FakeDb()

    async def _noop_connect():
        return None

    async def _noop_disconnect():
        return None

    server.connect_db = _noop_connect
    server.disconnect_db = _noop_disconnect
    auth_routes.get_db = lambda: _fake_db
    student_routes.get_db = lambda: _fake_db
    staff_routes.get_db = lambda: _fake_db
    attendance_routes.get_db = lambda: _fake_db
    fees_routes.get_db = lambda: _fake_db


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


@pytest.fixture
def fake_db():
    if not APP_AVAILABLE:
        pytest.skip(f"App not importable: {_import_error}")
    return _fake_db


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
        "class_id": "class-1",
        "roll_number": f"ROLL{suffix}",
        "guardian_name": f"Parent {suffix}",
        "guardian_phone": f"9{suffix:09d}",
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
