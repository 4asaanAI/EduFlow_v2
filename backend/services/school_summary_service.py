"""The whole school on one page, for the two people who run it.

Abhimanyu, 2026-08-12: build the scheduled reports, at least for Aman and Adesh, so they
have a summary of everything in one place.

--------------------------------------------------------------------------------
What "scheduled" honestly means here, and what it does not
--------------------------------------------------------------------------------

There is no scheduler on this platform and nothing that can email a report at 8am: the
container service this subscription would need will not provision, and the only messaging
credentials that work send from American numbers. The screen this replaces already learnt
that lesson the hard way, by showing two reports as "Active" that had never existed.

So the summary is **produced and kept the first time either of them opens it on a given
day**, and every earlier day's is kept exactly as it was produced. In practice that gives
them what they asked for: one page, every day, and a history to look back on. What it does
not do is arrive by itself in an inbox, and the screen says so in those words rather than
implying otherwise.

When a sender the school can actually use exists, delivery is a small piece of work on
top: the summary is already stored, dated and rendered as plain text.

--------------------------------------------------------------------------------
Who may read it
--------------------------------------------------------------------------------

The school's owner and the principal, gated exactly like the action log and the daily
digest, because this carries money, the roll and what everyone changed. It is deliberately
NOT widened to the accountant head or the admin office: each of them already has the half
that is theirs, and this is the whole.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from services.actor_context import ActorContext
from services.daily_digest_service import build_daily_digest
from tenant import scoped_filter

# Kept for a year. A summary is small, and "what did the school look like in October"
# is exactly the question this is for.
KEEP_DAYS = 400

_OPEN = {"pending", "unpaid", "overdue"}


def _today_iso(actor_ctx: ActorContext) -> str:
    return actor_ctx.now().date().isoformat()


async def _roll(db, school_id: str) -> Dict[str, Any]:
    active = await db.students.count_documents(scoped_filter({"is_active": True}, school_id))
    total = await db.students.count_documents(scoped_filter({}, school_id))
    staff = await db.staff.count_documents(scoped_filter({}, school_id))
    return {"students_on_the_roll": active, "student_records_in_total": total,
            "staff": staff}


async def _attendance(db, school_id: str, day: str) -> Dict[str, Any]:
    # `student_attendance`, not `attendance`. Named wrongly in the first version of this
    # file, which reported "not marked yet" on a day the register had been taken: a
    # summary that is quietly wrong is worse than no summary.
    rows = await db.student_attendance.find(
        scoped_filter({"date": day}, school_id), {"_id": 0, "status": 1},
    ).to_list(5000)
    if not rows:
        return {"marked": False,
                "note": "No attendance has been marked for this day yet."}
    present = sum(1 for r in rows if str(r.get("status", "")).lower() in ("present", "late"))
    return {
        "marked": True,
        "children_marked": len(rows),
        "present": present,
        "absent": len(rows) - present,
        "present_percent": round(present * 100 / len(rows), 1) if rows else 0,
    }


async def _money(db, school_id: str, day: str) -> Dict[str, Any]:
    paid_today = await db.fee_transactions.find(
        scoped_filter({"payment_date": day}, school_id), {"_id": 0, "paid_amount": 1},
    ).to_list(5000)
    open_charges = await db.fee_transactions.find(
        scoped_filter({"status": {"$in": sorted(_OPEN)}}, school_id),
        {"_id": 0, "amount": 1, "paid_amount": 1, "student_id": 1, "due_date": 1},
    ).to_list(20000)

    outstanding = 0.0
    families = set()
    for row in open_charges:
        owed = float(row.get("amount") or 0) - float(row.get("paid_amount") or 0)
        if owed > 0:
            outstanding += owed
            families.add(row.get("student_id"))
    overdue = [r for r in open_charges if (r.get("due_date") or "") and r["due_date"] < day]

    return {
        "collected_today": round(sum(float(r.get("paid_amount") or 0) for r in paid_today), 2),
        "receipts_today": len(paid_today),
        "outstanding_in_total": round(outstanding, 2),
        "children_with_something_outstanding": len(families),
        "bills_past_their_due_date": len(overdue),
    }


async def _waiting_for_you(db, school_id: str) -> Dict[str, Any]:
    certificates = await db.certificates.count_documents(
        scoped_filter({"status": "pending_approval"}, school_id))
    leaves = await db.leave_requests.count_documents(
        scoped_filter({"status": "pending"}, school_id))
    approvals = await db.approval_requests.count_documents(
        scoped_filter({"status": "pending"}, school_id))
    discounts = await db.pending_discount_approvals.count_documents(
        scoped_filter({"status": "pending"}, school_id))
    return {
        "documents_awaiting_approval": certificates,
        "staff_leave_requests_waiting": leaves,
        "other_approvals_waiting": approvals,
        "discounts_awaiting_approval": discounts,
        "total": certificates + leaves + approvals + discounts,
    }


async def build_school_summary(db, actor_ctx: ActorContext, *, day: Optional[str] = None,
                               hours: int = 24) -> Dict[str, Any]:
    """Everything the two of them would otherwise open six screens to see."""
    school_id = actor_ctx.school_id
    day = day or _today_iso(actor_ctx)

    changes = await build_daily_digest(db, actor_ctx, hours=hours)
    summary = {
        "day": day,
        "produced_at": actor_ctx.now_utc().isoformat(),
        "school": await _roll(db, school_id),
        "attendance": await _attendance(db, school_id, day),
        "money": await _money(db, school_id, day),
        "waiting_for_you": await _waiting_for_you(db, school_id),
        "what_changed": {
            "total": changes.get("total_changes", 0),
            "by_person": changes.get("by_person", []),
            "worth_a_look": changes.get("noteworthy", []),
            "money_changes": changes.get("money_changes", 0),
        },
    }
    summary["text"] = render_summary_text(summary)
    return summary


def render_summary_text(summary: Dict[str, Any]) -> str:
    """The same page in plain words, so it can be read, printed, or sent the day a
    sender exists."""
    school = summary["school"]
    attendance = summary["attendance"]
    money = summary["money"]
    waiting = summary["waiting_for_you"]
    changed = summary["what_changed"]

    lines = [f"The Aaryans, Joya - {summary['day']}", ""]
    lines.append(f"On the roll: {school['students_on_the_roll']:,} children, "
                 f"{school['staff']:,} staff.")

    if attendance.get("marked"):
        lines.append(f"Attendance: {attendance['present']:,} of "
                     f"{attendance['children_marked']:,} present "
                     f"({attendance['present_percent']}%), {attendance['absent']:,} absent.")
    else:
        lines.append("Attendance: not marked yet today.")

    lines.append(f"Collected today: {money['collected_today']:,.0f} across "
                 f"{money['receipts_today']:,} receipts.")
    lines.append(f"Outstanding: {money['outstanding_in_total']:,.0f} across "
                 f"{money['children_with_something_outstanding']:,} children, "
                 f"{money['bills_past_their_due_date']:,} bills past their due date.")

    if waiting["total"]:
        lines.append("")
        lines.append(f"Waiting for you: {waiting['total']} thing(s).")
        for label, count in (
            ("documents to approve", waiting["documents_awaiting_approval"]),
            ("staff leave requests", waiting["staff_leave_requests_waiting"]),
            ("other approvals", waiting["other_approvals_waiting"]),
            ("discounts to approve", waiting["discounts_awaiting_approval"]),
        ):
            if count:
                lines.append(f"- {count} {label}")

    lines.append("")
    if changed["total"]:
        lines.append(f"Changes today: {changed['total']}, of which "
                     f"{changed['money_changes']} touched money.")
        for person in changed["by_person"][:5]:
            lines.append(f"- {person.get('name', 'somebody')}: {person.get('total', 0)}")
        for item in changed["worth_a_look"][:5]:
            lines.append(f"- worth a look: {item.get('who')}: {item.get('what')}")
    else:
        lines.append("Changes today: none.")

    return "\n".join(lines)


async def save_summary(db, actor_ctx: ActorContext, summary: Dict[str, Any]) -> Dict[str, Any]:
    """Keep the day's summary, once. A second call on the same day returns the one
    already kept rather than producing a different picture of the same day."""
    school_id = actor_ctx.school_id
    existing = await db.school_summaries.find_one(
        scoped_filter({"day": summary["day"]}, school_id), {"_id": 0},
    )
    if existing:
        return existing
    doc = {**summary, "id": str(uuid.uuid4()), "schoolId": school_id}
    await db.school_summaries.insert_one({**doc, "_id": doc["id"]})
    return doc


async def summary_for_day(db, actor_ctx: ActorContext, *, day: Optional[str] = None) -> Dict[str, Any]:
    """The day's summary: the one already kept, or produced and kept now.

    This IS the schedule. There is no cron on this platform and nothing that can email a
    report, so the day's page is produced the first time one of them opens it and kept
    exactly as produced. Yesterday's is never rebuilt from today's data, which would
    quietly rewrite history.
    """
    day = day or _today_iso(actor_ctx)
    kept = await db.school_summaries.find_one(
        scoped_filter({"day": day}, actor_ctx.school_id), {"_id": 0},
    )
    if kept:
        return {**kept, "freshly_produced": False}
    if day != _today_iso(actor_ctx):
        return {"day": day, "not_kept": True,
                "note": "No summary was kept for that day. It is not rebuilt from "
                        "today's figures, because that would describe the wrong day."}
    produced = await build_school_summary(db, actor_ctx, day=day)
    saved = await save_summary(db, actor_ctx, produced)
    return {**saved, "freshly_produced": True}


async def list_summaries(db, actor_ctx: ActorContext, limit: int = 30) -> list[dict]:
    rows = await db.school_summaries.find(
        scoped_filter({}, actor_ctx.school_id),
        {"_id": 0, "id": 1, "day": 1, "produced_at": 1, "money": 1, "attendance": 1},
    ).to_list(max(1, min(int(limit or 30), 200)))
    return sorted(rows, key=lambda r: r.get("day") or "", reverse=True)
