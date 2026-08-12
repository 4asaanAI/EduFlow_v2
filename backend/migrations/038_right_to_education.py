"""Release 2, step 7 - record the children who hold a Right to Education place.

Some children hold a place paid for by the government. They **pay no school fee at all**.
If they use the school bus they pay for the bus, and a late bus payment is fined on the
ordinary schedule.

--------------------------------------------------------------------------------
This is a mark on the child, and deliberately NOT a discount
--------------------------------------------------------------------------------

Recording it as a 100% discount would be wrong twice over. The fee is not reduced, it does
not apply; and a discount interacts with the concession rules and can be edited away by
anyone who may edit a discount. So it is its own field, ``rte_place``, and the billing
path skips the school fee for these children rather than discounting it to nothing.

--------------------------------------------------------------------------------
Where the 21 come from, and the discrepancy that turned out not to be one
--------------------------------------------------------------------------------

``Students-06-08-2026-12-08-00.xlsx`` carries an ``IsRteStudent`` column and **21 children
are marked Yes**. Confirmed by Abhimanyu on 2026-08-11. Cross-checked against the payment
ledger and it holds: of the 13 who appear there, **not one was charged a school fee.**

The school marks them twice over: all 21 also carry ``(RTE)`` inside the child's own name.

**Admission 15067 was carried for days as a discrepancy and is not one.** Its name appeared
to contain "RTE" while its flag said No. The child is **PIRTEEK CHOUDHARY**: the letters
r-t-e are inside the spelling of the name. Nothing about that child is a Right to Education
place, and the school's flag column and its naming agree everywhere. Recorded here so
nobody re-opens it.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/038_right_to_education.py
    ... 038_right_to_education.py --apply
    ... 038_right_to_education.py --rollback <the file it saved>

Never run this through ``run_all.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

SCHOOL_ID = "aaryans-joya"
EXPORT = "aaryans_database/Students-06-08-2026-12-08-00.xlsx"
EXPECTED = 21


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_export(root: str) -> list[dict]:
    """The children the school itself marks as holding a Right to Education place."""
    import openpyxl

    rows = list(openpyxl.load_workbook(os.path.join(root, EXPORT), read_only=True)
                .active.iter_rows(values_only=True))
    header = [str(h).strip() if h is not None else "" for h in rows[0]]
    try:
        flag = header.index("IsRteStudent")
        admission = header.index("AdmissionNo")
        name = header.index("Name")
    except ValueError as exc:
        raise SystemExit(f"the export does not carry the column this migration needs: {exc}")

    found = []
    for row in rows[1:]:
        if str(row[flag]).strip().lower() in ("yes", "true", "1"):
            found.append({
                "admission_number": str(row[admission]).strip(),
                "name_marks_it_too": "RTE" in str(row[name] or "").upper(),
            })
    return found


async def plan(db, marked: list[dict]) -> dict:
    students = await db.students.find(
        {"schoolId": SCHOOL_ID},
        {"_id": 0, "id": 1, "admission_number": 1, "rte_place": 1, "uses_transport": 1},
    ).to_list(5000)
    by_admission = {str(s.get("admission_number") or "").strip(): s for s in students}

    changes, not_on_platform = [], []
    for row in marked:
        student = by_admission.get(row["admission_number"])
        if not student:
            not_on_platform.append(row["admission_number"])
            continue
        changes.append({
            "id": student["id"],
            "admission_number": row["admission_number"],
            "uses_transport": bool(student.get("uses_transport")),
            "before": {"rte_place": student.get("rte_place")},
            "after": {"rte_place": True},
        })
    return {
        "marked_in_the_export": len(marked),
        "changes": changes,
        "not_on_platform": not_on_platform,
        "also_marked_in_the_name": sum(1 for row in marked if row["name_marks_it_too"]),
        "ride_the_bus": sum(1 for c in changes if c["uses_transport"]),
    }


async def apply(db, marked: list[dict], *, dry_run: bool = True) -> dict:
    result = await plan(db, marked)

    # A count that has drifted means the school's list has changed, and whether a child
    # owes any school fee at all is not something to discover by accident.
    if result["marked_in_the_export"] != EXPECTED:
        result["blocked_by"] = [
            f"the export now marks {result['marked_in_the_export']} children, not the "
            f"{EXPECTED} the school confirmed on 2026-08-11. Whether a child owes any "
            "school fee is not a number to accept silently. Confirm the list again."
        ]
        return result
    if not result["changes"]:
        result["blocked_by"] = [
            "none of the marked children were found on the platform, so this would mark "
            "nobody and report success. Check the admission numbers first."
        ]
        return result
    if dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    for change in result["changes"]:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": change["id"]},
            {"$set": {
                "rte_place": True,
                "rte_source": "the school's own student export of 6 August 2026, "
                              "confirmed by Abhimanyu on 2026-08-11",
                "rte_marked_at": now,
            }},
        )
    result["applied"] = True
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    for row in saved:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": row["id"]},
            {"$unset": {"rte_place": "", "rte_source": "", "rte_marked_at": ""}},
        )
    return {"restored": len(saved)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Release 2 step 7: Right to Education places.")
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
        print(f"the mark was removed from {out['restored']} children")
        return 0

    result = await apply(db, read_export(root), dry_run=not args.apply)

    print(f"  marked in the school's export           {result['marked_in_the_export']:>5}")
    print(f"  also marked inside the child's name     {result['also_marked_in_the_name']:>5}")
    print(f"  records to mark                         {len(result['changes']):>5}")
    print(f"  of those, riding the school bus         {result['ride_the_bus']:>5}")
    print(f"  in the export, not on the platform      {len(result['not_on_platform']):>5}")
    print("\n  These children owe NO school fee. Those on the bus pay for the bus, and a")
    print("  late bus payment is fined on the ordinary schedule.")

    if result.get("blocked_by"):
        print("\nNOTHING WAS WRITTEN.")
        for reason in result["blocked_by"]:
            print(f"  {reason}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-038-rte-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result["changes"], handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
