from __future__ import annotations

"""R4-5 - telling Layaa AI that the platform itself is broken.

--------------------------------------------------------------------------------
What this is, and what it is NOT
--------------------------------------------------------------------------------

The school already has an issue tracker: ``routes/issues.py`` holds facility requests
for the maintenance person and tech requests for the IT person. Both stay inside the
school. Neither is this.

This is the route OUT. When something is wrong with the platform and neither the staff
nor Flo can fix it, the school tells us, and it reaches us without anybody telephoning.
It is a third kind of issue in the same tracker, not a second tracker.

Three things follow from that, and they are the whole design:

1. **Anyone may raise one.** Owner down to student. A student is the person most likely
   to be first to see a screen that will not load, and a report we refused to accept is
   a fault we find out about a week later. There is deliberately no permission gate on
   raising a ticket. (Reading other people's tickets is gated; raising your own is not.)

2. **It is written down here BEFORE it is sent.** A ticket that only exists once Layaa
   AI acknowledges it is a ticket that vanishes whenever the connection does, and the
   person is told it failed while believing they reported it. The local record is the
   truth; delivery is a property of that record which can be retried and can be seen.

3. **It is never raised silently.** The person who raised it gets a reference back and
   can see its state. Flo raising one on somebody's behalf is still shown to them.

--------------------------------------------------------------------------------
The part that is not code
--------------------------------------------------------------------------------

The hard problem in R4-5 is teaching Flo WHEN NOT to raise one. A ticket for something
the receptionist could have fixed in ten seconds trains everybody to ignore tickets, and
then the one that mattered is ignored too. That judgement lives in the tool description
Flo reads (``ai/tool_functions_v2.py``) and in :data:`WHEN_NOT_TO_RAISE` below, which is
quoted into it so there is one wording rather than two that drift apart.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services import audit_changes
from services.audit_service import write_audit_doc
from services.layaastat import tickets as layaastat_tickets
from tenant import add_school_id, get_school_id, scoped_query

logger = logging.getLogger(__name__)

COLLECTION = "platform_tickets"

# Matches LayaaStat's `ticket_kind`. An unknown value is corrected rather than refused,
# for the same reason it is corrected at the other end: a vocabulary mismatch between
# two versions must never cost us a real report.
KINDS = ("bug", "incident", "support", "feedback")
PRIORITIES = ("low", "normal", "high", "urgent")

MAX_TITLE = 200
MAX_DETAIL = 20_000
# ~5 MB of image. base64 inflates by a third, so the encoded string is allowed to be
# larger than the picture. The ceiling exists because images are the quiet cost in this
# release; the same 5 MB is enforced again at the LayaaStat end, on the decoded bytes.
MAX_SCREENSHOT_CHARS = 7_000_000


class PlatformTicketError(Exception):
    """Something about the request itself is wrong. The message is shown to a person."""


# Quoted verbatim into Flo's tool description, so the rule Flo reads and the rule
# written down here can never drift apart.
WHEN_NOT_TO_RAISE = (
    "Do NOT raise a ticket when the school can fix it themselves. Try first, and say what "
    "you tried. Things that are NOT tickets: somebody cannot find a screen (show them "
    "where it is); somebody is refused a screen their profile does not include (explain "
    "who can do it); a report looks empty because a filter or a date range is set (tell "
    "them which one); a password or a sign-in problem (the owner can reset it); a request "
    "for a feature that does not exist (say it does not exist); data that is wrong because "
    "somebody typed it wrong (help them correct it). Raise a ticket only when the platform "
    "itself is not doing what it is supposed to do and nobody at the school can put it "
    "right. If you are unsure, ask the person whether they want it reported rather than "
    "deciding for them."
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Optional[str], limit: int) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:limit]


def _public(doc: Dict[str, Any]) -> Dict[str, Any]:
    """A ticket as the school sees it. Never returns the dict that was inserted.

    ``insert_one`` stamps Mongo's ``_id`` into the caller's dict IN PLACE, and an
    ObjectId is not JSON, so echoing the inserted dict raises AFTER the write has
    committed and tells the sender the opposite of what happened. That cost a live
    failure on every staff message send on 12 August; it is not repeated here.
    """
    return {k: v for k, v in doc.items() if k not in ("_id", "screenshot_base64")}


async def raise_ticket(
    db,
    user: Dict[str, Any],
    *,
    title: str,
    detail: Optional[str] = None,
    kind: str = "support",
    priority: str = "normal",
    raised_by_assistant: bool = False,
    context: Optional[Dict[str, Any]] = None,
    app_url: Optional[str] = None,
    screenshot_base64: Optional[str] = None,
    screenshot_mime: Optional[str] = None,
) -> Dict[str, Any]:
    """Record a problem and send it to Layaa AI. The ONE path; REST and Flo both use it.

    Returns the saved ticket plus a plain sentence about what happened to it. Raises
    :class:`PlatformTicketError` only when the request itself is unusable; a delivery
    that failed is a successful outcome with ``delivered`` False, because the report
    exists and can be sent again.
    """
    clean_title = _clean(title, MAX_TITLE)
    if not clean_title:
        raise PlatformTicketError("Please say in one line what is wrong.")
    clean_detail = _clean(detail, MAX_DETAIL)

    if kind not in KINDS:
        kind = "support"
    if priority not in PRIORITIES:
        priority = "normal"

    shot = screenshot_base64 if isinstance(screenshot_base64, str) and screenshot_base64.strip() else None
    screenshot_too_big = bool(shot) and len(shot) > MAX_SCREENSHOT_CHARS
    if screenshot_too_big:
        # Dropped, and SAID. The person looked at that picture before pressing send, so
        # silently discarding it would leave them believing we can see what they saw.
        shot = None

    ticket_id = str(uuid.uuid4())
    doc = add_school_id({
        "_id": ticket_id,
        "id": ticket_id,
        "type": "platform",
        "title": clean_title,
        "detail": clean_detail,
        "kind": kind,
        "priority": priority,
        "source": "assistant" if raised_by_assistant else "person",
        "context": dict(context or {}),
        "app_url": _clean(app_url, 500),
        "raised_by": user.get("id"),
        "raised_by_name": user.get("name", ""),
        "raised_by_role": user.get("role"),
        "raised_by_sub_category": user.get("sub_category"),
        "branch_id": user.get("branch_id", ""),
        "had_screenshot": bool(shot),
        # Local state, which is about US and this school. The state at Layaa AI's end is
        # theirs and is not mirrored here: two copies of one status is how a ticket comes
        # to be closed in one place and open in the other.
        "status": "open",
        "delivered": False,
        "delivery_reason": None,
        "delivery_attempts": 0,
        "last_attempt_at": None,
        "layaastat_reference": None,
        "layaastat_number": None,
        "created_at": _now(),
        "updated_at": _now(),
    })

    # ── 1. Write it down. If this fails, nothing was reported and we say so. ──────
    await db.platform_tickets.insert_one(doc)

    # ── 2. Record the change, like every other action (R4-2). ────────────────────
    # `created` and not `edit`: nothing existed before, so there is no previous value,
    # and claiming one would be the exact dishonesty R4-1 exists to end.
    await _audit(db, user, "platform_ticket_raise", ticket_id, audit_changes.created({
        "title": clean_title,
        "kind": kind,
        "priority": priority,
        "source": doc["source"],
    }))

    # ── 3. Send it. Failure here never unmakes the ticket. ───────────────────────
    result = await _attempt_delivery(db, doc, screenshot_base64=shot, screenshot_mime=screenshot_mime)

    saved = await db.platform_tickets.find_one({"id": ticket_id}, {"_id": 0})
    out = dict(saved or _public(doc))
    out["message"] = _message_for(result, screenshot_too_big=screenshot_too_big)
    out["screenshot_dropped_too_large"] = screenshot_too_big
    return out


async def resend_ticket(db, user: Dict[str, Any], ticket_id: str) -> Dict[str, Any]:
    """Try again to deliver a ticket that is already recorded here.

    The screenshot is NOT re-sent: it was never kept in the school's database (only the
    fact that there was one). Re-sending would mean storing every picture twice, here
    and at Layaa AI, which is the most expensive possible way to keep one image. The
    reply says so plainly rather than letting anyone assume the picture went the second
    time.
    """
    doc = await db.platform_tickets.find_one(scoped_query({"id": ticket_id}, branch_id=user.get("branch_id")))
    if not doc:
        raise PlatformTicketError("That ticket could not be found.")
    if doc.get("delivered"):
        return {**_public(doc), "message": "This ticket already reached Layaa AI, so nothing was sent again."}

    result = await _attempt_delivery(db, doc, screenshot_base64=None, screenshot_mime=None)
    await _audit(db, user, "platform_ticket_resend", ticket_id, audit_changes.none(
        "A ticket that had not reached Layaa AI was sent again. Nothing about the ticket "
        "itself changed, only whether it has been delivered."
    ))
    saved = await db.platform_tickets.find_one({"id": ticket_id}, {"_id": 0})
    out = dict(saved or _public(doc))
    note = "" if result.get("delivered") else " The picture that came with it was not kept here, so it was not sent again."
    out["message"] = _message_for(result, screenshot_too_big=False) + (note if doc.get("had_screenshot") else "")
    return out


async def list_tickets(
    db,
    user: Dict[str, Any],
    *,
    mine_only: bool,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
) -> Dict[str, Any]:
    """Tickets this person may see, newest first, with the true total beside them.

    ``mine_only`` is decided by the CALLER from the permission table, never here, so
    there is one place that answers "who may see everybody's tickets".
    """
    query: Dict[str, Any] = {}
    if mine_only:
        query["raised_by"] = user.get("id")
    if status:
        query["status"] = status
    scoped = scoped_query(query, branch_id=user.get("branch_id"))

    total = await db.platform_tickets.count_documents(scoped)
    items = await (
        db.platform_tickets
        .find(scoped, {"_id": 0, "screenshot_base64": 0})
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    # The total is returned alongside so a page can never be mistaken for the whole
    # list. That is the Release 3 rule and it applies to a new table on the day it is
    # created, not once somebody notices.
    return {"items": items, "total": total}


async def _attempt_delivery(
    db,
    doc: Dict[str, Any],
    *,
    screenshot_base64: Optional[str],
    screenshot_mime: Optional[str],
) -> Dict[str, Any]:
    """Send once and record the outcome on the ticket. Never raises."""
    payload = layaastat_tickets.build_payload(
        title=doc["title"],
        detail=doc.get("detail"),
        kind=doc.get("kind", "support"),
        priority=doc.get("priority", "normal"),
        source=doc.get("source", "person"),
        reporter_name=doc.get("raised_by_name") or None,
        reporter_role=_role_words(doc),
        context=_context_for_layaastat(doc),
        app_url=doc.get("app_url"),
        # The school's own id for this report is what makes a retry land once at the
        # other end instead of creating a second copy of the same problem.
        external_ref=doc["id"],
        screenshot_base64=screenshot_base64,
        screenshot_mime=screenshot_mime,
    )

    result = await layaastat_tickets.send_ticket(payload)

    update = {
        "delivered": bool(result.get("delivered")),
        "delivery_reason": result.get("reason"),
        "delivery_code": result.get("code"),
        "last_attempt_at": _now(),
        "updated_at": _now(),
    }
    if result.get("delivered"):
        update["layaastat_reference"] = result.get("reference")
        update["layaastat_number"] = result.get("ticket_number")
        update["screenshot_stored_at_layaa"] = bool(result.get("screenshot_stored"))
    try:
        await db.platform_tickets.update_one({"id": doc["id"]}, {"$set": update, "$inc": {"delivery_attempts": 1}})
    except Exception:
        # The ticket exists and may well have been delivered. Failing to write down that
        # it was delivered is worth a loud log and nothing more: raising here would
        # report a failure for a ticket that actually arrived.
        logger.exception("platform ticket delivery state not saved ticket=%s", doc["id"])
    return result


def _role_words(doc: Dict[str, Any]) -> Optional[str]:
    """A role in words for whoever reads the ticket at our end."""
    role = doc.get("raised_by_role")
    sub = doc.get("raised_by_sub_category")
    if not role:
        return None
    return f"{role} ({sub})" if sub else str(role)


def _context_for_layaastat(doc: Dict[str, Any]) -> Dict[str, Any]:
    """What travelled with the report, plus the two facts we always want.

    Deliberately built from the ticket rather than passed through from the caller, so a
    field cannot be dropped by one entrance and included by the other. `school` is the
    school's own id and is a belt-and-braces label only: the tenant a ticket belongs to
    is decided by the ingest key, never by anything in the body.
    """
    ctx = dict(doc.get("context") or {})
    ctx.setdefault("school", get_school_id())
    if doc.get("had_screenshot"):
        ctx.setdefault("screenshot", "the person sent a picture of their screen")
    return ctx


def _message_for(result: Dict[str, Any], *, screenshot_too_big: bool) -> str:
    """One sentence for the person who pressed the button. No jargon, no codes."""
    parts: List[str] = []
    if result.get("delivered"):
        number = result.get("ticket_number")
        parts.append(
            f"Reported to Layaa AI as ticket {number}." if number else "Reported to Layaa AI."
        )
        if result.get("screenshot_rejected"):
            parts.append("The picture of your screen could not be saved, so describe what you saw in words if you can.")
    else:
        parts.append("Saved here, but it has not reached Layaa AI yet.")
        reason = result.get("reason")
        if reason:
            parts.append(reason)
        parts.append("Nothing has been lost and it can be sent again.")
    if screenshot_too_big:
        parts.append("The picture of your screen was too large to send, so it was left out.")
    return " ".join(parts)


async def _audit(db, user: Dict[str, Any], action: str, ticket_id: str, changes: Dict[str, Any]) -> None:
    """One audit row, in the R4-1 shape. Never hand-build a `changes` dict."""
    await write_audit_doc(
        db,
        add_school_id({
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "entity_type": COLLECTION,
            "entity_id": ticket_id,
            "action": action,
            "changed_by": user.get("id"),
            "changed_by_name": user.get("name", ""),
            "changed_by_role": user.get("role"),
            "collection": COLLECTION,
            "changes": changes,
            "created_at": _now(),
        }),
        school_id=get_school_id(),
        branch_id=user.get("branch_id", ""),
    )
