from __future__ import annotations

import logging
import builtins
from types import SimpleNamespace

import pytest

from middleware.auth import create_jwt
import routes.image_gen as image_gen_routes

ORIGINAL_GEMINI_IMAGE = image_gen_routes._gemini_image


def _headers() -> dict:
    token = create_jwt({"user_id": "admin-1", "role": "owner", "name": "Admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_image_gen_state(fake_db, monkeypatch):
    fake_db.file_uploads.docs[:] = []
    fake_db.audit_logs.docs[:] = []

    async def no_background(*_args, **_kwargs):
        return None

    monkeypatch.setattr(image_gen_routes, "_gemini_image", no_background)
    monkeypatch.setattr(
        image_gen_routes,
        "upload_bytes",
        lambda **kwargs: SimpleNamespace(
            bucket="eduflow-test",
            key=kwargs["key"],
            etag="etag",
            sha256="sha",
            size_bytes=len(kwargs["content"]),
        ),
    )
    monkeypatch.setattr(image_gen_routes, "create_presigned_get_url", lambda key: f"https://signed.test/{key}")


def _certificate_payload(**overrides):
    payload = {
        "cert_type": "bonafide",
        "school_name": "The Aaryans",
        "student_name": "Demo Student",
        "student_id": "student-1",
        "class": "5",
        "academic_year": "2026-27",
    }
    payload.update(overrides)
    return payload


def test_certificate_persist_false_returns_binary_without_db_write(client, fake_db):
    response = client.post("/api/image-gen/certificate", json=_certificate_payload(), headers=_headers())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert fake_db.file_uploads.docs == []


def test_certificate_persist_true_stores_pdf_and_returns_json(client, fake_db):
    response = client.post(
        "/api/image-gen/certificate",
        json=_certificate_payload(persist=True),
        headers=_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["file_url"].startswith("https://signed.test/aaryans-joya/uploads/")
    assert body["expires_in"] == 3600
    assert fake_db.file_uploads.docs[-1]["linked_table"] == "certificate"
    assert fake_db.file_uploads.docs[-1]["linked_id"] == "student-1"
    assert fake_db.audit_logs.docs[-1]["action"] == "certificate_generated"


def test_id_cards_persist_true_stores_pdf(client, fake_db):
    response = client.post(
        "/api/image-gen/id-cards",
        json={
            "persist": True,
            "school_name": "The Aaryans",
            "academic_year": "2026-27",
            "class_id": "class-1",
            "students": [{"name": "Demo Student", "class": "5", "admission_number": "ADM1"}],
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert fake_db.file_uploads.docs[-1]["linked_table"] == "id_card"
    assert fake_db.audit_logs.docs[-1]["action"] == "id_card_generated"


@pytest.mark.asyncio
async def test_gemini_failure_logs_warning_and_falls_back(monkeypatch, caplog):
    monkeypatch.setattr(image_gen_routes, "GEMINI_API_KEY", "test-key")
    original_import = builtins.__import__

    def fail_google_import(name, *args, **kwargs):
        if name == "google":
            raise RuntimeError("gemini unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_google_import)
    caplog.set_level(logging.WARNING, logger=image_gen_routes.logger.name)

    result = await ORIGINAL_GEMINI_IMAGE("prompt")

    assert result is None
    assert "gemini_image_generation_failed" in caplog.text
