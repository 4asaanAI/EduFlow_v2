from __future__ import annotations

import pytest

from middleware.auth import create_jwt
from tests.backend.factories import make_class, make_staff, make_student

def _headers(user_id: str, role: str, sub_category: str | None = None):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": "branch-a"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "guardians", "students", "classes", "staff", "subjects", "student_attendance",
        "exam_results", "fee_transactions", "assignments", "student_leave_requests",
        "library_loans", "announcements", "quizzes", "quiz_attempts",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


def test_guardian_dashboard_is_horizontally_scoped(client, fake_db):
    fake_db.students.docs.extend([
        make_student(id="ward-a", class_id="class-a", branch_id="branch-a", name="Ward A"),
        make_student(id="ward-b", class_id="class-b", branch_id="branch-a", name="Ward B"),
    ])
    fake_db.guardians.docs.extend([
        {"id": "g-a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-a", "user_id": "parent-a", "relation": "Mother"},
        {"id": "g-b", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-b", "user_id": "parent-b", "relation": "Father"},
    ])
    fake_db.student_attendance.docs.extend([
        {"id": "att-a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-a", "date": "2099-01-01", "status": "present"},
        {"id": "att-b", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-b", "date": "2099-01-01", "status": "absent"},
    ])
    fake_db.fee_transactions.docs.extend([
        {"id": "fee-a", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-a", "amount": 1000, "paid_amount": 0, "status": "pending"},
        {"id": "fee-b", "schoolId": "aaryans-joya", "branch_id": "branch-a", "student_id": "ward-b", "amount": 5000, "paid_amount": 0, "status": "pending"},
    ])
    headers = _headers("parent-a", "parent")
    wards = client.get("/api/guardian/wards", headers=headers)
    assert wards.status_code == 200
    assert [row["id"] for row in wards.json()["data"]] == ["ward-a"]
    dashboard = client.get("/api/guardian/wards/ward-a/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["student"]["name"] == "Ward A"
    assert [row["id"] for row in dashboard.json()["data"]["fees"]["transactions"]] == ["fee-a"]
    assert client.get("/api/guardian/wards/ward-b/dashboard", headers=headers).status_code == 403


def test_quiz_authoring_hides_answers_and_server_grades_attempt(client, fake_db):
    teacher = _headers("teacher-user", "teacher")
    student = _headers("student-user", "student")
    fake_db.staff.docs.append(make_staff(id="teacher-staff", user_id="teacher-user", branch_id="branch-a"))
    class_doc = make_class(id="class-a", branch_id="branch-a")
    class_doc["class_teacher_id"] = "teacher-staff"
    fake_db.classes.docs.append(class_doc)
    fake_db.students.docs.append(make_student(
        id="student-a", user_id="student-user", class_id="class-a", branch_id="branch-a"
    ))
    created = client.post("/api/quizzes", headers=teacher, json={
        "title": "Fractions check", "class_id": "class-a", "duration_minutes": 10,
        "questions": [
            {"prompt": "Half of 10?", "options": ["2", "5", "10"], "correct_option": 1, "points": 2},
            {"prompt": "Quarter of 8?", "options": ["2", "4"], "correct_option": 0, "points": 1},
        ],
    })
    assert created.status_code == 200
    quiz_id = created.json()["data"]["id"]
    questions = created.json()["data"]["questions"]
    assert client.patch(f"/api/quizzes/{quiz_id}/publish", headers=teacher).status_code == 200
    listing = client.get("/api/quizzes", headers=student)
    assert listing.status_code == 200
    assert "questions" not in listing.json()["data"][0]
    attempt = client.post(f"/api/quizzes/{quiz_id}/attempts", headers=student)
    assert attempt.status_code == 200
    attempt_data = attempt.json()["data"]
    assert all("correct_option" not in question for question in attempt_data["quiz"]["questions"])
    answers = {questions[0]["id"]: 1, questions[1]["id"]: 1}
    submitted = client.post(
        f"/api/quizzes/attempts/{attempt_data['id']}/submit", headers=student,
        json={"answers": answers},
    )
    assert submitted.status_code == 200
    assert submitted.json()["data"]["score"] == 2
    assert submitted.json()["data"]["percentage"] == pytest.approx(66.67)
    assert client.post(f"/api/quizzes/{quiz_id}/attempts", headers=student).status_code == 409


def test_quiz_rejects_unassigned_teacher_and_cross_student_submission(client, fake_db):
    fake_db.staff.docs.append(make_staff(id="teacher-staff", user_id="teacher-user", branch_id="branch-a"))
    fake_db.classes.docs.append(make_class(id="class-a", branch_id="branch-a"))
    denied = client.post("/api/quizzes", headers=_headers("teacher-user", "teacher"), json={
        "title": "Unauthorized", "class_id": "class-a",
        "questions": [{"prompt": "Q", "options": ["A", "B"], "correct_option": 0}],
    })
    assert denied.status_code == 403
    fake_db.students.docs.extend([
        make_student(id="student-a", user_id="student-a-user", class_id="class-a", branch_id="branch-a"),
        make_student(id="student-b", user_id="student-b-user", class_id="class-a", branch_id="branch-a"),
    ])
    fake_db.quiz_attempts.docs.append({
        "id": "attempt-a", "schoolId": "aaryans-joya", "branch_id": "branch-a",
        "quiz_id": "quiz-a", "student_id": "student-a", "student_user_id": "student-a-user",
        "status": "in_progress",
    })
    assert client.post(
        "/api/quizzes/attempts/attempt-a/submit", headers=_headers("student-b-user", "student"),
        json={"answers": {}},
    ).status_code == 404


@pytest.mark.parametrize("path", ["/api/guardian/wards", "/api/quizzes"])
def test_guardian_and_quiz_surfaces_require_authentication(client, path):
    assert client.get(path).status_code == 401
