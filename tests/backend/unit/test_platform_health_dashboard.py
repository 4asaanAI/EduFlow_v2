from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

pytestmark = pytest.mark.asyncio

from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection, APP_AVAILABLE

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from server import app
from tests.backend.conftest import _fake_db


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _owner_headers():
    return _bearer({
        "user_id": "owner-1", "role": "owner", "name": "Aman",
        "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


def _admin_headers():
    return _bearer({
        "user_id": "admin-1", "role": "admin", "name": "Adesh",
        "sub_category": "principal", "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


# ─── Mock httpx so network is never hit ──────────────────────────────────────

class _FakeResponse:
    status_code = 200


class _FakeAsyncClient:
    def __init__(self, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, url, **kwargs):
        return _FakeResponse()


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clean():
    _fake_db.audit_logs.docs[:] = []
    _fake_db.fee_sync_jobs.docs[:] = []
    _fake_db.token_balances.docs[:] = []
    _fake_db.auth_users.docs[:] = [
        {
            "id": "admin-1",
            "username": "admin",
            "password_hash": "x",
            "is_active": True,
            "schoolId": "aaryans-joya",
            "user_info": {"id": "admin-1", "role": "owner", "name": "Admin"},
        }
    ]
    yield
    _fake_db.audit_logs.docs[:] = []
    _fake_db.fee_sync_jobs.docs[:] = []
    _fake_db.token_balances.docs[:] = []
    _fake_db.auth_users.docs[:] = []


@pytest.fixture
def client(monkeypatch):
    import routes.operator as op
    monkeypatch.setattr(op, "httpx", type("httpx", (), {"AsyncClient": _FakeAsyncClient})())
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ─── Auth tests ───────────────────────────────────────────────────────────────

def test_platform_health_unauthenticated_returns_401(client):
    resp = client.get("/api/operator/platform-health")
    assert resp.status_code == 401


def test_platform_health_wrong_role_returns_403(client):
    resp = client.get("/api/operator/platform-health", headers=_admin_headers())
    assert resp.status_code == 403


# ─── Shape test ───────────────────────────────────────────────────────────────

def test_platform_health_owner_returns_200_with_expected_shape(client):
    resp = client.get("/api/operator/platform-health", headers=_owner_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert "service_checks" in data
    assert "token_pool" in data
    assert "fee_sync_last" in data
    assert "error_rate" in data
    assert "active_user_count" in data
    assert "generated_at" in data
    sc = data["service_checks"]
    assert sc["db"] in ("ok", "error", "degraded")
    assert sc["overall"] in ("ok", "degraded", "down")


# ─── Fee sync tests ───────────────────────────────────────────────────────────

def test_fee_sync_last_returns_most_recent_job(client):
    _fake_db.fee_sync_jobs.docs[:] = [
        {
            "id": "job-old",
            "schoolId": "aaryans-joya",
            "status": "completed",
            "started_at": "2026-05-17T05:00:00",
            "completed_at": "2026-05-17T05:02:00",
        },
        {
            "id": "job-new",
            "schoolId": "aaryans-joya",
            "status": "completed",
            "started_at": "2026-05-18T05:00:00",
            "completed_at": "2026-05-18T05:01:45",
        },
    ]
    resp = client.get("/api/operator/platform-health", headers=_owner_headers())
    assert resp.status_code == 200
    fee_sync = resp.json()["data"]["fee_sync_last"]
    assert fee_sync is not None
    assert fee_sync["job_id"] == "job-new"


def test_fee_sync_last_is_null_when_no_jobs(client):
    _fake_db.fee_sync_jobs.docs[:] = []
    resp = client.get("/api/operator/platform-health", headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["fee_sync_last"] is None


# ─── Error rate tests ─────────────────────────────────────────────────────────

def test_error_rate_counts_failed_audit_actions(client):
    recent = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    _fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "action": "fee_sync_failed", "created_at": recent},
        {"id": "a2", "schoolId": "aaryans-joya", "action": "import_error", "created_at": recent},
        {"id": "a3", "schoolId": "aaryans-joya", "action": "fee_collected", "created_at": recent},
    ]
    resp = client.get("/api/operator/platform-health", headers=_owner_headers())
    assert resp.status_code == 200
    er = resp.json()["data"]["error_rate"]
    assert er["error_count"] == 2
    assert er["window_minutes"] == 60


def test_error_rate_excludes_old_entries(client):
    old = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    _fake_db.audit_logs.docs[:] = [
        {"id": "a1", "schoolId": "aaryans-joya", "action": "fee_sync_failed", "created_at": old},
    ]
    resp = client.get("/api/operator/platform-health", headers=_owner_headers())
    assert resp.status_code == 200
    er = resp.json()["data"]["error_rate"]
    assert er["error_count"] == 0


# ─── Active user count ────────────────────────────────────────────────────────

def test_active_user_count_counts_only_active_users(client):
    _fake_db.auth_users.docs[:] = [
        {"id": "u1", "schoolId": "aaryans-joya", "is_active": True, "role": "owner"},
        {"id": "u2", "schoolId": "aaryans-joya", "is_active": True, "role": "admin"},
        {"id": "u3", "schoolId": "aaryans-joya", "is_active": False, "role": "teacher"},
    ]
    resp = client.get("/api/operator/platform-health", headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["active_user_count"] == 2
