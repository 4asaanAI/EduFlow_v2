from __future__ import annotations

"""R4-5 - Flo notices the disk filling up before it stops the school working.

--------------------------------------------------------------------------------
Why this exists and why it is this small
--------------------------------------------------------------------------------

Release 4 records everything that changes. Recording everything is what fills a disk.
R4-3 is the cost control (two years in full, a monthly summary forever), and this is the
alarm that tells us whether R4-3 is keeping up, BEFORE the day the school cannot save an
attendance register.

Three constraints shaped it, and each one removed code rather than adding it:

1. **"Have it check on a schedule against figures already collected, not by thinking
   about the platform continuously"** (Release 4, Part 4a). So this reads MongoDB's own
   `dbStats`, which the database maintains anyway. It never scans a collection and never
   asks the language model anything. A check costs one command.

2. **"Measure before optimising. Get the real number before designing around a guess."**
   So when no ceiling is configured, this reports the size and explicitly declines to
   judge it. A made-up threshold would produce made-up alarms, and an alarm nobody
   believes is worse than no alarm.

3. **A concern is raised early, with a number and a plain sentence.** Not "storage
   warning: 82%".

--------------------------------------------------------------------------------
The bit worth reading twice
--------------------------------------------------------------------------------

Being unable to measure is itself reported, and is NOT reported as "fine". A storage
check that quietly returns nothing when the command fails looks exactly like a school
with plenty of room, which is the shape of fault this whole release exists to end.
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Set this to the plan's real limit in megabytes. Unset means "we do not know", and
#: this module says so rather than pretending a default is the truth.
CEILING_ENV = "STORAGE_CEILING_MB"

#: Speak up at seven tenths full. Early enough that thinning, or a bigger plan, can be
#: arranged calmly; late enough that it is not crying wolf at every quiet school.
CONCERN_FRACTION = 0.70
#: At nine tenths this stops being a note and becomes something we must act on.
URGENT_FRACTION = 0.90

_MB = 1024 * 1024


def ceiling_mb() -> Optional[float]:
    raw = os.environ.get(CEILING_ENV)
    if not raw:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        # A ceiling nobody can parse is the same as no ceiling, and saying so beats
        # silently falling back to a number nobody chose.
        logger.warning("%s is set to %r, which is not a number. Treating it as unset.", CEILING_ENV, raw)
        return None
    return value if value > 0 else None


async def measure(db) -> Dict[str, Any]:
    """How much room the school's records are taking. Never raises.

    Uses the figures the database already keeps. ``storage_size`` is what is actually
    occupied on disk, which is the number a hosting limit is measured against;
    ``data_size`` is the logical size and is usually larger, which is why reporting that
    one instead would raise an alarm months early.
    """
    try:
        stats = await db.command("dbStats")
    except Exception as exc:
        logger.warning("storage check could not read dbStats", exc_info=True)
        return {
            "measured": False,
            # Said out loud. Not knowing is a different fact from being fine.
            "reason": "The platform could not read how much room the school's records are using.",
            "detail": str(exc)[:200],
        }

    storage_bytes = float(stats.get("storageSize") or 0) + float(stats.get("indexSize") or 0)
    return {
        "measured": True,
        "used_mb": round(storage_bytes / _MB, 1),
        "data_mb": round(float(stats.get("dataSize") or 0) / _MB, 1),
        "index_mb": round(float(stats.get("indexSize") or 0) / _MB, 1),
        "collections": int(stats.get("collections") or 0),
        "documents": int(stats.get("objects") or 0),
    }


async def biggest_collections(db, limit: int = 5) -> List[Dict[str, Any]]:
    """The few collections taking the most room, so a concern says WHERE it went.

    Best-effort and deliberately quiet on failure: this is the explanatory half of the
    message, and losing it must never cost us the alarm itself.
    """
    out: List[Dict[str, Any]] = []
    try:
        names = await db.list_collection_names()
    except Exception:
        return out
    for name in names:
        try:
            stats = await db.command("collStats", name)
        except Exception:
            continue
        size = float(stats.get("storageSize") or 0) + float(stats.get("totalIndexSize") or 0)
        out.append({"name": name, "mb": round(size / _MB, 1), "documents": int(stats.get("count") or 0)})
    out.sort(key=lambda c: c["mb"], reverse=True)
    return out[:limit]


def assess(reading: Dict[str, Any], *, ceiling: Optional[float] = None) -> Dict[str, Any]:
    """Turn a reading into a level and a sentence a person can act on.

    Levels: ``unknown``, ``fine``, ``concern``, ``urgent``. ``unknown`` is a real level,
    not a synonym for ``fine``.
    """
    if not reading.get("measured"):
        return {
            "level": "unknown",
            "message": (
                reading.get("reason", "How much room the records are using could not be read.")
                + " That is not the same as there being plenty of room, so it is worth checking."
            ),
            "should_report": True,
        }

    used = reading["used_mb"]
    limit = ceiling if ceiling is not None else ceiling_mb()

    if limit is None:
        return {
            "level": "fine",
            "message": (
                f"The school's records are using about {_words(used)}. "
                "Nobody has told the platform what its storage limit is, so it cannot say "
                "whether that is a lot. The number itself is the useful part for now."
            ),
            "should_report": False,
        }

    fraction = used / limit
    left = max(0.0, limit - used)
    where = f"{_words(used)} of {_words(limit)}, so about {_words(left)} left"

    if fraction >= URGENT_FRACTION:
        return {
            "level": "urgent",
            "used_fraction": round(fraction, 3),
            "message": (
                f"The school's records are nearly out of room: {where}. When it fills, the "
                "platform will stop being able to save anything new, including attendance "
                "and fee payments. This needs sorting out now, not soon."
            ),
            "should_report": True,
        }
    if fraction >= CONCERN_FRACTION:
        return {
            "level": "concern",
            "used_fraction": round(fraction, 3),
            "message": (
                f"The school's records are filling up: {where}. Nothing is broken and "
                "nothing is at risk today, but this is the point to arrange more room "
                "rather than wait for it to run out."
            ),
            "should_report": True,
        }
    return {
        "level": "fine",
        "used_fraction": round(fraction, 3),
        "message": f"There is plenty of room for the school's records: {where}.",
        "should_report": False,
    }


async def check(db, *, ceiling: Optional[float] = None) -> Dict[str, Any]:
    """One reading plus its verdict. This is what everything else calls."""
    reading = await measure(db)
    verdict = assess(reading, ceiling=ceiling)
    result = {**reading, **verdict}
    if verdict["level"] in ("concern", "urgent"):
        result["biggest"] = await biggest_collections(db)
    return result


#: How a storage ticket is recognised again later. Kept as a constant because the
#: de-duplication below depends on matching it exactly, and a typo would turn "report
#: once" into "report every time the check runs".
TICKET_TITLE_PREFIX = "Storage: "

#: The account a ticket raised by the watcher is attributed to. Not a real person on
#: purpose: nobody pressed a button, and putting a member of staff's name on it would
#: make it look as though somebody at the school had reported it.
_WATCHER_USER = {
    "id": "platform-watcher",
    "name": "The platform, watching itself",
    "role": "owner",
    "sub_category": None,
    "branch_id": "",
}


async def maybe_report(db) -> Dict[str, Any]:
    """Check the room left and tell Layaa AI if it needs telling. Never raises.

    Reports ONCE per problem, not once per check. Whether we have already said this is
    answered by looking for an open storage ticket rather than by keeping a "last told"
    timestamp somewhere: a timestamp is another piece of state to get wrong, and it goes
    stale the moment somebody closes the ticket without the disk having changed.
    """
    from services import platform_ticket_service

    try:
        result = await check(db)
    except Exception:
        logger.exception("storage watch failed")
        return {"reported": False, "reason": "the check itself failed"}

    if not result.get("should_report"):
        return {"reported": False, "level": result.get("level"), "reason": "nothing worth saying"}

    try:
        existing = await db.platform_tickets.find_one({
            "title": {"$regex": "^" + TICKET_TITLE_PREFIX},
            "status": "open",
        })
    except Exception:
        # If we cannot tell whether we already said it, say nothing rather than risk
        # sending the same ticket every minute for a week. A missed repeat is a small
        # harm; a ticket storm is how an inbox gets ignored.
        logger.exception("storage watch could not check for an existing ticket")
        return {"reported": False, "reason": "could not check whether this was already reported"}
    if existing:
        return {"reported": False, "level": result["level"], "reason": "already reported and still open"}

    detail_lines = [result["message"]]
    for col in result.get("biggest") or []:
        detail_lines.append(f"  {col['name']}: {_words(col['mb'])} across {col['documents']:,} records")

    try:
        await platform_ticket_service.raise_ticket(
            db,
            _WATCHER_USER,
            title=TICKET_TITLE_PREFIX + _words(result.get("used_mb", 0)) + " in use",
            detail="\n".join(detail_lines),
            kind="incident" if result["level"] == "urgent" else "support",
            priority="urgent" if result["level"] == "urgent" else "normal",
            raised_by_assistant=True,
            context={
                "raised_by": "the storage watch, not a person",
                "level": result["level"],
                "used_mb": result.get("used_mb"),
                "documents": result.get("documents"),
            },
        )
    except Exception:
        logger.exception("storage watch could not raise a ticket")
        return {"reported": False, "level": result["level"], "reason": "the ticket could not be raised"}
    return {"reported": True, "level": result["level"]}


def _words(mb: float) -> str:
    """A size a person reads without converting anything in their head."""
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB"
    return f"{mb:.0f} MB"
