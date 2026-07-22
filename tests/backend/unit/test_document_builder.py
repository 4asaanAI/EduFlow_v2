"""UI Sweep Epic 10, Story 10.1 — the shared document builder.

These assert the bytes are a REAL file of the claimed type, by opening them again with
the corresponding reader. Asserting "no exception was raised" would pass for a builder
that wrote an empty or corrupt file, which is exactly the class of defect that would
reach the owner as "the download won't open".
"""
from __future__ import annotations

import io
import zipfile

import pytest

from services.document_builder import (
    CONTENT_TYPES,
    MAX_ROWS,
    DocumentBuildError,
    build_document,
    safe_filename,
)

pytestmark = pytest.mark.asyncio


# ── The files are real files ────────────────────────────────────────────────────

def test_xlsx_opens_as_a_workbook_with_the_data_in_it():
    doc = build_document(
        doc_type="xlsx",
        title="Fee Sheet",
        headers=["Student", "Class", "Owed"],
        rows=[["Asha", "5-A", "12000"], ["Bipin", "3-B", "9000"]],
    )
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(doc.content))
    ws = wb.active
    values = [[c.value for c in row] for row in ws.iter_rows()]
    assert ["Student", "Class", "Owed"] in values
    assert ["Asha", "5-A", "12000"] in values
    assert doc.content_type == CONTENT_TYPES["xlsx"]


def test_docx_opens_as_a_document_with_the_text_in_it():
    doc = build_document(
        doc_type="docx",
        title="Principal's Circular",
        paragraphs=["School reopens on 1 April.", "Uniforms are compulsory."],
    )
    from docx import Document

    parsed = Document(io.BytesIO(doc.content))
    text = "\n".join(p.text for p in parsed.paragraphs)
    assert "Principal's Circular" in text
    assert "School reopens on 1 April." in text


def test_pptx_opens_as_a_presentation():
    doc = build_document(
        doc_type="pptx",
        title="School Profile",
        slides=[{"title": "Results", "bullets": ["100% pass", "12 distinctions"]}],
    )
    from pptx import Presentation

    prs = Presentation(io.BytesIO(doc.content))
    titles = [s.shapes.title.text for s in prs.slides if s.shapes.title]
    assert "School Profile" in titles
    assert "Results" in titles


def test_pdf_is_a_pdf():
    doc = build_document(doc_type="pdf", title="Notice", paragraphs=["Holiday on Monday."])
    assert doc.content.startswith(b"%PDF")
    assert doc.content_type == "application/pdf"


def test_office_files_are_valid_zip_containers():
    """A .docx/.xlsx/.pptx is a zip. A truncated write produces bytes that look
    plausible and fail to open — this catches that without a full parse."""
    for doc_type in ("docx", "xlsx", "pptx"):
        doc = build_document(doc_type=doc_type, title="T", paragraphs=["body"])
        assert zipfile.is_zipfile(io.BytesIO(doc.content)), doc_type


def test_csv_and_markdown_come_out_as_text():
    csv_doc = build_document(doc_type="csv", headers=["A", "B"], rows=[["1", "2"]])
    assert csv_doc.content.decode().splitlines()[0] == "A,B"

    md_doc = build_document(doc_type="md", title="Policy", headers=["A"], rows=[["1"]])
    text = md_doc.content.decode()
    assert text.startswith("# Policy")
    assert "| A |" in text


# ── Filenames are the security-sensitive part ───────────────────────────────────

@pytest.mark.parametrize("dangerous", [
    "../../../etc/passwd",
    "..\\..\\windows\\system32\\config",
    'fee"; rm -rf /',
    "report\nContent-Disposition: attachment; filename=evil",
    "  ",
    "",
])
def test_filenames_cannot_escape_or_forge_a_header(dangerous):
    """The name may come from a person or from Flo. A path separator walks outside
    the school's S3 prefix; a newline or quote forges a response header."""
    name = safe_filename(dangerous, "xlsx")
    assert "/" not in name and "\\" not in name
    assert "\n" not in name and "\r" not in name
    assert '"' not in name and ";" not in name
    assert ".." not in name
    assert name.endswith(".xlsx")
    assert len(name) > len(".xlsx")


def test_a_traversal_attempt_keeps_only_the_last_component():
    assert safe_filename("../../secret-report", "pdf") == "secret-report.pdf"


def test_the_extension_is_not_doubled():
    assert safe_filename("fees.xlsx", "xlsx") == "fees.xlsx"


def test_a_very_long_name_is_cut():
    assert len(safe_filename("x" * 500, "pdf")) <= 85


# ── Refusing, rather than writing something broken ──────────────────────────────

def test_an_unsupported_type_is_refused():
    with pytest.raises(DocumentBuildError) as exc:
        build_document(doc_type="exe", title="x")
    assert "Unsupported" in str(exc.value)


def test_an_empty_description_is_refused():
    """Refused BEFORE storage, so no orphan object is left in S3 with no record."""
    with pytest.raises(DocumentBuildError):
        build_document(doc_type="docx")


def test_an_absurd_title_is_refused():
    with pytest.raises(DocumentBuildError):
        build_document(doc_type="docx", title="t" * 400)


# ── Honest truncation ───────────────────────────────────────────────────────────

def test_too_many_rows_are_cut_and_the_file_says_so():
    """A silently short export is the Epic 4 defect — a failure that looks like a
    complete answer — in a new place."""
    rows = [[str(i), "x"] for i in range(MAX_ROWS + 500)]
    doc = build_document(doc_type="csv", headers=["N", "V"], rows=rows)

    assert doc.truncated is True
    text = doc.content.decode()
    assert "only the first" in text
    assert f"{MAX_ROWS + 500:,}" in text


def test_a_normal_export_is_not_marked_truncated():
    doc = build_document(doc_type="csv", headers=["N"], rows=[["1"], ["2"]])
    assert doc.truncated is False
    assert doc.notes == []


# ── Real data is ragged ─────────────────────────────────────────────────────────

def test_ragged_rows_are_padded_rather_than_rejected():
    """Refusing a whole export because one student has no phone number would be
    worse than filling a blank."""
    doc = build_document(
        doc_type="csv",
        headers=["Name", "Class", "Phone"],
        rows=[["Asha", "5-A", "99999"], ["Bipin"], ["Chetan", "3-B"]],
    )
    lines = doc.content.decode().strip().splitlines()
    assert all(line.count(",") == 2 for line in lines), lines


def test_none_values_become_blanks_not_the_word_none():
    doc = build_document(doc_type="csv", headers=["A", "B"], rows=[[None, "x"]])
    assert "None" not in doc.content.decode()


def test_devanagari_does_not_lose_the_whole_pdf():
    """fpdf2's core fonts are Latin-1. A Hindi circular must still produce a file
    rather than raising and losing everything the user asked for."""
    doc = build_document(doc_type="pdf", title="Notice", paragraphs=["आज छुट्टी है"])
    assert doc.content.startswith(b"%PDF")


def test_devanagari_survives_intact_in_the_office_formats():
    doc = build_document(doc_type="docx", title="सूचना", paragraphs=["आज छुट्टी है"])
    from docx import Document

    text = "\n".join(p.text for p in Document(io.BytesIO(doc.content)).paragraphs)
    assert "आज छुट्टी है" in text


def test_an_excel_sheet_name_cannot_break_the_workbook():
    """Excel refuses to open a file whose sheet name holds []:*?/\\ — it does not
    warn, it just fails, so this is silently fatal if unhandled."""
    doc = build_document(doc_type="xlsx", title="Fees [2026]: Class 5/A?", rows=[["x"]])
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(doc.content))
    assert len(wb.active.title) <= 31
    assert not set("[]:*?/\\") & set(wb.active.title)
