"""Release 2, step 8 - load what the school has actually collected.

The platform records **one payment for the entire school**. The school's payment ledger
holds **3,177 receipts covering 3.56 crore, from 1,722 children**, between 23 January and
7 August 2026. Until this runs, no family's balance on the platform means anything.

Source: ``aaryans_database/Fees-log-detailed-11-08-2026-17-36.xlsx``, the latest ledger.

--------------------------------------------------------------------------------
What is loaded, and the halves that are deliberately NOT
--------------------------------------------------------------------------------

The ledger's own summary row disagrees with the sum of its own rows, and counting it here
shows exactly where:

===================  ==================  ==================  ==========
figure               the summary says    the rows add up to  agrees?
===================  ==================  ==================  ==========
money collected      3,56,23,748         3,56,23,748         **yes**
discount given       52,69,692           52,69,692           **yes**
total billed         4,12,46,380         4,29,39,500         no
balance outstanding  3,52,940            10,75,327           no
===================  ==================  ==================  ==========

**So money collected and discounts are loaded, and billed and balance are not.** That is
Abhimanyu's instruction of 2026-08-11 (load the money actually collected and each child's
normal fee, nothing else) and it also sidesteps the disagreement entirely rather than
picking a side of it. What each family should have been billed comes from the fee
structures loaded in step 3, which three independent documents agree on.

--------------------------------------------------------------------------------
Running it twice must not double anybody's payments
--------------------------------------------------------------------------------

Every row carries a ``ledger_key``: the receipt number, the line's position on that
receipt, and the fee head. A row whose key is already on the platform is skipped and
counted. That is what makes this safe to re-run, which matters on a write of this size.

--------------------------------------------------------------------------------
What it refuses to do
--------------------------------------------------------------------------------

* **26 lines carry no admission number.** They are reported, never attached to a guess.
* **A child not on the platform is reported, never created.** Creating a student from a
  payment line would mint a child record with no admission the school approved.
* If more than ``MAX_UNMATCHED_SHARE`` of the money cannot be placed on a real child, the
  whole migration refuses. Loading most of a school's collections and reporting success
  is worse than loading none, because nobody goes looking for the rest.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/039_load_payments_from_ledger.py
    ... 039_load_payments_from_ledger.py --apply
    ... 039_load_payments_from_ledger.py --rollback <the file it saved>

Never run this through ``run_all.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone

SCHOOL_ID = "aaryans-joya"
LEDGER = "aaryans_database/Fees-log-detailed-11-08-2026-17-36.xlsx"
ACADEMIC_YEAR = "2026-2027"

# Refuse rather than load a partial picture of the school's money.
MAX_UNMATCHED_SHARE = 0.05

COL_RECEIPT, COL_ADMISSION, COL_TYPE = 0, 1, 7
COL_BILLED, COL_PAID, COL_DISCOUNT, COL_BALANCE = 8, 9, 10, 11
COL_MODE, COL_REFERENCE, COL_DATE, COL_REMARK = 12, 13, 15, 21

_MONTHS = {
    "apr": "april", "may": "may", "jun": "june", "jul": "july", "aug": "august",
    "sep": "september", "oct": "october", "nov": "november", "dec": "december",
    "jan": "january", "feb": "february", "mar": "march",
}


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def classify(fee_type: str) -> tuple[str, str]:
    """Turn the office's wording into a fee head and a period the platform can group by.

    The office writes the same charge several ways across the year, so this matches on
    what the wording contains rather than on an exact string. Anything it does not
    recognise keeps its original wording and lands in the ``other`` period, where it is
    counted and reported rather than being quietly dropped.
    """
    text = (fee_type or "").strip().lower()
    if not text:
        return "Unlabelled", "other"
    if "transport" in text:
        for short, full in _MONTHS.items():
            if re.search(rf"\b{short}", text):
                return "Transport Fee", f"transport-{full}"
        return "Transport Fee", "transport-other"
    if "composite" in text:
        # The quarter number must be the digit that sits in front of the word "quarter",
        # not simply a digit somewhere in the line. The school writes its fourth quarter
        # as "composite fee 4 qtr (jan, feb, march) 2 (jan)", and a looser rule reads the
        # stray 2 and files 122 payments under the second quarter.
        match = re.search(r"\b([1-4])(?:st|nd|rd|th)?\s*q", text)
        if match:
            return "Composite Fee", f"q{match.group(1)}"
        return "Composite Fee", "other"
    if "registration" in text:
        return "Registration Fee", "admission"
    if "admission" in text:
        return "Admission Fee", "admission"
    if "due" in text:
        return "Dues carried forward", "previous-session"
    if "fine" in text:
        return "Late Fine", "fine"
    if "bounse" in text or "bounce" in text:
        return "Cheque bounce charge", "other"
    return fee_type.strip(), "other"


def read_ledger(root: str) -> list[dict]:
    """The real fee lines, which stop at the summary row.

    The file has a second table appended below that summary (a payment-mode breakdown
    with completely different columns). Reading past the summary would treat those as
    payments, and they are not.
    """
    import openpyxl

    rows = list(openpyxl.load_workbook(os.path.join(root, LEDGER), read_only=True)
                .active.iter_rows(values_only=True))[2:]
    try:
        end = next(i for i, row in enumerate(rows) if str(row[COL_RECEIPT]).strip() == "Total")
    except StopIteration:
        raise SystemExit(
            "the ledger has no 'Total' row, so where the fee lines stop cannot be known. "
            "Refusing to read the whole sheet as payments."
        )

    seen_on_receipt: dict[str, int] = {}
    lines = []
    for row in rows[:end]:
        receipt = str(row[COL_RECEIPT] or "").strip()
        admission = str(row[COL_ADMISSION] or "").strip()
        head, period = classify(str(row[COL_TYPE] or ""))
        position = seen_on_receipt.get(receipt, 0)
        seen_on_receipt[receipt] = position + 1

        def money(index):
            try:
                return float(row[index] or 0)
            except (TypeError, ValueError):
                return 0.0

        lines.append({
            "receipt": receipt,
            "admission_number": admission,
            "fee_head": head,
            "fee_period": period,
            "original_wording": str(row[COL_TYPE] or "").strip(),
            "paid": money(COL_PAID),
            "discount": money(COL_DISCOUNT),
            "mode": str(row[COL_MODE] or "").strip() or "Cash",
            "reference": str(row[COL_REFERENCE] or "").strip(),
            "paid_on": str(row[COL_DATE] or "").strip(),
            "remark": str(row[COL_REMARK] or "").strip(),
            "ledger_key": f"ledger|{receipt}|{position}|{head.lower()}|{period}",
        })
    return lines


def _iso(day: str) -> str:
    """The ledger writes dates as DD-MM-YYYY."""
    try:
        return datetime.strptime(day, "%d-%m-%Y").date().isoformat()
    except (ValueError, TypeError):
        return ""


async def plan(db, lines: list[dict]) -> dict:
    students = await db.students.find(
        {"schoolId": SCHOOL_ID},
        {"_id": 0, "id": 1, "admission_number": 1, "branch_id": 1},
    ).to_list(5000)
    by_admission = {str(s.get("admission_number") or "").strip(): s for s in students}

    already = await db.fee_transactions.find(
        {"schoolId": SCHOOL_ID, "ledger_key": {"$exists": True}}, {"_id": 0, "ledger_key": 1}
    ).to_list(50000)
    loaded_keys = {row["ledger_key"] for row in already}

    to_create, no_admission, not_on_platform, already_loaded = [], [], [], 0
    unrecognised = {}
    money_placed = money_unplaced = 0.0

    for line in lines:
        value = line["paid"] + line["discount"]
        if not line["admission_number"]:
            no_admission.append(line)
            money_unplaced += value
            continue
        student = by_admission.get(line["admission_number"])
        if not student:
            not_on_platform.append(line["admission_number"])
            money_unplaced += value
            continue
        money_placed += value
        if line["fee_period"] == "other":
            unrecognised[line["original_wording"]] = unrecognised.get(line["original_wording"], 0) + 1
        if line["ledger_key"] in loaded_keys:
            already_loaded += 1
            continue

        to_create.append({
            "id": str(uuid.uuid4()),
            "schoolId": SCHOOL_ID,
            "branch_id": student.get("branch_id", ""),
            "student_id": student["id"],
            "admission_number": line["admission_number"],
            "receipt_number": line["receipt"],
            "ledger_key": line["ledger_key"],
            "fee_head": line["fee_head"],
            "fee_type": line["fee_head"],
            "fee_period": line["fee_period"],
            "original_wording": line["original_wording"],
            "amount": line["paid"],
            "paid_amount": line["paid"],
            "discount_amount": line["discount"],
            "payment_mode": line["mode"],
            "reference": line["reference"],
            "payment_date": _iso(line["paid_on"]),
            "remark": line["remark"],
            "status": "paid" if line["paid"] > 0 else "waived",
            "academic_year": ACADEMIC_YEAR,
            "source": "the school's payment ledger of 11 August 2026 (Release 2 step 8)",
        })

    total_money = money_placed + money_unplaced
    return {
        "lines": len(lines),
        "to_create": to_create,
        "already_loaded": already_loaded,
        "no_admission_number": no_admission,
        "not_on_platform": sorted(set(not_on_platform)),
        "unrecognised_wording": unrecognised,
        "money_placed": money_placed,
        "money_unplaced": money_unplaced,
        "unplaced_share": (money_unplaced / total_money) if total_money else 0.0,
        "collected": sum(row["paid_amount"] for row in to_create),
        "discounted": sum(row["discount_amount"] for row in to_create),
    }


async def apply(db, lines: list[dict], *, dry_run: bool = True) -> dict:
    result = await plan(db, lines)
    if result["unplaced_share"] > MAX_UNMATCHED_SHARE:
        result["blocked_by"] = [
            f"{result['unplaced_share'] * 100:.1f}% of the money in this ledger could not "
            "be placed on a child on the platform. Loading most of a school's collections "
            "and reporting success is worse than loading none: nobody goes looking for "
            "the rest. Fix the admission numbers first."
        ]
        return result
    if dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    for doc in result["to_create"]:
        await db.fee_transactions.insert_one({**doc, "_id": doc["id"], "created_at": now})
    result["applied"] = True
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        ids = json.load(handle)
    out = await db.fee_transactions.delete_many({"schoolId": SCHOOL_ID, "id": {"$in": ids}})
    return {"deleted": out.deleted_count, "expected": len(ids)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Release 2 step 8: load the school's collections.")
    parser.add_argument("--apply", action="store_true", help="actually write. Default is a dry run.")
    parser.add_argument("--rollback", help="path to a rollback file from a previous --apply")
    args = parser.parse_args()

    root = _repo_root()
    sys.path.insert(0, os.path.join(root, "backend"))
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, "backend", ".env"))
    except ImportError:
        pass
    from database import connect_db, get_db

    await connect_db()
    db = get_db()

    if args.rollback:
        out = await rollback_from(db, args.rollback)
        print(f"removed {out['deleted']} of {out['expected']} loaded payment records")
        return 0

    result = await apply(db, read_ledger(root), dry_run=not args.apply)

    print(f"  fee lines in the ledger                 {result['lines']:>6}")
    print(f"  already on the platform, skipped        {result['already_loaded']:>6}")
    print(f"  payment records to create               {len(result['to_create']):>6}")
    print(f"  money collected, to load          {result['collected']:>12,.0f}")
    print(f"  discounts given, to load          {result['discounted']:>12,.0f}")
    print(f"\n  lines with no admission number          {len(result['no_admission_number']):>6}")
    print(f"  children named, not on the platform     {len(result['not_on_platform']):>6}")
    print(f"  money that could not be placed    {result['money_unplaced']:>12,.0f}"
          f"   ({result['unplaced_share'] * 100:.2f}%)")

    if result["unrecognised_wording"]:
        print("\n  Wording this does not recognise, kept as written and grouped as 'other':")
        for wording, count in sorted(result["unrecognised_wording"].items(), key=lambda kv: -kv[1])[:10]:
            print(f"    {count:>5}  {wording[:60]}")

    print("\n  NOT loaded, deliberately: what the ledger says was billed and what it says")
    print("  is outstanding. Those two are the only figures its own summary disagrees")
    print("  with its own rows about. Money collected and discounts agree to the rupee.")

    if result.get("blocked_by"):
        print("\nNOTHING WAS WRITTEN.")
        for reason in result["blocked_by"]:
            print(f"  {reason}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-039-payments-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([doc["id"] for doc in result["to_create"]], handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
