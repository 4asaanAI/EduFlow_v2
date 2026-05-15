"""Unit + integration tests for require_access() — Part 4 Story P4-2.1.

Tests are HTTP integration tests via a tiny in-process FastAPI app with a
test endpoint wired to Depends(require_access(...)).  The TestClient handles
full ASGI dispatch so token decoding runs through the real middleware stack.
"""

from __future__ import annotations

import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from middleware.auth import require_access, create_jwt


# ─── Tiny test app ─────────────────────────────────────────────────────────

def _make_app(dep):
    """Return a minimal FastAPI app with GET /probe using the given dependency."""
    mini = FastAPI()

    @mini.get("/probe")
    def probe(user: dict = Depends(dep)):
        return {"role": user.get("role"), "sub_category": user.get("sub_category")}

    return mini


def _bearer(payload: dict) -> dict:
    """Return Authorization headers for a JWT built from *payload*."""
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


# ─── Tests ─────────────────────────────────────────────────────────────────

def test_require_access_role_match_no_sub():
    """Admin user, require_access("admin") → 200."""
    app = _make_app(require_access("admin"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = _bearer({"user_id": "u1", "role": "admin", "name": "Test"})
    resp = client.get("/probe", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_require_access_role_and_sub_match():
    """Admin+accountant, require_access("admin", sub_category="accountant") → 200."""
    app = _make_app(require_access("admin", sub_category="accountant"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = _bearer({"user_id": "u2", "role": "admin", "sub_category": "accountant", "name": "Test"})
    resp = client.get("/probe", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["sub_category"] == "accountant"


def test_require_access_sub_mismatch():
    """Admin+principal, require_access("admin", sub_category="accountant") → 403."""
    app = _make_app(require_access("admin", sub_category="accountant"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = _bearer({"user_id": "u3", "role": "admin", "sub_category": "principal", "name": "Test"})
    resp = client.get("/probe", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"


def test_require_access_role_mismatch():
    """Teacher user, require_access("admin") → 403."""
    app = _make_app(require_access("admin"))
    client = TestClient(app, raise_server_exceptions=False)
    headers = _bearer({"user_id": "u4", "role": "teacher", "name": "Test"})
    resp = client.get("/probe", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"


def test_require_access_no_args_raises():
    """require_access() with no args raises ValueError at factory time (not at request time)."""
    with pytest.raises(ValueError, match="require_access()"):
        require_access()


def test_require_access_tuple_sub_category():
    """Admin+receptionist, require_access("admin", sub_category=("principal","receptionist")) → 200."""
    app = _make_app(require_access("admin", sub_category=("principal", "receptionist")))
    client = TestClient(app, raise_server_exceptions=False)
    headers = _bearer({"user_id": "u5", "role": "admin", "sub_category": "receptionist", "name": "Test"})
    resp = client.get("/probe", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["sub_category"] == "receptionist"


def test_require_access_no_auth_header():
    """No Authorization header → 401."""
    app = _make_app(require_access("admin"))
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/probe")
    assert resp.status_code == 401
