"""UI Sweep — D-37: minting a generated file's download link at request time.

`GET /api/uploads/link/{file_id}` exchanges the short opaque id Flo now writes into a
chat message for a FRESH presigned URL. The signed URL never travels through the model,
so it can never be corrupted in transcription or served stale — the two ways D-37 and
Story 10.3's expiry problem failed.

The tests that matter most: the endpoint is authenticated, it refuses a file the caller
is not entitled to, and a missing file comes back as our own JSON — never as S3's raw
XML with the school's bucket and account number on screen.
"""
from __future__ import annotations

import pytest

from middleware.auth import create_jwt

pytestmark = pytest.mark.asyncio

SCHOOL = "aaryans-joya"


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _owner():
    return _bearer({"user_id": "d-owner", "role": "owner", "name": "Owner"})


def _principal():
    return _bearer({"user_id": "d-prin", "role": "admin", "sub_category": "principal", "name": "Principal"})


def _teacher():
    return _bearer({"user_id": "d-teach", "role": "teacher", "branch_id": "branch-a", "name": "Teacher"})


def _student():
    return _bearer({"user_id": "d-stu", "role": "student", "name": "Student"})


def _url(file_id: str) -> str:
    return f"/api/uploads/link/{file_id}"


@pytest.fixture(autouse=True)
def _clean_uploads(fake_db):
    saved = list(fake_db.file_uploads.docs)
    fake_db.file_uploads.docs[:] = []
    yield
    fake_db.file_uploads.docs[:] = saved


@pytest.fixture(autouse=True)
def _fake_presign(monkeypatch):
    """A fresh URL each mint, tagged with the key so tests can prove it was minted
    from the stored object and not carried from anywhere."""
    import routes.upload as upload

    monkeypatch.setattr(
        upload, "create_presigned_get_url",
        lambda key, **kw: f"https://s3.example/{key}?signed=fresh",
    )


def _put(fake_db, *, file_id: str, uploaded_by: str, school: str = SCHOOL, s3_key: str | None = "x"):
    record = {
        "id": file_id,
        "_id": file_id,
        "schoolId": school,
        "uploaded_by": uploaded_by,
        "file_name": f"{file_id}.docx",
        "safe_filename": f"{file_id}.docx",
        "file_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "file_size_kb": 14,
        "generated": True,
    }
    if s3_key is not None:
        record["s3_key"] = f"{school}/uploads/{file_id}/{s3_key}.docx"
    fake_db.file_uploads.docs.append(record)


# ── Authentication and entitlement ───────────────────────────────────────────────

def test_unauthenticated_cannot_get_a_link(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="d-owner")
    resp = client.get(_url("f1"))
    assert resp.status_code == 401


def test_a_user_cannot_get_a_file_they_do_not_own(client, fake_db):
    """A teacher who is neither the uploader nor a principal is refused — the existing
    file-access permission, no new one."""
    _put(fake_db, file_id="f1", uploaded_by="d-owner")
    resp = client.get(_url("f1"), headers=_teacher())
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Forbidden"


def test_a_student_cannot_get_someone_elses_file(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="d-owner")
    resp = client.get(_url("f1"), headers=_student())
    assert resp.status_code == 403


def test_the_uploader_gets_a_fresh_link(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="d-owner")
    resp = client.get(_url("f1"), headers=_owner())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["download_url"] == "https://s3.example/aaryans-joya/uploads/f1/x.docx?signed=fresh"
    assert data["expires_in_seconds"] > 0
    assert data["file_name"] == "f1.docx"


def test_owner_can_get_any_file_in_the_school(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="d-teach")
    resp = client.get(_url("f1"), headers=_owner())
    assert resp.status_code == 200


def test_principal_can_get_any_file_in_the_school(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="d-teach")
    resp = client.get(_url("f1"), headers=_principal())
    assert resp.status_code == 200


# ── The link is minted fresh, not stored ──────────────────────────────────────────

def test_the_link_is_minted_fresh_at_request_time(client, fake_db, monkeypatch):
    """The whole fix: the URL is signed when the person taps, from the stored key."""
    import routes.upload as upload

    calls = []
    monkeypatch.setattr(
        upload, "create_presigned_get_url",
        lambda key, **kw: (calls.append(key), f"https://s3.example/{key}?signed=fresh")[1],
    )
    _put(fake_db, file_id="f1", uploaded_by="d-owner")
    client.get(_url("f1"), headers=_owner())
    assert calls == ["aaryans-joya/uploads/f1/x.docx"]


# ── Failures are honest, never raw S3 XML ─────────────────────────────────────────

def test_a_missing_file_is_a_plain_not_found_not_xml(client, fake_db):
    """Story 10.3: a dead file must be answered in words, not as S3 XML carrying the
    school's bucket name and account number."""
    resp = client.get(_url("does-not-exist"), headers=_owner())
    assert resp.status_code == 404
    body = resp.json()
    assert "ask for it again" in body["detail"].lower()
    assert "<?xml" not in resp.text
    assert "<Error>" not in resp.text


def test_a_file_from_another_school_is_not_found(client, fake_db):
    """Tenant isolation: an id that exists under a different school is invisible here."""
    _put(fake_db, file_id="f1", uploaded_by="d-owner", school="other-school")
    resp = client.get(_url("f1"), headers=_owner())
    assert resp.status_code == 404


def test_a_file_not_yet_in_s3_says_so(client, fake_db):
    _put(fake_db, file_id="f1", uploaded_by="d-owner", s3_key=None)
    resp = client.get(_url("f1"), headers=_owner())
    assert resp.status_code == 409
