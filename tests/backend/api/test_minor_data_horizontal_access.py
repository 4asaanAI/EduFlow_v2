from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_student

pytestmark = pytest.mark.asyncio


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


TEACHER = _bearer({"user_id": "teacher-scope-1", "role": "teacher", "name": "Teacher"})
STUDENT_A = _bearer({"user_id": "student-user-a", "role": "student", "name": "Student A", "branch_id": "branch-a"})


@pytest.fixture
def minor_records(fake_db):
    original_students = list(fake_db.students.docs)
    original_guardians = list(fake_db.guardians.docs)
    own = make_student(
        id="student-a",
        user_id="student-user-a",
        name="Student Alpha",
        class_id="class-a",
    )
    other = make_student(
        id="student-b",
        user_id="student-user-b",
        name="Student Beta",
        class_id="class-b",
    )
    fake_db.students.docs.extend([own, other])
    fake_db.guardians.docs.extend([
        {"id": "guardian-a", "schoolId": "aaryans-joya", "student_id": "student-a", "name": "Guardian Alpha"},
        {"id": "guardian-b", "schoolId": "aaryans-joya", "student_id": "student-b", "name": "Guardian Beta"},
    ])
    yield own, other
    fake_db.students.docs[:] = original_students
    fake_db.guardians.docs[:] = original_guardians


async def test_teacher_search_excludes_students_outside_assigned_classes(
    client, fake_db, minor_records, monkeypatch
):
    import routes.search as search_routes

    async def assigned_scope(db, user, school_id):
        return {"all_class_ids": ["class-a"]}

    monkeypatch.setattr(search_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(search_routes, "compute_teacher_scope", assigned_scope)

    response = client.get("/api/search?q=Student&type=students", headers=TEACHER)

    assert response.status_code == 200
    result_ids = {item.get("id") for item in response.json()["data"]}
    assert "student-a" in result_ids
    assert "student-b" not in result_ids


async def test_teacher_with_no_assignment_searches_no_students(
    client, fake_db, minor_records, monkeypatch
):
    import routes.search as search_routes

    async def empty_scope(db, user, school_id):
        return {"all_class_ids": []}

    monkeypatch.setattr(search_routes, "get_db", lambda: fake_db)
    monkeypatch.setattr(search_routes, "compute_teacher_scope", empty_scope)

    response = client.get("/api/search?q=Student&type=students", headers=TEACHER)

    assert response.status_code == 200
    assert response.json()["data"] == []


async def test_teacher_direct_student_read_requires_assigned_class(
    client, minor_records, monkeypatch
):
    import routes.students as student_routes

    async def assigned_scope(db, user, school_id):
        return {"all_class_ids": ["class-a"]}

    monkeypatch.setattr(student_routes, "compute_teacher_scope", assigned_scope)

    allowed = client.get("/api/students/student-a", headers=TEACHER)
    denied = client.get("/api/students/student-b", headers=TEACHER)

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Forbidden"}


async def test_student_can_read_only_own_guardians(client, minor_records):
    allowed = client.get("/api/students/student-a/guardians", headers=STUDENT_A)
    denied = client.get("/api/students/student-b/guardians", headers=STUDENT_A)

    assert allowed.status_code == 200
    assert [item["id"] for item in allowed.json()["data"]] == ["guardian-a"]
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Forbidden"}


async def test_student_can_read_only_own_fee_discounts(client, minor_records):
    allowed = client.get("/api/fees/discounts/student-a", headers=STUDENT_A)
    denied = client.get("/api/fees/discounts/student-b", headers=STUDENT_A)

    assert allowed.status_code == 200
    assert allowed.json()["data"]["student_id"] == "student-a"
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Forbidden"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/search?q=Student&type=students",
        "/api/students/student-a",
        "/api/students/student-a/guardians",
        "/api/fees/discounts/student-a",
    ],
)
async def test_protected_minor_read_paths_require_authentication(client, path):
    response = client.get(path)
    assert response.status_code == 401
