from __future__ import annotations

import pytest
from middleware.auth import create_jwt

SCHOOL = "aaryans-joya"

# The FakeDb is a session-wide singleton with no auto-reset. Snapshot every
# collection this module touches, clear it for the test, then restore the exact
# prior state on teardown — so seeded docs never leak into (or wipe state from)
# unrelated tests that share the same singleton.
_TOUCHED = ("classes", "subjects", "students", "exam_results", "student_attendance", "guardians")


@pytest.fixture(autouse=True)
def _isolate_collections(fake_db):
    snapshot = {coll: list(getattr(fake_db, coll).docs) for coll in _TOUCHED}
    for coll in _TOUCHED:
        getattr(fake_db, coll).docs = []
    yield
    for coll in _TOUCHED:
        getattr(fake_db, coll).docs = snapshot[coll]


def _teacher_h(uid="t1"):
    return {"Authorization": f"Bearer {create_jwt({'user_id': uid, 'role': 'teacher', 'name': 'Teacher'})}"}


def _student_h():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 's-user', 'role': 'student', 'name': 'Stu'})}"}


def _admin_h():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'p1', 'role': 'admin', 'name': 'Principal', 'sub_category': 'principal'})}"}


def _seed_structure(fake_db):
    """t1 is class teacher of cls-1 and teaches a subject in cls-2 (but is NOT its
    class teacher). cls-3 is unrelated to t1."""
    fake_db.classes.docs = [
        {"id": "cls-1", "schoolId": SCHOOL, "name": "9", "section": "A", "class_teacher_id": "t1"},
        {"id": "cls-2", "schoolId": SCHOOL, "name": "9", "section": "B", "class_teacher_id": "other"},
        {"id": "cls-3", "schoolId": SCHOOL, "name": "10", "section": "A", "class_teacher_id": "other"},
    ]
    fake_db.subjects.docs = [
        {"id": "sub-1", "schoolId": SCHOOL, "class_id": "cls-2", "name": "Science", "teacher_id": "t1"},
        {"id": "sub-2", "schoolId": SCHOOL, "class_id": "cls-3", "name": "Maths", "teacher_id": "other"},
    ]
    fake_db.students.docs = [
        {"id": "stu-1", "schoolId": SCHOOL, "class_id": "cls-1", "name": "A", "is_active": True},
        {"id": "stu-2", "schoolId": SCHOOL, "class_id": "cls-2", "name": "B", "is_active": True},
        {"id": "stu-3", "schoolId": SCHOOL, "class_id": "cls-3", "name": "C", "is_active": True},
    ]


# ── /my-teaching-scope ────────────────────────────────────────────────────

def test_scope_unauthenticated_returns_401(client):
    resp = client.get("/api/academics/my-teaching-scope")
    assert resp.status_code == 401


def test_scope_wrong_role_returns_403(client, fake_db):
    resp = client.get("/api/academics/my-teaching-scope", headers=_student_h())
    assert resp.status_code == 403


def test_scope_teacher_resolves_from_academic_structure(client, fake_db):
    _seed_structure(fake_db)
    resp = client.get("/api/academics/my-teaching-scope", headers=_teacher_h())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_teacher"] is True
    assert data["class_teacher_class_ids"] == ["cls-1"]
    assert data["subject_class_ids"] == ["cls-2"]
    assert sorted(data["all_class_ids"]) == ["cls-1", "cls-2"]
    assert data["subject_ids"] == ["sub-1"]
    assert {c["id"] for c in data["classes"]} == {"cls-1", "cls-2"}


def test_scope_admin_is_not_teacher(client, fake_db):
    _seed_structure(fake_db)
    resp = client.get("/api/academics/my-teaching-scope", headers=_admin_h())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_teacher"] is False
    assert data["all_class_ids"] == []


def test_scope_teacher_with_no_assignment_is_empty(client, fake_db):
    _seed_structure(fake_db)
    resp = client.get("/api/academics/my-teaching-scope", headers=_teacher_h("nobody"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_teacher"] is True
    assert data["all_class_ids"] == []


# ── Attendance is class-teacher-only ──────────────────────────────────────

def test_attendance_today_allowed_for_class_teacher(client, fake_db):
    _seed_structure(fake_db)
    fake_db.student_attendance.docs = []
    resp = client.get("/api/attendance/student/today/cls-1", headers=_teacher_h())
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_attendance_today_denied_for_subject_only_teacher(client, fake_db):
    """t1 teaches a subject in cls-2 but is not its class teacher → no attendance."""
    _seed_structure(fake_db)
    fake_db.student_attendance.docs = []
    resp = client.get("/api/attendance/student/today/cls-2", headers=_teacher_h())
    assert resp.status_code == 403


def test_attendance_today_denied_for_unrelated_class(client, fake_db):
    _seed_structure(fake_db)
    fake_db.student_attendance.docs = []
    resp = client.get("/api/attendance/student/today/cls-3", headers=_teacher_h())
    assert resp.status_code == 403


# ── Students list scoping ─────────────────────────────────────────────────

def test_students_list_scoped_to_assigned_classes(client, fake_db):
    _seed_structure(fake_db)
    fake_db.guardians.docs = []
    resp = client.get("/api/students/", headers=_teacher_h())
    assert resp.status_code == 200
    ids = {s["id"] for s in resp.json()["data"]}
    # cls-1 (class teacher) + cls-2 (subject) students, never cls-3.
    assert ids == {"stu-1", "stu-2"}


def test_students_list_blocks_out_of_scope_class_filter(client, fake_db):
    _seed_structure(fake_db)
    fake_db.guardians.docs = []
    resp = client.get("/api/students/?class_id=cls-3", headers=_teacher_h())
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_students_list_empty_for_unassigned_teacher(client, fake_db):
    _seed_structure(fake_db)
    fake_db.guardians.docs = []
    resp = client.get("/api/students/", headers=_teacher_h("nobody"))
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ── Results scoping ───────────────────────────────────────────────────────

def test_results_scoped_to_assigned_class_students(client, fake_db):
    _seed_structure(fake_db)
    fake_db.exam_results.docs = [
        {"id": "r1", "schoolId": SCHOOL, "student_id": "stu-1", "subject_id": "sub-1", "marks_obtained": 80},
        {"id": "r2", "schoolId": SCHOOL, "student_id": "stu-2", "subject_id": "sub-1", "marks_obtained": 70},
        {"id": "r3", "schoolId": SCHOOL, "student_id": "stu-3", "subject_id": "sub-2", "marks_obtained": 60},
    ]
    resp = client.get("/api/academics/results", headers=_teacher_h())
    assert resp.status_code == 200
    student_ids = {r["student_id"] for r in resp.json()["data"]}
    # stu-3 is in cls-3 (not assigned) → its result must not leak.
    assert student_ids == {"stu-1", "stu-2"}


def test_results_single_student_out_of_scope_forbidden(client, fake_db):
    _seed_structure(fake_db)
    fake_db.exam_results.docs = [
        {"id": "r3", "schoolId": SCHOOL, "student_id": "stu-3", "subject_id": "sub-2", "marks_obtained": 60},
    ]
    resp = client.get("/api/academics/results?student_id=stu-3", headers=_teacher_h())
    assert resp.status_code == 403
