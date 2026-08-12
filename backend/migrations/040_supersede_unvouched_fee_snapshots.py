"""Release 2, step 8 (second half) - retire the fee figures nobody stands behind.

**1,844 children carry a ``fee_snapshot`` whose own ``source`` field says it is not the
fee ledger.** It came from a student export in August. Nobody has ever vouched for those
numbers, and until step 8 they were the only fee figures on the platform, so they are what
anyone looking at a child's record has been reading.

Abhimanyu, 2026-08-12: **use only the current and latest data.** The current and latest
data is the payment ledger of 11 August, loaded by migration 039, and the fee structures
loaded by migration 035, which three independent documents agree on.

--------------------------------------------------------------------------------
Retired, not deleted
--------------------------------------------------------------------------------

The old figure is moved to ``superseded_fee_snapshot`` rather than thrown away, with the
date and the reason beside it. Two reasons: somebody will ask where a number on an old
printout came from, and a migration that destroys the only copy of anything is a migration
that cannot really be undone.

**Nothing reads ``superseded_fee_snapshot``.** That is the point: the record survives and
no screen, report or bill can pick it up by accident.

--------------------------------------------------------------------------------
It reports the disagreement before it retires anything
--------------------------------------------------------------------------------

Every dry run prints how far the old figures sit from what the school actually collected,
per child and in total. That is the number worth reading: it is the size of the gap
between what the platform has been showing and what the school's own ledger says.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Run **migration 039 first**, or this retires the only fee figures on the platform and
leaves nothing in their place::

    backend/.venv/Scripts/python.exe backend/migrations/040_supersede_unvouched_fee_snapshots.py
    ... 040_supersede_unvouched_fee_snapshots.py --apply
    ... 040_supersede_unvouched_fee_snapshots.py --rollback <the file it saved>

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


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _snapshot_total(snapshot) -> float:
    """Whatever this snapshot claims the family owes or has paid, as one number.

    The shape is not consistent across the export, so this adds up the numeric values it
    finds rather than assuming a key that may not be there.
    """
    if isinstance(snapshot, dict):
        total = 0.0
        for value in snapshot.values():
            if isinstance(value, (int, float)):
                total += float(value)
        return total
    if isinstance(snapshot, (int, float)):
        return float(snapshot)
    return 0.0


async def plan(db) -> dict:
    students = await db.students.find(
        {"schoolId": SCHOOL_ID, "fee_snapshot": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "admission_number": 1, "fee_snapshot": 1},
    ).to_list(5000)

    paid_by_student: dict[str, float] = {}
    loaded = await db.fee_transactions.find(
        {"schoolId": SCHOOL_ID, "ledger_key": {"$exists": True}},
        {"_id": 0, "student_id": 1, "paid_amount": 1},
    ).to_list(50000)
    for row in loaded:
        paid_by_student[row["student_id"]] = paid_by_student.get(row["student_id"], 0.0) + float(
            row.get("paid_amount") or 0
        )

    changes, differences = [], []
    for student in students:
        old = _snapshot_total(student.get("fee_snapshot"))
        real = paid_by_student.get(student["id"], 0.0)
        changes.append({
            "id": student["id"],
            "admission_number": student.get("admission_number"),
            "before": student.get("fee_snapshot"),
        })
        if abs(old - real) >= 1:
            differences.append({
                "admission_number": student.get("admission_number"),
                "old_figure": old,
                "the_ledger_says": real,
                "difference": old - real,
            })

    return {
        "carrying_a_snapshot": len(students),
        "changes": changes,
        "the_ledger_has_been_loaded_for": len(paid_by_student),
        "differences": differences,
        "total_difference": sum(abs(row["difference"]) for row in differences),
    }


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if not result["the_ledger_has_been_loaded_for"]:
        result["blocked_by"] = [
            "no payments from the school's ledger are on the platform yet, so this would "
            "retire the only fee figures there are and leave nothing in their place. Run "
            "migration 039 first."
        ]
        return result
    if not result["changes"]:
        result["blocked_by"] = ["no child carries a fee snapshot, so there is nothing to retire."]
        return result
    if dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    for change in result["changes"]:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": change["id"]},
            {"$set": {
                "superseded_fee_snapshot": change["before"],
                "superseded_fee_snapshot_at": now,
                "superseded_fee_snapshot_reason":
                    "not the fee ledger by its own label; replaced by the school's payment "
                    "ledger of 11 August 2026 (Release 2 step 8)",
            }, "$unset": {"fee_snapshot": ""}},
        )
    result["applied"] = True
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    for row in saved:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": row["id"]},
            {"$set": {"fee_snapshot": row["before"]},
             "$unset": {"superseded_fee_snapshot": "", "superseded_fee_snapshot_at": "",
                        "superseded_fee_snapshot_reason": ""}},
        )
    return {"restored": len(saved)}


async def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Release 2 step 8: retire the fee figures nobody vouched for."
    )
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
        print(f"put the old figures back on {out['restored']} children")
        return 0

    result = await apply(db, dry_run=not args.apply)

    print(f"  children carrying an unvouched figure   {result['carrying_a_snapshot']:>6}")
    print(f"  children with ledger payments loaded    {result['the_ledger_has_been_loaded_for']:>6}")
    print(f"  where the two disagree by 1 or more     {len(result['differences']):>6}")
    print(f"  total disagreement                {result['total_difference']:>12,.0f}")
    print("\n  The old figure is MOVED, not deleted: it stays on the record as")
    print("  superseded_fee_snapshot, which nothing on the platform reads.")

    if result.get("blocked_by"):
        print("\nNOTHING WAS WRITTEN.")
        for reason in result["blocked_by"]:
            print(f"  {reason}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-040-fee-snapshots-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result["changes"], handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
