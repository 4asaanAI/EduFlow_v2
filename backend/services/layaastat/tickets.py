from __future__ import annotations

"""R4-5 - sending a ticket from the school to Layaa AI.

Why this is not part of ``LayaaMonitor``
--------------------------------------------------------------------------------

The monitor buffers telemetry, flushes it later, retries in the background and drops a
batch it cannot deliver. Every one of those behaviours is right for telemetry and wrong
for a ticket:

- **Buffered** means the ticket sits in memory until twenty more events happen. A school
  reporting that fees are broken at four o'clock on a Friday would have it delivered on
  Monday, or not at all if the server restarts first.
- **Dropped on failure** means the report is lost with only a log line to show for it.
  That is exactly what happened to every product event for weeks under D-41.
- **No result to the caller** means the person is told "sent" either way.

So a ticket is sent immediately, once, and the OUTCOME IS RETURNED. The caller has
already written the ticket down locally before calling this, so a failure here is a
delivery to retry, never a report that never existed.

The key
--------------------------------------------------------------------------------

Reuses ``LAYAASTAT_INGEST_KEY``, which is tenant-bound: the key alone decides which
client the ticket is filed against, and nothing this module sends can override it. That
is deliberate. A field in the body naming the school would be a field that could be
wrong.
"""

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Ten seconds, not the five the telemetry client uses. A ticket may carry a screenshot
# of up to five megabytes, and a slow upload that is cut off looks to the sender exactly
# like a platform that ignored them.
_TIMEOUT_SECONDS = 10.0


def is_enabled() -> bool:
    """True when there is somewhere to send a ticket and a key to send it with."""
    return bool(os.environ.get("LAYAASTAT_URL") and os.environ.get("LAYAASTAT_INGEST_KEY"))


async def send_ticket(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST one ticket to LayaaStat. Never raises.

    Returns a dict that always carries ``delivered`` (bool) and ``reason`` (a sentence
    a person can read), plus ``reference`` and ``ticket_number`` when it worked.

    The reason is written for a human because it is shown to one. "not_configured" on a
    screen tells a receptionist nothing; "this school's copy of the platform has not
    been given an address to send tickets to" tells them to telephone us instead.
    """
    endpoint = os.environ.get("LAYAASTAT_URL")
    key = os.environ.get("LAYAASTAT_INGEST_KEY")
    if not endpoint or not key:
        return {
            "delivered": False,
            "reason": "This school's platform has not been set up to send tickets to Layaa AI yet.",
            "code": "not_configured",
        }

    url = endpoint.rstrip("/") + "/api/tickets"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"x-ingest-key": key, "content-type": "application/json"},
            )
    except Exception as exc:  # network, DNS, timeout, missing httpx
        logger.warning("layaastat ticket send failed url=%s", url, exc_info=True)
        return {
            "delivered": False,
            "reason": "Layaa AI could not be reached just now. The ticket is saved here and can be sent again.",
            "code": "unreachable",
            "detail": str(exc)[:200],
        }

    if resp.status_code < 300:
        try:
            body = resp.json()
        except Exception:
            body = {}
        return {
            "delivered": True,
            # 200 rather than 201 means LayaaStat already had this ticket. Reported as
            # delivered, because it is: the report reached us. Saying otherwise would
            # make a person send it a third time.
            "duplicate": bool(body.get("duplicate")),
            "reason": "Sent to Layaa AI.",
            "reference": body.get("id"),
            "ticket_number": body.get("number"),
            "screenshot_stored": bool(body.get("screenshot_stored")),
            # Reported rather than swallowed: the sender looked at that picture before
            # pressing send, so they will assume it went.
            "screenshot_rejected": bool(body.get("screenshot_rejected")),
            "people_notified": body.get("notified", 0),
        }

    # 4xx is a permanent refusal: a bad key, or a body LayaaStat will not accept. Sending
    # it again unchanged will be refused again, so say so rather than invite a retry.
    permanent = 400 <= resp.status_code < 500 and resp.status_code != 429
    return {
        "delivered": False,
        "reason": (
            "Layaa AI refused this ticket, so something needs fixing at our end before it can be sent."
            if permanent else
            "Layaa AI is having trouble just now. The ticket is saved here and can be sent again."
        ),
        "code": "refused" if permanent else "unavailable",
        "status": resp.status_code,
        "detail": (resp.text or "")[:200],
    }


def build_payload(
    *,
    title: str,
    detail: Optional[str],
    kind: str,
    priority: str,
    source: str,
    reporter_name: Optional[str],
    reporter_role: Optional[str],
    context: Dict[str, Any],
    app_url: Optional[str],
    external_ref: str,
    screenshot_base64: Optional[str] = None,
    screenshot_mime: Optional[str] = None,
) -> Dict[str, Any]:
    """Shape one ticket for LayaaStat's inbox.

    ``external_ref`` is the school's own id for the report and is what makes a re-send
    land once. It is required, not optional: without it a retry after a timeout creates
    a second copy of the same problem and we work both.
    """
    payload: Dict[str, Any] = {
        "title": title,
        "detail": detail,
        "kind": kind,
        "priority": priority,
        "source": source,
        "reporter_name": reporter_name,
        "reporter_role": reporter_role,
        "context": context,
        "app_url": app_url,
        "external_ref": external_ref,
    }
    if screenshot_base64:
        payload["screenshot_base64"] = screenshot_base64
        payload["screenshot_mime"] = screenshot_mime or "image/png"
    return payload
