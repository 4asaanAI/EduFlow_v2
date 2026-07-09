from __future__ import annotations

from types import SimpleNamespace

import pytest

from middleware.auth import create_jwt
import routes.image_gen as image_gen_routes


def _headers(role="owner", sub_category=None) -> dict:
    claims = {"user_id": "u-1", "role": role, "name": "Admin"}
    if sub_category:
        claims["sub_category"] = sub_category
    token = create_jwt(claims)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_image_gen_state(fake_db, monkeypatch):
    fake_db.file_uploads.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    fake_db.image_gen_quota.docs[:] = []
    # `fake_db` is a shared module singleton that other test files mutate; ensure
    # the student/class our DB-resolved cert & ID-card tests need are present
    # (non-destructive — R9.5 resolves identity from the DB, not the payload).
    if not any(s.get("id") == "student-1" for s in fake_db.students.docs):
        fake_db.students.docs.append({
            "id": "student-1", "schoolId": "aaryans-joya", "name": "Demo Student",
            "class_id": "class-1", "admission_number": "ADM1", "roll_number": "1",
            "is_active": True, "status": "active",
        })
    if not any(c.get("id") == "class-1" for c in fake_db.classes.docs):
        fake_db.classes.docs.append({
            "id": "class-1", "schoolId": "aaryans-joya", "name": "Class 5", "section": "A",
        })

    # R9.5 AC2: the Gemini/Imagen leg was removed — backgrounds are drawn locally.
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
    # R9.5 AC1: identity comes from the DB by student_id; client name/class are
    # ignored (kept here to prove they DON'T drive the output).
    payload = {"cert_type": "bonafide", "student_id": "student-1",
               "student_name": "IGNORED", "class": "IGNORED"}
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


def test_certificate_requires_student_id(client):
    # R9.5 AC1: no client-supplied identity — a missing student_id is a 400.
    resp = client.post("/api/image-gen/certificate",
                       json={"cert_type": "bonafide", "student_name": "Forged Name"},
                       headers=_headers())
    assert resp.status_code == 400


def test_certificate_unknown_student_is_404(client):
    resp = client.post("/api/image-gen/certificate",
                       json={"cert_type": "bonafide", "student_id": "no-such-student"},
                       headers=_headers())
    assert resp.status_code == 404


def test_certificate_denied_for_non_principal_admin(client):
    # R9.5 AC1: owner/principal only — an accountant admin can no longer mint certs.
    resp = client.post("/api/image-gen/certificate", json=_certificate_payload(),
                       headers=_headers(role="admin", sub_category="accountant"))
    assert resp.status_code == 403


def test_id_cards_persist_true_stores_pdf(client, fake_db):
    response = client.post(
        "/api/image-gen/id-cards",
        json={"persist": True, "class_id": "class-1", "students": [{"student_id": "student-1"}]},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert fake_db.file_uploads.docs[-1]["linked_table"] == "id_card"
    assert fake_db.audit_logs.docs[-1]["action"] == "id_card_generated"


def test_id_cards_requires_student_ids(client):
    resp = client.post("/api/image-gen/id-cards",
                       json={"students": [{"name": "Forged", "class": "5"}]},
                       headers=_headers())
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_daily_cap_blocks_over_limit(fake_db, monkeypatch):
    from routes import image_gen
    monkeypatch.setattr(image_gen, "DAILY_GEN_CAP", 2)
    ok1 = await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "certificate")
    ok2 = await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "certificate")
    ok3 = await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "certificate")
    assert ok1 and ok2 and not ok3
    # a different kind has its own counter
    assert await image_gen._enforce_daily_cap(fake_db, "aaryans-joya", "id_card")
