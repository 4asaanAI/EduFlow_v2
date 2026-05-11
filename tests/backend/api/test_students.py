"""
API Tests: Students — EduFlow Backend

Tests for student CRUD endpoints under /api/students.
All endpoints require JWT authentication (admin or teacher role).
"""

import pytest


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
            "/api/students?class_name=Class+5",
            headers=auth_headers,
        )
        assert response.status_code in (200, 204)


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
        """Given an invalid ObjectId format, should return 422 or 400."""
        response = client.get(
            "/api/students/not-a-valid-id",
            headers=auth_headers,
        )
        assert response.status_code in (400, 422)


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
        assert result.get("name") == student_data["name"]

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
