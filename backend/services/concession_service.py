"""The school's four fee concessions, as rules that recompute themselves.

Release 2, finishing plan step 5. The authority for every rule in this file is
``_bmad-output/implementation-artifacts/release-2/fee-rules-from-sonu-2026-08-11.md``,
which records what the school's accountant head said and what was checked against the
school's own payment ledger.

--------------------------------------------------------------------------------
Why this is not four rows in the existing discount mechanism
--------------------------------------------------------------------------------

``fee_discount_types`` + ``fee_discounts`` (see ``discount_service.py``) records a
discount somebody typed in, once, against one child. Three of the four concessions below
are not that: they are rules whose amount follows from the child's own class band and
has to be recomputed every quarter. Recording the sibling concession as a plain discount
row would mean somebody re-typing it for roughly 500 children four times a year, and
every re-typing is a chance to give away or overcharge money.

So: **the three recurring ones are computed here, from marks on the child's record.
Only the one-time admission concession is a stored amount**, and even that is stored
with who authorised it and which instalment consumed it, so it cannot repeat.

--------------------------------------------------------------------------------
The four rules
--------------------------------------------------------------------------------

1. **Sibling.** The youngest child in a family pays full; every other child in that
   family is discounted. The amount is flat per quarter and depends on the discounted
   child's OWN class band: the seven values in ``SIBLING_BY_QUARTERLY_BAND``. Those seven
   figures are already loaded on the platform and correct; they are repeated here as the
   rule's own table, not recreated as data.
2. **Employee's child.** 50% off, for the child of any employee of the school, whatever
   their job.
3. **Whole year paid by 30 April.** 5% off the session's fee. A parent paying the full
   year in August does not qualify.
4. **One-time at admission.** Not a rule but a decision: a family asks, Aman or Adesh
   decide an amount, Sonu applies it once, at the family's first instalment.

**They do not stack.** A child entitled to both the employee and the sibling concession
keeps the employee one. Not the better of the two by calculation: the employee one, by
rule.

**Transport carries no concession of any kind**, for anybody. Every function here takes
a school-fee amount and the callers must never pass a transport figure into it.
``assert_not_transport`` exists so that a caller who gets this wrong fails loudly.

**Right to Education children are not handled here** and must not be. They pay no school
fee at all; that is the absence of a charge, not a concession, and treating it as a 100%
discount would let it interact with these rules and be reversible by anyone who can edit
a discount. That is step 7.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

# The seven sibling values, keyed by the discounted child's own quarterly band. Both
# columns come from the school's 2026-27 fee sheet and both were confirmed against the
# payment ledger (853 lines at exactly one of these seven values, across 503 children).
SIBLING_BY_QUARTERLY_BAND = {
    7050: 1410,    # NUR, LKG, UKG
    8250: 1560,    # 1st, 2nd
    8850: 1650,    # 3rd, 4th, 5th
    9750: 1800,    # 6th, 7th, 8th
    12000: 2100,   # 9th, 10th
    16500: 2610,   # 11th, 12th Commerce
    17700: 2910,   # 11th, 12th Science
}

EMPLOYEE_CHILD_PERCENT = Decimal("50")
FULL_YEAR_PERCENT = Decimal("5")

# The whole year must be paid on or before this date to earn the 5% (Abhimanyu,
# 2026-08-11, answer 3). Month and day only: the year is the session's.
FULL_YEAR_DEADLINE_MONTH = 4
FULL_YEAR_DEADLINE_DAY = 30


class ConcessionRuleError(Exception):
    """The rule cannot be applied honestly, so it refuses rather than guessing."""


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _round(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def assert_not_transport(kind: str) -> None:
    """Transport is never discounted. A caller passing a transport charge in here has
    made a mistake that would give money away, so it fails loudly rather than quietly
    returning a number."""
    if "transport" in (kind or "").strip().lower():
        raise ConcessionRuleError(
            "transport carries no concession of any kind - see fee rules section 3. "
            f"Refusing to compute a concession on the charge {kind!r}."
        )


# ───────────────────────────── the four rules ──────────────────────────────


def sibling_amount(quarterly_amount: Any) -> float:
    """The flat per-quarter sibling concession for a child on this band.

    Refuses on an unknown band rather than interpolating: an invented seventh-and-a-half
    value is money the school never agreed to give away.
    """
    band = int(_money(quarterly_amount))
    if band not in SIBLING_BY_QUARTERLY_BAND:
        raise ConcessionRuleError(
            f"{band:,} is not one of the school's seven quarterly bands, so there is no "
            "sibling concession value for it. The seven are "
            f"{sorted(SIBLING_BY_QUARTERLY_BAND)}."
        )
    return float(SIBLING_BY_QUARTERLY_BAND[band])


def employee_child_amount(quarterly_amount: Any) -> float:
    """Half the quarter's fee, for the child of any employee of the school."""
    return _round(_money(quarterly_amount) * EMPLOYEE_CHILD_PERCENT / 100)


def _as_date(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        raise ConcessionRuleError(f"{value!r} is not a date I can read (expected YYYY-MM-DD)")


def full_year_qualifies(paid_on: Any, *, session_start_year: int) -> bool:
    """Was the whole year paid on or before 30 April of the session it belongs to?"""
    when = _as_date(paid_on)
    if when is None:
        return False
    return when <= date(session_start_year, FULL_YEAR_DEADLINE_MONTH, FULL_YEAR_DEADLINE_DAY)


def full_year_amount(annual_amount: Any, paid_on: Any, *, session_start_year: int) -> float:
    """5% of the session's fee, and zero if it was not paid in time.

    This one is decided at the moment of PAYMENT, not when the quarter is billed, so its
    caller is the payment path (step 8) rather than charge generation.
    """
    if not full_year_qualifies(paid_on, session_start_year=session_start_year):
        return 0.0
    return _round(_money(annual_amount) * FULL_YEAR_PERCENT / 100)


def admission_concession(student: dict, installment_code: str) -> tuple[float, Optional[dict]]:
    """The one-time concession Aman or Adesh authorised at admission.

    Returns ``(amount, record)``. Zero unless the child carries an authorised amount that
    has not already been consumed by an instalment.

    **It must never repeat**, so the stored record carries ``applied_to``. Once that names
    an instalment, this returns the amount again only for that same instalment (so
    re-previewing a quarter is not a second gift) and zero for every other one.
    """
    record = (student.get("concessions") or {}).get("admission_discount")
    if not record:
        return 0.0, None
    amount = _money(record.get("amount"))
    if amount <= 0:
        return 0.0, None
    if not record.get("authorised_by"):
        raise ConcessionRuleError(
            "an admission concession must record who authorised it - Aman or Adesh decide "
            "it, Sonu applies it. Refusing to give money away with no name against it."
        )
    already = record.get("applied_to")
    if already and already != installment_code:
        return 0.0, None
    return _round(amount), record


# ───────────────────────── putting them together ───────────────────────────


def compute_concessions(
    student: dict,
    *,
    quarterly_amount: Any,
    installment_code: str,
    fee_head: str = "Composite Fee",
) -> dict:
    """Every concession this child is owed on one quarter's school fee.

    Returns ``{"lines": [...], "total": float, "gross": float, "net": float}``. Each line
    says which rule produced it and why, so a family asking "why is my bill this figure"
    can be answered from the record rather than from somebody's memory.

    The concessions never take a bill below zero.
    """
    assert_not_transport(fee_head)
    marks = student.get("concessions") or {}
    gross = _money(quarterly_amount)
    lines: list[dict] = []

    # Rule: they do not stack, and the employee one wins by rule (not by size).
    if marks.get("employee_child"):
        lines.append({
            "rule": "employee_child",
            "label": "Employee's child (50%)",
            "amount": employee_child_amount(gross),
            "why": "child of an employee of the school",
        })
        if marks.get("sibling"):
            lines.append({
                "rule": "sibling",
                "label": "Sibling concession",
                "amount": 0.0,
                "why": "not applied: the employee concession wins and they do not stack",
            })
    elif marks.get("sibling"):
        lines.append({
            "rule": "sibling",
            "label": "Sibling concession",
            "amount": sibling_amount(gross),
            "why": "an elder child in a family; the youngest pays full",
        })

    one_time, record = admission_concession(student, installment_code)
    if record is not None and one_time > 0:
        lines.append({
            "rule": "admission_one_time",
            "label": "One-time concession agreed at admission",
            "amount": one_time,
            "why": f"authorised by {record.get('authorised_by')}",
            "authorised_by": record.get("authorised_by"),
            "authorised_on": record.get("authorised_on"),
            "applies_once": True,
            "installment_code": installment_code,
        })

    total = sum((_money(line["amount"]) for line in lines), Decimal("0"))
    total = min(total, gross)
    return {
        "lines": lines,
        "total": _round(total),
        "gross": _round(gross),
        "net": _round(gross - total),
    }
