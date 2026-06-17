from __future__ import annotations
from middleware.auth import create_jwt


def _h(payload):
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner_h():
    return _h({"user_id": "o1", "role": "owner", "name": "Owner"})


def _principal_h():
    return _h({"user_id": "p1", "role": "admin", "name": "Principal", "sub_category": "principal"})


def _teacher_h(uid="t1"):
    return _h({"user_id": uid, "role": "teacher", "name": "Teacher"})


def _student_h():
    return _h({"user_id": "stu-u1", "role": "student", "name": "Pupil"})


def _seed(fake_db, *, class_teacher_id=None):
    """One exam + one class with two subjects (math→t1, science→t2) and two students."""
    fake_db.exams.docs = [
        {"id": "exam-1", "schoolId": "aaryans-joya", "name": "Unit Test 1", "class_id": "cls-1", "exam_type": "unit_test"},
    ]
    fake_db.classes.docs = [
        {"id": "cls-1", "schoolId": "aaryans-joya", "name": "Class 5", "section": "A", "class_teacher_id": class_teacher_id},
    ]
    fake_db.subjects.docs = [
        {"id": "sub-math", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Math", "teacher_id": "t1"},
        {"id": "sub-sci", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Science", "teacher_id": "t2"},
    ]
    fake_db.students.docs = [
        {"id": "s1", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Aarav", "roll_number": "1", "is_active": True},
        {"id": "s2", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Bina", "roll_number": "2", "is_active": True},
    ]
    fake_db.exam_subjects.docs = []
    fake_db.exam_results.docs = []


# ── Sheet auto-fetch ────────────────────────────────────────────────────────

def test_sheet_autofetches_subjects_and_students(client, fake_db):
    _seed(fake_db)
    resp = client.get("/api/academics/exams/exam-1/class/cls-1/sheet", headers=_principal_h())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert {s["name"] for s in data["subjects"]} == {"Math", "Science"}
    assert {s["name"] for s in data["students"]} == {"Aarav", "Bina"}
    # No schedule yet → defaults
    assert all(s["max_marks"] == 100 for s in data["subjects"])
    assert all(s["exam_date"] is None for s in data["subjects"])


def test_sheet_owner_is_view_only(client, fake_db):
    _seed(fake_db)
    resp = client.get("/api/academics/exams/exam-1/class/cls-1/sheet", headers=_owner_h())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_owner_view"] is True
    assert data["can_edit"] is False
    assert all(s["can_edit"] is False for s in data["subjects"])


def test_sheet_subject_teacher_can_only_edit_own_subject(client, fake_db):
    _seed(fake_db)
    resp = client.get("/api/academics/exams/exam-1/class/cls-1/sheet", headers=_teacher_h("t1"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    by_name = {s["name"]: s for s in data["subjects"]}
    assert by_name["Math"]["can_edit"] is True
    assert by_name["Science"]["can_edit"] is False
    assert data["can_edit"] is True


def test_sheet_class_teacher_can_edit_all_subjects(client, fake_db):
    _seed(fake_db, class_teacher_id="t1")
    resp = client.get("/api/academics/exams/exam-1/class/cls-1/sheet", headers=_teacher_h("t1"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(s["can_edit"] is True for s in data["subjects"])


def test_sheet_unknown_exam_404(client, fake_db):
    _seed(fake_db)
    resp = client.get("/api/academics/exams/nope/class/cls-1/sheet", headers=_principal_h())
    assert resp.status_code == 404


def test_sheet_unauthenticated_returns_401(client):
    resp = client.get("/api/academics/exams/exam-1/class/cls-1/sheet")
    assert resp.status_code == 401


def test_sheet_student_role_returns_403(client, fake_db):
    _seed(fake_db)
    resp = client.get("/api/academics/exams/exam-1/class/cls-1/sheet", headers=_student_h())
    assert resp.status_code == 403


# ── Schedule upsert ─────────────────────────────────────────────────────────

def test_schedule_principal_can_save_dates_and_max(client, fake_db):
    _seed(fake_db)
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={
        "subjects": [
            {"subject_id": "sub-math", "exam_date": "2026-07-01", "max_marks": 50},
            {"subject_id": "sub-sci", "exam_date": "2026-07-02", "max_marks": 80},
        ]
    }, headers=_principal_h())
    assert resp.status_code == 200
    assert resp.json()["data"]["saved"] == 2
    saved = {d["subject_id"]: d for d in fake_db.exam_subjects.docs}
    assert saved["sub-math"]["exam_date"] == "2026-07-01"
    assert saved["sub-math"]["max_marks"] == 50
    assert saved["sub-sci"]["max_marks"] == 80


def test_schedule_owner_forbidden(client, fake_db):
    _seed(fake_db)
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={
        "subjects": [{"subject_id": "sub-math", "exam_date": "2026-07-01", "max_marks": 50}]
    }, headers=_owner_h())
    assert resp.status_code == 403


def test_schedule_subject_teacher_can_save_own_subject(client, fake_db):
    _seed(fake_db)
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={
        "subjects": [{"subject_id": "sub-math", "exam_date": "2026-07-01", "max_marks": 50}]
    }, headers=_teacher_h("t1"))
    assert resp.status_code == 200
    assert resp.json()["data"]["saved"] == 1


def test_schedule_subject_teacher_blocked_on_other_subject(client, fake_db):
    _seed(fake_db)
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={
        "subjects": [{"subject_id": "sub-sci", "exam_date": "2026-07-01", "max_marks": 50}]
    }, headers=_teacher_h("t1"))
    assert resp.status_code == 403


def test_schedule_rejects_nonpositive_max(client, fake_db):
    _seed(fake_db)
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={
        "subjects": [{"subject_id": "sub-math", "max_marks": 0}]
    }, headers=_principal_h())
    assert resp.status_code == 400


def test_schedule_unauthenticated_returns_401(client):
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={"subjects": []})
    assert resp.status_code == 401


def test_schedule_student_role_returns_403(client, fake_db):
    _seed(fake_db)
    resp = client.put("/api/academics/exams/exam-1/class/cls-1/schedule", json={"subjects": []}, headers=_student_h())
    assert resp.status_code == 403
