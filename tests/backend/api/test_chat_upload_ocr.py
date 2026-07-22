"""UI Sweep Epic 10, Story 10.5 — Flo reads a photographed page.

OCR runs at the UPLOAD boundary, so Flo receives ordinary text and the chat pipeline
needs no knowledge of images at all. These tests cover the access rule and the three
distinct outcomes (read / nothing to read / engine unavailable).
"""
from __future__ import annotations

import io

import pytest

from middleware.auth import create_jwt
from routes.chat_upload import may_read_images

pytestmark = pytest.mark.asyncio

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _upload(client, headers):
    return client.post(
        "/api/chat/upload",
        headers=headers,
        files={"file": ("form.png", io.BytesIO(PNG_1PX), "image/png")},
    )


@pytest.fixture(autouse=True)
def _clean(fake_db):
    saved = list(fake_db.audit_logs.docs)
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.audit_logs.docs[:] = saved


# ── Who may have Flo read a photograph ──────────────────────────────────────────

@pytest.mark.parametrize("user,allowed", [
    ({"role": "owner"}, True),
    ({"role": "admin", "sub_category": "principal"}, True),
    ({"role": "admin", "sub_category": "accountant"}, True),
    ({"role": "admin", "sub_category": "receptionist"}, True),
    ({"role": "admin", "sub_category": "transport_head"}, True),
    # Narrowed by the owner on 2026-07-22 AFTER an earlier draft included teachers.
    # Removed deliberately — this is paperwork handling, and it belongs to the office.
    ({"role": "teacher"}, False),
    ({"role": "student"}, False),
    ({}, False),
    (None, False),
])
def test_the_access_rule_is_owner_principal_and_office_staff(user, allowed):
    assert may_read_images(user) is allowed


def test_a_teacher_is_told_plainly_that_the_image_was_not_read(client):
    resp = _upload(client, _bearer({"user_id": "t1", "role": "teacher", "name": "T"}))

    assert resp.status_code == 200
    body = resp.json()
    assert "not read" in body["extracted_text"]
    assert "Owner, the Principal and office staff" in body["extracted_text"]
    # The bytes are not handed on to someone who may not use them.
    assert body["image_data"] is None


def test_a_student_cannot_have_an_image_read(client):
    resp = _upload(client, _bearer({"user_id": "s1", "role": "student", "name": "S"}))
    assert "not read" in resp.json()["extracted_text"]


def test_uploading_unauthenticated_is_refused(client):
    resp = client.post(
        "/api/chat/upload",
        files={"file": ("form.png", io.BytesIO(PNG_1PX), "image/png")},
    )
    assert resp.status_code == 401


# ── The three outcomes stay distinct ────────────────────────────────────────────

def _patch_ocr(monkeypatch, **kwargs):
    from services.ocr_service import OcrResult
    import routes.chat_upload as mod

    monkeypatch.setattr(mod, "extract_image_text", lambda data: OcrResult(**kwargs))


def test_an_unavailable_engine_never_reads_as_a_blank_page(client, monkeypatch):
    """Before the deploy that installs tesseract, every request lands here."""
    _patch_ocr(monkeypatch, text="", available=False,
               reason="The OCR engine is not installed on this server yet.")

    body = _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"})).json()

    assert "not installed on this server yet" in body["extracted_text"]
    assert body["ocr_note"]
    assert "blank" not in body["extracted_text"].lower()


def test_text_found_on_the_page_is_handed_to_flo_as_ordinary_text(client, monkeypatch):
    _patch_ocr(monkeypatch, text="ADMISSION FORM\nName: Asha Kumari",
               available=True, language="eng+hin", char_count=32)

    body = _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"})).json()

    assert "ADMISSION FORM" in body["extracted_text"]
    assert "Asha Kumari" in body["extracted_text"]
    assert body["ocr_note"] is None


def test_a_page_with_no_text_says_so_and_admits_it_cannot_see(client, monkeypatch):
    """OCR reads letters. Asked to describe a photograph it returns nothing, and Flo
    must not imply it looked at the picture."""
    _patch_ocr(monkeypatch, text="", available=True,
               reason="No text was found on that page.")

    body = _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"})).json()

    assert "No text was found" in body["extracted_text"]
    assert "does not describe photographs" in body["extracted_text"]


def test_a_missing_hindi_pack_is_surfaced_rather_than_silently_dropping_hindi(client, monkeypatch):
    _patch_ocr(monkeypatch, text="NOTICE", available=True, language="eng", char_count=6,
               notes=["Hindi text may not have been read: the Hindi language pack is not installed."])

    body = _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"})).json()
    assert "Hindi language pack is not installed" in body["extracted_text"]


# ── Auditing ────────────────────────────────────────────────────────────────────

def test_reading_an_image_is_audited(client, monkeypatch, fake_db):
    _patch_ocr(monkeypatch, text="FEE RECEIPT", available=True, char_count=11)
    _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"}))

    rows = [a for a in fake_db.audit_logs.docs if a.get("action") == "image_text_read"]
    assert len(rows) == 1
    assert rows[0]["changes"]["chars_found"] == 11


def test_the_audit_row_never_holds_the_text_that_was_read(client, monkeypatch, fake_db):
    """NFR-S2, and doubly so here: the page may be a child's medical note."""
    _patch_ocr(monkeypatch, text="Asha Kumari has asthma. Phone 9876543210.",
               available=True, char_count=41)
    _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"}))

    blob = str([a for a in fake_db.audit_logs.docs if a.get("action") == "image_text_read"])
    assert "Asha Kumari" not in blob
    assert "asthma" not in blob
    assert "9876543210" not in blob


def test_a_refused_read_is_not_audited_as_a_read(client, fake_db):
    _upload(client, _bearer({"user_id": "t1", "role": "teacher", "name": "T"}))
    assert [a for a in fake_db.audit_logs.docs if a.get("action") == "image_text_read"] == []


def test_a_failed_audit_does_not_lose_the_extracted_text(client, monkeypatch):
    """Auditing is fail-open elsewhere in this platform; a logging problem must not
    cost the user the answer they asked for."""
    _patch_ocr(monkeypatch, text="CIRCULAR", available=True, char_count=8)

    import routes.chat_upload as mod

    async def _boom(*a, **k):
        raise RuntimeError("audit down")

    monkeypatch.setattr(mod, "write_audit", _boom)

    body = _upload(client, _bearer({"user_id": "o1", "role": "owner", "name": "O"})).json()
    assert "CIRCULAR" in body["extracted_text"]


# ── Non-image uploads are unaffected ────────────────────────────────────────────

def test_a_text_file_still_works_for_everyone(client):
    resp = client.post(
        "/api/chat/upload",
        headers=_bearer({"user_id": "t1", "role": "teacher", "name": "T"}),
        files={"file": ("notes.txt", io.BytesIO(b"lesson plan for Monday"), "text/plain")},
    )
    assert resp.status_code == 200
    assert "lesson plan for Monday" in resp.json()["extracted_text"]
