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

from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import APP_AVAILABLE, FakeCollection

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from server import app
from tests.backend.conftest import _fake_db
import routes.operator as operator_mod


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _owner_headers():
    return _bearer({"user_id": "owner-1", "role": "owner", "name": "Aman"})


def _admin_headers():
    return _bearer({"user_id": "admin-1", "role": "admin", "name": "Adesh", "sub_category": "principal"})


_VALID_BODY = {
    "school_name": "Sunrise Academy",
    "school_id": "sunrise-academy",
    "owner_email": "owner@sunrise.edu",
    "plan_tier": "starter",
}


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _wipe_test_school_docs():
    _fake_db.schools.docs[:] = []
    _fake_db.school_settings.docs[:] = []
    _fake_db.staff.docs[:] = [d for d in _fake_db.staff.docs if d.get("schoolId") != "sunrise-academy"]
    _fake_db.classes.docs[:] = [d for d in _fake_db.classes.docs if d.get("schoolId") != "sunrise-academy"]
    _fake_db.students.docs[:] = [d for d in _fake_db.students.docs if d.get("schoolId") != "sunrise-academy"]
    _fake_db.fee_structures.docs[:] = [d for d in _fake_db.fee_structures.docs if d.get("schoolId") != "sunrise-academy"]
    # Only remove auth_users seeded by this test module; preserve any globally seeded accounts
    _fake_db.auth_users.docs[:] = [d for d in _fake_db.auth_users.docs if d.get("schoolId") != "sunrise-academy"]


@pytest.fixture(autouse=True)
def _clean():
    _wipe_test_school_docs()
    yield
    _wipe_test_school_docs()


@pytest.fixture(scope="module")
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ─── Security: POST /api/operator/schools ─────────────────────────────────────

def test_create_school_unauthenticated_returns_401(client):
    resp = client.post("/api/operator/schools", json=_VALID_BODY)
    assert resp.status_code == 401


def test_create_school_wrong_role_returns_403(client):
    resp = client.post("/api/operator/schools", json=_VALID_BODY, headers=_admin_headers())
    assert resp.status_code == 403


# ─── Security: GET /api/operator/schools/{id}/onboarding-status ───────────────

def test_onboarding_status_unauthenticated_returns_401(client):
    _fake_db.schools.docs.append({"school_id": "sunrise-academy", "school_name": "Sunrise", "status": "onboarding"})
    resp = client.get("/api/operator/schools/sunrise-academy/onboarding-status")
    assert resp.status_code == 401


def test_onboarding_status_wrong_role_returns_403(client):
    _fake_db.schools.docs.append({"school_id": "sunrise-academy", "school_name": "Sunrise", "status": "onboarding"})
    resp = client.get("/api/operator/schools/sunrise-academy/onboarding-status", headers=_admin_headers())
    assert resp.status_code == 403


# ─── Security: PATCH /api/operator/schools/{id}/deactivate ────────────────────

def test_deactivate_school_unauthenticated_returns_401(client):
    _fake_db.schools.docs.append({"school_id": "sunrise-academy", "school_name": "Sunrise", "status": "onboarding"})
    resp = client.patch("/api/operator/schools/sunrise-academy/deactivate")
    assert resp.status_code == 401


def test_deactivate_school_wrong_role_returns_403(client):
    _fake_db.schools.docs.append({"school_id": "sunrise-academy", "school_name": "Sunrise", "status": "onboarding"})
    resp = client.patch("/api/operator/schools/sunrise-academy/deactivate", headers=_admin_headers())
    assert resp.status_code == 403


# ─── Functional: POST /api/operator/schools ───────────────────────────────────

def test_create_school_success(client, monkeypatch):
    monkeypatch.setattr(operator_mod, "send_welcome_email", lambda *a, **kw: None)
    resp = client.post("/api/operator/schools", json=_VALID_BODY, headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["school_id"] == "sunrise-academy"
    assert data["data"]["owner_username"] == "owner@sunrise.edu"
    assert len(data["data"]["temporary_password"]) == 12

    # school doc created
    assert any(d["school_id"] == "sunrise-academy" for d in _fake_db.schools.docs)
    # school_settings created with correct schoolId
    assert any(d.get("schoolId") == "sunrise-academy" for d in _fake_db.school_settings.docs)
    # auth_users owner created with R12.1 fields
    owner_doc = next((d for d in _fake_db.auth_users.docs if d.get("schoolId") == "sunrise-academy"), None)
    assert owner_doc is not None
    assert owner_doc["role"] == "owner"
    assert owner_doc["must_change_password"] is True
    assert owner_doc["is_active"] is True
    assert owner_doc["username"] == "owner@sunrise.edu"
    # R12.1: username_lower and user_info sub-doc must be present for login to work.
    assert owner_doc.get("username_lower") == "owner@sunrise.edu"
    user_info = owner_doc.get("user_info", {})
    assert user_info.get("role") == "owner"
    assert user_info.get("id") == owner_doc["id"]
    assert user_info.get("name")
    assert user_info.get("initials")


def test_create_school_duplicate_id_returns_409(client, monkeypatch):
    """R12.4: 409 only fires when provisioning is fully complete (owner auth row exists)."""
    monkeypatch.setattr(operator_mod, "send_welcome_email", lambda *a, **kw: None)
    _fake_db.schools.docs.append({"school_id": "sunrise-academy", "status": "active"})
    _fake_db.auth_users.docs.append({
        "id": "user-existing",
        "schoolId": "sunrise-academy",
        "role": "owner",
        "username_lower": "owner@sunrise.edu",
    })
    resp = client.post("/api/operator/schools", json=_VALID_BODY, headers=_owner_headers())
    assert resp.status_code == 409
    assert "already exists" in resp.json()["detail"]


def test_create_school_partial_failure_allows_resume(client, monkeypatch):
    """R12.4 AC2: a stale schools row (no owner auth) lets provisioning resume cleanly."""
    monkeypatch.setattr(operator_mod, "send_welcome_email", lambda *a, **kw: None)
    _fake_db.schools.docs.append({"school_id": "sunrise-academy", "status": "onboarding"})
    # No auth_users row → partial failure state
    resp = client.post("/api/operator/schools", json=_VALID_BODY, headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    # Auth row was created on resume
    owner = next((d for d in _fake_db.auth_users.docs if d.get("schoolId") == "sunrise-academy"), None)
    assert owner is not None
    assert owner.get("username_lower") == "owner@sunrise.edu"


def test_create_school_invalid_slug_returns_400(client):
    body = {**_VALID_BODY, "school_id": "My School"}
    resp = client.post("/api/operator/schools", json=body, headers=_owner_headers())
    assert resp.status_code == 400
    assert "school_id" in resp.json()["detail"]


def test_create_school_invalid_slug_uppercase_returns_400(client):
    body = {**_VALID_BODY, "school_id": "SunriseAcademy"}
    resp = client.post("/api/operator/schools", json=body, headers=_owner_headers())
    assert resp.status_code == 400


def test_create_school_email_fail_open(client, monkeypatch):
    """School creation succeeds even when send_welcome_email raises."""
    def _raise(*a, **kw):
        raise RuntimeError("SMTP down")
    monkeypatch.setattr(operator_mod, "send_welcome_email", _raise)
    resp = client.post("/api/operator/schools", json=_VALID_BODY, headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ─── Functional: GET onboarding-status ───────────────────────────────────────

def test_onboarding_status_all_incomplete(client):
    _fake_db.schools.docs.append({
        "school_id": "sunrise-academy", "school_name": "Sunrise Academy", "status": "onboarding",
    })
    resp = client.get("/api/operator/schools/sunrise-academy/onboarding-status", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["completed"] is False
    assert data["steps"]["profile_created"] is True
    assert data["steps"]["first_staff_added"] is False
    assert data["steps"]["first_class_configured"] is False
    assert data["steps"]["first_student_imported"] is False
    assert data["steps"]["first_fee_record_created"] is False


def test_onboarding_status_partial(client):
    _fake_db.schools.docs.append({
        "school_id": "sunrise-academy", "school_name": "Sunrise Academy", "status": "onboarding",
    })
    _fake_db.staff.docs.append({"schoolId": "sunrise-academy", "id": "s1", "name": "Teacher One"})
    _fake_db.classes.docs.append({"schoolId": "sunrise-academy", "id": "c1", "name": "Class 1"})

    resp = client.get("/api/operator/schools/sunrise-academy/onboarding-status", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["completed"] is False
    assert data["steps"]["first_staff_added"] is True
    assert data["steps"]["first_class_configured"] is True
    assert data["steps"]["first_student_imported"] is False
    assert data["steps"]["first_fee_record_created"] is False


def test_onboarding_status_complete_sets_active(client, monkeypatch):
    _fake_db.schools.docs.append({
        "school_id": "sunrise-academy", "school_name": "Sunrise Academy", "status": "onboarding",
    })
    _fake_db.staff.docs.append({"schoolId": "sunrise-academy", "id": "s1"})
    _fake_db.classes.docs.append({"schoolId": "sunrise-academy", "id": "c1"})
    _fake_db.students.docs.append({"schoolId": "sunrise-academy", "id": "stu1"})
    _fake_db.fee_structures.docs.append({"schoolId": "sunrise-academy", "id": "fee1"})

    monkeypatch.setattr(operator_mod, "send_operator_completion_email", lambda *a, **kw: None)

    # mock the async Slack helper
    async def _noop_slack(*a, **kw):
        pass
    monkeypatch.setattr(operator_mod, "_send_operator_slack", _noop_slack)

    resp = client.get("/api/operator/schools/sunrise-academy/onboarding-status", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["completed"] is True
    assert data["status"] == "active"

    school_in_db = next(d for d in _fake_db.schools.docs if d["school_id"] == "sunrise-academy")
    assert school_in_db["status"] == "active"
    assert "activated_at" in school_in_db


def test_onboarding_status_school_not_found_returns_404(client):
    resp = client.get("/api/operator/schools/nonexistent/onboarding-status", headers=_owner_headers())
    assert resp.status_code == 404


# ─── Functional: PATCH deactivate ────────────────────────────────────────────

def test_deactivate_school_success(client):
    _fake_db.schools.docs.append({
        "school_id": "sunrise-academy", "school_name": "Sunrise Academy", "status": "onboarding",
    })
    resp = client.patch("/api/operator/schools/sunrise-academy/deactivate", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["status"] == "deactivated"

    school_in_db = next(d for d in _fake_db.schools.docs if d["school_id"] == "sunrise-academy")
    assert school_in_db["status"] == "deactivated"


def test_deactivate_school_not_found_returns_404(client):
    resp = client.patch("/api/operator/schools/ghost-school/deactivate", headers=_owner_headers())
    assert resp.status_code == 404
