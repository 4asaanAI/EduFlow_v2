"""Turn a structured description into a real Word, Excel, PowerPoint or PDF file.

UI Sweep Epic 10, Story 10.1.

WHY THIS EXISTS. Flo told the owner it could write the *content* of a circular or a fee
sheet but "not directly generate a real .docx file in this setup". That was Flo
underselling the platform: `python-docx`, `openpyxl`, `python-pptx` and `fpdf2` are all
already pinned in requirements.txt. Three of them were only ever used to READ uploaded
files (`routes/chat_upload.py`); only PDF was used to write, for certificates and fee
receipts. Nothing was missing except a place to put the writing code.

THE RULE THIS MODULE ENFORCES: there is ONE builder. Four half-built generators
scattered across route files is what happens otherwise, and then a fix to page size or
filename sanitising lands in one of them.

WHAT THIS MODULE IS NOT: it does not fetch data, decide who may see it, store anything,
or write an audit row. It takes a description and returns bytes. Authorization belongs
to the caller, because the caller knows which data it drew on — see
`services/document_export.py` for the storing half and `ai/tool_functions_v2.py` for the
gate.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Caps mirror the `.to_list(N)` limits already used in routes/exports.py. A document
# nobody can open is not a successful export, and an unbounded row count is how a
# request for "every fee record" becomes an out-of-memory on a small instance.
MAX_ROWS = 5000
MAX_COLUMNS = 60
MAX_CELL_CHARS = 2000
MAX_SLIDES = 100
MAX_PARAGRAPHS = 2000

CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
    "csv": "text/csv",
    "md": "text/markdown",
    "txt": "text/plain",
}

SUPPORTED_TYPES = tuple(CONTENT_TYPES)


class DocumentBuildError(Exception):
    """The description could not be turned into a file.

    Raised BEFORE anything is stored, so a malformed request never leaves an orphan
    object in S3 with no `file_uploads` record pointing at it.
    """


@dataclass
class BuiltDocument:
    content: bytes
    content_type: str
    filename: str
    doc_type: str
    truncated: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def size_bytes(self) -> int:
        return len(self.content)


# ── Filename hygiene ────────────────────────────────────────────────────────────

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str, doc_type: str) -> str:
    """Make a filename safe for an S3 key AND for a Content-Disposition header.

    Both matter. A path separator walks outside the intended `{school_id}/uploads/`
    prefix; a newline or a quote forges a response header. The name may come from a
    person or from Flo, so neither is trusted.
    """
    base = (name or "").strip()
    # Take the last path component before sanitising, so "../../etc/passwd" cannot
    # survive as "......etc-passwd" and read like a traversal attempt.
    base = base.replace("\\", "/").split("/")[-1]
    for suffix in SUPPORTED_TYPES:
        if base.lower().endswith("." + suffix):
            base = base[: -(len(suffix) + 1)]
            break
    base = _UNSAFE.sub("-", base).strip("-._")
    base = re.sub(r"-{2,}", "-", base)
    if not base:
        base = "document"
    return f"{base[:80]}.{doc_type}"


def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return text[:MAX_CELL_CHARS]


def _validate(doc_type: str, title: str) -> None:
    if doc_type not in SUPPORTED_TYPES:
        raise DocumentBuildError(
            f"Unsupported document type '{doc_type}'. "
            f"Supported: {', '.join(SUPPORTED_TYPES)}."
        )
    if title is not None and len(str(title)) > 300:
        raise DocumentBuildError("Title is too long (max 300 characters).")


def _normalise_table(headers: Optional[List[Any]], rows: Optional[List[List[Any]]]):
    """Return (headers, rows, truncated). Ragged rows are padded, not rejected —
    real data is ragged, and refusing the whole document over one short row would
    be worse than filling a blank."""
    hdrs = [_clean_cell(h) for h in (headers or [])][:MAX_COLUMNS]
    raw = rows or []
    truncated = len(raw) > MAX_ROWS
    out: List[List[str]] = []
    width = len(hdrs)
    for row in raw[:MAX_ROWS]:
        if not isinstance(row, (list, tuple)):
            row = [row]
        cells = [_clean_cell(c) for c in row][:MAX_COLUMNS]
        width = max(width, len(cells))
        out.append(cells)
    if not hdrs and out:
        width = max(len(r) for r in out)
    for row in out:
        row.extend([""] * (width - len(row)))
    if hdrs:
        hdrs.extend([""] * (width - len(hdrs)))
    return hdrs, out, truncated


# ── Builders, one per type ──────────────────────────────────────────────────────

def _build_docx(title, paragraphs, headers, rows, truncated_note):
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise DocumentBuildError("Word support is not installed on this server.") from exc

    doc = Document()
    if title:
        doc.add_heading(str(title)[:300], level=1)
    for para in (paragraphs or [])[:MAX_PARAGRAPHS]:
        doc.add_paragraph(_clean_cell(para))
    if rows:
        table = doc.add_table(rows=1 if headers else 0, cols=len(rows[0]) or 1)
        table.style = "Table Grid"
        if headers:
            for i, h in enumerate(headers):
                table.rows[0].cells[i].text = h
        for row in rows:
            cells = table.add_row().cells
            for i, value in enumerate(row):
                cells[i].text = value
    if truncated_note:
        doc.add_paragraph(truncated_note)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_xlsx(title, paragraphs, headers, rows, truncated_note):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as exc:  # pragma: no cover
        raise DocumentBuildError("Excel support is not installed on this server.") from exc

    wb = Workbook()
    ws = wb.active
    # Sheet names cannot exceed 31 chars or contain []:*?/\ — Excel refuses to open
    # the file rather than complaining, so this is silently fatal if not handled.
    ws.title = (re.sub(r"[\[\]:*?/\\]", "-", str(title or "Sheet"))[:31]) or "Sheet"

    for para in (paragraphs or [])[:20]:
        ws.append([_clean_cell(para)])
    if paragraphs:
        ws.append([])
    if headers:
        ws.append(headers)
        for cell in ws[ws.max_row]:
            cell.font = Font(bold=True)
    for row in rows:
        ws.append(row)
    if truncated_note:
        ws.append([])
        ws.append([truncated_note])

    # Width by content so a fee sheet opens readable rather than as ####.
    for idx, column_cells in enumerate(ws.columns, start=1):
        longest = max((len(str(c.value)) for c in column_cells if c.value is not None), default=0)
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(60, max(10, longest + 2))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _build_pptx(title, paragraphs, headers, rows, truncated_note, slides):
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
    except ImportError as exc:  # pragma: no cover
        raise DocumentBuildError("PowerPoint support is not installed on this server.") from exc

    prs = Presentation()
    if title:
        cover = prs.slides.add_slide(prs.slide_layouts[0])
        cover.shapes.title.text = str(title)[:300]
        if len(cover.placeholders) > 1 and paragraphs:
            cover.placeholders[1].text = _clean_cell(paragraphs[0])

    body_slides = slides or []
    if not body_slides and (paragraphs or rows):
        body_slides = [{"title": "Details", "bullets": [_clean_cell(p) for p in (paragraphs or [])[1:]]}]

    for spec in body_slides[:MAX_SLIDES]:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.shapes.title.text = _clean_cell(spec.get("title", ""))[:200]
        bullets = spec.get("bullets") or []
        frame = slide.placeholders[1].text_frame
        frame.clear()
        for i, bullet in enumerate(bullets[:20]):
            para = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
            para.text = _clean_cell(bullet)
            para.font.size = Pt(18)

    if rows:
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = "Data"
        # A slide cannot hold thousands of rows legibly; show a window and say so.
        shown = rows[:12]
        table_rows = len(shown) + (1 if headers else 0)
        shape = slide.shapes.add_table(
            table_rows, len(shown[0]), Inches(0.5), Inches(1.5), Inches(9), Inches(0.4 * table_rows)
        )
        table = shape.table
        offset = 0
        if headers:
            for i, h in enumerate(headers):
                table.cell(0, i).text = h
            offset = 1
        for r, row in enumerate(shown):
            for c, value in enumerate(row):
                table.cell(r + offset, c).text = value

    if truncated_note:
        note_slide = prs.slides.add_slide(prs.slide_layouts[5])
        note_slide.shapes.title.text = truncated_note[:200]

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def _build_pdf(title, paragraphs, headers, rows, truncated_note):
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover
        raise DocumentBuildError("PDF support is not installed on this server.") from exc

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def _latin1(text: str) -> str:
        # fpdf2's core fonts are Latin-1 only. Devanagari would raise and lose the
        # whole document, so it is transliterated away rather than crashing. Recorded
        # as a known limit in the epic log rather than hidden.
        return str(text).encode("latin-1", "replace").decode("latin-1")

    if title:
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, _latin1(str(title)[:300]))
        pdf.ln(2)

    pdf.set_font("Helvetica", size=11)
    for para in (paragraphs or [])[:MAX_PARAGRAPHS]:
        pdf.multi_cell(0, 6, _latin1(_clean_cell(para)))
        pdf.ln(1)

    if rows:
        pdf.ln(3)
        usable = pdf.w - 2 * pdf.l_margin
        col_count = len(rows[0]) or 1
        col_width = usable / col_count
        if headers:
            pdf.set_font("Helvetica", "B", 9)
            for h in headers:
                pdf.cell(col_width, 7, _latin1(h)[:40], border=1)
            pdf.ln()
        pdf.set_font("Helvetica", size=9)
        for row in rows:
            if pdf.get_y() > pdf.h - 25:
                pdf.add_page()
            for value in row:
                pdf.cell(col_width, 6, _latin1(value)[:40], border=1)
            pdf.ln()

    if truncated_note:
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 6, _latin1(truncated_note))

    out = pdf.output(dest="S")
    return bytes(out) if isinstance(out, (bytes, bytearray)) else out.encode("latin-1")


def _build_text(doc_type, title, paragraphs, headers, rows, truncated_note):
    lines: List[str] = []
    if doc_type == "csv":
        import csv

        buf = io.StringIO()
        writer = csv.writer(buf)
        if headers:
            writer.writerow(headers)
        writer.writerows(rows)
        if truncated_note:
            writer.writerow([truncated_note])
        return buf.getvalue().encode("utf-8")

    if title:
        lines.append(f"# {title}" if doc_type == "md" else str(title))
        lines.append("")
    lines.extend(_clean_cell(p) for p in (paragraphs or [])[:MAX_PARAGRAPHS])
    if rows:
        lines.append("")
        if doc_type == "md" and headers:
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join([" --- "] * len(headers)) + "|")
            lines.extend("| " + " | ".join(r) + " |" for r in rows)
        else:
            if headers:
                lines.append("\t".join(headers))
            lines.extend("\t".join(r) for r in rows)
    if truncated_note:
        lines.extend(["", truncated_note])
    return "\n".join(lines).encode("utf-8")


# ── The one entry point ─────────────────────────────────────────────────────────

def build_document(
    *,
    doc_type: str,
    filename: str = "",
    title: str = "",
    paragraphs: Optional[List[Any]] = None,
    headers: Optional[List[Any]] = None,
    rows: Optional[List[List[Any]]] = None,
    slides: Optional[List[Dict[str, Any]]] = None,
) -> BuiltDocument:
    """Build a document and return its bytes. Never touches the database or S3.

    Raises DocumentBuildError for anything malformed, before any caller has stored
    something it would then have to clean up.
    """
    doc_type = (doc_type or "").lower().lstrip(".")
    _validate(doc_type, title)

    if not any([title, paragraphs, rows, slides]):
        raise DocumentBuildError("Nothing to put in the document — provide a title, text, rows or slides.")

    hdrs, norm_rows, truncated = _normalise_table(headers, rows)
    note = ""
    if truncated:
        # Say it in the file itself. A silently short export is the Epic 4 defect
        # (a failure that looks like a complete answer) in a new place.
        note = f"Note: only the first {MAX_ROWS:,} rows are included. {len(rows):,} rows matched."

    if doc_type == "docx":
        content = _build_docx(title, paragraphs, hdrs, norm_rows, note)
    elif doc_type == "xlsx":
        content = _build_xlsx(title, paragraphs, hdrs, norm_rows, note)
    elif doc_type == "pptx":
        content = _build_pptx(title, paragraphs, hdrs, norm_rows, note, slides)
    elif doc_type == "pdf":
        content = _build_pdf(title, paragraphs, hdrs, norm_rows, note)
    else:
        content = _build_text(doc_type, title, paragraphs, hdrs, norm_rows, note)

    return BuiltDocument(
        content=content,
        content_type=CONTENT_TYPES[doc_type],
        filename=safe_filename(filename or title or "document", doc_type),
        doc_type=doc_type,
        truncated=truncated,
        notes=[note] if note else [],
    )
