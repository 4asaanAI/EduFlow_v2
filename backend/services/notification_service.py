"""Canonical persistent notification writer."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import uuid

from tenant import add_school_id, get_school_id
from services.txn_context import session_kwargs

logger = logging.getLogger(__name__)


async def create_notification(
    db,
    *,
    user_id: str | None,
    notification_type: str,
    title: str = "",
    message: str,
    source_id: str = "",
    source_type: str = "",
    school_id: str | None = None,
) -> bool:
    """Create a notification without blocking the parent workflow on failure."""
    if not user_id:
        logger.warning(
            "notification_user_missing",
            extra={"notification_delivery_failed": True, "source_type": source_type, "source_id": source_id},
        )
        return False

    doc = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "title": title or message,
        "message": message,
        "source_record_id": source_id,
        "source_record_type": source_type,
        "read": False,
        # R15.4 (P-L1): persist a tz-aware UTC timestamp so notification ordering
        # and TTL comparisons are unambiguous across workers/timezones.
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, school_id or get_school_id())

    try:
        # AI Layer Hardening D-review: enlist in the AI plan executor's transaction
        # when one is active (ambient txn_context session) so a notification for a
        # write that gets rolled back is itself rolled back (AD14 — "a rolled-back
        # plan sends nothing"). Outside the executor this is {} → unchanged behavior.
        await db.notifications.insert_one(doc, **session_kwargs())
    except Exception:
        logger.warning(
            "notification_write_failed",
            extra={
                "notification_delivery_failed": True,
                "user_id": user_id,
                "source_type": source_type,
                "source_id": source_id,
            },
            exc_info=True,
        )
        return False
    return True


async def fan_out_notifications(
    db,
    user_ids,
    *,
    notification_type: str,
    title: str,
    message: str,
    source_id: str = "",
    source_type: str = "",
    school_id: str | None = None,
    concurrency: int = 10,
) -> dict[str, int]:
    semaphore = asyncio.Semaphore(concurrency)

    async def _send(user_id):
        async with semaphore:
            return await create_notification(
                db,
                user_id=user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                source_id=source_id,
                source_type=source_type,
                school_id=school_id,
            )

    results = await asyncio.gather(*[_send(user_id) for user_id in user_ids], return_exceptions=True)
    notifications_failed = sum(1 for result in results if result is False or isinstance(result, Exception))
    notifications_sent = len(results) - notifications_failed
    for result in results:
        if isinstance(result, Exception):
            logger.warning(
                "notification_fan_out_exception",
                extra={"notification_delivery_failed": True, "source_type": source_type, "source_id": source_id},
                exc_info=(type(result), result, result.__traceback__),
            )
    logger.info(
        "fan_out_complete",
        extra={"notifications_sent": notifications_sent, "notifications_failed": notifications_failed},
    )
    return {"sent": notifications_sent, "failed": notifications_failed}
