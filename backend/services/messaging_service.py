"""Parent messaging service — the ONE write path for sending WhatsApp/SMS to families.

Both the REST panels (`routes/messaging.py`) and Flo's `send_parent_message` tool call
`send_messages(...)`, so a message Flo sends and a message a staff member sends are
produced by identical code. The parity gate in `tests/backend/parity/` enforces this.

Three facts drive the design, and each is a real-world constraint, not a preference:

1. **WhatsApp wording is not ours to choose.** Meta requires business-initiated
   WhatsApp messages to use a pre-approved template, referenced by a Twilio Content
   SID, with only numbered variables filled in. So a WhatsApp template here stores a
   `twilio_template_sid` plus an ordered `variables` list; its `body` is a LOCAL
   PREVIEW of the approved wording, shown on the confirm card so a human can see what
   will land — editing that body changes the preview, never what Meta sends. This is
   surprising enough that `update_message_template` says so out loud.

2. **SMS wording is ours entirely.** Free text, placeholders substituted locally, no
   approval. This is the channel that can honour "say it like this instead".

3. **Sending cannot be undone.** Every send is gated on explicit human confirmation,
   bounded by a per-request cap and a per-school daily cap, and written to
   `message_logs` one row per recipient — so "what did we send that family?" is
   answerable afterwards.

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter, scoped_query

logger = logging.getLogger(__name__)

# Per-request recipient cap. Deliberately env-tunable and defaulted ABOVE the school's
# current roll (1,876 on 2026-08-08) because the owner chose whole-school sends. It is
# a runaway-guard, not a policy limit — no student count is hardcoded anywhere; the
# recipient list is always counted live at send time.
MAX_RECIPIENTS_PER_SEND = int(os.environ.get("MESSAGING_MAX_RECIPIENTS", "2500"))

# Per-school daily ceiling across every channel, shared with the legacy SMS routes.
DAILY_CAP = int(os.environ.get("SMS_DAILY_CAP_PER_SCHOOL", "1000"))

CHANNELS = ("whatsapp", "sms")

AUDIENCES = (
    "students",            # explicit student_ids
    "class",               # every family in one class
    "fee_defaulters",      # families with outstanding fees
    "attendance_defaulters",  # families below the attendance threshold this month
    "all",                 # every active student's family
)

ATTENDANCE_THRESHOLD_PCT = 75.0

# Placeholders a template body may use. Anything else is left untouched rather than
# blanked, so a typo is visible on the confirm card instead of silently vanishing.
PLACEHOLDERS = (
    "guardian_name", "student_name", "class_section",
    "amount", "attendance_pct", "school_name", "date",
)

_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


class MessagingValidationError(Exception):
    """Bad input (unknown channel/audience, missing template, empty body) → HTTP 400."""


class MessagingNotConfiguredError(Exception):
    """The channel's provider credentials are absent → HTTP 503.

    Raised rather than silently recording 'not_configured' and reporting success —
    that is exactly the failure mode this service exists to remove.
    """


class MessagingLimitError(Exception):
    """A per-request or per-school cap would be exceeded → HTTP 429."""


def _session_kwargs(session) -> dict:
    return _txn_session_kwargs(session)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Channel configuration ───────────────────────────────────────────────────

def whatsapp_config() -> dict:
    return {
        "account_sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "auth_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "from_number": os.environ.get("TWILIO_WHATSAPP_FROM", ""),
    }


def sms_config() -> dict:
    return {
        "account_sid": os.environ.get("TWILIO_ACCOUNT_SID", ""),
        "auth_token": os.environ.get("TWILIO_AUTH_TOKEN", ""),
        "from_number": os.environ.get("TWILIO_PHONE_NUMBER", ""),
    }


def channel_status(channel: str) -> dict:
    """Report whether a channel can actually send, and what is missing if not.

    Surfaced by `GET /api/messaging/status` and by Flo, so "why did nothing arrive?"
    has an answer before anyone presses send rather than after.
    """
    cfg = whatsapp_config() if channel == "whatsapp" else sms_config()
    missing = []
    if not cfg["account_sid"] or cfg["account_sid"].startswith("your_"):
        missing.append("TWILIO_ACCOUNT_SID")
    if not cfg["auth_token"]:
        missing.append("TWILIO_AUTH_TOKEN")
    if not cfg["from_number"]:
        missing.append("TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_PHONE_NUMBER")
    return {"channel": channel, "ready": not missing, "missing": missing}


def get_twilio_client():
    cfg = sms_config()
    if not cfg["account_sid"] or not cfg["auth_token"] or cfg["account_sid"].startswith("your_"):
        return None
    from twilio.rest import Client

    return Client(cfg["account_sid"], cfg["auth_token"])


def normalize_phone(phone: str) -> str:
    """Normalize to E.164, assuming India when no country code is present."""
    p = (phone or "").strip().replace(" ", "").replace("-", "")
    if not p:
        return ""
    if p.startswith("+"):
        return p
    return "+91" + p.lstrip("0")


# ─── Templates ───────────────────────────────────────────────────────────────

def render(body: str, recipient: dict, *, school_name: str = "The Aaryans") -> str:
    """Substitute {placeholders} from a recipient. Unknown names are left as-is."""
    values = {
        "guardian_name": recipient.get("guardian_name") or "Parent",
        "student_name": recipient.get("student_name") or "your child",
        "class_section": recipient.get("class_section") or "",
        "amount": recipient.get("amount") or "",
        "attendance_pct": recipient.get("attendance_pct") or "",
        "school_name": school_name,
        "date": _now().strftime("%d %b %Y"),
    }

    def _sub(m):
        key = m.group(1)
        return str(values[key]) if key in values else m.group(0)

    return _PLACEHOLDER_RE.sub(_sub, body or "")


async def list_templates(db, actor_ctx: ActorContext, *, channel: str = "") -> list:
    q = {}
    if channel:
        q["channel"] = channel
    rows = await db.message_templates.find(
        scoped_filter(q, actor_ctx.school_id), {"_id": 0}
    ).to_list(200)
    return sorted(rows, key=lambda r: (r.get("channel", ""), r.get("name", "")))


async def get_template(db, actor_ctx: ActorContext, template_ref: str) -> Optional[dict]:
    """Find a template by id, or case-insensitively by name."""
    if not template_ref:
        return None
    row = await db.message_templates.find_one(
        scoped_filter({"id": template_ref}, actor_ctx.school_id), {"_id": 0}
    )
    if row:
        return row
    return await db.message_templates.find_one(
        scoped_filter(
            {"name": {"$regex": f"^{re.escape(template_ref)}$", "$options": "i"}},
            actor_ctx.school_id,
        ),
        {"_id": 0},
    )


def _validate_template_fields(channel: str, body: str, twilio_template_sid: str) -> None:
    if channel not in CHANNELS:
        raise MessagingValidationError(f"channel must be one of {', '.join(CHANNELS)}.")
    if not (body or "").strip():
        raise MessagingValidationError("The message wording cannot be empty.")
    if len(body) > 1600:
        raise MessagingValidationError("The message wording must be 1600 characters or fewer.")
    if channel == "whatsapp" and not (twilio_template_sid or "").strip():
        raise MessagingValidationError(
            "A WhatsApp template needs its Meta-approved Twilio template SID "
            "(twilio_template_sid). WhatsApp does not permit free-text wording for "
            "messages a business starts."
        )


async def create_template(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    name = (params.get("name") or "").strip()
    if not name:
        raise MessagingValidationError("name is required.")
    channel = (params.get("channel") or "sms").strip().lower()
    body = params.get("body") or ""
    sid = params.get("twilio_template_sid") or ""
    _validate_template_fields(channel, body, sid)

    if await get_template(db, actor_ctx, name):
        raise MessagingValidationError(f"A template named '{name}' already exists.")

    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "name": name,
        "channel": channel,
        "body": body,
        "twilio_template_sid": sid,
        # Ordered placeholder names mapped onto Twilio's numbered variables {{1}}, {{2}}…
        "variables": list(params.get("variables") or []),
        "description": params.get("description") or "",
        "is_builtin": False,
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }
    await db.message_templates.insert_one(doc, **_session_kwargs(session))
    public = {k: v for k, v in doc.items() if k != "_id"}
    await _audit(db, actor_ctx, "create", doc["id"], {"name": name, "channel": channel})
    return {"template": public}


async def update_template(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    ref = params.get("template_id") or params.get("name") or ""
    existing = await get_template(db, actor_ctx, ref)
    if not existing:
        raise MessagingValidationError(f"No message template found for '{ref}'.")

    channel = (params.get("channel") or existing.get("channel") or "sms").strip().lower()
    body = params.get("body") if params.get("body") is not None else existing.get("body", "")
    sid = (
        params.get("twilio_template_sid")
        if params.get("twilio_template_sid") is not None
        else existing.get("twilio_template_sid", "")
    )
    _validate_template_fields(channel, body, sid)

    updates = {
        "channel": channel,
        "body": body,
        "twilio_template_sid": sid,
        "updated_by": actor_ctx.user_id,
        "updated_at": actor_ctx.now_iso(),
    }
    if params.get("name"):
        updates["name"] = params["name"].strip()
    if params.get("variables") is not None:
        updates["variables"] = list(params["variables"])
    if params.get("description") is not None:
        updates["description"] = params["description"]

    await db.message_templates.update_one(
        scoped_filter({"id": existing["id"]}, actor_ctx.school_id),
        {"$set": updates},
        **_session_kwargs(session),
    )
    await _audit(db, actor_ctx, "update", existing["id"], {"name": updates.get("name", existing.get("name"))})

    result = {**existing, **updates}
    # The single most misleading thing this system can do is let someone "fix" WhatsApp
    # wording and believe parents will see the change. Say so at the point of the edit.
    note = ""
    if channel == "whatsapp":
        note = (
            "Saved — but note this only changes the PREVIEW shown before sending. The "
            "wording WhatsApp actually delivers lives in the approved template at Twilio "
            f"({sid or 'no SID set'}) and can only be changed there, with Meta's re-approval."
        )
    return {"template": result, "note": note}


async def delete_template(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    ref = params.get("template_id") or params.get("name") or ""
    existing = await get_template(db, actor_ctx, ref)
    if not existing:
        raise MessagingValidationError(f"No message template found for '{ref}'.")
    await db.message_templates.delete_one(
        scoped_filter({"id": existing["id"]}, actor_ctx.school_id),
        **_session_kwargs(session),
    )
    await _audit(db, actor_ctx, "delete", existing["id"], {"name": existing.get("name")})
    return {"deleted": True, "id": existing["id"], "name": existing.get("name", "")}


async def submit_whatsapp_template_for_approval(
    db, actor_ctx: ActorContext, params: dict, *, session=None
) -> dict:
    """Create a WhatsApp template at Twilio and submit it to Meta for approval.

    This is the ONLY honest way to "change the WhatsApp wording": new wording is a new
    approved template, not an edit to an existing one. Twilio's Content API does the
    creation over plain HTTP — no extra automation service is needed — but the wait for
    Meta's decision is Meta's, and cannot be engineered away. Approval is usually
    minutes and occasionally a day, and Meta can reject wording that looks promotional.

    The template is stored locally as `approval_status: pending` and is deliberately NOT
    usable for sending until `refresh_whatsapp_template_status` sees it approved.
    """
    name = (params.get("name") or "").strip()
    body = (params.get("body") or "").strip()
    if not name or not body:
        raise MessagingValidationError("name and body are required.")
    variables = list(params.get("variables") or [])

    cfg = whatsapp_config()
    if not cfg["account_sid"] or not cfg["auth_token"]:
        raise MessagingNotConfiguredError(
            "Twilio credentials are missing, so a new WhatsApp template cannot be "
            "submitted for approval."
        )

    # Twilio numbers its variables {{1}}, {{2}}… — translate our named placeholders.
    twilio_body = body
    for i, var in enumerate(variables):
        twilio_body = twilio_body.replace("{" + var + "}", "{{" + str(i + 1) + "}}")

    import httpx

    payload = {
        "friendly_name": re.sub(r"[^a-z0-9_]+", "_", name.lower())[:64],
        "language": params.get("language") or "en",
        "variables": {str(i + 1): var for i, var in enumerate(variables)},
        "types": {"twilio/text": {"body": twilio_body}},
    }
    async with httpx.AsyncClient(timeout=30) as http:
        created = await http.post(
            "https://content.twilio.com/v1/Content",
            json=payload,
            auth=(cfg["account_sid"], cfg["auth_token"]),
        )
        if created.status_code >= 300:
            raise MessagingValidationError(
                f"Twilio would not accept this template ({created.status_code}): "
                f"{created.text[:300]}"
            )
        content_sid = created.json().get("sid", "")

        approval = await http.post(
            f"https://content.twilio.com/v1/Content/{content_sid}/ApprovalRequests/whatsapp",
            json={"name": payload["friendly_name"],
                  "category": params.get("category") or "UTILITY"},
            auth=(cfg["account_sid"], cfg["auth_token"]),
        )
        approval_state = (
            approval.json().get("status", "pending")
            if approval.status_code < 300 else "submission_failed"
        )

    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "name": name,
        "channel": "whatsapp",
        "body": body,
        "twilio_template_sid": content_sid,
        "variables": variables,
        "description": params.get("description") or "",
        "approval_status": approval_state,
        "is_builtin": False,
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }
    await db.message_templates.insert_one(doc, **_session_kwargs(session))
    await _audit(db, actor_ctx, "submit_for_approval", doc["id"],
                 {"name": name, "content_sid": content_sid, "status": approval_state})
    return {
        "template": {k: v for k, v in doc.items() if k != "_id"},
        "message": (
            f"Submitted '{name}' to WhatsApp for approval (status: {approval_state}). "
            "It cannot be used for sending until Meta approves it — usually minutes, "
            "sometimes a day. Ask me to check its status."
        ),
    }


async def refresh_whatsapp_template_status(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Ask Twilio where a submitted WhatsApp template stands with Meta."""
    ref = params.get("template_id") or params.get("template_name") or params.get("name") or ""
    tpl = await get_template(db, actor_ctx, ref)
    if not tpl:
        raise MessagingValidationError(f"No message template found for '{ref}'.")
    sid = tpl.get("twilio_template_sid")
    if not sid:
        raise MessagingValidationError(f"'{tpl.get('name')}' has no Twilio template SID.")

    cfg = whatsapp_config()
    if not cfg["account_sid"] or not cfg["auth_token"]:
        raise MessagingNotConfiguredError("Twilio credentials are missing.")

    import httpx

    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.get(
            f"https://content.twilio.com/v1/Content/{sid}/ApprovalRequests",
            auth=(cfg["account_sid"], cfg["auth_token"]),
        )
    if resp.status_code >= 300:
        raise MessagingValidationError(f"Twilio could not be reached ({resp.status_code}).")
    state = ((resp.json() or {}).get("whatsapp") or {}).get("status", "unknown")

    await db.message_templates.update_one(
        scoped_filter({"id": tpl["id"]}, actor_ctx.school_id),
        {"$set": {"approval_status": state}},
    )
    return {"name": tpl.get("name", ""), "approval_status": state,
            "usable": state == "approved",
            "message": f"'{tpl.get('name')}' is currently: {state}."}


async def _audit(db, actor_ctx: ActorContext, action: str, entity_id: str, changes: dict) -> None:
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "message_template",
            "entity_id": entity_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role or "",
            "changes": changes,
            "timestamp": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
    )


# ─── Recipient resolution ────────────────────────────────────────────────────

async def _class_map(db, actor_ctx: ActorContext, class_ids: list) -> dict:
    ids = [c for c in set(class_ids) if c]
    if not ids:
        return {}
    rows = await db.classes.find(
        # branch-scope: intentional — pinned by unique ids already narrowed to this
        # actor's students, so a branch filter could only turn a real row into a miss.
        scoped_filter({"id": {"$in": ids}}, actor_ctx.school_id),
        {"_id": 0, "id": 1, "name": 1, "section": 1},
    ).to_list(500)
    return {r["id"]: r for r in rows}


def _class_section(student: dict, cls: dict) -> str:
    section = (cls or {}).get("section") or student.get("section") or ""
    name = (cls or {}).get("name", "")
    return "-".join(p for p in (name, section) if p)


async def resolve_recipients(db, actor_ctx: ActorContext, params: dict) -> list:
    """Turn an audience spec into a concrete, de-duplicated recipient list.

    Shared by the preview (what the confirm card counts) and the send, so the number a
    person approves is produced by the same code that later does the sending.
    """
    audience = (params.get("audience") or "students").strip().lower()
    if audience not in AUDIENCES:
        raise MessagingValidationError(f"audience must be one of {', '.join(AUDIENCES)}.")
    bid = actor_ctx.branch_id

    student_ids: list = []
    extras: dict = {}

    if audience == "students":
        student_ids = [s for s in (params.get("student_ids") or []) if s]
        if not student_ids and params.get("student_id"):
            student_ids = [params["student_id"]]
        if not student_ids:
            raise MessagingValidationError("student_ids is required when audience is 'students'.")

    elif audience == "class":
        class_id = params.get("class_id")
        if not class_id:
            raise MessagingValidationError("class_id is required when audience is 'class'.")
        rows = await db.students.find(
            scoped_query({"class_id": class_id}, branch_id=bid), {"_id": 0, "id": 1}
        ).to_list(MAX_RECIPIENTS_PER_SEND)
        student_ids = [r["id"] for r in rows]

    elif audience == "fee_defaulters":
        txns = await db.fee_transactions.find(
            scoped_query({"status": {"$in": ["pending", "overdue", "unpaid"]}}, branch_id=bid),
            {"_id": 0, "student_id": 1, "amount": 1},
        ).to_list(20000)
        owed: dict = {}
        for t in txns:
            sid = t.get("student_id")
            if sid:
                owed[sid] = owed.get(sid, 0) + float(t.get("amount") or 0)
        student_ids = list(owed.keys())
        extras = {sid: {"amount": f"{amt:,.0f}"} for sid, amt in owed.items()}

    elif audience == "attendance_defaulters":
        month_start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        recs = await db.student_attendance.find(
            scoped_query({"date": {"$gte": month_start.isoformat()[:10]}}, branch_id=bid),
            {"_id": 0, "student_id": 1, "status": 1},
        ).to_list(100000)
        tally: dict = {}
        for r in recs:
            sid = r.get("student_id")
            if not sid:
                continue
            t = tally.setdefault(sid, {"present": 0, "total": 0})
            t["total"] += 1
            if r.get("status") == "present":
                t["present"] += 1
        for sid, t in tally.items():
            if t["total"] and (t["present"] / t["total"] * 100) < ATTENDANCE_THRESHOLD_PCT:
                student_ids.append(sid)
                extras[sid] = {"attendance_pct": round(t["present"] / t["total"] * 100, 1)}

    elif audience == "all":
        rows = await db.students.find(
            scoped_query({"status": {"$ne": "inactive"}}, branch_id=bid), {"_id": 0, "id": 1}
        ).to_list(MAX_RECIPIENTS_PER_SEND)
        student_ids = [r["id"] for r in rows]

    student_ids = list(dict.fromkeys(student_ids))
    if not student_ids:
        return []

    students = await db.students.find(
        scoped_query({"id": {"$in": student_ids}}, branch_id=bid),
        {"_id": 0, "id": 1, "name": 1, "class_id": 1, "section": 1,
         "phone": 1, "whatsapp_phone": 1, "father_phone": 1, "mother_phone": 1,
         "guardian_phone": 1},
    ).to_list(MAX_RECIPIENTS_PER_SEND)
    smap = {s["id"]: s for s in students}

    guardians = await db.guardians.find(
        scoped_filter({"student_id": {"$in": student_ids}}, actor_ctx.school_id),
        {"_id": 0, "student_id": 1, "name": 1, "phone": 1, "whatsapp_phone": 1, "is_primary": 1},
    ).to_list(MAX_RECIPIENTS_PER_SEND * 3)
    gmap: dict = {}
    for g in guardians:
        sid = g.get("student_id")
        if sid and (sid not in gmap or g.get("is_primary")):
            gmap[sid] = g

    cmap = await _class_map(db, actor_ctx, [s.get("class_id") for s in students])

    recipients = []
    seen_phones = set()
    for sid in student_ids:
        s = smap.get(sid)
        if not s:
            continue
        g = gmap.get(sid, {})
        phone = normalize_phone(
            g.get("whatsapp_phone") or g.get("phone")
            or s.get("whatsapp_phone") or s.get("guardian_phone")
            or s.get("father_phone") or s.get("mother_phone") or s.get("phone") or ""
        )
        if not phone:
            continue
        # One message per number: siblings sharing a guardian's phone would otherwise
        # get the same notice two or three times in a row.
        if phone in seen_phones:
            continue
        seen_phones.add(phone)
        rec = {
            "student_id": sid,
            "student_name": s.get("name", ""),
            "guardian_name": g.get("name") or "Parent",
            "class_section": _class_section(s, cmap.get(s.get("class_id"))),
            "phone": phone,
        }
        rec.update(extras.get(sid, {}))
        recipients.append(rec)
    return recipients


# ─── Preview + send ──────────────────────────────────────────────────────────

async def preview(db, actor_ctx: ActorContext, params: dict) -> dict:
    """What a send WOULD do. Powers the confirm card; performs no writes."""
    channel = (params.get("channel") or "sms").strip().lower()
    if channel not in CHANNELS:
        raise MessagingValidationError(f"channel must be one of {', '.join(CHANNELS)}.")

    recipients = await resolve_recipients(db, actor_ctx, params)
    body, template = await _resolve_body(db, actor_ctx, params, channel)
    sample = render(body, recipients[0]) if recipients else render(body, {})
    return {
        "channel": channel,
        "audience": params.get("audience") or "students",
        "recipient_count": len(recipients),
        "sample_message": sample,
        "sample_to": recipients[0]["phone"] if recipients else "",
        "template_name": (template or {}).get("name", ""),
        "status": channel_status(channel),
        "recipients": recipients,
    }


async def _resolve_body(db, actor_ctx: ActorContext, params: dict, channel: str):
    """Return (body, template). Free text is SMS-only; WhatsApp must use a template."""
    template = None
    if params.get("template_id") or params.get("template_name"):
        template = await get_template(
            db, actor_ctx, params.get("template_id") or params.get("template_name")
        )
        if not template:
            raise MessagingValidationError(
                f"No message template found for "
                f"'{params.get('template_id') or params.get('template_name')}'."
            )
        # A template awaiting Meta's decision would be rejected at the provider for
        # every recipient. Refuse the whole batch here rather than log 1,876 failures.
        state = template.get("approval_status")
        if template.get("channel") == "whatsapp" and state and state != "approved":
            raise MessagingValidationError(
                f"'{template.get('name')}' is still {state} with WhatsApp and cannot be "
                "used yet. Use an approved template, or send this as an SMS."
            )
        return template.get("body", ""), template

    body = (params.get("body") or "").strip()
    if not body:
        raise MessagingValidationError("Either template_name or body is required.")
    if channel == "whatsapp":
        raise MessagingValidationError(
            "WhatsApp cannot send free-typed wording — Meta requires a pre-approved "
            "template. Pick a WhatsApp template by name, or send this as an SMS."
        )
    return body, None


async def _check_daily_cap(db, actor_ctx: ActorContext, new_count: int) -> None:
    today = _now().strftime("%Y-%m-%d")
    sent_today = await db.message_logs.count_documents(
        {"schoolId": actor_ctx.school_id, "sent_at": {"$regex": f"^{today}"}}
    )
    if sent_today + new_count > DAILY_CAP:
        raise MessagingLimitError(
            f"This would pass the school's daily limit of {DAILY_CAP} messages "
            f"({sent_today} already sent today). Raise SMS_DAILY_CAP_PER_SCHOOL or "
            f"send the rest tomorrow."
        )


async def send_messages(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Send to every resolved recipient and write one `message_logs` row each.

    Returns counts plus a short per-recipient log. Never raises for an individual
    delivery failure — one bad number must not abort the other 1,800.
    """
    channel = (params.get("channel") or "sms").strip().lower()
    if channel not in CHANNELS:
        raise MessagingValidationError(f"channel must be one of {', '.join(CHANNELS)}.")

    status = channel_status(channel)
    if not status["ready"]:
        raise MessagingNotConfiguredError(
            f"{channel.upper()} is not configured on this server — missing "
            f"{', '.join(status['missing'])}. Nothing was sent."
        )

    recipients = params.get("_recipients")
    if recipients is None:
        recipients = await resolve_recipients(db, actor_ctx, params)
    if not recipients:
        return {"sent": 0, "failed": 0, "recipient_count": 0, "logs": [],
                "message": "No families matched — nothing was sent."}

    if len(recipients) > MAX_RECIPIENTS_PER_SEND:
        raise MessagingLimitError(
            f"{len(recipients)} recipients exceeds the {MAX_RECIPIENTS_PER_SEND} "
            f"per-send limit. Narrow the audience or raise MESSAGING_MAX_RECIPIENTS."
        )
    await _check_daily_cap(db, actor_ctx, len(recipients))

    body, template = await _resolve_body(db, actor_ctx, params, channel)
    client = get_twilio_client()
    cfg = whatsapp_config() if channel == "whatsapp" else sms_config()
    from_number = cfg["from_number"]
    batch_id = str(uuid.uuid4())

    results = {"sent": 0, "failed": 0, "recipient_count": len(recipients),
               "batch_id": batch_id, "logs": []}

    for r in recipients:
        text = render(body, r)
        state, sid, err = "sent", None, None
        try:
            if channel == "whatsapp":
                variables = {
                    str(i + 1): str(r.get(name, ""))
                    for i, name in enumerate((template or {}).get("variables") or [])
                }
                msg = client.messages.create(
                    from_=f"whatsapp:{from_number}",
                    to=f"whatsapp:{r['phone']}",
                    content_sid=(template or {}).get("twilio_template_sid", ""),
                    content_variables=__import__("json").dumps(variables),
                )
            else:
                msg = client.messages.create(body=text, from_=from_number, to=r["phone"])
            sid = getattr(msg, "sid", None)
            results["sent"] += 1
        except Exception as exc:  # one bad number must not abort the batch
            state, err = "failed", str(exc)
            results["failed"] += 1
            logger.warning("message_send_failed student_id=%s channel=%s error=%s",
                           r.get("student_id"), channel, exc)

        log = {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "branch_id": actor_ctx.branch_id or "",
            "batch_id": batch_id,
            "channel": channel,
            "template_name": (template or {}).get("name", ""),
            "student_id": r.get("student_id", ""),
            "student_name": r.get("student_name", ""),
            "guardian_name": r.get("guardian_name", ""),
            "phone": r["phone"],
            "body": text,
            "status": state,
            "provider_sid": sid,
            "error": err,
            "sent_by": actor_ctx.user_id,
            "sent_by_name": actor_ctx.actor_name,
            "sent_at": actor_ctx.now_iso(),
            "created_at": _now(),
        }
        await db.message_logs.insert_one(log, **_session_kwargs(session))
        results["logs"].append({k: v for k, v in log.items() if k != "_id"})

    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "message_batch",
            "entity_id": batch_id,
            "action": "send_parent_message",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role or "",
            "changes": {
                "channel": channel,
                "audience": params.get("audience") or "students",
                "template": (template or {}).get("name", ""),
                "recipient_count": len(recipients),
                "sent": results["sent"],
                "failed": results["failed"],
            },
            "timestamp": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
    )

    results["message"] = (
        f"Sent {results['sent']} of {len(recipients)} {channel.upper()} messages"
        + (f" — {results['failed']} failed." if results["failed"] else ".")
    )
    return results
