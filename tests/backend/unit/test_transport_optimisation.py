from __future__ import annotations

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, os.path.join(ROOT, "backend"))

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")

# All tests are sync (TestClient); no asyncio mark needed

from fastapi.testclient import TestClient
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection, APP_AVAILABLE

if not APP_AVAILABLE:
    pytest.skip("App not importable", allow_module_level=True)

from server import app
from tests.backend.conftest import _fake_db


def _bearer(payload: dict) -> dict:
    token = create_jwt(payload)
    return {"Authorization": f"Bearer {token}"}


def _owner_headers():
    return _bearer({
        "user_id": "owner-1", "role": "owner", "name": "Admin",
        "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


def _transport_headers():
    return _bearer({
        "user_id": "transport-1", "role": "admin", "name": "Harish",
        "sub_category": "transport_head", "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


def _teacher_headers():
    return _bearer({
        "user_id": "teacher-1", "role": "teacher", "name": "Ravi",
        "branch_id": "branch-a", "schoolId": "aaryans-joya",
    })


client = TestClient(app, raise_server_exceptions=False)


# ─── POST /api/transport/geocode ─────────────────────────────────────────────

def test_geocode_503_when_no_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    resp = client.post(
        "/api/transport/geocode",
        json={"address": "Joya Bus Stand, Amroha, UP"},
        headers=_transport_headers(),
    )
    assert resp.status_code == 503
    assert "Maps API not configured" in resp.json().get("detail", "")


def test_geocode_returns_coordinates(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key-123")
    fake_result = {
        "lat": 28.9019,
        "lng": 78.4678,
        "formatted_address": "Joya, Amroha, Uttar Pradesh, India",
    }
    with patch("routes.operations._geocode_address", new=AsyncMock(return_value=fake_result)):
        resp = client.post(
            "/api/transport/geocode",
            json={"address": "Joya Bus Stand"},
            headers=_transport_headers(),
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["lat"] == 28.9019
    assert data["data"]["lng"] == 78.4678


def test_geocode_502_on_geocoding_failure(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key-123")
    with patch("routes.operations._geocode_address", new=AsyncMock(side_effect=RuntimeError("geocode_failed"))):
        resp = client.post(
            "/api/transport/geocode",
            json={"address": "Nowhere"},
            headers=_transport_headers(),
        )
    assert resp.status_code == 502


def test_geocode_422_on_empty_address(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key-123")
    resp = client.post(
        "/api/transport/geocode",
        json={"address": ""},
        headers=_transport_headers(),
    )
    assert resp.status_code == 422


def test_geocode_422_on_missing_address_field(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fake-key-123")
    resp = client.post(
        "/api/transport/geocode",
        json={},
        headers=_transport_headers(),
    )
    assert resp.status_code == 422


def test_geocode_unauthenticated_returns_401():
    resp = client.post("/api/transport/geocode", json={"address": "Test"})
    assert resp.status_code == 401


def test_geocode_wrong_role_returns_403():
    resp = client.post(
        "/api/transport/geocode",
        json={"address": "Test"},
        headers=_teacher_headers(),
    )
    assert resp.status_code == 403


# ─── GET /api/transport/suggest-route ────────────────────────────────────────

def test_suggest_route_422_when_student_has_no_coordinates():
    _fake_db.students.docs = [
        {
            "id": "stu-no-coords", "name": "Ravi Kumar",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
        }
    ]
    _fake_db.transport_routes.docs = []
    resp = client.get(
        "/api/transport/suggest-route?student_id=stu-no-coords",
        headers=_transport_headers(),
    )
    assert resp.status_code == 422


def test_suggest_route_happy_path():
    _fake_db.students.docs = [
        {
            "id": "stu-1", "name": "Priya Sharma",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "coordinates": {"lat": 28.90, "lng": 78.46},
            "route_zone_id": "zone-b",
        }
    ]
    _fake_db.transport_routes.docs = [
        {
            "id": "zone-a", "route_name": "Zone A",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 28.91, "lng": 78.47},
        },
        {
            "id": "zone-b", "route_name": "Zone B",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 28.95, "lng": 78.50},
        },
    ]
    resp = client.get(
        "/api/transport/suggest-route?student_id=stu-1",
        headers=_transport_headers(),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    zones = data["data"]
    assert len(zones) == 2
    # Nearest zone should be first (lower distance_km)
    assert zones[0]["distance_km"] <= zones[1]["distance_km"]
    # Current zone should be flagged
    current = next((z for z in zones if z["zone_id"] == "zone-b"), None)
    assert current is not None
    assert current["is_current"] is True


def test_suggest_route_unauthenticated_returns_401():
    resp = client.get("/api/transport/suggest-route?student_id=stu-1")
    assert resp.status_code == 401


def test_suggest_route_wrong_role_returns_403():
    resp = client.get(
        "/api/transport/suggest-route?student_id=stu-1",
        headers=_teacher_headers(),
    )
    assert resp.status_code == 403


# ─── GET /api/transport/cluster-analysis ─────────────────────────────────────

def test_cluster_analysis_happy_path():
    _fake_db.students.docs = [
        {
            "id": "stu-1", "name": "Amit",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "coordinates": {"lat": 28.90, "lng": 78.46},
            "route_zone_id": "zone-far",
        },
    ]
    _fake_db.transport_routes.docs = [
        {
            "id": "zone-near", "route_name": "Zone Near",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 28.901, "lng": 78.461},
        },
        {
            "id": "zone-far", "route_name": "Zone Far",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 29.50, "lng": 79.00},
        },
    ]
    resp = client.get("/api/transport/cluster-analysis", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["meta"]["total_with_coords"] >= 1
    # stu-1 is in zone-far but nearest is zone-near → suboptimal
    assert data["meta"]["total_suboptimal"] >= 1
    row = data["data"][0]
    assert row["nearest_zone_name"] == "Zone Near"
    assert row["current_zone_name"] == "Zone Far"


def test_cluster_analysis_all_optimal():
    _fake_db.students.docs = [
        {
            "id": "stu-opt", "name": "Geeta",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "coordinates": {"lat": 28.90, "lng": 78.46},
            "route_zone_id": "zone-1",
        },
    ]
    _fake_db.transport_routes.docs = [
        {
            "id": "zone-1", "route_name": "Zone 1",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 28.901, "lng": 78.461},
        },
        {
            "id": "zone-2", "route_name": "Zone 2",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 29.50, "lng": 79.00},
        },
    ]
    resp = client.get("/api/transport/cluster-analysis", headers=_owner_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["meta"]["total_suboptimal"] == 0
    assert data["data"] == []


def test_cluster_analysis_unauthenticated_returns_401():
    resp = client.get("/api/transport/cluster-analysis")
    assert resp.status_code == 401


def test_cluster_analysis_wrong_role_returns_403():
    resp = client.get("/api/transport/cluster-analysis", headers=_teacher_headers())
    assert resp.status_code == 403


# ─── PATCH /api/transport/students/{id}/coordinates ──────────────────────────

def test_set_student_coordinates_success():
    _fake_db.students.docs = [
        {
            "id": "stu-patch", "name": "Kiran",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
        }
    ]
    resp = client.patch(
        "/api/transport/students/stu-patch/coordinates",
        json={"lat": 28.91, "lng": 78.47},
        headers=_transport_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_set_student_coordinates_unauthenticated_returns_401():
    resp = client.patch(
        "/api/transport/students/stu-1/coordinates",
        json={"lat": 28.91, "lng": 78.47},
    )
    assert resp.status_code == 401


def test_set_student_coordinates_wrong_role_returns_403():
    resp = client.patch(
        "/api/transport/students/stu-1/coordinates",
        json={"lat": 28.91, "lng": 78.47},
        headers=_teacher_headers(),
    )
    assert resp.status_code == 403


# ─── PATCH /api/transport/zones/{id}/centroid ────────────────────────────────

def test_set_zone_centroid_success():
    _fake_db.transport_routes.docs = [
        {
            "id": "zone-patch", "route_name": "Zone Patch",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
        }
    ]
    resp = client.patch(
        "/api/transport/zones/zone-patch/centroid",
        json={"lat": 28.91, "lng": 78.47},
        headers=_transport_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_set_zone_centroid_unauthenticated_returns_401():
    resp = client.patch(
        "/api/transport/zones/zone-1/centroid",
        json={"lat": 28.91, "lng": 78.47},
    )
    assert resp.status_code == 401


def test_set_zone_centroid_wrong_role_returns_403():
    resp = client.patch(
        "/api/transport/zones/zone-1/centroid",
        json={"lat": 28.91, "lng": 78.47},
        headers=_teacher_headers(),
    )
    assert resp.status_code == 403


# ─── GET /api/transport/suggest-route — 404 for nonexistent student ──────────

def test_suggest_route_404_when_student_not_found():
    _fake_db.students.docs = []
    _fake_db.transport_routes.docs = []
    resp = client.get(
        "/api/transport/suggest-route?student_id=no-such-student",
        headers=_transport_headers(),
    )
    assert resp.status_code == 404


# ─── Cross-tenant isolation ───────────────────────────────────────────────────

def test_suggest_route_does_not_return_other_school_zones():
    _fake_db.students.docs = [
        {
            "id": "stu-iso", "name": "Tenant Check",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "coordinates": {"lat": 28.90, "lng": 78.46},
        }
    ]
    # Only other-school zone has a centroid — should never appear in results
    _fake_db.transport_routes.docs = [
        {
            "id": "zone-other", "route_name": "Other School Zone",
            "schoolId": "other-school", "branch_id": "branch-b",
            "is_active": True,
            "centroid": {"lat": 28.91, "lng": 78.47},
        },
    ]
    resp = client.get(
        "/api/transport/suggest-route?student_id=stu-iso",
        headers=_transport_headers(),
    )
    assert resp.status_code == 200
    zones = resp.json()["data"]
    zone_ids = [z["zone_id"] for z in zones]
    assert "zone-other" not in zone_ids


def test_cluster_analysis_does_not_return_other_school_students():
    _fake_db.students.docs = [
        {
            "id": "stu-mine", "name": "In School",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "coordinates": {"lat": 28.90, "lng": 78.46},
            "route_zone_id": "zone-far",
        },
        {
            "id": "stu-other", "name": "Other School",
            "schoolId": "other-school", "branch_id": "branch-b",
            "is_active": True,
            "coordinates": {"lat": 28.90, "lng": 78.46},
            "route_zone_id": "zone-far",
        },
    ]
    _fake_db.transport_routes.docs = [
        {
            "id": "zone-near", "route_name": "Near",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 28.901, "lng": 78.461},
        },
        {
            "id": "zone-far", "route_name": "Far",
            "schoolId": "aaryans-joya", "branch_id": "branch-a",
            "is_active": True,
            "centroid": {"lat": 29.50, "lng": 79.00},
        },
    ]
    resp = client.get("/api/transport/cluster-analysis", headers=_owner_headers())
    assert resp.status_code == 200
    student_ids = [row["student_id"] for row in resp.json()["data"]]
    assert "stu-other" not in student_ids


# ─── Haversine unit test ──────────────────────────────────────────────────────

def test_haversine_known_distance():
    from services.maps_service import haversine_km
    # Amroha to Moradabad ~50km straight line
    dist = haversine_km(28.9019, 78.4678, 28.8358, 78.7760)
    assert 25.0 < dist < 40.0
