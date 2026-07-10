from __future__ import annotations
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import get_current_user, require_role, require_owner_or_accountant, require_owner_or_principal
from tenant import get_school_id, scoped_filter, scoped_query
from datetime import datetime, timezone
import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sms", tags=["sms"])

# Per-school daily SMS send cap (configurable via env var; default 1000)
SMS_DAILY_CAP = int(os.environ.get("SMS_DAILY_CAP_PER_SCHOOL", "1000"))


def get_user(req: Request):
    return get_current_user(req)


async def _check_daily_cap(db, school_id: str, new_count: int) -> None:
    """Raise 429 if adding new_count messages would exceed the daily school cap."""
    today = datetime.now().strftime("%Y-%m-%d")
    sent_today = await db.sms_logs.count_documents(
        {"schoolId": school_id, "sent_at": {"$regex": f"^{today}"}}
    )
    if sent_today + new_count > SMS_DAILY_CAP:
        raise HTTPException(429, f"Daily SMS limit of {SMS_DAILY_CAP} reached for this school")


def get_twilio_client():
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not account_sid or not auth_token or account_sid == "your_twilio_account_sid":
        return None
    from twilio.rest import Client
    return Client(account_sid, auth_token)


def _normalize_whatsapp_phone(phone: str) -> str:
    """Normalize a phone number to E.164 format for WhatsApp (no whatsapp: prefix)."""
    normalized = phone.strip().replace(" ", "").replace("-", "")
    if not normalized.startswith("+"):
        normalized = "+91" + normalized.lstrip("0")
    return normalized


def _send_whatsapp_template(
    client,
    whatsapp_from: str,
    to_phone: str,
    template_sid: str,
    variables: dict,
) -> str:
    """Send a Twilio Content Template message via WhatsApp. Returns message SID."""
    msg = client.messages.create(
        from_=f"whatsapp:{whatsapp_from}",
        to=f"whatsapp:{to_phone}",
        content_sid=template_sid,
        content_variables=json.dumps({str(k): str(v) for k, v in variables.items()}),
    )
    return msg.sid


@router.post("/send-reminder")
async def send_fee_reminder(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    body = await request.json()
    student_id = body.get("student_id")
    phone = body.get("phone")
    message_text = body.get("message")
    student_name = body.get("student_name", "Student")
    amount = body.get("amount", "")

    if not phone:
        raise HTTPException(400, "Phone number is required")
    if not message_text:
        raise HTTPException(400, "Message is required")

    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
    client = get_twilio_client()

    sms_status = "sent"
    sms_sid = None
    error_msg = None

    if client and twilio_phone:
        try:
            # Normalize phone number - add country code if missing
            normalized_phone = phone.strip()
            if not normalized_phone.startswith("+"):
                normalized_phone = "+91" + normalized_phone.lstrip("0")

            msg = client.messages.create(
                body=message_text,
                from_=twilio_phone,
                to=normalized_phone
            )
            sms_sid = msg.sid
            sms_status = "sent"
        except Exception as e:
            sms_status = "failed"
            error_msg = str(e)
    else:
        sms_status = "not_configured"
        error_msg = "Twilio credentials not configured"

    # Log every attempt regardless of outcome
    log = {
        "schoolId": get_school_id(),
        "id": str(uuid.uuid4()),
        "student_id": student_id,
        "student_name": student_name,
        "phone": phone,
        "message": message_text,
        "amount": amount,
        "sent_by": user["id"],
        "sent_by_name": user["name"],
        "status": sms_status,
        "sms_sid": sms_sid,
        "error": error_msg,
        "sent_at": datetime.now().isoformat(),
        "created_at": datetime.now(timezone.utc),  # Native datetime for TTL index
    }
    await db.sms_logs.insert_one({**log, "_id": log["id"]})

    if sms_status == "failed":
        raise HTTPException(500, f"SMS failed: {error_msg}")

    return {"success": True, "data": log}


@router.post("/send-bulk")
async def send_bulk_reminders(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    recipients = body.get("recipients", [])   # [{student_id, phone, student_name, amount}]
    message_template = body.get("message_template", "")

    if not recipients:
        raise HTTPException(400, "No recipients provided")
    if len(recipients) > 500:
        raise HTTPException(400, "Bulk SMS is limited to 500 recipients per request")

    # Validate student_ids belong to caller's school (and branch for branch-bound users)
    student_ids_in = [r.get("student_id") for r in recipients if r.get("student_id")]
    if student_ids_in:
        valid_students = await db.students.find(
            scoped_query({"id": {"$in": student_ids_in}}, branch_id=bid),
            {"_id": 0, "id": 1},
        ).to_list(500)
        valid_ids = {s["id"] for s in valid_students}
        recipients = [r for r in recipients if not r.get("student_id") or r.get("student_id") in valid_ids]
        if not recipients:
            raise HTTPException(400, "No valid recipients found in this school/branch")

    await _check_daily_cap(db, get_school_id(), len(recipients))

    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
    client = get_twilio_client()

    results = {"sent": 0, "failed": 0, "not_configured": 0, "logs": []}

    for r in recipients:
        phone = r.get("phone", "")
        student_name = r.get("student_name", "Student")
        amount = r.get("amount", "")
        student_id = r.get("student_id", "")

        # Personalize message
        msg_text = message_template.replace("{name}", student_name).replace("{amount}", str(amount))

        sms_status = "sent"
        sms_sid = None
        error_msg = None

        if client and twilio_phone and phone:
            try:
                normalized_phone = phone.strip()
                if not normalized_phone.startswith("+"):
                    normalized_phone = "+91" + normalized_phone.lstrip("0")

                msg = client.messages.create(
                    body=msg_text,
                    from_=twilio_phone,
                    to=normalized_phone
                )
                sms_sid = msg.sid
                results["sent"] += 1
            except Exception as e:
                sms_status = "failed"
                error_msg = str(e)
                results["failed"] += 1
        else:
            sms_status = "not_configured"
            error_msg = "Twilio not configured"
            results["not_configured"] += 1

        log = {
            "schoolId": get_school_id(),
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "student_name": student_name,
            "phone": phone,
            "message": msg_text,
            "amount": amount,
            "sent_by": user["id"],
            "status": sms_status,
            "sms_sid": sms_sid,
            "error": error_msg,
            "sent_at": datetime.now().isoformat(),
            "created_at": datetime.now(timezone.utc),  # Native datetime for TTL index
        }
        await db.sms_logs.insert_one({**log, "_id": log["id"]})
        results["logs"].append(log)

    return {"success": True, "data": results}


@router.post("/send-parent-message")
async def send_parent_message(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    """Send SMS to parents of selected students via Twilio."""
    db = get_db()
    bid = user.get("branch_id")
    body = await request.json()
    student_ids = body.get("student_ids", [])
    message_text = body.get("message", "").strip()

    if not student_ids:
        raise HTTPException(400, "No students selected")
    if len(student_ids) > 500:
        raise HTTPException(400, "Bulk SMS is limited to 500 students per request")
    if not message_text:
        raise HTTPException(400, "Message is required")

    # Pre-validate all student_ids belong to caller's school/branch
    valid_students_list = await db.students.find(
        scoped_query({"id": {"$in": student_ids}}, branch_id=bid),
        {"_id": 0, "id": 1},
    ).to_list(500)
    valid_ids = {s["id"] for s in valid_students_list}
    student_ids = [sid for sid in student_ids if sid in valid_ids]
    if not student_ids:
        raise HTTPException(400, "No valid students found in this school/branch")

    await _check_daily_cap(db, get_school_id(), len(student_ids))

    twilio_phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
    client = get_twilio_client()

    results = {"sent": 0, "failed": 0, "no_phone": 0, "not_configured": 0, "logs": []}

    for sid in student_ids:
        student = await db.students.find_one(scoped_query({"id": sid}, branch_id=bid), {"_id": 0})
        if not student:
            continue

        # Look up guardian phone as primary contact
        guardian = await db.guardians.find_one({"student_id": sid}, {"_id": 0})
        phone = (guardian or {}).get("phone") or student.get("phone") or ""

        if not phone:
            results["no_phone"] += 1
            log = {
                "schoolId": get_school_id(),
                "id": str(uuid.uuid4()),
                "student_id": sid,
                "student_name": student.get("name", ""),
                "phone": "",
                "message": message_text,
                "sent_by": user["id"],
                "sent_by_name": user["name"],
                "status": "no_phone",
                "error": "No phone number on record",
                "sent_at": datetime.now().isoformat(),
                "created_at": datetime.now(timezone.utc),  # Native datetime for TTL index
            }
            await db.sms_logs.insert_one({**log, "_id": log["id"]})
            results["logs"].append(log)
            continue

        sms_status = "sent"
        sms_sid = None
        error_msg = None

        if client and twilio_phone:
            try:
                normalized = phone.strip()
                if not normalized.startswith("+"):
                    normalized = "+91" + normalized.lstrip("0")
                msg = client.messages.create(body=message_text, from_=twilio_phone, to=normalized)
                sms_sid = msg.sid
                results["sent"] += 1
            except Exception as e:
                sms_status = "failed"
                error_msg = str(e)
                results["failed"] += 1
        else:
            sms_status = "not_configured"
            error_msg = "Twilio credentials not configured"
            results["not_configured"] += 1

        log = {
            "schoolId": get_school_id(),
            "id": str(uuid.uuid4()),
            "student_id": sid,
            "student_name": student.get("name", ""),
            "phone": phone,
            "message": message_text,
            "sent_by": user["id"],
            "sent_by_name": user["name"],
            "status": sms_status,
            "sms_sid": sms_sid,
            "error": error_msg,
            "sent_at": datetime.now().isoformat(),
            "created_at": datetime.now(timezone.utc),  # Native datetime for TTL index
        }
        await db.sms_logs.insert_one({**log, "_id": log["id"]})
        results["logs"].append(log)

    return {"success": True, "data": results}


@router.get("/logs")
async def get_sms_logs(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    bid = user.get("branch_id")
    logs = await db.sms_logs.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("sent_at", -1).to_list(100)
    return {"success": True, "data": logs}


@router.get("/config-status")
async def get_config_status(request: Request, user: dict = Depends(require_role("admin", "owner"))):
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
    configured = bool(sid and token and phone and sid != "your_twilio_account_sid")

    wa_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    fee_sid = os.environ.get("TWILIO_WHATSAPP_FEE_TEMPLATE_SID", "")
    att_sid = os.environ.get("TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID", "")
    whatsapp_configured = bool(sid and token and wa_from and fee_sid and att_sid and sid != "your_twilio_account_sid")

    return {
        "success": True,
        "data": {
            "configured": configured,
            "phone_number": phone if configured else None,
            "whatsapp_configured": whatsapp_configured,
            "whatsapp_from": wa_from if whatsapp_configured else None,
        }
    }


# ─── WhatsApp endpoints ───────────────────────────────────────────────────────

@router.get("/whatsapp-defaulters")
async def get_whatsapp_defaulters(request: Request, user: dict = Depends(require_owner_or_accountant)):
    """Return fee defaulters + attendance defaulters with guardian phone numbers."""
    db = get_db()
    branch_id = user.get("branch_id")
    school_id = get_school_id()

    # Fee defaulters — students with any outstanding transaction this school year
    fee_query = scoped_query(
        {"status": {"$in": ["pending", "overdue", "unpaid"]}},
        branch_id=branch_id,
    )
    txns = await db.fee_transactions.find(fee_query, {"_id": 0, "student_id": 1, "amount": 1}).to_list(2000)
    fee_student_ids = list({t["student_id"] for t in txns if t.get("student_id")})

    # Attendance defaulters — students with attendance < 75% for the current month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    att_query = scoped_query(
        {"date": {"$gte": month_start.isoformat()[:10]}},
        branch_id=branch_id,
    )
    att_records = await db.student_attendance.find(att_query, {"_id": 0, "student_id": 1, "status": 1}).to_list(10000)

    student_att: dict[str, dict[str, int]] = {}
    for rec in att_records:
        sid = rec.get("student_id")
        if not sid:
            continue
        bucket = student_att.setdefault(sid, {"present": 0, "total": 0})
        bucket["total"] += 1
        if rec.get("status") == "present":
            bucket["present"] += 1

    att_student_ids = [
        sid for sid, counts in student_att.items()
        if counts["total"] > 0 and (counts["present"] / counts["total"]) < 0.75
    ]

    all_student_ids = list(set(fee_student_ids) | set(att_student_ids))
    if not all_student_ids:
        return {"success": True, "data": {"fee_defaulters": [], "attendance_defaulters": []}}

    # Batch fetch students
    students = await db.students.find(
        scoped_query({"id": {"$in": all_student_ids}}, branch_id=branch_id),
        {"_id": 0, "id": 1, "name": 1, "class_id": 1, "section": 1, "phone": 1},
    ).to_list(2000)
    student_map = {s["id"]: s for s in students}

    # Batch fetch guardians
    guardians = await db.guardians.find(
        {"student_id": {"$in": all_student_ids}, "schoolId": school_id},
        {"_id": 0, "student_id": 1, "name": 1, "phone": 1},
    ).to_list(2000)
    guardian_map = {g["student_id"]: g for g in guardians}

    # Aggregate outstanding amounts per student
    student_outstanding: dict[str, float] = {}
    for t in txns:
        sid = t.get("student_id")
        if sid:
            student_outstanding[sid] = student_outstanding.get(sid, 0) + float(t.get("amount") or 0)

    def _build_entry(sid: str, extra: dict | None = None) -> dict | None:
        s = student_map.get(sid)
        if not s:
            return None
        g = guardian_map.get(sid, {})
        phone = g.get("phone") or s.get("phone") or ""
        if not phone:
            return None
        entry = {
            "student_id": sid,
            "student_name": s.get("name", ""),
            "class_section": f"{s.get('class_id', '')} {s.get('section', '')}".strip(),
            "guardian_name": g.get("name", "Parent"),
            "phone": phone,
        }
        if extra:
            entry.update(extra)
        return entry

    fee_defaulters = [
        e for sid in fee_student_ids
        if (e := _build_entry(sid, {"outstanding_amount": student_outstanding.get(sid, 0)})) is not None
    ]
    attendance_defaulters = [
        e for sid in att_student_ids
        if (e := _build_entry(
            sid,
            {"attendance_pct": round(student_att[sid]["present"] / student_att[sid]["total"] * 100, 1)}
        )) is not None
    ]

    return {
        "success": True,
        "data": {
            "fee_defaulters": fee_defaulters,
            "attendance_defaulters": attendance_defaulters,
        },
    }


@router.post("/whatsapp-fee-reminders")
async def send_whatsapp_fee_reminders(
    request: Request, user: dict = Depends(require_owner_or_accountant)
):
    """Send WhatsApp fee reminder to a list of fee defaulters using Twilio Content Template."""
    db = get_db()
    body = await request.json()
    recipients = body.get("recipients", [])  # [{student_id, student_name, guardian_name, phone, class_section, outstanding_amount}]

    if not recipients:
        raise HTTPException(400, "No recipients provided")
    if len(recipients) > 500:
        raise HTTPException(400, "Bulk WhatsApp is limited to 500 recipients per request")

    wa_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    template_sid = os.environ.get("TWILIO_WHATSAPP_FEE_TEMPLATE_SID", "")
    client = get_twilio_client()
    whatsapp_ready = bool(client and wa_from and template_sid)

    results = {"sent": 0, "failed": 0, "not_configured": 0, "logs": []}

    for r in recipients:
        phone = r.get("phone", "")
        student_id = r.get("student_id", "")
        student_name = r.get("student_name", "Student")
        guardian_name = r.get("guardian_name", "Parent")
        class_section = r.get("class_section", "")
        amount = str(r.get("outstanding_amount", ""))

        wa_status = "sent"
        wa_sid = None
        error_msg = None

        if whatsapp_ready and phone:
            try:
                normalized = _normalize_whatsapp_phone(phone)
                wa_sid = _send_whatsapp_template(
                    client, wa_from, normalized, template_sid,
                    {"1": guardian_name, "2": student_name, "3": class_section, "4": amount},
                )
                results["sent"] += 1
            except Exception as exc:
                wa_status = "failed"
                error_msg = str(exc)
                results["failed"] += 1
                logger.warning("whatsapp_fee_reminder_failed student_id=%s error=%s", student_id, exc)
        else:
            wa_status = "not_configured"
            error_msg = "WhatsApp not configured" if not whatsapp_ready else "No phone number"
            results["not_configured"] += 1

        log = {
            "schoolId": get_school_id(),
            "id": str(uuid.uuid4()),
            "type": "whatsapp_fee_reminder",
            "student_id": student_id,
            "student_name": student_name,
            "phone": phone,
            "sent_by": user["id"],
            "sent_by_name": user.get("name", ""),
            "status": wa_status,
            "sms_sid": wa_sid,
            "error": error_msg,
            "sent_at": datetime.now().isoformat(),
            "created_at": datetime.now(timezone.utc),
        }
        await db.sms_logs.insert_one({**log, "_id": log["id"]})
        results["logs"].append(log)

    return {"success": True, "data": results}


@router.post("/whatsapp-attendance-alerts")
async def send_whatsapp_attendance_alerts(
    request: Request, user: dict = Depends(require_owner_or_principal)
):
    """Send WhatsApp attendance alert to a list of attendance defaulters using Twilio Content Template."""
    db = get_db()
    body = await request.json()
    recipients = body.get("recipients", [])  # [{student_id, student_name, guardian_name, phone, class_section, attendance_pct}]

    if not recipients:
        raise HTTPException(400, "No recipients provided")
    if len(recipients) > 500:
        raise HTTPException(400, "Bulk WhatsApp is limited to 500 recipients per request")

    wa_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    template_sid = os.environ.get("TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID", "")
    client = get_twilio_client()
    whatsapp_ready = bool(client and wa_from and template_sid)

    results = {"sent": 0, "failed": 0, "not_configured": 0, "logs": []}

    for r in recipients:
        phone = r.get("phone", "")
        student_id = r.get("student_id", "")
        student_name = r.get("student_name", "Student")
        guardian_name = r.get("guardian_name", "Parent")
        class_section = r.get("class_section", "")
        att_pct = str(r.get("attendance_pct", ""))

        wa_status = "sent"
        wa_sid = None
        error_msg = None

        if whatsapp_ready and phone:
            try:
                normalized = _normalize_whatsapp_phone(phone)
                wa_sid = _send_whatsapp_template(
                    client, wa_from, normalized, template_sid,
                    {"1": guardian_name, "2": student_name, "3": class_section, "4": att_pct},
                )
                results["sent"] += 1
            except Exception as exc:
                wa_status = "failed"
                error_msg = str(exc)
                results["failed"] += 1
                logger.warning("whatsapp_attendance_alert_failed student_id=%s error=%s", student_id, exc)
        else:
            wa_status = "not_configured"
            error_msg = "WhatsApp not configured" if not whatsapp_ready else "No phone number"
            results["not_configured"] += 1

        log = {
            "schoolId": get_school_id(),
            "id": str(uuid.uuid4()),
            "type": "whatsapp_attendance_alert",
            "student_id": student_id,
            "student_name": student_name,
            "phone": phone,
            "sent_by": user["id"],
            "sent_by_name": user.get("name", ""),
            "status": wa_status,
            "sms_sid": wa_sid,
            "error": error_msg,
            "sent_at": datetime.now().isoformat(),
            "created_at": datetime.now(timezone.utc),
        }
        await db.sms_logs.insert_one({**log, "_id": log["id"]})
        results["logs"].append(log)

    return {"success": True, "data": results}
