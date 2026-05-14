"""AI write-dispatch rate limiter.

Hourly clock-window counters keyed by (user_id, session_id, hour_bucket).
Per-role defaults live in backend/config/ai_rate_limits.yaml; operators may
raise a school's ceiling via the ai_rate_limit_overrides collection.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "ai_rate_limits.yaml"

# Module-level cache (file mtime → parsed dict). Recomputed when the YAML file
# is touched so operators can adjust limits without a process restart.
_config_cache: dict[str, Any] = {"mtime": None, "data": None}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hour_bucket(now: datetime) -> str:
    """Return the UTC hour-bucket key for `now`, e.g. '2026-05-15T14:00:00Z'."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    truncated = now.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return truncated.strftime("%Y-%m-%dT%H:00:00Z")


def hour_bucket_start(bucket: str) -> datetime:
    """Inverse of hour_bucket — parse a bucket string back to its datetime."""
    return datetime.strptime(bucket, "%Y-%m-%dT%H:00:00Z").replace(tzinfo=timezone.utc)


def seconds_until_next_hour(now: datetime) -> int:
    """Seconds remaining until the next clock-hour boundary."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    return max(1, int((next_hour - now).total_seconds()))


def _load_yaml_defaults() -> dict[str, int]:
    """Read role limits from disk, caching by file mtime."""
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except FileNotFoundError:
        logger.error("ai_rate_limits.yaml missing at %s — using empty defaults", CONFIG_PATH)
        return {}

    if _config_cache["mtime"] == mtime and _config_cache["data"] is not None:
        return _config_cache["data"]

    try:
        with open(CONFIG_PATH, "r") as f:
            parsed = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        logger.exception("Failed to parse ai_rate_limits.yaml — using empty defaults")
        return _config_cache["data"] or {}

    roles = parsed.get("roles") or {}
    if not isinstance(roles, dict):
        logger.error("ai_rate_limits.yaml: 'roles' is not a mapping")
        roles = {}

    cleaned = {str(k): int(v) for k, v in roles.items() if isinstance(v, (int, float))}
    _config_cache["mtime"] = mtime
    _config_cache["data"] = cleaned
    return cleaned


def reset_config_cache() -> None:
    """Test helper — force the next call to re-read disk."""
    _config_cache["mtime"] = None
    _config_cache["data"] = None


async def resolve_limit(
    *,
    role: str,
    school_id: Optional[str],
    db,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> int:
    """Resolve the effective hourly limit for a role+school.

    Operator overrides win over YAML defaults. An override with an expired
    `expires_at` is ignored. A `None` school_id falls straight to YAML defaults.
    """
    defaults = _load_yaml_defaults()
    default_limit = int(defaults.get(role, 0))

    if not school_id:
        return default_limit

    now = (now_fn or _now)()
    query = {
        "school_id": school_id,
        "role": role,
        "superseded": {"$ne": True},
        "$or": [{"expires_at": None}, {"expires_at": {"$gt": now}}],
    }
    try:
        cursor = db.ai_rate_limit_overrides.find(query)
        cursor = cursor.sort("created_at", -1)
        rows = await cursor.to_list(1)
    except AttributeError:
        # Collection missing on legacy fake DBs — fall back to defaults.
        return default_limit
    except Exception:
        logger.exception("ai_rate_limit_overrides lookup failed for school=%s role=%s", school_id, role)
        return default_limit

    if rows:
        return int(rows[0].get("limit", default_limit))
    return default_limit


@dataclass
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int
    bucket: str

    def to_response_payload(self) -> dict[str, Any]:
        return {
            "success": False,
            "error": "rate_limit_exceeded",
            "retry_after_seconds": self.retry_after_seconds,
            "limit": self.limit,
            "window": "hour",
        }


async def increment_and_check(
    *,
    user_id: str,
    role: str,
    school_id: Optional[str],
    db,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> RateLimitResult:
    """Atomically increment the user-hour counter and decide allow/deny.

    Counter is scoped to (user_id, hour_bucket) — NOT per session — to prevent
    a malicious client from rotating session_id and creating fresh counter
    rows to bypass the limit. Session context is captured in audit log rows
    for forensics.

    A role with a limit of 0 always rejects. A non-listed role falls back to
    the YAML default for that role (also typically 0 — fail closed).

    To avoid unbounded counter inflation past the limit (which would skew the
    operator dashboard), we first read the current count and skip the $inc
    when the user is already at or past the ceiling.
    """
    nf = now_fn or _now
    now = nf()
    bucket = hour_bucket(now)
    bucket_dt = hour_bucket_start(bucket)
    expires_at = bucket_dt + timedelta(minutes=65)
    retry_secs = seconds_until_next_hour(now)

    limit = await resolve_limit(role=role, school_id=school_id, db=db, now_fn=nf)

    if limit <= 0:
        return RateLimitResult(
            allowed=False,
            count=0,
            limit=limit,
            retry_after_seconds=retry_secs,
            bucket=bucket,
        )

    key = {"user_id": user_id, "hour_bucket": bucket}

    # Pre-check: if already at the limit, do NOT increment further. This is
    # a deliberate TOCTOU window — the worst case is `limit + N_concurrent`
    # rows past the ceiling, which is bounded and acceptable.
    existing = await db.ai_rate_limit_counters.find_one(key)
    existing_count = int((existing or {}).get("count", 0))
    if existing_count >= limit:
        return RateLimitResult(
            allowed=False,
            count=existing_count,
            limit=limit,
            retry_after_seconds=retry_secs,
            bucket=bucket,
        )

    update = {
        "$inc": {"count": 1},
        "$setOnInsert": {"expires_at": expires_at, "created_at": now, "role": role},
    }

    new_count: Optional[int] = None
    find_one_and_update = getattr(db.ai_rate_limit_counters, "find_one_and_update", None)
    if callable(find_one_and_update):
        try:
            from pymongo import ReturnDocument

            doc = await find_one_and_update(
                key,
                update,
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            if isinstance(doc, dict):
                new_count = int(doc.get("count", 1))
        except Exception:
            logger.exception("find_one_and_update failed; falling back to update+find")

    if new_count is None:
        await db.ai_rate_limit_counters.update_one(key, update, upsert=True)
        doc = await db.ai_rate_limit_counters.find_one(key)
        new_count = int((doc or {}).get("count", 1))

    return RateLimitResult(
        allowed=new_count <= limit,
        count=new_count,
        limit=limit,
        retry_after_seconds=retry_secs,
        bucket=bucket,
    )


async def get_current_count(
    *,
    user_id: str,
    db,
    session_id: Optional[str] = None,
    now_fn: Optional[Callable[[], datetime]] = None,
) -> dict[str, Any]:
    """Read-only — return the current-hour count for a user.

    `session_id` is accepted for back-compat with Story 7-43's dashboard but
    is purely informational — counters are scoped per (user_id, hour_bucket).
    """
    bucket = hour_bucket((now_fn or _now)())
    doc = await db.ai_rate_limit_counters.find_one({
        "user_id": user_id,
        "hour_bucket": bucket,
    })
    return {
        "user_id": user_id,
        "session_id": session_id,
        "hour_bucket": bucket,
        "count": int((doc or {}).get("count", 0)),
    }
