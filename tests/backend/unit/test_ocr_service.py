"""UI Sweep Epic 10, Story 10.5 — reading a printed page on this server.

The most important tests here separate THREE answers that a careless implementation
returns identically as an empty string:
  - this server cannot do OCR yet (needs a deploy)
  - the page had no text on it
  - the file was not a readable image

Collapsing those is the Epic 4 defect — a failure that looks like a real result —
in a new place.
"""
from __future__ import annotations

import pytest

from services import ocr_service
from services.ocr_service import MAX_IMAGE_BYTES, OcrResult, extract_text, ocr_available, sniff_image_type

pytestmark = pytest.mark.asyncio

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ── Content sniffing, not the file extension ────────────────────────────────────

@pytest.mark.parametrize("data,expected", [
    (PNG_1PX, "image/png"),
    (b"\xff\xd8\xff\xe0rest", "image/jpeg"),
    (b"GIF89a...", "image/gif"),
    (b"BMxxxx", "image/bmp"),
    (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    (b"II*\x00rest", "image/tiff"),
])
def test_real_images_are_recognised_by_their_bytes(data, expected):
    assert sniff_image_type(data) == expected


@pytest.mark.parametrize("data", [
    b"PK\x03\x04zip-not-an-image",
    b"%PDF-1.7",
    b"#!/bin/sh\nrm -rf /",
    b"",
])
def test_a_non_image_is_not_mistaken_for_one(data):
    """A .png that is really an archive must never reach the OCR process."""
    assert sniff_image_type(data) is None


def test_a_non_image_is_refused_with_a_reason(monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))
    result = extract_text(b"PK\x03\x04not-an-image")

    assert result.found_text is False
    assert result.available is True
    assert "not an image" in result.reason


def test_an_oversized_file_is_refused_before_any_work(monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))
    result = extract_text(b"\x89PNG\r\n\x1a\n" + b"\x00" * (MAX_IMAGE_BYTES + 1))

    assert result.found_text is False
    assert "too large" in result.reason


def test_an_empty_file_is_refused(monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))
    assert "empty" in extract_text(b"").reason


# ── The three answers stay distinct ─────────────────────────────────────────────

def test_an_unavailable_engine_says_so_rather_than_returning_a_blank_page(monkeypatch):
    """THE test for this story. Before the deploy that installs tesseract, every
    request lands here — and it must not read as 'the page was blank'."""
    monkeypatch.setattr(
        ocr_service, "ocr_available",
        lambda: (False, "The OCR engine is not installed on this server yet."),
    )
    result = extract_text(PNG_1PX)

    assert result.available is False
    assert result.found_text is False
    assert "not installed" in result.reason
    assert result.text == ""


def test_availability_distinguishes_the_library_from_the_binary(monkeypatch):
    """The Python wrapper installs from pip; the tesseract program does not. Saying
    which one is missing is the difference between a useful message and a shrug."""
    monkeypatch.setattr(ocr_service.shutil, "which", lambda name: None)
    available, why = ocr_available()

    if not available and "library" not in why:
        assert "tesseract" in why.lower()
        assert "deployment" in why.lower()


def test_a_blank_page_is_reported_as_no_text_not_as_a_failure(monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))

    class _FakeTess:
        @staticmethod
        def image_to_string(image, lang=""):
            return "   \n  "

    class _FakeImage:
        @staticmethod
        def open(fh):
            class _Img:
                def load(self):
                    return None
            return _Img()

    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", _FakeTess)
    monkeypatch.setitem(sys.modules, "PIL", type("m", (), {"Image": _FakeImage}))
    monkeypatch.setitem(sys.modules, "PIL.Image", _FakeImage)

    result = extract_text(PNG_1PX)
    assert result.available is True
    assert result.found_text is False
    assert "No text was found" in result.reason


def test_text_on_a_page_comes_back_with_the_language_used(monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))

    class _FakeTess:
        @staticmethod
        def image_to_string(image, lang=""):
            return "ADMISSION FORM\nName: Asha Kumari\n"

    class _FakeImage:
        @staticmethod
        def open(fh):
            class _Img:
                def load(self):
                    return None
            return _Img()

    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", _FakeTess)
    monkeypatch.setitem(sys.modules, "PIL", type("m", (), {"Image": _FakeImage}))
    monkeypatch.setitem(sys.modules, "PIL.Image", _FakeImage)

    result = extract_text(PNG_1PX)
    assert result.found_text is True
    assert "Asha Kumari" in result.text
    assert result.language == "eng+hin"
    assert result.char_count > 0


def test_a_missing_hindi_pack_falls_back_to_english_and_says_so(monkeypatch):
    """Tesseract errors on a missing language pack rather than degrading, so the
    languages are tried in order — and the user is told Hindi may be missing."""
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))

    class _FakeTess:
        @staticmethod
        def image_to_string(image, lang=""):
            if "hin" in lang:
                raise RuntimeError("Failed loading language 'hin'")
            return "NOTICE"

    class _FakeImage:
        @staticmethod
        def open(fh):
            class _Img:
                def load(self):
                    return None
            return _Img()

    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", _FakeTess)
    monkeypatch.setitem(sys.modules, "PIL", type("m", (), {"Image": _FakeImage}))
    monkeypatch.setitem(sys.modules, "PIL.Image", _FakeImage)

    result = extract_text(PNG_1PX)
    assert result.text == "NOTICE"
    assert result.language == "eng"
    assert any("Hindi" in n for n in result.notes)


def test_a_damaged_image_is_reported_as_damaged(monkeypatch):
    monkeypatch.setattr(ocr_service, "ocr_available", lambda: (True, ""))

    class _FakeImage:
        @staticmethod
        def open(fh):
            raise OSError("cannot identify image file")

    import sys
    monkeypatch.setitem(sys.modules, "pytesseract", type("m", (), {}))
    monkeypatch.setitem(sys.modules, "PIL", type("m", (), {"Image": _FakeImage}))
    monkeypatch.setitem(sys.modules, "PIL.Image", _FakeImage)

    result = extract_text(PNG_1PX)
    assert result.available is True
    assert "damaged" in result.reason


def test_the_result_never_claims_to_have_seen_anything():
    """OCR reads letters. It does not see. Nothing in the result type invites a
    caller to describe a photograph."""
    result = OcrResult(text="some words")
    assert not hasattr(result, "description")
    assert not hasattr(result, "objects")
    assert result.found_text is True
