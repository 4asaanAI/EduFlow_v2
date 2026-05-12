"""
API Tests: Students — EduFlow Backend

Tests for student CRUD endpoints under /api/students.
All endpoints require JWT authentication (admin or teacher role).
"""

import pytest
from types import SimpleNamespace


class TestGetStudents:
    """GET /api/students"""

    def test_get_students_authenticated(self, client, auth_headers):
        """Given a valid token, should return list of students."""
        response = client.get("/api/students", headers=auth_headers)

        # Accept 200 (data) or 204 (empty)
        assert response.status_code in (200, 204)
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_get_students_unauthenticated(self, client):
        """Without token, should return 401."""
        response = client.get("/api/students")
        assert response.status_code == 401

    def test_get_students_filter_by_class(self, client, auth_headers):
        """Filtering by class should work without error."""
        response = client.get(
            "/api/students?class_id=class-1",
            headers=auth_headers,
        )
        assert response.status_code in (200, 204)

    def test_list_excludes_inactive_by_default(self, client, auth_headers, student_data):
        create = client.post("/api/students", json=student_data, headers=auth_headers)
        student_id = create.json()["data"]["id"]
        delete = client.delete(f"/api/students/{student_id}", headers=auth_headers)
        assert delete.status_code == 200

        default_list = client.get("/api/students", headers=auth_headers).json()
        assert student_id not in [student["id"] for student in default_list["data"]]

        inactive_list = client.get("/api/students?include_inactive=true", headers=auth_headers).json()
        assert student_id in [student["id"] for student in inactive_list["data"]]

    def test_list_paginates_at_twenty(self, client, auth_headers):
        response = client.get("/api/students?limit=200&sort=name", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["per_page"] == 20
        assert len(data["data"]) <= 20


class TestGetStudentById:
    """GET /api/students/{student_id}"""

    def test_get_nonexistent_student(self, client, auth_headers):
        """Given a fake ObjectId, should return 404."""
        response = client.get(
            "/api/students/000000000000000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_get_student_invalid_id_format(self, client, auth_headers):
        """Given an invalid/nonexistent id, should return a client error."""
        response = client.get(
            "/api/students/not-a-valid-id",
            headers=auth_headers,
        )
        assert response.status_code in (400, 404, 422)


class TestCreateStudent:
    """POST /api/students"""

    def test_create_student_valid_data(self, client, auth_headers, student_data):
        """Given valid student data, should create and return the new student."""
        response = client.post(
            "/api/students",
            json=student_data,
            headers=auth_headers,
        )

        # May return 201 Created or 200 OK depending on implementation
        assert response.status_code in (200, 201)
        result = response.json()
        assert result.get("data", result).get("name") == student_data["name"]

    def test_create_student_missing_required_fields(self, client, auth_headers):
        """Given incomplete data, should return 422."""
        response = client.post(
            "/api/students",
            json={"name": "Incomplete Student"},  # missing required fields
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_create_student_unauthenticated(self, client, student_data):
        """Without token, should return 401."""
        response = client.post("/api/students", json=student_data)
        assert response.status_code == 401

    def test_create_student_rejects_non_current_class(self, client, auth_headers, student_data, fake_db):
        fake_db.classes.docs.append({"id": "old-class", "schoolId": "aaryans-joya", "academic_year_id": "old-year", "name": "Old", "section": "A"})
        payload = {**student_data, "class_id": "old-class"}
        response = client.post("/api/students", json=payload, headers=auth_headers)
        assert response.status_code == 400


class TestUpdateStudent:
    """PATCH /api/students/{student_id}"""

    def test_update_student_logs_field_changes(self, client, auth_headers, student_data, fake_db):
        create = client.post("/api/students", json=student_data, headers=auth_headers)
        student_id = create.json()["data"]["id"]

        response = client.patch(
            f"/api/students/{student_id}",
            json={"name": "Updated Student", "roll_number": "R-500"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["data"]["name"] == "Updated Student"
        audits = [a for a in fake_db.audit_logs.docs if a["entity_id"] == student_id and a["action"] == "update"]
        assert audits
        assert audits[-1]["changes"]["name"]["previous"] == student_data["name"]
        assert audits[-1]["changes"]["name"]["new"] == "Updated Student"


class TestStudentPhoto:
    """POST /api/students/{student_id}/photo"""

    def test_upload_student_photo_uses_s3_and_updates_profile(self, client, auth_headers, student_data, fake_db, monkeypatch):
        import routes.students as student_routes

        create = client.post("/api/students", json=student_data, headers=auth_headers)
        student_id = create.json()["data"]["id"]

        monkeypatch.setattr(
            student_routes,
            "upload_bytes",
            lambda **_kwargs: SimpleNamespace(bucket="test-bucket", key="uploads/photo.png", etag="etag", sha256="abc", size_bytes=10),
        )
        monkeypatch.setattr(student_routes, "create_presigned_get_url", lambda _key: "https://signed.example/photo.png")

        response = client.post(
            f"/api/students/{student_id}/photo",
            files={"file": ("photo.png", b"fake-image", "image/png")},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json()["data"]["photo_url"].startswith("/api/uploads/serve/")
        student = next(s for s in fake_db.students.docs if s["id"] == student_id)
        assert student["photo_url"].startswith("/api/uploads/serve/")
        assert fake_db.file_uploads.docs[-1]["storage"] == "s3"


class TestEraseStudent:
    """POST /api/students/{student_id}/erase"""

    def test_erase_student_requires_reason(self, client, auth_headers, student_data):
        create = client.post("/api/students", json=student_data, headers=auth_headers)
        student_id = create.json()["data"]["id"]

        response = client.post(f"/api/students/{student_id}/erase", data={"reason": "short"}, headers=auth_headers)

        assert response.status_code == 400

    def test_erase_student_removes_pii_and_pseudonymizes_attendance(self, client, auth_headers, student_data, fake_db):
        create = client.post("/api/students", json=student_data, headers=auth_headers)
        student_id = create.json()["data"]["id"]
        fake_db.student_attendance.docs.append({"id": "att-1", "schoolId": "aaryans-joya", "student_id": student_id, "student_name": student_data["name"]})

        response = client.post(
            f"/api/students/{student_id}/erase",
            data={"reason": "Parent submitted verified DPDP erasure request"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        token = response.json()["data"]["erasure_token"]
        assert not [s for s in fake_db.students.docs if s.get("id") == student_id]
        assert fake_db.student_attendance.docs[-1]["student_id"] == token
        assert fake_db.student_attendance.docs[-1]["student_name"] is None
