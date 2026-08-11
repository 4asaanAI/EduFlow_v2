"""R2-15 - the day in one page, for the two people who run the school.

Aman asked that everything on the platform be visible to him. Today that means opening
the Audit Log and reading it: a screen you have to remember to go and look at, listing
every row of every kind, in the order it happened.

This is a reader over the same rows. Nothing new is recorded. What it adds is the shape:
who did what, how much of it, and what is worth a second look.

--------------------------------------------------------------------------------
Two decisions worth keeping
--------------------------------------------------------------------------------

**Short enough to actually be read.** A digest nobody opens is worse than the audit log,
because it feels like oversight without being any. So it counts by person and by kind,
and it names only the handful of things that deserve a name.

**Not WhatsApp, yet.** There is no production WhatsApp sender for this school (see the
standing note in CLAUDE.md: the only sender on the account is Twilio's shared sandbox,
which can reach nobody). So the digest is built as DATA with a plain-text rendering, and
the channel is whoever asks for it. Adding WhatsApp later means calling
``render_digest_text`` from the messaging service, not rewriting this.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from tenant import scoped_query

# What each action is called when a person reads it. An audit `action` is a machine
# name - `student_update`, `certificate_delete` - and putting those in front of the
# school's owner is how a summary stops being read.
_ACTION_WORDS = [
    ("undo", "put a change back"),
    ("delete", "removed"),
    ("erase", "erased"),
    ("create", "added"),
    ("update", "edited"),
    ("approve", "approved"),
    ("reject", "rejected"),
    ("import", "imported"),
    ("payment", "recorded a payment"),
    ("attendance", "marked attendance"),
]

# Things the two of them should look at rather than merely count. Each is here because
# somebody would want to know the same day, not at the end of the month.
NOTEWORTHY = {
    "delete": "a record was removed",
    "erase": "a record was erased",
    "undo": "somebody put their own change back",
    "period_close": "the accounting period was closed",
    "period_open": "the accounting period was reopened",
    "year_end": "the year-end promotion was run",
    "certificate_delete": "a certificate was deleted",
    "set_profile_password": "a password was changed",
    "create_student_login": "a login was created",
}

# Money is Aman's and Sonu's. The principal sees the school's finances too (2026-08-10),
# so both leadership profiles get the finance half; this constant exists so that if that
# ever narrows, it narrows in one place.
FINANCE_COLLECTIONS = {
    "fee_transactions", "fee_structures", "expenses", "payroll", "salaries",
    "discounts", "accounting_periods", "commercial",
}


def _describe_action(action: str) -> str:
    lowered = str(action or "").lower()
    for needle, word in _ACTION_WORDS:
        if needle in lowered:
            return word
    return "changed something"


def _noteworthy_reason(action: str) -> str:
    lowered = str(action or "").lower()
    for needle, reason in NOTEWORTHY.items():
        if needle in lowered:
            return reason
    return ""


def _since(hours: int, now: datetime) -> str:
    return (now - timedelta(hours=hours)).isoformat()


async def build_daily_digest(db, actor_ctx, hours: int = 24) -> Dict[str, Any]:
    """The last day's activity, grouped by person and by kind.

    `hours` is a window rather than a calendar day on purpose: the digest is read
    whenever it is opened, and "since yesterday" is the useful question at 9am and at
    4pm alike.
    """
    now = datetime.now(timezone.utc)
    cutoff = _since(hours, now)

    rows: List[dict] = await db.audit_logs.find(
        scoped_query({}, branch_id=actor_ctx.branch_id), {"_id": 0}
    ).sort("created_at", -1).to_list(2000)
    rows = [r for r in rows if str(r.get("created_at") or "") >= cutoff]

    # Who did what. Names are resolved in one query rather than one per row: the audit
    # log is the highest-volume collection on the platform and an N+1 here would be felt.
    actor_ids = sorted({r.get("changed_by") for r in rows if r.get("changed_by")})
    names: Dict[str, str] = {}
    if actor_ids:
        people = await db.users.find(
            scoped_query({"id": {"$in": actor_ids}}, branch_id=actor_ctx.branch_id),
            {"_id": 0, "id": 1, "name": 1, "role": 1, "sub_category": 1},
        ).to_list(len(actor_ids))
        names = {p["id"]: p.get("name") or "Somebody" for p in people if p.get("id")}

    by_person: Dict[str, Dict[str, Any]] = {}
    by_area: Dict[str, int] = {}
    noteworthy: List[dict] = []

    for row in rows:
        actor = row.get("changed_by") or "unknown"
        entry = by_person.setdefault(actor, {
            "user_id": actor,
            "name": names.get(actor, "Somebody no longer on the platform"),
            "total": 0,
            "what": {},
        })
        entry["total"] += 1
        word = _describe_action(row.get("action"))
        entry["what"][word] = entry["what"].get(word, 0) + 1

        area = row.get("entity_type") or row.get("collection") or "other"
        by_area[area] = by_area.get(area, 0) + 1

        reason = _noteworthy_reason(row.get("action"))
        if reason:
            noteworthy.append({
                "at": row.get("created_at"),
                "who": entry["name"],
                "what": reason,
                "area": area,
                "entity_id": row.get("entity_id"),
                "reason_given": row.get("reason") or "",
            })

    money_changes = sum(count for area, count in by_area.items() if area in FINANCE_COLLECTIONS)

    return {
        "window_hours": hours,
        "generated_at": now.isoformat(),
        "total_changes": len(rows),
        "by_person": sorted(by_person.values(), key=lambda p: -p["total"]),
        "by_area": dict(sorted(by_area.items(), key=lambda kv: -kv[1])),
        "money_changes": money_changes,
        # Newest first, and capped. A "things to look at" list of ninety items is a
        # second audit log, which is the thing this exists to replace.
        "noteworthy": noteworthy[:15],
        "noteworthy_total": len(noteworthy),
        "quiet_day": not rows,
    }


def render_digest_text(digest: Dict[str, Any]) -> str:
    """The digest as plain words.

    Kept separate from the data so the same summary can go to a screen today and to
    WhatsApp or email the day a sender exists, without either one rewriting the other.
    """
    if digest.get("quiet_day"):
        return "Nothing was changed on the platform in the last day."

    lines = [f"{digest['total_changes']} changes on the platform in the last day."]

    for person in digest["by_person"]:
        what = ", ".join(f"{count} {word}" for word, count in
                         sorted(person["what"].items(), key=lambda kv: -kv[1]))
        lines.append(f"- {person['name']}: {person['total']} in total ({what}).")

    if digest["money_changes"]:
        lines.append(f"- {digest['money_changes']} of them were about money.")

    if digest["noteworthy"]:
        lines.append("")
        lines.append("Worth a look:")
        for item in digest["noteworthy"]:
            tail = f" - reason given: {item['reason_given']}" if item["reason_given"] else ""
            lines.append(f"- {item['who']}: {item['what']} ({item['area']}){tail}")
        if digest["noteworthy_total"] > len(digest["noteworthy"]):
            hidden = digest["noteworthy_total"] - len(digest["noteworthy"])
            # Never let a cap read as "that was everything".
            lines.append(f"- and {hidden} more, in the Audit Log.")

    return "\n".join(lines)
