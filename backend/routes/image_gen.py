from __future__ import annotations

"""
Gemini-powered image generation for certificates and ID cards.
Uses Imagen 3 for visual backgrounds, fpdf2 for PDF assembly.
"""
import io
import os
import asyncio
import logging
import uuid
from datetime import datetime
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response, JSONResponse
from database import get_db
from middleware.auth import require_owner_or_principal
from tenant import add_school_id, get_school_id
from services.s3_storage import (
    PRESIGNED_URL_EXPIRY_SECONDS,
    build_upload_key,
    create_presigned_get_url,
    upload_bytes,
)
from services.audit_service import write_audit

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/image-gen", tags=["image-gen"])

# R9.5 (X9 AC3): per-school, per-kind daily generation cap (abuse guard).
DAILY_GEN_CAP = 200

CERT_LABELS = {
    "transfer": "Transfer Certificate",
    "bonafide": "Bonafide Certificate",
    "character": "Character Certificate",
    "sports": "Sports Certificate",
    "participation": "Participation Certificate",
    "migration": "Migration Certificate",
}

CERT_STYLES = {
    "transfer":    "royal blue and maroon, formal institutional departure document",
    "bonafide":    "navy blue and gold, academic prestige, enrollment verification",
    "character":   "deep navy and silver, distinguished formal endorsement",
    "sports":      "vibrant blue and orange, athletic energy, achievement",
    "participation": "blue and emerald green, vibrant academic celebration",
    "migration":   "formal blue and bronze, official academic migration",
}

CERT_BODIES = {
    "transfer":    "This is to certify that {name} was a student of {school} in Class {cls}. Transfer Certificate is granted on {date} for the academic year {ay}. Conduct and character were Good throughout.",
    "bonafide":    "This is to certify that {name} is a bonafide student of {school}, currently studying in Class {cls} during the academic year {ay}. This certificate is issued on request for official purposes.",
    "character":   "This is to certify that {name} of Class {cls} has been a student of {school} during the academic year {ay}. The student maintained exemplary character and conduct. We wish all success in future endeavours.",
    "sports":      "This is to certify that {name} of Class {cls} has actively participated in sports activities at {school} during the academic year {ay}. The student has shown commendable sportsmanship and dedication.",
    "participation": "This is to certify that {name} of Class {cls} participated in activities organised by {school} during the academic year {ay}. The student has shown enthusiasm and active involvement.",
    "migration":   "This is to certify that {name}, a student of Class {cls} at {school}, is granted this Migration Certificate for the academic year {ay}. All dues and formalities have been cleared.",
}


# ─── Prompt builders (no hardcoding) ─────────────────────────────────────────

def _cert_prompt(cert_type: str, cert_title: str) -> str:
    style = CERT_STYLES.get(cert_type, "navy blue and gold, formal academic")
    return (
        f"A formal school {cert_title} background design. "
        f"Color scheme: {style}. "
        f"Elegant decorative border with classical ornamental corner patterns and a subtle central watermark area. "
        f"A4 portrait format. Official academic document aesthetic. "
        f"Wide clear area in the centre for printed text content. "
        f"No text, no letters, no numbers anywhere — purely decorative art."
    )


def _id_card_prompt(school_name: str) -> str:
    return (
        f"A professional student ID card background for a school named {school_name}. "
        f"Horizontal layout, credit-card proportions (85mm x 54mm). "
        f"Blue gradient with subtle geometric pattern, top header strip in dark navy, "
        f"white centre area for content, light footer strip. "
        f"Clean modern academic design. "
        f"No text, no letters, no words — purely decorative background art."
    )


# ─── Backgrounds ──────────────────────────────────────────────────────────────
#
# R9.5 (X9 AC2): the Google Gemini/Imagen leg was REMOVED. It shipped school data
# (school name, and the request context) to Google — contradicting the platform's
# Azure-residency / DPDP ADR — and degraded silently to a plain background on any
# failure. Certificates and ID cards are decorative-background documents whose text
# is drawn locally with fpdf2; the locally-drawn `_plain_cert_bg`/`_plain_card`
# designs are used exclusively now: deterministic, zero external data egress, zero
# cost, no silent degrade. `_cert_prompt`/`_id_card_prompt` are retained only as
# documentation of the (now unused) design intent.


# ─── PDF builders ─────────────────────────────────────────────────────────────

def _build_cert_pdf(data: dict, bg: bytes | None) -> bytes:
    from fpdf import FPDF

    school   = data.get("school_name", "School")
    affil    = data.get("affiliation", "")
    ctype    = data.get("cert_type", "bonafide")
    title    = CERT_LABELS.get(ctype, "Certificate")
    name     = data.get("student_name", "")
    cls      = data.get("class", "")
    serial   = data.get("serial_number", "")
    issued   = data.get("issued_date", datetime.now().strftime("%d-%m-%Y"))
    ay       = data.get("academic_year", "")

    # R9.5 AC3: type-guard — `class` may arrive as a non-string (int/None); coerce
    # before .lower() so it can't raise. Strip a leading "Class " to avoid
    # "Class Class 10-A" when the class name already includes the word.
    cls = str(cls or "")
    if cls.lower().startswith("class "):
        cls = cls[6:].strip()
    tmpl = CERT_BODIES.get(ctype, CERT_BODIES["bonafide"])
    body = tmpl.format(name=name, school=school, cls=cls, date=issued, ay=ay)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_margins(0, 0, 0)

    # ── Background ──
    if bg:
        try:
            pdf.image(io.BytesIO(bg), x=0, y=0, w=210, h=297)
        except Exception as e:
            logger.warning(f"BG image embed failed: {e}")
            _plain_cert_bg(pdf)
    else:
        _plain_cert_bg(pdf)

    # ── Serial + Date ──
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(70, 70, 70)
    pdf.set_xy(120, 18);  pdf.cell(80, 5, f"Serial No.: {serial}", align="R")
    pdf.set_xy(120, 24);  pdf.cell(80, 5, f"Date: {issued}", align="R")

    # ── School name ──
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(26, 58, 110)
    pdf.set_xy(15, 38);   pdf.cell(180, 10, school.upper(), align="C")

    if affil:
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(90, 90, 90)
        pdf.set_xy(15, 50);  pdf.cell(180, 6, affil, align="C")

    # ── Divider ──
    pdf.set_draw_color(26, 58, 110)
    pdf.set_line_width(0.8)
    pdf.line(20, 60, 190, 60)

    # ── Certificate title ──
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(26, 58, 110)
    pdf.set_xy(15, 65);   pdf.cell(180, 10, title.upper(), align="C")

    # ── Body text ──
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(25, 25, 25)
    pdf.set_xy(25, 90)
    pdf.multi_cell(160, 9, body, align="J")

    # ── Signature lines ──
    y_sig = 235
    pdf.set_draw_color(60, 60, 60)
    pdf.set_line_width(0.4)
    pdf.line(30, y_sig, 88, y_sig)
    pdf.line(122, y_sig, 180, y_sig)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(50, 50, 50)
    pdf.set_xy(30, y_sig + 3);  pdf.cell(58, 5, "Class Teacher", align="C")
    pdf.set_xy(122, y_sig + 3); pdf.cell(58, 5, "Principal", align="C")

    # ── Footer ──
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(160, 160, 160)
    pdf.set_xy(15, 284)
    pdf.cell(180, 5, f"Computer-generated certificate  ·  {school}  ·  AY {ay}", align="C")

    return bytes(pdf.output())


def _plain_cert_bg(pdf):
    from fpdf import FPDF
    pdf.set_fill_color(255, 255, 255)
    pdf.rect(0, 0, 210, 297, "F")
    pdf.set_draw_color(26, 58, 110)
    pdf.set_line_width(2.0);  pdf.rect(8, 8, 194, 281)
    pdf.set_line_width(0.5);  pdf.rect(11, 11, 188, 275)


def _build_id_cards_pdf(students: list, school: str, ay: str, bg: bytes | None) -> bytes:
    from fpdf import FPDF

    CW, CH = 85.6, 53.98   # card dimensions mm
    COLS, ROWS = 2, 4
    GAP = 4.0
    MX = (210 - COLS * CW - (COLS - 1) * GAP) / 2
    MY = (297 - ROWS * CH - (ROWS - 1) * GAP) / 2

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    per_page = COLS * ROWS

    for page_idx in range(0, max(1, len(students)), per_page):
        page_students = students[page_idx : page_idx + per_page]
        pdf.add_page()
        pdf.set_fill_color(240, 244, 252)
        pdf.rect(0, 0, 210, 297, "F")

        for i, s in enumerate(page_students):
            col = i % COLS
            row = i // COLS
            x = MX + col * (CW + GAP)
            y = MY + row * (CH + GAP)

            # ── Card background ──
            if bg:
                try:
                    pdf.image(io.BytesIO(bg), x=x, y=y, w=CW, h=CH)
                except Exception:
                    _plain_card(pdf, x, y, CW, CH)
            else:
                _plain_card(pdf, x, y, CW, CH)

            # ── Card border ──
            pdf.set_draw_color(79, 143, 247)
            pdf.set_line_width(0.4)
            pdf.rect(x, y, CW, CH)

            # ── Header strip ──
            pdf.set_fill_color(26, 58, 110)
            pdf.rect(x, y, CW, 9, "F")
            pdf.set_font("Helvetica", "B", 6.5)
            pdf.set_text_color(255, 255, 255)
            pdf.set_xy(x, y + 1.8)
            pdf.cell(CW, 4.5, school[:38].upper(), align="C")

            # ── Photo box ──
            pdf.set_fill_color(230, 235, 248)
            pdf.set_draw_color(180, 190, 210)
            pdf.set_line_width(0.3)
            pdf.rect(x + 3, y + 11, 17, 22, "FD")
            pdf.set_font("Helvetica", "", 5)
            pdf.set_text_color(150, 155, 170)
            pdf.set_xy(x + 3, y + 20.5)
            pdf.cell(17, 4, "PHOTO", align="C")

            # ── Student info ──
            name = s.get("name", "")
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.set_text_color(18, 18, 40)
            pdf.set_xy(x + 23, y + 12)
            pdf.cell(CW - 26, 5, name[:24], align="L")

            pdf.set_font("Helvetica", "", 7)
            pdf.set_text_color(55, 55, 75)
            info_rows = [
                ("Class",    s.get("class", "N/A")),
                ("Adm No",   s.get("admission_number", "N/A")),
                ("Roll",     s.get("roll_number", "N/A")),
            ]
            for j, (lbl, val) in enumerate(info_rows):
                pdf.set_xy(x + 23, y + 18.5 + j * 5.2)
                pdf.cell(CW - 26, 4, f"{lbl}: {val}", align="L")

            # ── Footer strip ──
            pdf.set_fill_color(220, 232, 255)
            pdf.rect(x, y + CH - 8, CW, 8, "F")
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(50, 60, 100)
            pdf.set_xy(x, y + CH - 5.5)
            pdf.cell(CW, 4, f"AY: {ay}  ·  STUDENT ID CARD", align="C")

    return bytes(pdf.output())


def _plain_card(pdf, x, y, w, h):
    pdf.set_fill_color(248, 250, 255)
    pdf.rect(x, y, w, h, "F")


def _safe_filename(filename: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in filename)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "generated-document.pdf"


async def _persist_generated_pdf(
    *,
    pdf_bytes: bytes,
    filename: str,
    user: dict,
    linked_table: str,
    linked_id: str,
    audit_action: str,
) -> dict:
    db = get_db()
    school_id = get_school_id()
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.pdf"
    original_filename = _safe_filename(filename)
    stored = upload_bytes(
        content=pdf_bytes,
        key=build_upload_key(file_id, original_filename, school_id=school_id),
        content_type="application/pdf",
        original_filename=original_filename,
    )
    record = add_school_id({
        "_id": file_id,
        "id": file_id,
        "uploaded_by": user["id"],
        "file_url": f"/api/uploads/serve/{safe_filename}",
        "file_name": original_filename,
        "safe_filename": safe_filename,
        "file_type": "application/pdf",
        "file_size_kb": int(len(pdf_bytes) / 1024),
        "file_size_bytes": len(pdf_bytes),
        "linked_table": linked_table,
        "linked_id": linked_id or None,
        "created_at": datetime.now().isoformat(),
        "storage": "s3",
        "s3_bucket": stored.bucket,
        "s3_key": stored.key,
        "s3_etag": stored.etag,
        "sha256": stored.sha256,
    }, school_id)
    await db.file_uploads.insert_one(record)
    await write_audit(
        db,
        action=audit_action,
        entity_id=linked_id or file_id,
        collection=linked_table,
        changed_by=user["id"],
        changed_by_role=user.get("role", ""),
        school_id=school_id,
        branch_id=user.get("branch_id", ""),
        changes={"file_id": file_id, "file_name": original_filename},
    )
    return {
        "success": True,
        "file_url": create_presigned_get_url(stored.key),
        "expires_in": PRESIGNED_URL_EXPIRY_SECONDS,
        "file_id": file_id,
    }


# ─── DB resolution + rate cap (R9.5 / X9) ──────────────────────────────────────

async def _enforce_daily_cap(db, school_id: str, kind: str) -> bool:
    """Per-school, per-kind daily generation cap (X9 AC3). Returns False when over.

    Robust, test-friendly increment: find the day's counter, reject if at the cap,
    else bump (or create). A tiny race can let a couple past the cap concurrently —
    acceptable for an abuse brake.
    """
    day = date.today().isoformat()
    q = {"schoolId": school_id, "kind": kind, "day": day}
    existing = await db.image_gen_quota.find_one(q)
    if existing:
        if existing.get("count", 0) >= DAILY_GEN_CAP:
            return False
        await db.image_gen_quota.update_one({"_id": existing["_id"]}, {"$inc": {"count": 1}})
    else:
        await db.image_gen_quota.insert_one({"_id": str(uuid.uuid4()), **q, "count": 1})
    return True


async def _school_meta(db) -> dict:
    settings = await db.school_settings.find_one({}, {"_id": 0}) or {}
    ay_doc = await db.academic_years.find_one({"is_current": True}, {"_id": 0, "name": 1}) or {}
    return {
        "school_name": settings.get("school_name") or "School",
        "affiliation": settings.get("affiliation") or settings.get("board") or "",
        "academic_year": ay_doc.get("name", ""),
    }


async def _resolve_class_name(db, class_id) -> str:
    if not class_id:
        return ""
    cls = await db.classes.find_one({"id": class_id}, {"_id": 0, "name": 1, "section": 1})
    if not cls:
        return ""
    name = str(cls.get("name", "")).strip()
    section = str(cls.get("section", "")).strip()
    return f"{name}-{section}" if section else name


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/certificate")
async def generate_certificate(request: Request, user: dict = Depends(require_owner_or_principal)):
    # R9.5 AC1: owner/principal only (was any admin sub_category — a forgery surface).
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

    db = get_db()
    school_id = get_school_id()

    # R9.5 AC1: resolve the student's identity from the DB by student_id — NEVER
    # from client-supplied name/class/marks (those were the forgery vector).
    student_id = str(data.get("student_id") or "").strip()
    if not student_id:
        raise HTTPException(400, "student_id is required")
    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    if not await _enforce_daily_cap(db, school_id, "certificate"):
        raise HTTPException(429, "Daily certificate generation limit reached — try again tomorrow")

    meta = await _school_meta(db)
    cert_type = data.get("cert_type", "bonafide")  # selects a template — not identity
    title = CERT_LABELS.get(cert_type, "Certificate")
    doc_data = {
        "cert_type": cert_type,
        "student_name": student.get("name", ""),
        "class": await _resolve_class_name(db, student.get("class_id")),
        "admission_number": student.get("admission_number", ""),
        "school_name": meta["school_name"],
        "affiliation": meta["affiliation"],
        "academic_year": meta["academic_year"],
        "serial_number": str(data.get("serial_number") or ""),   # cosmetic reference
        "issued_date": datetime.now().strftime("%d-%m-%Y"),
    }

    # R9.5 AC2: no external image provider — background is drawn locally.
    pdf_bytes = _build_cert_pdf(doc_data, None)
    safe_student = (student.get("name") or "certificate").replace(" ", "-")
    filename = f"{title.replace(' ', '-')}-{safe_student}.pdf"
    if data.get("persist") is True:
        return JSONResponse(content=await _persist_generated_pdf(
            pdf_bytes=pdf_bytes,
            filename=filename,
            user=user,
            linked_table="certificate",
            linked_id=student_id,
            audit_action="certificate_generated",
        ))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/id-cards")
async def generate_id_cards(request: Request, user: dict = Depends(require_owner_or_principal)):
    # R9.5 AC1: owner/principal only.
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

    db = get_db()
    school_id = get_school_id()

    # R9.5 AC1: resolve card content from the DB by student_id — reject client-only
    # data. Accept a list of {student_id} (or {id}) and fetch the real records.
    raw = data.get("students", [])
    ids = [str(s.get("student_id") or s.get("id") or "").strip()
           for s in raw if isinstance(s, dict)]
    ids = [i for i in ids if i]
    if not ids:
        return JSONResponse(status_code=400, content={"detail": "students with student_id are required"})

    if not await _enforce_daily_cap(db, school_id, "id_card"):
        raise HTTPException(429, "Daily ID-card generation limit reached — try again tomorrow")

    docs = await db.students.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids))
    by_id = {d["id"]: d for d in docs if d.get("id")}
    class_ids = list({d.get("class_id") for d in docs if d.get("class_id")})
    class_docs = await db.classes.find(
        {"id": {"$in": class_ids}}, {"_id": 0, "id": 1, "name": 1, "section": 1}
    ).to_list(len(class_ids) or 1) if class_ids else []
    cls_by_id = {}
    for c in class_docs:
        nm = str(c.get("name", "")).strip()
        sec = str(c.get("section", "")).strip()
        cls_by_id[c.get("id")] = f"{nm}-{sec}" if sec else nm

    resolved = []
    for sid in ids:
        d = by_id.get(sid)
        if not d:
            continue
        resolved.append({
            "name": d.get("name", ""),
            "class": cls_by_id.get(d.get("class_id"), ""),
            "admission_number": d.get("admission_number", "N/A"),
            "roll_number": d.get("roll_number", "N/A"),
        })
    if not resolved:
        return JSONResponse(status_code=404, content={"detail": "No matching students found"})

    meta = await _school_meta(db)
    pdf_bytes = _build_id_cards_pdf(resolved, meta["school_name"], meta["academic_year"], None)
    filename = f"ID-Cards-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    if data.get("persist") is True:
        linked_id = str(data.get("batch_id") or data.get("class_id") or "batch")
        return JSONResponse(content=await _persist_generated_pdf(
            pdf_bytes=pdf_bytes,
            filename=filename,
            user=user,
            linked_table="id_card",
            linked_id=linked_id,
            audit_action="id_card_generated",
        ))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
