"""AI-write kill-switch (AI Layer Hardening, Story F.4 / AD9).

A school operator can disable ALL AI writes instantly during the pilot. The flag
lives in `db.system_flags` keyed `ai_writes_enabled`; the executor path checks it
before committing any write. Reads are never gated.

A short-TTL in-process cache (≤60s) bounds how stale a flag read can be — the AC
requires "rejects writes within ≤60s" of the operator flipping it — while keeping
the steady-state hot path free of a per-confirm Mongo round-trip. Flipping the
flag OFF takes effect on the next cache expiry (≤`CACHE_TTL_SECONDS`).

`time.monotonic()` is used for the cache clock (not `datetime.now()`) so it is
immune to wall-clock adjustments and is trivially monkeypatchable in tests.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

FLAG_KEY = "ai_writes_enabled"
CACHE_TTL_SECONDS = 30  # ≤60s staleness bound required by F.4

# (value, monotonic_expiry). Module-level so it is shared across requests in a worker.
_cache: Tuple[Optional[bool], float] = (None, 0.0)


def _monotonic() -> float:
    return time.monotonic()


def reset_cache() -> None:
    """Drop the cached flag — used by tests and by an explicit operator override."""
    global _cache
    _cache = (None, 0.0)


async def ai_writes_enabled(db) -> bool:
    """Return whether AI writes are currently enabled (default: enabled).

    Fail-OPEN: if the flag doc is absent we treat writes as enabled (the kill
    switch is opt-in — a school that never set it should not be blocked). A Mongo
    error also fails open but is logged loudly; the kill switch is a safety brake,
    not an availability dependency, and a stuck-closed brake would be its own
    incident.
    """
    global _cache
    cached_value, expiry = _cache
    now = _monotonic()
    if cached_value is not None and now < expiry:
        return cached_value

    enabled = True
    try:
        doc = await db.system_flags.find_one({"key": FLAG_KEY})
        if doc is not None and doc.get("enabled") is False:
            enabled = False
    except Exception:
        logger.warning("ai_writes_enabled flag read failed — failing open", exc_info=True)
        enabled = True

    _cache = (enabled, now + CACHE_TTL_SECONDS)
    return enabled


async def set_ai_writes_enabled(db, *, enabled: bool, actor_id: str = "", school_id: Optional[str] = None) -> None:
    """Operator helper to flip the kill-switch and immediately invalidate the cache."""
    doc = {"key": FLAG_KEY, "enabled": bool(enabled)}
    if school_id is not None:
        doc["schoolId"] = school_id
    await db.system_flags.update_one(
        {"key": FLAG_KEY},
        {"$set": {**doc, "updated_by": actor_id}},
        upsert=True,
    )
    reset_cache()
