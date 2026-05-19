from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

pytestmark = pytest.mark.asyncio

from tests.backend.conftest import APP_AVAILABLE, FakeCollection  # noqa: E402

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from middleware.auth import create_jwt, hash_password  # noqa: E402
from server import app  # noqa: E402
from tests.backend.conftest import _fake_db  # noqa: E402
import middleware.school_context as school_context_mod  # noqa: E402


def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _school_a_headers() -> dict:
    return _bearer({"user_id": "ua1", "role": "owner", "name": "OwnerA", "school_id": "school-a"})


@pytest.fixture(scope="module")
def client():
    school_context_mod.get_raw_db = lambda: _fake_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_schools():
    _fake_db.schools.docs[:] = []
    yield
    _fake_db.schools.docs[:] = []


# ─── Unit: scoped_filter strict mode ─────────────────────────────────────────

def test_scoped_filter_strict_no_exists_false():
    from tenant import scoped_filter

    result = scoped_filter({})
    assert "$exists" not in str(result), "scoped_filter must not contain $exists clause"


def test_scoped_filter_plain_school_id():
    from tenant import scoped_filter

    result = scoped_filter({}, school_id="test-school")
    assert result == {"schoolId": "test-school"}


def test_scoped_filter_with_base_query():
    from tenant import scoped_filter

    result = scoped_filter({"status": "active"}, school_id="test-school")
    assert result == {"$and": [{"status": "active"}, {"schoolId": "test-school"}]}


def test_scoped_filter_preserves_existing_schoolid():
    from tenant import scoped_filter

    result = scoped_filter({"schoolId": "my-school", "status": "x"}, school_id="other")
    assert result == {"schoolId": "my-school", "status": "x"}


# ─── Unit: get_school_id with ContextVar ─────────────────────────────────────

def test_get_school_id_reads_context_var():
    from tenant import _school_id_var, get_school_id

    token = _school_id_var.set("custom-school")
    try:
        assert get_school_id() == "custom-school"
    finally:
        _school_id_var.reset(token)


def test_get_school_id_falls_back_to_env(monkeypatch):
    from tenant import _school_id_var, get_school_id

    token = _school_id_var.set(None)
    try:
        monkeypatch.setenv("SCHOOL_ID", "env-school")
        assert get_school_id() == "env-school"
    finally:
        _school_id_var.reset(token)


def test_get_school_id_falls_back_to_default(monkeypatch):
    from tenant import _school_id_var, get_school_id

    token = _school_id_var.set(None)
    try:
        monkeypatch.delenv("SCHOOL_ID", raising=False)
        assert get_school_id() == "aaryans-joya"
    finally:
        _school_id_var.reset(token)


# ─── Middleware: unauthenticated passthrough ──────────────────────────────────

def test_middleware_unauthenticated_returns_401(client):
    resp = client.get("/api/students")
    assert resp.status_code == 401


def test_middleware_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "u1", "role": "student", "name": "S", "school_id": "school-a"})
    resp = client.post("/api/operator/schools", json={}, headers=headers)
    assert resp.status_code == 403


# ─── Middleware: deactivated school enforcement ───────────────────────────────

def test_deactivated_school_returns_402(client):
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "deactivated"})
    resp = client.get("/api/students", headers=_school_a_headers())
    assert resp.status_code == 402
    assert "deactivated" in resp.json()["detail"].lower()


def test_active_school_passes_middleware(client):
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "active"})
    resp = client.get("/api/students", headers=_school_a_headers())
    assert resp.status_code != 402


def test_no_school_doc_passes_middleware(client):
    """If school not found in schools collection, proceed normally (fail-open)."""
    resp = client.get("/api/students", headers=_school_a_headers())
    assert resp.status_code != 402


def test_deactivated_school_login_not_blocked(client):
    """/api/auth/login is in _SKIP_PATHS — deactivated school must not return 402."""
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "deactivated"})
    resp = client.post(
        "/api/auth/login",
        json={"username": "no_such_user@test.com", "password": "wrong"},
    )
    assert resp.status_code != 402


def test_deactivated_school_refresh_not_blocked(client):
    """AC3: /api/auth/refresh must not return 402 for deactivated schools (sign-out path)."""
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "deactivated"})
    # Refresh uses a cookie, not a Bearer token — middleware skips school context
    # entirely for requests without a Bearer header, so 402 must never be returned.
    resp = client.post("/api/auth/refresh")
    assert resp.status_code != 402


def test_no_bearer_token_skips_school_context(client):
    """Requests without Authorization header must pass through with 401, not 500."""
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "deactivated"})
    resp = client.get("/api/students")
    assert resp.status_code == 401


def test_jwt_without_school_id_skips_school_context(client):
    """JWT with no school_id claim — middleware skips context injection, route still works."""
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "deactivated"})
    headers = _bearer({"user_id": "u1", "role": "owner", "name": "Owner"})
    resp = client.get("/api/students", headers=headers)
    assert resp.status_code != 402


# ─── JWT: school_id claim in login response ───────────────────────────────────

def test_login_jwt_contains_school_id(client):
    """Successful login for a school-scoped user returns a JWT with school_id claim."""
    _fake_db.auth_users.docs.append({
        "id": "auth-sc-login",
        "username": "sc_login@test.com",
        "username_lower": "sc_login@test.com",
        "password_hash": hash_password("TestPass123!"),
        "is_active": True,
        "schoolId": "school-a",
        "role": "owner",
        "user_info": {"id": "uid-sc-login", "name": "SC Login", "role": "owner"},
    })
    try:
        resp = client.post(
            "/api/auth/login",
            json={"username": "sc_login@test.com", "password": "TestPass123!"},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        from jose import jwt as _jose
        payload = _jose.decode(
            token,
            "test-jwt-secret-key-not-for-production",
            algorithms=["HS256"],
        )
        assert "school_id" in payload
        assert payload["school_id"] == "school-a"
    finally:
        _fake_db.auth_users.docs[:] = [
            d for d in _fake_db.auth_users.docs if d.get("username") != "sc_login@test.com"
        ]


def test_login_school_id_scoped_lookup(client):
    """Login with school_id field scopes the auth_users lookup."""
    _fake_db.auth_users.docs.append({
        "id": "auth-scoped-school",
        "username": "scoped@test.com",
        "username_lower": "scoped@test.com",
        "password_hash": hash_password("ScopedPass1!"),
        "is_active": True,
        "schoolId": "target-school",
        "role": "owner",
        "user_info": {"id": "uid-scoped", "name": "Scoped Owner", "role": "owner"},
    })
    try:
        resp = client.post(
            "/api/auth/login",
            json={
                "username": "scoped@test.com",
                "password": "ScopedPass1!",
                "school_id": "target-school",
            },
        )
        assert resp.status_code == 200
    finally:
        _fake_db.auth_users.docs[:] = [
            d for d in _fake_db.auth_users.docs if d.get("username") != "scoped@test.com"
        ]


# ─── Cross-tenant isolation ───────────────────────────────────────────────────

def test_school_a_cannot_read_school_b_students(client):
    """Students seeded for school-b must not appear in school-a query results."""
    _fake_db.students.docs.append({
        "id": "sb-isolation-student",
        "schoolId": "school-b",
        "name": "B Student",
        "class_id": "c1",
        "admission_number": "ADM-ISO",
        "is_active": True,
        "status": "active",
    })
    _fake_db.schools.docs.append({"school_id": "school-a", "status": "active"})
    try:
        resp = client.get("/api/students", headers=_school_a_headers())
        assert resp.status_code == 200
        returned_ids = [s.get("id") for s in resp.json().get("data", [])]
        assert "sb-isolation-student" not in returned_ids
    finally:
        _fake_db.students.docs[:] = [
            d for d in _fake_db.students.docs if d.get("id") != "sb-isolation-student"
        ]


# ─── Deactivate school: refresh token invalidation ───────────────────────────

def test_deactivate_school_invalidates_refresh_tokens(client):
    """Deactivating a school deletes refresh tokens for all its users."""
    _fake_db.schools.docs.append({"school_id": "school-deact-rt", "status": "active"})
    _fake_db.auth_users.docs.append({
        "id": "auth-deact-rt",
        "username": "deact_rt@test.com",
        "username_lower": "deact_rt@test.com",
        "password_hash": "x",
        "is_active": True,
        "schoolId": "school-deact-rt",
        "role": "owner",
        "user_info": {"id": "uid-deact-rt", "name": "Deact RT Owner", "role": "owner"},
    })
    _fake_db.refresh_tokens.docs.append({
        "token_hash": "deact_rt_token_hash",
        "user_id": "uid-deact-rt",
        "revoked_at": None,
    })
    try:
        headers = _bearer({"user_id": "op1", "role": "owner", "name": "OpOwner", "school_id": "aaryans-joya"})
        resp = client.patch(
            "/api/operator/schools/school-deact-rt/deactivate", headers=headers
        )
        assert resp.status_code == 200
        remaining = [
            t for t in _fake_db.refresh_tokens.docs if t.get("user_id") == "uid-deact-rt"
        ]
        assert len(remaining) == 0
    finally:
        _fake_db.schools.docs[:] = [
            d for d in _fake_db.schools.docs if d.get("school_id") != "school-deact-rt"
        ]
        _fake_db.auth_users.docs[:] = [
            d for d in _fake_db.auth_users.docs if d.get("username") != "deact_rt@test.com"
        ]
        _fake_db.refresh_tokens.docs[:] = [
            d for d in _fake_db.refresh_tokens.docs if d.get("token_hash") != "deact_rt_token_hash"
        ]
