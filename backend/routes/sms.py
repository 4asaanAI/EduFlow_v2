from fastapi import APIRouter, Request, HTTPException
from database import get_db
from datetime import datetime
import os
import uuid

router = APIRouter(prefix="/api/sms", tags=["sms"])


def get_user(req: Request):
    return {
        "id": req.headers.get("X-User-Id", "user-admin-001"),
        "role": req.headers.get("X-User-Role", "admin"),
        "name": req.headers.get("X-User-Name", "Admin"),
    }


def get_twilio_client():
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    if not account_sid or not auth_token or account_sid == "your_twilio_account_sid":
        return None
    from twilio.rest import Client
    return Client(account_sid, auth_token)


@router.post("/send-reminder")
async def send_fee_reminder(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")

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
    }
    await db.sms_logs.insert_one({**log, "_id": log["id"]})

    if sms_status == "failed":
        raise HTTPException(500, f"SMS failed: {error_msg}")

    return {"success": True, "data": log}


@router.post("/send-bulk")
async def send_bulk_reminders(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")

    body = await request.json()
    recipients = body.get("recipients", [])   # [{student_id, phone, student_name, amount}]
    message_template = body.get("message_template", "")

    if not recipients:
        raise HTTPException(400, "No recipients provided")

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
        }
        await db.sms_logs.insert_one({**log, "_id": log["id"]})
        results["logs"].append(log)

    return {"success": True, "data": results}


@router.get("/logs")
async def get_sms_logs(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    logs = await db.sms_logs.find({}, {"_id": 0}).sort("sent_at", -1).to_list(100)
    return {"success": True, "data": logs}


@router.get("/config-status")
async def get_config_status(request: Request):
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
    configured = bool(sid and token and phone and sid != "your_twilio_account_sid")
    return {
        "success": True,
        "data": {
            "configured": configured,
            "phone_number": phone if configured else None,
        }
    }
