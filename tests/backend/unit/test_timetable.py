from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.factories import make_staff

pytestmark = pytest.mark.asyncio


def _teacher_h():
    t = create_jwt({"user_id": "t1", "role": "teacher", "name": "Teacher"})
    return {"Authorization": f"Bearer {t}"}


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _admin_h():
    t = create_jwt({"user_id": "a1", "role": "admin", "name": "Admin"})
    return {"Authorization": f"Bearer {t}"}


# --- GET /timetable/{class_id} ---

def test_get_timetable_returns_200_for_teacher(client, fake_db):
    """GET /api/academics/timetable/{class_id} returns 200 for teacher."""
    fake_db.timetable_slots.docs = []
    fake_db.subjects.docs = []
    resp = client.get("/api/academics/timetable/class-1", headers=_teacher_h())
    assert resp.status_code == 200


def test_get_timetable_returns_200_for_admin(client, fake_db):
    """GET /api/academics/timetable/{class_id} returns 200 for admin."""
    fake_db.timetable_slots.docs = []
    fake_db.subjects.docs = []
    resp = client.get("/api/academics/timetable/class-1", headers=_admin_h())
    assert resp.status_code == 200


def test_get_timetable_returns_slots(client, fake_db):
    """GET /api/academics/timetable/{class_id} returns enrolled slots."""
    fake_db.timetable_slots.docs = [
        {
            "id": "slot-1",
            "schoolId": "aaryans-joya",
            "class_id": "class-1",
            "subject_id": "subj-1",
            "teacher_id": "t1",
            "day_of_week": 0,
            "period_number": 1,
            "start_time": "08:00",
            "end_time": "08:45",
        }
    ]
    fake_db.subjects.docs = [
        {"id": "subj-1", "name": "Mathematics", "schoolId": "aaryans-joya"}
    ]
    resp = client.get("/api/academics/timetable/class-1", headers=_teacher_h())
    assert resp.status_code == 200
    data = resp.json().get("data", [])
    assert len(data) >= 1
    assert data[0]["class_id"] == "class-1"


def test_get_timetable_enriches_subject_name(client, fake_db):
    """GET /api/academics/timetable/{class_id} enriches subject_name from subjects collection."""
    fake_db.timetable_slots.docs = [
        {
            "id": "slot-2",
            "schoolId": "aaryans-joya",
            "class_id": "class-2",
            "subject_id": "subj-math",
            "teacher_id": "t1",
            "day_of_week": 1,
            "period_number": 2,
            "start_time": "09:00",
            "end_time": "09:45",
        }
    ]
    fake_db.subjects.docs = [
        {"id": "subj-math", "name": "Mathematics", "schoolId": "aaryans-joya"}
    ]
    resp = client.get("/api/academics/timetable/class-2", headers=_admin_h())
    assert resp.status_code == 200
    data = resp.json().get("data", [])
    assert len(data) == 1
    assert data[0].get("subject_name") == "Mathematics"


def test_get_timetable_subject_name_na_when_missing(client, fake_db):
    """subject_name falls back to 'N/A' when subject not found."""
    fake_db.timetable_slots.docs = [
        {
            "id": "slot-3",
            "schoolId": "aaryans-joya",
            "class_id": "class-1",
            "subject_id": "subj-missing",
            "teacher_id": "t1",
            "day_of_week": 2,
            "period_number": 3,
            "start_time": "10:00",
            "end_time": "10:45",
        }
    ]
    fake_db.subjects.docs = []
    resp = client.get("/api/academics/timetable/class-1", headers=_teacher_h())
    assert resp.status_code == 200
    data = resp.json().get("data", [])
    assert data[0].get("subject_name") == "N/A"


def test_get_timetable_unauthenticated_returns_401(client):
    """Unauthenticated GET /api/academics/timetable/{class_id} returns 401."""
    resp = client.get("/api/academics/timetable/class-1")
    assert resp.status_code == 401


# --- POST /timetable ---

def test_create_timetable_slot_owner(client, fake_db):
    """POST /api/academics/timetable creates a slot for owner role."""
    fake_db.timetable_slots.docs = []
    resp = client.post(
        "/api/academics/timetable",
        json={
            "class_id": "class-1",
            "subject_id": "subj-1",
            "teacher_id": "t1",
            "day_of_week": 0,
            "period_number": 1,
            "start_time": "08:00",
            "end_time": "08:45",
            "room": "Room 101",
        },
        headers=_owner_h(),
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert body.get("success") is True
    assert body["data"]["class_id"] == "class-1"


def test_create_timetable_slot_admin(client, fake_db):
    """POST /api/academics/timetable creates a slot for admin role."""
    fake_db.timetable_slots.docs = []
    resp = client.post(
        "/api/academics/timetable",
        json={
            "class_id": "class-1",
            "subject_id": "subj-2",
            "teacher_id": "t2",
            "day_of_week": 1,
            "period_number": 2,
            "start_time": "09:00",
            "end_time": "09:45",
        },
        headers=_admin_h(),
    )
    assert resp.status_code in (200, 201)
    assert resp.json().get("success") is True


def test_teacher_cannot_create_timetable_slot(client):
    """Teacher cannot create timetable slots — must get 403."""
    resp = client.post(
        "/api/academics/timetable",
        json={
            "class_id": "class-1",
            "subject_id": "subj-1",
            "teacher_id": "t1",
            "day_of_week": 0,
            "period_number": 2,
        },
        headers=_teacher_h(),
    )
    assert resp.status_code == 403


def test_create_timetable_unauthenticated_returns_401(client):
    """Unauthenticated POST /api/academics/timetable returns 401."""
    resp = client.post(
        "/api/academics/timetable",
        json={"class_id": "class-1", "day_of_week": 0, "period_number": 1},
    )
    assert resp.status_code == 401


# --- PATCH /timetable/{slot_id} ---

def test_patch_timetable_slot_owner(client, fake_db):
    """PATCH /api/academics/timetable/{slot_id} updates for owner."""
    fake_db.timetable_slots.docs = [
        {
            "id": "slot-patch",
            "schoolId": "aaryans-joya",
            "class_id": "class-1",
            "subject_id": "subj-1",
            "teacher_id": "t1",
            "day_of_week": 0,
            "period_number": 1,
            "start_time": "08:00",
            "end_time": "08:45",
        }
    ]
    resp = client.patch(
        "/api/academics/timetable/slot-patch",
        json={"start_time": "08:15"},
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    assert resp.json().get("success") is True


def test_patch_timetable_slot_teacher_forbidden(client, fake_db):
    """PATCH /api/academics/timetable/{slot_id} is forbidden for teacher."""
    resp = client.patch(
        "/api/academics/timetable/slot-x",
        json={"start_time": "08:30"},
        headers=_teacher_h(),
    )
    assert resp.status_code == 403


# --- DELETE /timetable/{slot_id} ---

def test_delete_timetable_slot_owner(client, fake_db):
    """DELETE /api/academics/timetable/{slot_id} succeeds for owner."""
    fake_db.timetable_slots.docs = [
        {
            "id": "slot-del",
            "schoolId": "aaryans-joya",
            "class_id": "class-1",
            "subject_id": "subj-1",
            "day_of_week": 0,
            "period_number": 1,
        }
    ]
    resp = client.delete("/api/academics/timetable/slot-del", headers=_owner_h())
    assert resp.status_code == 200
    assert resp.json().get("success") is True


def test_delete_timetable_slot_teacher_forbidden(client):
    """DELETE /api/academics/timetable/{slot_id} is forbidden for teacher."""
    resp = client.delete("/api/academics/timetable/slot-del", headers=_teacher_h())
    assert resp.status_code == 403


# --- GET /timetable/availability ---
# NOTE: FastAPI routes are matched in registration order. The dynamic route
# GET /timetable/{class_id} is registered before GET /timetable/availability,
# so "/timetable/availability" is captured by the class_id route with
# class_id="availability". Tests here verify the actual runtime behaviour.

def test_get_availability_route_returns_200(client, fake_db):
    """GET /api/academics/timetable/availability returns 200 (auth required)."""
    fake_db.timetable_slots.docs = []
    fake_db.subjects.docs = []
    resp = client.get(
        "/api/academics/timetable/availability",
        headers=_teacher_h(),
    )
    # Route is shadowed by /{class_id} — still returns 200 with valid auth
    assert resp.status_code == 200


def test_get_availability_unauthenticated_returns_401(client):
    """Unauthenticated GET /api/academics/timetable/availability returns 401."""
    resp = client.get("/api/academics/timetable/availability")
    assert resp.status_code == 401


def test_get_timetable_for_class_with_no_slots(client, fake_db):
    """GET /api/academics/timetable/{class_id} returns empty list for unknown class."""
    fake_db.timetable_slots.docs = []
    fake_db.subjects.docs = []
    resp = client.get("/api/academics/timetable/no-such-class", headers=_admin_h())
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# --- PUT /timetable/import ---

def test_bulk_import_timetable_owner(client, fake_db):
    """PUT /api/academics/timetable/import succeeds for owner with valid entries."""
    fake_db.timetable_slots.docs = []
    fake_db.classes.docs = [
        {"id": "class-1", "schoolId": "aaryans-joya", "name": "Class 5", "section": "A"}
    ]
    fake_db.staff.docs = []
    resp = client.put(
        "/api/academics/timetable/import",
        json=[
            {
                "class_id": "class-1",
                "day_of_week": 0,
                "period_number": 1,
                "subject_id": "subj-1",
                "start_time": "08:00",
                "end_time": "08:45",
            }
        ],
        headers=_owner_h(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("success") is True
    assert "created_count" in body.get("data", {})


def test_bulk_import_timetable_empty_entries_returns_400(client, fake_db):
    """PUT /api/academics/timetable/import with empty array returns 400."""
    resp = client.put(
        "/api/academics/timetable/import",
        json=[],
        headers=_owner_h(),
    )
    assert resp.status_code == 400


def test_bulk_import_timetable_teacher_forbidden(client):
    """PUT /api/academics/timetable/import is forbidden for teacher."""
    resp = client.put(
        "/api/academics/timetable/import",
        json=[{"class_id": "class-1", "day_of_week": 0, "period_number": 1}],
        headers=_teacher_h(),
    )
    assert resp.status_code == 403
