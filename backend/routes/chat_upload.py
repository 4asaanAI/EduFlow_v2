from __future__ import annotations

"""
Chat file upload endpoint — extract text from uploaded files for AI context.

Files uploaded here are processed in-memory and never stored to S3 or the
database. This is intentional: chat uploads are ephemeral AI context, not
durable user documents.

Supported formats:
  Text:   .txt  .md  .html  .htm  .csv  .json  .xml  .py  .js  .ts
  Office: .docx  .xlsx  .xls  .pptx  .pdf
  Image:  .png  .jpg  .jpeg  .heic  .webp  .gif  (returns placeholder)
  Media:  .mp3  .mp4  .mov  .wav  .m4a       (returns placeholder)
  Zip:    .zip  (extracts and reads text files inside)
"""

import io
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat-upload"])

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_TEXT_LENGTH = 40_000                # chars forwarded to LLM context
BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".sh", ".cmd", ".com", ".ps1",
    ".vbs", ".jar", ".msi", ".dll", ".bin", ".scr",
}

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".yaml", ".yml",
    ".sql", ".log",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".heic", ".webp", ".gif", ".bmp", ".tiff"}
MEDIA_EXTENSIONS = {".mp3", ".mp4", ".mov", ".wav", ".m4a", ".aac", ".avi", ".mkv"}


def _read_plain_text(data: bytes, filename: str) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _extract_pdf(data: bytes, filename: str) -> str:
    try:
        import pypdf  # noqa: F401 — optional dep
        reader = pypdf.PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        if pages:
            return "\n\n".join(pages)
        return f"[PDF: {filename} — no extractable text found (may be scanned)]"
    except ImportError:
        logger.warning("pypdf not installed; cannot extract PDF text")
        return f"[PDF: {filename} — install pypdf to enable text extraction]"
    except Exception as exc:
        logger.warning("PDF extraction error for %s: %s", filename, exc)
        return f"[PDF: {filename} — extraction error: {exc}]"


def _extract_docx(data: bytes, filename: str) -> str:
    try:
        from docx import Document  # noqa: F401
        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Also extract table cells
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    paragraphs.append(" | ".join(cells))
        return "\n\n".join(paragraphs) if paragraphs else f"[DOCX: {filename} — no text found]"
    except ImportError:
        logger.warning("python-docx not installed; cannot extract .docx text")
        return f"[DOCX: {filename} — install python-docx to enable text extraction]"
    except Exception as exc:
        logger.warning("DOCX extraction error for %s: %s", filename, exc)
        return f"[DOCX: {filename} — extraction error: {exc}]"


def _extract_xlsx(data: bytes, filename: str) -> str:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                row_vals = [str(v) if v is not None else "" for v in row]
                if any(v.strip() for v in row_vals):
                    rows.append(" | ".join(row_vals))
            if rows:
                sheets.append(f"=== Sheet: {sheet_name} ===\n" + "\n".join(rows))
        return "\n\n".join(sheets) if sheets else f"[XLSX: {filename} — no data found]"
    except ImportError:
        logger.warning("openpyxl not installed; cannot extract .xlsx text")
        return f"[XLSX: {filename} — install openpyxl to enable text extraction]"
    except Exception as exc:
        logger.warning("XLSX extraction error for %s: %s", filename, exc)
        return f"[XLSX: {filename} — extraction error: {exc}]"


def _extract_pptx(data: bytes, filename: str) -> str:
    try:
        from pptx import Presentation  # noqa: F401
        prs = Presentation(io.BytesIO(data))
        slides = []
        for i, slide in enumerate(prs.slides, 1):
            texts = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    texts.append(shape.text.strip())
            if texts:
                slides.append(f"--- Slide {i} ---\n" + "\n".join(texts))
        return "\n\n".join(slides) if slides else f"[PPTX: {filename} — no text found]"
    except ImportError:
        logger.warning("python-pptx not installed; cannot extract .pptx text")
        return f"[PPTX: {filename} — install python-pptx to enable text extraction]"
    except Exception as exc:
        logger.warning("PPTX extraction error for %s: %s", filename, exc)
        return f"[PPTX: {filename} — extraction error: {exc}]"


def _extract_zip(data: bytes, filename: str) -> str:
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return f"[ZIP: {filename} — invalid or corrupted archive]"

    parts = [f"[ZIP archive: {filename}]", "Contents:"]
    members = zf.namelist()
    parts.append(", ".join(members[:50]) + ("..." if len(members) > 50 else ""))
    parts.append("")

    text_members = [m for m in members if Path(m).suffix.lower() in TEXT_EXTENSIONS]
    for member in text_members[:10]:  # cap at 10 text files
        try:
            member_data = zf.read(member)
            if len(member_data) > 200_000:
                text = f"[{member} — too large to display]"
            else:
                text = _read_plain_text(member_data, member)[:5000]
            parts.append(f"=== {member} ===\n{text}")
        except Exception:
            parts.append(f"=== {member} === [unreadable]")

    return "\n".join(parts)


def _extract_text(data: bytes, filename: str, suffix: str) -> str:
    suffix = suffix.lower()

    if suffix in TEXT_EXTENSIONS:
        return _read_plain_text(data, filename)

    if suffix == ".pdf":
        return _extract_pdf(data, filename)

    if suffix == ".docx":
        return _extract_docx(data, filename)

    if suffix in (".xlsx", ".xls"):
        return _extract_xlsx(data, filename)

    if suffix == ".pptx":
        return _extract_pptx(data, filename)

    if suffix == ".zip":
        return _extract_zip(data, filename)

    if suffix in IMAGE_EXTENSIONS:
        return (
            f"[Image: {filename}]\n"
            "Note: Image content cannot be read as text. "
            "If you need the AI to analyse this image, please describe what is in it."
        )

    if suffix in MEDIA_EXTENSIONS:
        return (
            f"[Audio/Video: {filename}]\n"
            "Note: Media files cannot be transcribed in this version."
        )

    return f"[File: {filename} — unsupported format '{suffix}']"


@router.post("/upload")
async def upload_chat_file(request: Request, file: UploadFile = File(...)):
    """Accept a file and return extracted text for inclusion in the AI conversation context."""
    get_current_user(request)  # auth guard — raises 401 if not authenticated

    data = await file.read()
    filename = file.filename or "uploaded_file"
    suffix = Path(filename).suffix.lower()
    if suffix in BLOCKED_EXTENSIONS:
        raise HTTPException(415, f"File type {suffix} is not permitted")

    if len(data) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_FILE_SIZE_BYTES // (1024*1024)} MB)")

    extracted = _extract_text(data, filename, suffix)

    if len(extracted) > MAX_TEXT_LENGTH:
        extracted = extracted[:MAX_TEXT_LENGTH] + f"\n\n[... truncated — original {len(extracted):,} chars]"

    return {
        "success": True,
        "filename": filename,
        "size_bytes": len(data),
        "extracted_text": extracted,
        "char_count": len(extracted),
    }
