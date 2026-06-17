from __future__ import annotations
"""Tests: Exam management CRUD — permissions, teacher scope gate, PATCH/DELETE."""

import pytest
from middleware.auth import create_jwt

def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


_OWNER = _bearer({"user_id": "owner-1", "role": "owner", "name": "Owner"})
_PRINCIPAL = _bearer({"user_id": "p-1", "role": "admin", "name": "Principal", "sub_category": "principal"})
_MANAGEMENT = _bearer({"user_id": "mgmt-1", "role": "admin", "name": "Manager", "sub_category": "management"})
_ACCOUNTANT = _bearer({"user_id": "acc-1", "role": "admin", "name": "Accountant", "sub_category": "accountant"})
_TEACHER = _bearer({"user_id": "t-1", "role": "teacher", "name": "Teacher"})


class TestExamCreatePermissions:
    def test_unauthenticated_post_exams_returns_401(self, client):
        resp = client.post("/api/academics/exams", json={"name": "Test Exam"})
        assert resp.status_code == 401

    def test_accountant_admin_post_exams_returns_403(self, client):
        resp = client.post("/api/academics/exams", json={"name": "Test Exam"}, headers=_ACCOUNTANT)
        assert resp.status_code == 403

    def test_owner_can_create_exam(self, client, fake_db):
        _snapshot = list(fake_db.exams.docs)
        resp = client.post("/api/academics/exams", json={"name": "Final Term 2026", "exam_type": "final_term"}, headers=_OWNER)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Final Term 2026"
        fake_db.exams.docs[:] = _snapshot

    def test_principal_can_create_exam(self, client, fake_db):
        _snapshot = list(fake_db.exams.docs)
        resp = client.post("/api/academics/exams", json={"name": "Mid Term", "exam_type": "mid_term", "class_id": "class-1"}, headers=_PRINCIPAL)
        assert resp.status_code == 200
        assert resp.json()["data"]["class_id"] == "class-1"
        fake_db.exams.docs[:] = _snapshot

    def test_management_can_create_exam(self, client, fake_db):
        _snapshot = list(fake_db.exams.docs)
        resp = client.post("/api/academics/exams", json={"name": "Unit Test 1", "exam_type": "unit_test"}, headers=_MANAGEMENT)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        fake_db.exams.docs[:] = _snapshot

    def test_create_exam_missing_name_returns_400(self, client):
        resp = client.post("/api/academics/exams", json={"exam_type": "unit_test"}, headers=_PRINCIPAL)
        assert resp.status_code == 400


class TestExamCreateTeacherScope:
    def test_teacher_can_create_exam_for_assigned_class(self, client, fake_db, monkeypatch):
        import routes.academics as acad
        async def _mock_scope(db, user, school_id):
            return {"all_class_ids": ["class-1"], "class_teacher_class_ids": [], "subject_ids": [], "subjects": [], "classes": []}
        monkeypatch.setattr(acad, "compute_teacher_scope", _mock_scope)

        _snapshot = list(fake_db.exams.docs)
        resp = client.post(
            "/api/academics/exams",
            json={"name": "Class 5 Unit Test", "exam_type": "unit_test", "class_id": "class-1"},
            headers=_TEACHER,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["created_by"] == "t-1"
        fake_db.exams.docs[:] = _snapshot

    def test_teacher_cannot_create_exam_for_unassigned_class(self, client, fake_db, monkeypatch):
        import services.teacher_scope_service as tss
        async def _mock_scope(db, user, school_id):
            return {"all_class_ids": [], "class_teacher_class_ids": [], "subject_ids": [], "subjects": [], "classes": []}
        monkeypatch.setattr(tss, "compute_teacher_scope", _mock_scope)

        resp = client.post(
            "/api/academics/exams",
            json={"name": "Forbidden Exam", "exam_type": "unit_test", "class_id": "class-99"},
            headers=_TEACHER,
        )
        assert resp.status_code == 403

    def test_teacher_can_create_exam_without_class(self, client, fake_db, monkeypatch):
        import services.teacher_scope_service as tss
        async def _mock_scope(db, user, school_id):
            return {"all_class_ids": [], "class_teacher_class_ids": [], "subject_ids": [], "subjects": [], "classes": []}
        monkeypatch.setattr(tss, "compute_teacher_scope", _mock_scope)

        _snapshot = list(fake_db.exams.docs)
        resp = client.post("/api/academics/exams", json={"name": "Generic Exam"}, headers=_TEACHER)
        assert resp.status_code == 200
        fake_db.exams.docs[:] = _snapshot


class TestExamGet:
    def test_unauthenticated_get_exams_returns_401(self, client):
        resp = client.get("/api/academics/exams")
        assert resp.status_code == 401

    def test_owner_can_list_exams(self, client, fake_db):
        fake_db.exams.docs = [
            {"id": "exam-1", "schoolId": "aaryans-joya", "name": "Term 1", "exam_type": "mid_term", "created_at": "2026-01-01T00:00:00"}
        ]
        resp = client.get("/api/academics/exams", headers=_OWNER)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        fake_db.exams.docs = []

    def test_accountant_student_cannot_list_exams(self, client):
        student_headers = _bearer({"user_id": "s-1", "role": "student", "name": "Student"})
        resp = client.get("/api/academics/exams", headers=student_headers)
        assert resp.status_code == 403


class TestExamPatch:
    def test_unauthenticated_patch_returns_401(self, client):
        resp = client.patch("/api/academics/exams/exam-999", json={"name": "New Name"})
        assert resp.status_code == 401

    def test_accountant_patch_returns_403(self, client):
        resp = client.patch("/api/academics/exams/exam-999", json={"name": "X"}, headers=_ACCOUNTANT)
        assert resp.status_code == 403

    def test_patch_nonexistent_exam_returns_404(self, client, fake_db):
        fake_db.exams.docs = []
        resp = client.patch("/api/academics/exams/no-such-exam", json={"name": "X"}, headers=_OWNER)
        assert resp.status_code == 404

    def test_principal_can_patch_exam(self, client, fake_db):
        fake_db.exams.docs = [
            {"id": "exam-patch-1", "schoolId": "aaryans-joya", "_id": "exam-patch-1", "name": "Old Name", "exam_type": "unit_test", "created_by": "p-1", "created_at": "2026-01-01T00:00:00"}
        ]
        resp = client.patch("/api/academics/exams/exam-patch-1", json={"name": "New Name"}, headers=_PRINCIPAL)
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "New Name"
        fake_db.exams.docs = []

    def test_teacher_cannot_patch_other_teachers_exam(self, client, fake_db):
        fake_db.exams.docs = [
            {"id": "exam-other", "schoolId": "aaryans-joya", "_id": "exam-other", "name": "Other Exam", "exam_type": "unit_test", "created_by": "t-other", "created_at": "2026-01-01T00:00:00"}
        ]
        resp = client.patch("/api/academics/exams/exam-other", json={"name": "X"}, headers=_TEACHER)
        assert resp.status_code == 403
        fake_db.exams.docs = []


class TestExamDelete:
    def test_unauthenticated_delete_returns_401(self, client):
        resp = client.delete("/api/academics/exams/exam-999")
        assert resp.status_code == 401

    def test_teacher_cannot_delete_exam(self, client):
        resp = client.delete("/api/academics/exams/exam-999", headers=_TEACHER)
        assert resp.status_code == 403

    def test_accountant_cannot_delete_exam(self, client):
        resp = client.delete("/api/academics/exams/exam-999", headers=_ACCOUNTANT)
        assert resp.status_code == 403

    def test_delete_nonexistent_exam_returns_404(self, client, fake_db):
        fake_db.exams.docs = []
        resp = client.delete("/api/academics/exams/no-such-exam", headers=_PRINCIPAL)
        assert resp.status_code == 404

    def test_principal_can_delete_exam(self, client, fake_db):
        fake_db.exams.docs = [
            {"id": "exam-del-1", "schoolId": "aaryans-joya", "_id": "exam-del-1", "name": "To Delete", "exam_type": "unit_test", "created_at": "2026-01-01T00:00:00"}
        ]
        resp = client.delete("/api/academics/exams/exam-del-1", headers=_PRINCIPAL)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert all(e["id"] != "exam-del-1" for e in fake_db.exams.docs)

    def test_owner_can_delete_exam(self, client, fake_db):
        fake_db.exams.docs = [
            {"id": "exam-del-2", "schoolId": "aaryans-joya", "_id": "exam-del-2", "name": "Owner Delete", "exam_type": "unit_test", "created_at": "2026-01-01T00:00:00"}
        ]
        resp = client.delete("/api/academics/exams/exam-del-2", headers=_OWNER)
        assert resp.status_code == 200
        fake_db.exams.docs = []
