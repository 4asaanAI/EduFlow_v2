"""The school's late fine, worked out the school's way and not the old supplier's.

Release 2, finishing plan step 9. The authority is
``_bmad-output/implementation-artifacts/release-2/fee-rules-from-sonu-2026-08-11.md``,
section 2.

--------------------------------------------------------------------------------
The rule
--------------------------------------------------------------------------------

Fees are charged quarterly and each quarter has a 15-day window to pay.

* **10 rupees a day** from the 16th of the quarter's first month until that quarter
  ends.
* **1,000** when the next quarter begins. The daily fine then **stops for good** on that
  quarter.
* **The 1,000 repeats** at every following quarter end while the quarter stays unpaid,
  so a family that pays nothing all session is charged it four times on Q1.

| Quarter | Due by | Daily fine runs | First 1,000 |
|---|---|---|---|
| Q1 April to June | 15 April | 16 April to 30 June | 1 July |
| Q2 July to September | 15 July | 16 July to 30 September | 1 October |
| Q3 October to December | 15 October | 16 October to 31 December | 1 January |
| Q4 January to March | 15 January | 16 January to 31 March | 1 April |

--------------------------------------------------------------------------------
⚠️ This is exactly where the previous supplier is wrong
--------------------------------------------------------------------------------

Vedmarg keeps a quarter's daily fine running after the next quarter has begun, so two
daily fines accrue at once and families are overcharged. **Only one daily fine ever runs
at a time: the current quarter's.** Here that is structural rather than a check - each
quarter's daily window ends at its own quarter end and the windows cannot overlap - and
``test_only_one_daily_fine_ever_runs_at_a_time`` pins it.

--------------------------------------------------------------------------------
What the fine is charged on
--------------------------------------------------------------------------------

**The whole outstanding bill, transport included** (rules section 2.2). There is no
separate transport fine and no separate transport due date. The daily figure is a flat
10 rupees rather than a percentage, so the total decides *whether* a fine runs, not how
big it is: one fine per child per quarter, never one per fee head.

**Right to Education children owe no school fee**, so theirs is worked out on transport
alone. That falls out of the rule rather than needing a special case: their outstanding
figure simply has no school fee in it.

--------------------------------------------------------------------------------
What this file deliberately does NOT do
--------------------------------------------------------------------------------

**It writes nothing.** Nothing about fines is loaded to the school's database before the
money actually collected is (step 8), on Abhimanyu's explicit instruction, so that a
wrong fine never reaches a family while the rest of the ledger is being settled.

**It does not claim ledger support for the repeat.** All 1,217 fine lines in the school's
ledger are exact multiples of ten, which is consistent with this rule and is not proof of
it: the ledger stops on 7 August and the session's second quarter end has not happened.
The repeat rests on Abhimanyu's confirmation, given twice and the second time against a
specific number.

--------------------------------------------------------------------------------
One judgement, stated rather than buried
--------------------------------------------------------------------------------

A family paying on the 20th is charged for the 16th to the 20th **inclusive**, so five
days. "10 rupees a day from the 16th" does not say whether the day of payment counts.
Inclusive is the ordinary reading and is what the office would do by hand. It is worth a
sentence from Sonu, and it is one day's fine either way.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

DAILY_FINE = 10
QUARTER_END_FINE = 1000

# code -> (due month, due day, last month of the quarter, last day, year offset from the
# session's April start). A session starting April 2026 runs to March 2027.
QUARTERS = {
    "q1": {"label": "Q1 April to June",       "due": (4, 15, 0),  "ends": (6, 30, 0)},
    "q2": {"label": "Q2 July to September",   "due": (7, 15, 0),  "ends": (9, 30, 0)},
    "q3": {"label": "Q3 October to December", "due": (10, 15, 0), "ends": (12, 31, 0)},
    "q4": {"label": "Q4 January to March",    "due": (1, 15, 1),  "ends": (3, 31, 1)},
}

# The four moments in a session at which an unpaid quarter takes 1,000, in order.
_FLAT_POINTS = ((7, 1, 0), (10, 1, 0), (1, 1, 1), (4, 1, 1))


class LateFineError(Exception):
    """The fine cannot be worked out honestly, so it refuses rather than guessing."""


def _as_date(value: Any, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except (TypeError, ValueError):
        raise LateFineError(f"{field} is not a date I can read (expected YYYY-MM-DD): {value!r}")


def _point(spec: tuple[int, int, int], session_start_year: int) -> date:
    month, day, offset = spec
    return date(session_start_year + offset, month, day)


def due_date(quarter: str, session_start_year: int) -> date:
    """The 15th the quarter must be paid by."""
    if quarter not in QUARTERS:
        raise LateFineError(f"{quarter!r} is not one of the school's four quarters: {sorted(QUARTERS)}")
    return _point(QUARTERS[quarter]["due"], session_start_year)


def quarter_end(quarter: str, session_start_year: int) -> date:
    """The last day the quarter's daily fine can run."""
    if quarter not in QUARTERS:
        raise LateFineError(f"{quarter!r} is not one of the school's four quarters: {sorted(QUARTERS)}")
    return _point(QUARTERS[quarter]["ends"], session_start_year)


def quarter_end_charge_dates(quarter: str, session_start_year: int) -> list[date]:
    """Every date on which an unpaid quarter takes another 1,000, in order.

    Q1 has four (1 July, 1 October, 1 January, 1 April), Q2 three, Q3 two, Q4 one. The
    list ends with the session, which is what "four times over a full year of arrears"
    means; it does not run on for ever.
    """
    ends = quarter_end(quarter, session_start_year)
    return [d for d in (_point(p, session_start_year) for p in _FLAT_POINTS) if d > ends]


def compute_late_fine(
    *,
    quarter: str,
    session_start_year: int,
    as_of: Any,
    outstanding_amount: Any,
    settled_on: Any = None,
) -> dict:
    """What one child owes in fines on one quarter.

    ``outstanding_amount`` is the whole bill for that quarter that is still unpaid,
    **transport included**. Zero or less means nothing is late and there is no fine.
    ``settled_on`` is the day the quarter was cleared, or ``None`` while it is still
    outstanding.

    Returns ``{"daily_days", "daily_amount", "quarter_end_charges", "flat_amount",
    "total", "lines"}``.
    """
    today = _as_date(as_of, "as_of")
    settled = _as_date(settled_on, "settled_on") if settled_on not in (None, "") else None
    try:
        outstanding = float(outstanding_amount or 0)
    except (TypeError, ValueError):
        raise LateFineError(f"outstanding_amount must be a number, got {outstanding_amount!r}")

    starts = due_date(quarter, session_start_year) + timedelta(days=1)   # the 16th
    ends = quarter_end(quarter, session_start_year)
    lines: list[dict] = []

    if outstanding <= 0:
        return {"daily_days": 0, "daily_amount": 0.0, "quarter_end_charges": 0,
                "flat_amount": 0.0, "total": 0.0, "lines": lines,
                "why": "nothing outstanding on this quarter, so no fine"}

    # The last day the daily fine can count for. It stops at the quarter end even if the
    # family never pays: this is the half the old system gets wrong.
    last_day = min(today, ends)
    if settled is not None:
        last_day = min(last_day, settled)

    days = (last_day - starts).days + 1 if last_day >= starts else 0
    daily_amount = float(days * DAILY_FINE)
    if days:
        lines.append({
            "rule": "daily",
            "label": f"Late fine, {DAILY_FINE} a day",
            "from": starts.isoformat(),
            "to": last_day.isoformat(),
            "days": days,
            "amount": daily_amount,
            "why": "10 a day from the 16th, and it stops when the quarter ends",
        })

    # The 1,000 at each following quarter end, while it is still unpaid.
    charge_dates = [
        when for when in quarter_end_charge_dates(quarter, session_start_year)
        if when <= today and (settled is None or when <= settled)
    ]
    flat_amount = float(len(charge_dates) * QUARTER_END_FINE)
    for when in charge_dates:
        lines.append({
            "rule": "quarter_end",
            "label": f"Quarter-end fine, {QUARTER_END_FINE}",
            "on": when.isoformat(),
            "amount": float(QUARTER_END_FINE),
            "why": "the quarter was still unpaid when a new quarter began",
        })

    return {
        "daily_days": days,
        "daily_amount": daily_amount,
        "quarter_end_charges": len(charge_dates),
        "flat_amount": flat_amount,
        "total": daily_amount + flat_amount,
        "lines": lines,
    }


def assess_quarters(
    quarters: list[dict],
    *,
    session_start_year: int,
    as_of: Any,
) -> dict:
    """Every fine a child owes across the quarters they are behind on.

    ``quarters`` is ``[{"quarter": "q1", "outstanding_amount": 9750, "settled_on": None},
    ...]``, one entry per quarter, each figure being the whole bill for that quarter
    **including transport**.

    Reports ``daily_running`` so anyone reading it can see that only one quarter's daily
    fine is accruing, which is the thing the old system gets wrong.
    """
    today = _as_date(as_of, "as_of")
    per_quarter, total = [], 0.0
    for row in quarters:
        result = compute_late_fine(
            quarter=row["quarter"],
            session_start_year=session_start_year,
            as_of=today,
            outstanding_amount=row.get("outstanding_amount"),
            settled_on=row.get("settled_on"),
        )
        result["quarter"] = row["quarter"]
        result["still_accruing_daily"] = bool(
            result["daily_days"]
            and today <= quarter_end(row["quarter"], session_start_year)
            and not row.get("settled_on")
        )
        per_quarter.append(result)
        total += result["total"]

    running = [q["quarter"] for q in per_quarter if q["still_accruing_daily"]]
    if len(running) > 1:
        raise LateFineError(
            "more than one daily fine is running at once "
            f"({', '.join(running)}), which is the fault that overcharges families. "
            "Only the current quarter's daily fine may run."
        )
    return {
        "as_of": today.isoformat(),
        "quarters": per_quarter,
        "total": total,
        "daily_running": running[0] if running else None,
    }
