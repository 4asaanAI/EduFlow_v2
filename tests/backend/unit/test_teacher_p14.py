from __future__ import annotations
import pytest
from middleware.auth import create_jwt
from tests.backend.conftest import FakeCollection


def _teacher_h():
    t = create_jwt({"user_id": "t1", "role": "teacher", "name": "Teacher"})
    return {"Authorization": f"Bearer {t}"}


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _principal_h():
    t = create_jwt({"user_id": "p1", "role": "admin", "name": "Principal", "sub_category": "principal"})
    return {"Authorization": f"Bearer {t}"}


def test_bulk_results_marks_above_max_returns_partial(client, fake_db):
    """Bulk results with marks > max_marks returns partial success shape.

    Uses owner token so class-access check always passes, isolating the marks
    validation logic.
    """
    fake_db.exams.docs = [{"id": "exam-1", "schoolId": "aaryans-joya", "max_marks": 100, "class_id": "cls-1"}]
    fake_db.exam_results.docs = []
    fake_db.students.docs = [
        {"id": "s1", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Student One"},
        {"id": "s2", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Student Two"},
    ]
    resp = client.post("/api/academics/results/bulk", json={
        "results": [
            {"exam_id": "exam-1", "student_id": "s1", "marks_obtained": 85},   # valid
            {"exam_id": "exam-1", "student_id": "s2", "marks_obtained": 105},  # invalid
        ]
    }, headers=_owner_h())
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") == "partial"
    assert data.get("saved") == 1
    assert len(data.get("errors", [])) == 1


def test_bulk_results_all_invalid_returns_failure(client, fake_db):
    """All invalid rows returns success:False."""
    fake_db.exams.docs = [{"id": "exam-2", "schoolId": "aaryans-joya", "max_marks": 100}]
    fake_db.exam_results.docs = []
    resp = client.post("/api/academics/results/bulk", json={
        "results": [{"exam_id": "exam-2", "student_id": "s3", "marks_obtained": 200}]
    }, headers=_owner_h())
    assert resp.status_code == 200
    assert resp.json().get("success") is False


def test_bulk_results_all_valid_returns_success(client, fake_db):
    """All valid rows returns success:True with saved count."""
    fake_db.exams.docs = [{"id": "exam-3", "schoolId": "aaryans-joya", "max_marks": 100, "class_id": "cls-1"}]
    fake_db.exam_results.docs = []
    fake_db.students.docs = [
        {"id": "s4", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Student Four"},
    ]
    resp = client.post("/api/academics/results/bulk", json={
        "results": [{"exam_id": "exam-3", "student_id": "s4", "marks_obtained": 75}]
    }, headers=_owner_h())
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True
    assert data.get("data", {}).get("saved") == 1


def test_bulk_results_preserves_zero_and_stable_result_id(client, fake_db):
    fake_db.exams.docs = [{"id": "exam-zero", "schoolId": "aaryans-joya", "max_marks": 100, "class_id": "cls-1"}]
    fake_db.students.docs = [{"id": "s-zero", "schoolId": "aaryans-joya", "class_id": "cls-1", "name": "Student"}]
    fake_db.exam_results.docs = [{
        "id": "result-stable", "schoolId": "aaryans-joya", "exam_id": "exam-zero",
        "student_id": "s-zero", "subject_id": None, "marks_obtained": 20,
        "max_marks": 100, "published": False, "created_at": "2026-01-01T00:00:00",
    }]

    resp = client.post("/api/academics/results/bulk", json={"results": [{
        "exam_id": "exam-zero", "student_id": "s-zero", "marks_obtained": 0,
    }]}, headers=_owner_h())

    assert resp.status_code == 200
    stored = fake_db.exam_results.docs[0]
    assert stored["id"] == "result-stable"
    assert stored["marks_obtained"] == 0
    assert stored["created_at"] == "2026-01-01T00:00:00"


def test_bulk_results_rejects_unknown_student(client, fake_db):
    fake_db.exams.docs = [{"id": "exam-unknown", "schoolId": "aaryans-joya", "class_id": "cls-1", "max_marks": 100}]
    fake_db.students.docs = []
    fake_db.exam_results.docs = []

    resp = client.post("/api/academics/results/bulk", json={"results": [{
        "exam_id": "exam-unknown", "student_id": "missing", "marks_obtained": 50,
    }]}, headers=_owner_h())

    assert resp.json()["success"] is False
    assert resp.json()["errors"][0]["reason"] == "Student not found"
    assert fake_db.exam_results.docs == []


def test_bulk_results_locks_published_rows(client, fake_db):
    fake_db.exams.docs = [{"id": "exam-pub", "schoolId": "aaryans-joya", "class_id": "cls-1", "max_marks": 100}]
    fake_db.students.docs = [{"id": "s-pub", "schoolId": "aaryans-joya", "class_id": "cls-1"}]
    fake_db.exam_results.docs = [{
        "id": "result-pub", "schoolId": "aaryans-joya", "exam_id": "exam-pub",
        "student_id": "s-pub", "subject_id": None, "marks_obtained": 70,
        "max_marks": 100, "published": True, "is_published": True,
    }]

    resp = client.post("/api/academics/results/bulk", json={"results": [{
        "exam_id": "exam-pub", "student_id": "s-pub", "marks_obtained": 90,
    }]}, headers=_owner_h())

    assert resp.json()["success"] is False
    assert "correction workflow" in resp.json()["errors"][0]["reason"]
    assert fake_db.exam_results.docs[0]["marks_obtained"] == 70


def test_publish_result_endpoint_accessible_to_principal(client, fake_db):
    """Principal can publish exam results."""
    fake_db.exam_results.docs = [{"id": "res-1", "schoolId": "aaryans-joya", "is_published": False}]
    resp = client.patch("/api/academics/results/res-1/publish", headers=_principal_h())
    assert resp.status_code == 200
    assert resp.json().get("success") is True


def test_publish_result_not_found_returns_404(client, fake_db):
    """Publish endpoint returns 404 for unknown result_id."""
    fake_db.exam_results.docs = []
    resp = client.patch("/api/academics/results/nonexistent-result/publish", headers=_principal_h())
    assert resp.status_code == 404


def test_principal_correction_preserves_history_and_publication(client, fake_db):
    fake_db.exam_results.docs = [{
        "id": "res-correct", "schoolId": "aaryans-joya", "marks_obtained": 62,
        "max_marks": 100, "grade": "B", "remarks": "Initial", "published": True,
        "is_published": True,
    }]
    fake_db.exam_result_corrections.docs = []

    resp = client.patch("/api/academics/results/res-correct/correct", json={
        "marks_obtained": 72, "reason": "Verified totaling error",
    }, headers=_principal_h())

    assert resp.status_code == 200
    assert fake_db.exam_results.docs[0]["marks_obtained"] == 72
    assert fake_db.exam_results.docs[0]["published"] is True
    assert fake_db.exam_result_corrections.docs[0]["before"]["marks_obtained"] == 62
    assert fake_db.exam_result_corrections.docs[0]["after"]["marks_obtained"] == 72


def test_teacher_cannot_correct_published_result(client, fake_db):
    fake_db.exam_results.docs = [{"id": "res-locked", "schoolId": "aaryans-joya", "published": True}]
    resp = client.patch("/api/academics/results/res-locked/correct", json={
        "marks_obtained": 70, "reason": "Verified correction",
    }, headers=_teacher_h())
    assert resp.status_code == 403


def test_correct_result_unauthenticated_returns_401(client):
    resp = client.patch("/api/academics/results/res-locked/correct", json={
        "marks_obtained": 70, "reason": "Verified correction",
    })
    assert resp.status_code == 401


def test_question_papers_have_school_id(client, fake_db):
    """Question papers list endpoint is school-scoped (returns 200)."""
    fake_db.question_papers.docs = [
        {"id": "qp-1", "schoolId": "aaryans-joya", "teacher_id": "t1", "title": "Math Paper"},
    ]
    resp = client.get("/api/academics/question-papers", headers=_teacher_h())
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("success") is True


def test_question_papers_teacher_sees_only_own(client, fake_db):
    """Teacher only sees their own question papers."""
    fake_db.question_papers.docs = [
        {"id": "qp-2", "schoolId": "aaryans-joya", "teacher_id": "t1", "title": "My Paper"},
        {"id": "qp-3", "schoolId": "aaryans-joya", "teacher_id": "other-teacher", "title": "Other Paper"},
    ]
    resp = client.get("/api/academics/question-papers", headers=_teacher_h())
    assert resp.status_code == 200
    papers = resp.json().get("data", [])
    teacher_ids = {p.get("teacher_id") for p in papers}
    # Teacher t1 should not see other-teacher's papers
    assert "other-teacher" not in teacher_ids


def test_staff_me_route_accessible(client, fake_db):
    """GET /staff/me is accessible to teachers (routing order check)."""
    fake_db.staff.docs = []
    resp = client.get("/api/attendance/staff/me", headers=_teacher_h())
    # Should not 404 due to routing shadowing — staff/me must be before staff
    assert resp.status_code == 200
    assert resp.json().get("success") is True
