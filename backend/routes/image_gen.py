from __future__ import annotations

"""
Gemini-powered image generation for certificates and ID cards.
Uses Imagen 3 for visual backgrounds, fpdf2 for PDF assembly.
"""
import io
import os
import asyncio
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import Response, JSONResponse
from middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/image-gen", tags=["image-gen"])

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

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


# ─── Gemini Imagen call ───────────────────────────────────────────────────────

async def _gemini_image(prompt: str, aspect_ratio: str = "3:4") -> bytes | None:
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — background will be plain")
        return None

    def _call():
        try:
            from google import genai
            from google.genai import types
            print(f"[AI] gemini | image-gen | aspect={aspect_ratio} | prompt_len={len(prompt)}")
            client = genai.Client(api_key=GEMINI_API_KEY)
            resp = client.models.generate_images(
                model="imagen-3.0-generate-012",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type="image/png",
                    aspect_ratio=aspect_ratio,
                ),
            )
            data = resp.generated_images[0].image.image_bytes
            print(f"[AI] gemini | image-gen | done | {len(data)} bytes")
            return data
        except Exception as exc:
            logger.error(f"Gemini image generation error: {exc}")
            return None

    return await asyncio.to_thread(_call)


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
    date     = data.get("issued_date", datetime.now().strftime("%d-%m-%Y"))
    ay       = data.get("academic_year", "")

    tmpl = CERT_BODIES.get(ctype, CERT_BODIES["bonafide"])
    body = tmpl.format(name=name, school=school, cls=cls, date=date, ay=ay)

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
    pdf.set_xy(120, 24);  pdf.cell(80, 5, f"Date: {date}", align="R")

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


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/certificate")
async def generate_certificate(request: Request):
    user = get_current_user(request)
    if user["role"] not in ("admin", "owner"):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

    cert_type = data.get("cert_type", "bonafide")
    title = CERT_LABELS.get(cert_type, "Certificate")
    prompt = _cert_prompt(cert_type, title)
    bg = await _gemini_image(prompt, aspect_ratio="3:4")

    pdf_bytes = _build_cert_pdf(data, bg)
    student = data.get("student_name", "certificate").replace(" ", "-")
    filename = f"{title.replace(' ', '-')}-{student}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/id-cards")
async def generate_id_cards(request: Request):
    user = get_current_user(request)
    if user["role"] not in ("admin", "owner"):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Invalid JSON"})

    students = data.get("students", [])
    school = data.get("school_name", "School")
    ay = data.get("academic_year", "")

    if not students:
        return JSONResponse(status_code=400, content={"detail": "No students provided"})

    prompt = _id_card_prompt(school)
    bg = await _gemini_image(prompt, aspect_ratio="16:9")

    pdf_bytes = _build_id_cards_pdf(students, school, ay, bg)
    filename = f"ID-Cards-{datetime.now().strftime('%Y-%m-%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
