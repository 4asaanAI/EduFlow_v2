"""R4-3 - two years in full, a monthly summary kept forever.

--------------------------------------------------------------------------------
The decision
--------------------------------------------------------------------------------

Abhimanyu, 2026-08-12, decision 8. Every audit entry was kept forever and nothing ever
deleted one, so the school's history could only grow and so could the bill. Two years
covers a full school session plus the one before it, which is as far back as a fee or
attendance dispute realistically reaches. Beyond that a **monthly summary is kept
forever**, so nothing is ever truly gone.

--------------------------------------------------------------------------------
The rule that decides the whole design: summarise, verify, THEN delete
--------------------------------------------------------------------------------

Every step here is ordered so that a failure at any point loses nothing:

1. Read the month's detail.
2. Write the summary.
3. Read the summary back and confirm it is there.
4. Only then delete the detail.

Deleting first, or deleting on the assumption the summary write worked, would destroy the
school's history on a bad day and nobody would find out until somebody went looking years
later. The audit writer is deliberately fail-open elsewhere on the platform - it logs and
carries on rather than failing a person's save - and that behaviour, combined with
delete-first, is exactly how a year of records would vanish silently.

--------------------------------------------------------------------------------
History that quietly shrinks is the same failure as history never written
--------------------------------------------------------------------------------

That is the whole idea behind Release 4, and thinning is where it bites hardest. So the
thinning **writes its own audit row** saying which months it summarised and how many
entries it replaced. A person looking at 2024 sees a summary and an entry explaining why
the detail is a summary. They never see a silent absence and conclude the school had a
quiet year.

--------------------------------------------------------------------------------
Cost (decision 13)
--------------------------------------------------------------------------------

A summary row holds counts, not copies. One row per person per kind of change per month,
rather than one row per change. For a school of this size that is roughly a thousandth of
the space, and it is what makes "keep it forever" affordable at all.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services import audit_changes
from services.audit_service import write_audit_doc
from tenant import add_school_id

logger = logging.getLogger(__name__)

#: Decision 8. Full detail is kept for this long. NEVER thin inside this window,
#: whatever the size of the collection.
RETENTION_YEARS = 2

#: Where summaries live. A separate collection on purpose: a summary is not an audit
#: entry and must never be returned by a query asking "what changed on this record",
#: or a reader would take a count of 41 attendance marks for a single change.
SUMMARY_COLLECTION = "audit_summaries"


class RetentionRefusedError(Exception):
    """The thinning stopped rather than risk losing history. Carries a reason."""


def cutoff_iso(now: Optional[datetime] = None, *, years: int = RETENTION_YEARS) -> str:
    """The instant before which detail may be summarised away.

    Uses a plain year subtraction rather than 365-day arithmetic, so the boundary lands
    on the same calendar date and does not drift by a day every leap year. A drifting
    boundary would eventually thin a month that a person still expects in full.
    """
    now = now or datetime.now(timezone.utc)
    try:
        cut = now.replace(year=now.year - years)
    except ValueError:
        # 29 February. Step back to the 28th rather than raising, which would stop the
        # job dead once every four years for no reason anybody would think to look for.
        cut = now.replace(month=2, day=28, year=now.year - years)
    return cut.isoformat()


def _month_of(created_at: Any) -> str:
    """The 'YYYY-MM' an entry belongs to, or '' if its date cannot be read."""
    text = str(created_at or "")
    if len(text) >= 7 and text[4] == "-":
        return text[:7]
    return ""


def summarise(entries: List[dict], month: str, school_id: str) -> List[dict]:
    """Turn one month of detail into summary rows: one per person, kind and collection.

    Entries whose date cannot be read are NOT summarised and NOT counted. They are left
    alone by the caller, because a row we cannot place in time is a row we cannot promise
    is outside the two-year window.
    """
    buckets: Dict[tuple, dict] = {}
    for entry in entries:
        key = (
            entry.get("changed_by") or "",
            entry.get("action") or "",
            entry.get("collection") or entry.get("entity_type") or "",
        )
        row = buckets.get(key)
        if row is None:
            row = buckets[key] = {
                "id": str(uuid.uuid4()),
                "month": month,
                "changed_by": key[0],
                "changed_by_role": entry.get("changed_by_role") or "",
                "action": key[1],
                "collection": key[2],
                "count": 0,
                "first_at": entry.get("created_at"),
                "last_at": entry.get("created_at"),
                "summarised_at": datetime.now(timezone.utc).isoformat(),
            }
        row["count"] += 1
        created = entry.get("created_at")
        if created:
            if not row["first_at"] or created < row["first_at"]:
                row["first_at"] = created
            if not row["last_at"] or created > row["last_at"]:
                row["last_at"] = created
    return [add_school_id(row, school_id) for row in buckets.values()]


async def plan(db, *, now: Optional[datetime] = None) -> dict:
    """What thinning WOULD do, changing nothing. Safe to run against production.

    This exists so the first thing anybody does with retention is look, not act. The
    numbers it reports are the ones to check before letting the real job near the
    school's history.
    """
    cut = cutoff_iso(now)
    old = await db.audit_logs.find(
        {"created_at": {"$lt": cut}}, {"_id": 0, "created_at": 1}
    ).to_list(200_000)
    months: Dict[str, int] = {}
    undated = 0
    for entry in old:
        month = _month_of(entry.get("created_at"))
        if not month:
            undated += 1
            continue
        months[month] = months.get(month, 0) + 1
    return {
        "cutoff": cut,
        "retention_years": RETENTION_YEARS,
        "months": dict(sorted(months.items())),
        "entries_to_summarise": sum(months.values()),
        # Reported, never hidden. A row whose date cannot be read is left in full, and a
        # caller who is not told about it would think everything had been dealt with.
        #
        # Note what this number does and does not cover. Dates are compared as text, so
        # an unreadable value only reaches this function when it sorts BELOW the cutoff
        # (an empty string, a stray "0000-…"). One that sorts above - "sometime",
        # "unknown" - is treated as recent by the query and never considered for
        # thinning at all. That asymmetry is the safe direction: an entry we cannot place
        # in time is kept in full rather than summarised away, and the only cost is that
        # it is not counted here.
        "entries_with_unreadable_dates_left_alone": undated,
    }


async def thin_one_month(db, month: str, school_id: str, *, now: Optional[datetime] = None) -> dict:
    """Summarise one month and delete its detail. Summary first, verified, then delete.

    Returns what it did. Raises `RetentionRefusedError` rather than deleting anything it
    is not certain has been summarised.
    """
    cut = cutoff_iso(now)
    if month >= cut[:7]:
        raise RetentionRefusedError(
            f"{month} is inside the {RETENTION_YEARS}-year window and is kept in full."
        )

    already = await db[SUMMARY_COLLECTION].find_one({"month": month}, {"_id": 0})
    if already:
        # Idempotent. Re-running must not summarise a summary, which would replace real
        # counts with a count of one.
        return {"month": month, "skipped": "already summarised", "summarised": 0, "deleted": 0}

    entries = await db.audit_logs.find(
        {"created_at": {"$gte": f"{month}-01", "$lt": f"{month}-32"}}, {"_id": 0}
    ).to_list(200_000)
    dated = [e for e in entries if _month_of(e.get("created_at")) == month]
    if not dated:
        return {"month": month, "skipped": "nothing to summarise", "summarised": 0, "deleted": 0}

    rows = summarise(dated, month, school_id)
    for row in rows:
        await db[SUMMARY_COLLECTION].insert_one({**row, "_id": row["id"]})

    # Read it back. An insert that reported success and did not land is exactly the case
    # that would otherwise delete a month of the school's history.
    written = await db[SUMMARY_COLLECTION].count_documents({"month": month})
    if written < len(rows):
        raise RetentionRefusedError(
            f"Summary for {month} did not save in full ({written} of {len(rows)} rows). "
            "Nothing was deleted."
        )

    ids = [e.get("id") for e in dated if e.get("id")]
    deleted = 0
    if ids:
        result = await db.audit_logs.delete_many({"id": {"$in": ids}})
        deleted = getattr(result, "deleted_count", 0) or 0

    # The thinning is itself a change to the school's history, so it goes on the record
    # beside everything else. Without this, a person opening 2024 sees a summary where
    # detail used to be and no explanation of who replaced it or when.
    await write_audit_doc(
        db,
        {
            "id": str(uuid.uuid4()),
            "entity_type": SUMMARY_COLLECTION,
            "collection": SUMMARY_COLLECTION,
            "entity_id": month,
            "action": "audit_thin",
            "changed_by": "system",
            "changed_by_role": "system",
            "changes": audit_changes.bulk(
                {"month": month, "summary_rows": len(rows), "detail_removed": deleted},
                affected=deleted,
            ),
            "reason": (
                f"{month} is older than {RETENTION_YEARS} years. Its {deleted} entries were "
                f"replaced by {len(rows)} monthly summary rows, which are kept permanently."
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        school_id=school_id,
    )
    return {"month": month, "summarised": len(rows), "deleted": deleted}


async def run(db, school_id: str, *, now: Optional[datetime] = None,
              max_months: Optional[int] = None) -> dict:
    """Thin every month that is past the window, oldest first.

    Oldest first matters: if the job is interrupted, what has been dealt with is a
    contiguous run from the beginning rather than a scatter, so the next run picks up
    exactly where this one stopped.
    """
    preview = await plan(db, now=now)
    months = list(preview["months"])
    if max_months is not None:
        months = months[:max_months]

    done: List[dict] = []
    for month in months:
        try:
            done.append(await thin_one_month(db, month, school_id, now=now))
        except RetentionRefusedError as exc:
            # Stop at the first refusal rather than carrying on. A refusal means the
            # safety check failed, and the same fault is likely to affect the next month
            # too - continuing would turn one skipped month into a run of them.
            logger.error("audit_retention_refused", extra={"month": month, "reason": str(exc)})
            done.append({"month": month, "refused": str(exc)})
            break
    return {
        "cutoff": preview["cutoff"],
        "months_processed": done,
        "entries_with_unreadable_dates_left_alone":
            preview["entries_with_unreadable_dates_left_alone"],
    }
