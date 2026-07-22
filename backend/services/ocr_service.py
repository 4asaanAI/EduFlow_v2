"""Read the words off a photographed page, on this server, for nothing.

UI Sweep Epic 10, Story 10.5.

Abhimanyu chose this over a paid vision service for printed paper, 2026-07-22:
"make the ability or skill of using Tesseract or PaddleOCR for printed paper available
to Flo — free, private, on your own server."

WHY TESSERACT AND NOT PADDLEOCR OR EASYOCR. PaddleOCR pulls PaddlePaddle and EasyOCR
pulls Torch: hundreds of megabytes of model and a memory footprint this Elastic
Beanstalk instance does not have. Tesseract is a small C++ binary with a thin Python
wrapper. Recorded so the choice is not revisited blind.

WHY THIS IS THE RIGHT DEFAULT FOR A SCHOOL. Most of what a school photographs is
PRINTED — fee slips, admission forms, circulars, mark sheets. Tesseract reads those
accurately, costs nothing per page, and **the image never leaves this server**. For
photographs that may contain children, that privacy property is worth more than the
accuracy a hosted model would add.

WHAT IT CANNOT DO, and must never pretend to. OCR reads letters. It does not see. Ask
it what is happening in a photograph of a classroom and it will return nothing, which
is the correct answer for a tool that only reads text — not evidence the page was
blank. `ocr_available()` and the `reason` on every result exist so callers can tell
"there was no text" from "this server cannot do OCR yet".
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# The school's paperwork is English and Hindi. `hin` needs its own language pack
# (tesseract-ocr-hin); if it is missing Tesseract errors rather than falling back,
# so the languages are tried in order and the working one is reported.
PREFERRED_LANGUAGES = ("eng+hin", "eng")

# A photograph from a modern phone is a few megabytes. Well past that and it is not a
# page of A4 — it is someone trying to make the server do a lot of work.
MAX_IMAGE_BYTES = 12 * 1024 * 1024

# Content sniffing, NOT the file extension. A `.png` that is really a 200 MB archive
# must not reach the OCR process.
_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"BM": "image/bmp",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
}


class OcrUnavailable(Exception):
    """Tesseract is not installed on this server."""


@dataclass
class OcrResult:
    text: str
    language: str = ""
    available: bool = True
    reason: str = ""
    char_count: int = 0
    notes: List[str] = field(default_factory=list)

    @property
    def found_text(self) -> bool:
        return bool(self.text.strip())


def sniff_image_type(data: bytes) -> Optional[str]:
    """Identify an image by its bytes. Returns None if it is not an image."""
    for magic, mime in _MAGIC.items():
        if data.startswith(magic):
            return mime
    # WEBP is RIFF....WEBP
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def ocr_available() -> Tuple[bool, str]:
    """Is OCR usable on this server right now?

    Two separate things must be true: the Python wrapper is importable AND the
    `tesseract` binary is on PATH. The wrapper installs from pip; the binary does
    not. Reporting them separately is what lets the answer be "the server needs
    tesseract installed" rather than a stack trace.
    """
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False, "The OCR library is not installed on this server."
    if not shutil.which("tesseract"):
        return False, (
            "The OCR engine is not installed on this server yet. "
            "It needs the 'tesseract' program, which is added by a deployment."
        )
    return True, ""


def extract_text(data: bytes, *, languages: Optional[Tuple[str, ...]] = None) -> OcrResult:
    """Read the text off an image. Never raises for an unreadable page.

    An unavailable engine and an genuinely blank page are DIFFERENT ANSWERS and are
    reported differently — returning "" for both would be the Epic 4 defect (a
    failure that looks like a real result) in a new place.
    """
    available, why = ocr_available()
    if not available:
        return OcrResult(text="", available=False, reason=why)

    if not data:
        return OcrResult(text="", available=True, reason="The file was empty.")
    if len(data) > MAX_IMAGE_BYTES:
        return OcrResult(
            text="", available=True,
            reason=f"That image is too large to read (limit {MAX_IMAGE_BYTES // (1024 * 1024)} MB).",
        )

    mime = sniff_image_type(data)
    if not mime:
        return OcrResult(
            text="", available=True,
            reason="That file is not an image I can read. Send a photo or scan (PNG, JPEG, WEBP, TIFF or BMP).",
        )

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        return OcrResult(text="", available=False, reason=f"The OCR library is incomplete on this server ({exc}).")

    try:
        image = Image.open(__import__("io").BytesIO(data))
        image.load()
    except Exception:
        logger.warning("OCR could not open an image that passed content sniffing")
        return OcrResult(text="", available=True, reason="That image could not be opened — it may be damaged.")

    last_error = ""
    for lang in (languages or PREFERRED_LANGUAGES):
        try:
            text = pytesseract.image_to_string(image, lang=lang)
        except Exception as exc:  # a missing language pack lands here
            last_error = str(exc)
            continue
        cleaned = (text or "").strip()
        notes = []
        if lang == "eng" and "hin" in PREFERRED_LANGUAGES[0]:
            notes.append("Hindi text may not have been read: the Hindi language pack is not installed.")
        return OcrResult(
            text=cleaned,
            language=lang,
            available=True,
            reason="" if cleaned else "No text was found on that page.",
            char_count=len(cleaned),
            notes=notes,
        )

    logger.warning("OCR failed for every language attempted: %s", last_error)
    return OcrResult(text="", available=True, reason="The page could not be read.")
