from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from middleware.auth import create_jwt
import routes.upload as upload_routes
from server import app


def _headers(user_id: str, role: str) -> dict:
    token = create_jwt({"user_id": user_id, "role": role, "name": user_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_uploads(fake_db, monkeypatch):
    fake_db.file_uploads.docs[:] = []
    fake_db.orphaned_s3_keys.docs[:] = []
    monkeypatch.setattr(
        upload_routes,
        "upload_bytes",
        lambda **kwargs: SimpleNamespace(
            bucket="eduflow-test",
            key=kwargs["key"],
            etag="etag",
            sha256="sha",
            size_bytes=len(kwargs["content"]),
        ),
    )
    monkeypatch.setattr(upload_routes, "delete_object", lambda key: None)
    monkeypatch.setattr(upload_routes, "create_presigned_get_url", lambda key: f"https://signed.test/{key}")


def _post_upload(client, headers, filename: str, content: bytes):
    return client.post(
        "/api/uploads",
        data={"entity_type": "student", "entity_id": "student-1"},
        files={"file": (filename, content, "application/octet-stream")},
        headers=headers,
    )


def test_upload_rejects_disallowed_extension_for_student(client):
    response = _post_upload(client, _headers("student-1", "student"), "script.exe", b"MZ")

    assert response.status_code == 400


def test_upload_rejects_mismatched_magic_bytes(client):
    response = _post_upload(client, _headers("admin-1", "owner"), "invoice.pdf", b"\x89PNG\r\n\x1a\nimage")

    assert response.status_code == 415


def test_upload_accepts_bom_prefixed_pdf_and_school_scoped_s3_key(client, fake_db):
    response = _post_upload(client, _headers("teacher-1", "teacher"), "lesson.pdf", b"\xef\xbb\xbf%PDF-1.4\n")

    assert response.status_code == 200
    record = fake_db.file_uploads.docs[-1]
    assert record["schoolId"] == "aaryans-joya"
    assert record["s3_key"].startswith("aaryans-joya/uploads/")


def test_upload_documents_double_extension_limitation(client):
    response = _post_upload(client, _headers("admin-1", "owner"), "malware.exe.pdf", b"%PDF-1.4\n")

    assert response.status_code == 200


def test_role_size_limit_rejects_student_but_accepts_teacher(client, monkeypatch):
    monkeypatch.setattr(
        upload_routes,
        "MAX_SIZE_BY_ROLE",
        {"owner": 200, "admin": 200, "teacher": 200, "student": 50},
    )
    content = b"%PDF-1.4\n" + (b"0" * 100)  # 109 bytes — over student 50B, under teacher 200B

    student_response = _post_upload(client, _headers("student-1", "student"), "large.pdf", content)
    teacher_response = _post_upload(client, _headers("teacher-1", "teacher"), "large.pdf", content)

    assert student_response.status_code == 400
    assert "student upload limit" in student_response.json()["detail"]
    assert teacher_response.status_code == 200


def test_serve_file_requires_auth_allows_owner_and_denies_other_student(client, fake_db):
    fake_db.file_uploads.docs[:] = [
        {
            "_id": "upload-1",
            "id": "upload-1",
            "schoolId": "aaryans-joya",
            "uploaded_by": "student-1",
            "safe_filename": "owned.pdf",
            "s3_key": "aaryans-joya/uploads/upload-1/upload-1.pdf",
        }
    ]

    unauthenticated = client.get("/api/uploads/serve/owned.pdf", follow_redirects=False)
    owner = client.get("/api/uploads/serve/owned.pdf", headers=_headers("student-1", "student"), follow_redirects=False)
    other_student = client.get(
        "/api/uploads/serve/owned.pdf",
        headers=_headers("student-2", "student"),
        follow_redirects=False,
    )
    admin = client.get("/api/uploads/serve/owned.pdf", headers=_headers("admin-1", "owner"), follow_redirects=False)

    assert unauthenticated.status_code == 401
    assert owner.status_code == 307
    assert other_student.status_code == 403
    assert admin.status_code == 307


def test_list_uploads_is_school_scoped_and_paginated(client, fake_db):
    fake_db.file_uploads.docs[:] = [
        {"id": f"a-{i}", "schoolId": "aaryans-joya", "uploaded_by": "student-1", "created_at": f"2026-01-{i:02d}"}
        for i in range(1, 4)
    ] + [
        {"id": "other", "schoolId": "other-school", "uploaded_by": "student-1", "created_at": "2026-02-01"}
    ]

    admin = client.get("/api/uploads?page=2&limit=2", headers=_headers("admin-1", "owner"))
    student = client.get("/api/uploads", headers=_headers("student-1", "student"))

    assert admin.status_code == 200
    body = admin.json()
    assert body["meta"] == {"total": 3, "page": 2, "limit": 2, "has_more": False}
    assert [item["id"] for item in body["data"]] == ["a-1"]
    assert student.status_code == 200
    assert {item["id"] for item in student.json()["data"]} == {"a-1", "a-2", "a-3"}


def test_delete_file_is_school_scoped_and_uses_stored_legacy_key(client, fake_db, monkeypatch):
    deleted = []
    monkeypatch.setattr(upload_routes, "delete_object", lambda key: deleted.append(key))
    fake_db.file_uploads.docs[:] = [
        {
            "id": "legacy",
            "schoolId": "aaryans-joya",
            "uploaded_by": "student-1",
            "s3_key": "uploads/legacy/legacy.pdf",
        },
        {
            "id": "foreign",
            "schoolId": "other-school",
            "uploaded_by": "student-1",
            "s3_key": "other-school/uploads/foreign/foreign.pdf",
        },
    ]

    deleted_response = client.delete("/api/uploads/legacy", headers=_headers("admin-1", "owner"))
    foreign_response = client.delete("/api/uploads/foreign", headers=_headers("admin-1", "owner"))

    assert deleted_response.status_code == 200
    assert foreign_response.status_code == 404
    assert deleted == ["uploads/legacy/legacy.pdf"]


def test_delete_file_denies_different_non_admin_user(client, fake_db):
    fake_db.file_uploads.docs[:] = [
        {"id": "upload-1", "schoolId": "aaryans-joya", "uploaded_by": "student-1", "s3_key": "uploads/u/u.pdf"}
    ]

    response = client.delete("/api/uploads/upload-1", headers=_headers("student-2", "student"))

    assert response.status_code == 403


def test_upload_insert_and_delete_double_failure_records_orphan(fake_db, monkeypatch):
    async def fail_insert(_record):
        raise RuntimeError("insert failed")

    def fail_delete(_key):
        raise RuntimeError("delete failed")

    monkeypatch.setattr(fake_db.file_uploads, "insert_one", fail_insert)
    monkeypatch.setattr(upload_routes, "delete_object", fail_delete)

    with TestClient(app, raise_server_exceptions=False) as failing_client:
        response = _post_upload(failing_client, _headers("admin-1", "owner"), "orphan.pdf", b"%PDF-1.4\n")

    assert response.status_code == 500
    assert fake_db.orphaned_s3_keys.docs[-1]["reason"] == "insert_failed_delete_failed"
    assert fake_db.orphaned_s3_keys.docs[-1]["s3_key"].startswith("aaryans-joya/uploads/")
