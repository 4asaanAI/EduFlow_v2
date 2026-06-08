"""Shadow / dry-run mode for AI writes (Story F.5 / AD9).

In shadow mode a confirmed plan runs its writes inside a transaction that is
**always aborted** — committing nothing — and reports the would-be effect (the
step results) so the pilot accumulates parity evidence at zero write-risk before
live writes are enabled. Post-commit saga/side-effect steps never fire (the txn
never commits), so SMS/email are not sent.

The flag lives in `db.system_flags` keyed `ai_dry_run` (school-wide), mirroring the
kill-switch (F.4). Same short-TTL cache bounds staleness while keeping the hot
path free of a per-confirm Mongo round-trip.

NOTE: the "commits nothing" guarantee depends on a real transactional Mongo
(replica set). On the non-transactional FakeDb test tier an aborted txn does not
roll back, so the true no-commit behaviour is proven on the `@pytest.mark.mongo_real`
tier (D.1); the unit tier asserts the wiring (flag → dry_run → reported diff,
side-effects skipped).
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

FLAG_KEY = "ai_dry_run"
CACHE_TTL_SECONDS = 30

_cache: Tuple[Optional[bool], float] = (None, 0.0)


def reset_cache() -> None:
    global _cache
    _cache = (None, 0.0)


async def ai_dry_run_enabled(db) -> bool:
    """Return whether shadow/dry-run mode is on (default: OFF — live writes)."""
    global _cache
    cached_value, expiry = _cache
    now = time.monotonic()
    if cached_value is not None and now < expiry:
        return cached_value

    enabled = False
    try:
        doc = await db.system_flags.find_one({"key": FLAG_KEY})
        if doc is not None and doc.get("enabled") is True:
            enabled = True
    except Exception:
        logger.warning("ai_dry_run flag read failed — defaulting to live writes", exc_info=True)
        enabled = False

    _cache = (enabled, now + CACHE_TTL_SECONDS)
    return enabled


async def set_ai_dry_run(db, *, enabled: bool, actor_id: str = "", school_id: Optional[str] = None) -> None:
    doc = {"key": FLAG_KEY, "enabled": bool(enabled)}
    if school_id is not None:
        doc["schoolId"] = school_id
    await db.system_flags.update_one(
        {"key": FLAG_KEY},
        {"$set": {**doc, "updated_by": actor_id}},
        upsert=True,
    )
    reset_cache()
