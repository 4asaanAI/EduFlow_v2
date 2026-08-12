"""Release 2, step 6 - put the school's own sibling links on the children's records.

Sonu asked for a child with a brother or sister in the school to be tagged, with the
other children's admission numbers on the record and on the fee screen, so the office can
see at a glance who is owed which concession.

--------------------------------------------------------------------------------
Only what the school has itself stated
--------------------------------------------------------------------------------

Abhimanyu, 2026-08-11: use only the siblings the school has defined, and put everything
else in a file for the school to read when the logins are handed over.

So this writes **380 families the office named by hand** in the remark on a payment, and
**445 concession marks copied from discounts the office actually gave**. It infers
nothing. In particular it does NOT group children by father's name and mobile number,
which would find more families and would be guessing about money, and it does NOT work
out who is youngest, which the platform often cannot know: 787 children have no date of
birth recorded.

``scripts/sibling_links.py`` produces the reading and touches no database. Run it first.

--------------------------------------------------------------------------------
What lands on a child's record
--------------------------------------------------------------------------------

* ``siblings`` - the other children's admission numbers, which is the tag Sonu asked for
* ``sibling_source`` - that the school's own payment remarks are where it came from
* ``concessions.sibling`` - true ONLY for a child the office actually discounted

The concession mark and the family tag are deliberately two different things. Being in a
family does not earn the concession: the youngest child pays full. Copying the office's
own decision is safer than deciding it here, and it means the 380 children who pay full
keep paying full.

--------------------------------------------------------------------------------
What is deliberately left for a person, and reported
--------------------------------------------------------------------------------

* **58 children were given a sibling concession with no sibling ever named.** They are
  NOT marked here, because the whole instruction is to use only stated links. They are in
  the handover file so the school can name the sibling before anyone is billed.
* **31 families do not have exactly one child paying full**, which the school's own rule
  says they should. 17 of them had every child discounted. That is money and it is the
  school's to explain, so the marks follow what the office did and the families are named
  in the handover file.
* **43 remarks mention a sibling and no admission number could be read** out of them.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/037_sibling_links.py
    ... 037_sibling_links.py --apply
    ... 037_sibling_links.py --rollback <the file it saved>

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


async def plan(db, reading: dict) -> dict:
    students = await db.students.find(
        {"schoolId": SCHOOL_ID},
        {"_id": 0, "id": 1, "admission_number": 1, "siblings": 1, "concessions": 1},
    ).to_list(5000)
    by_admission = {}
    for student in students:
        adm = str(student.get("admission_number") or "").strip()
        if adm:
            by_admission[adm] = student

    to_mark = set(reading["to_mark"])
    changes, not_on_platform = [], []
    for family in reading["families"]:
        for adm in family["members"]:
            student = by_admission.get(adm)
            if not student:
                not_on_platform.append(adm)
                continue
            others = [m for m in family["members"] if m != adm]
            gets_concession = adm in to_mark
            changes.append({
                "id": student["id"],
                "admission_number": adm,
                "before": {
                    "siblings": student.get("siblings"),
                    "sibling": (student.get("concessions") or {}).get("sibling"),
                },
                "after": {
                    "siblings": others,
                    "sibling": gets_concession,
                },
            })

    return {
        "families": len(reading["families"]),
        "children_in_a_family": reading["children_in_a_stated_family"],
        "changes": changes,
        "not_on_platform": sorted(set(not_on_platform)),
        "will_get_the_concession": sum(1 for c in changes if c["after"]["sibling"]),
        "will_pay_full": sum(1 for c in changes if not c["after"]["sibling"]),
        "discounted_but_no_sibling_named": reading["discounted_with_no_stated_family"],
        "odd_families": reading["odd_families"],
        "unreadable": reading["unreadable"],
    }


async def apply(db, reading: dict, *, dry_run: bool = True) -> dict:
    result = await plan(db, reading)
    if not result["changes"]:
        result["blocked_by"] = [
            "not one child in the stated families was found on the platform, so this "
            "would mark nobody and report success. Check the admission numbers first."
        ]
        return result
    if dry_run:
        return result
    now = datetime.now(timezone.utc).isoformat()
    for change in result["changes"]:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": change["id"]},
            {"$set": {
                "siblings": change["after"]["siblings"],
                "sibling_source": "the school's own payment remarks, Release 2 step 6",
                "sibling_linked_at": now,
                "concessions.sibling": change["after"]["sibling"],
            }},
        )
    result["applied"] = True
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    restored = 0
    for row in saved:
        await db.students.update_one(
            {"schoolId": SCHOOL_ID, "id": row["id"]},
            {"$set": {
                "siblings": row["before"]["siblings"],
                "concessions.sibling": row["before"]["sibling"],
            }, "$unset": {"sibling_source": "", "sibling_linked_at": ""}},
        )
        restored += 1
    return {"restored": restored}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Release 2 step 6: the school's sibling links.")
    parser.add_argument("--apply", action="store_true", help="actually write. Default is a dry run.")
    parser.add_argument("--rollback", help="path to a rollback file from a previous --apply")
    args = parser.parse_args()

    root = _repo_root()
    sys.path.insert(0, os.path.join(root, "backend"))
    sys.path.insert(0, root)
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(root, "backend", ".env"))
    except ImportError:
        pass
    from database import connect_db, get_db
    from scripts.sibling_links import analyse, read_ledger

    await connect_db()
    db = get_db()

    if args.rollback:
        out = await rollback_from(db, args.rollback)
        print(f"restored {out['restored']} children to what they were before")
        return 0

    reading = analyse(read_ledger(root))
    result = await apply(db, reading, dry_run=not args.apply)

    print(f"  families the school itself named        {result['families']:>5}")
    print(f"  children in one                         {result['children_in_a_family']:>5}")
    print(f"  records to tag                          {len(result['changes']):>5}")
    print(f"  -> keep the sibling concession          {result['will_get_the_concession']:>5}")
    print(f"  -> pay the full fee (the youngest)      {result['will_pay_full']:>5}")
    print(f"  named in a remark, not on the platform  {len(result['not_on_platform']):>5}")

    print("\n  For a person, and NOT decided here:")
    print(f"    {len(result['discounted_but_no_sibling_named']):>4} children were given a sibling concession with no sibling named.")
    print(f"         They are NOT marked. Naming the sibling is what settles them.")
    print(f"    {len(result['odd_families']):>4} families do not have exactly one child paying full.")
    print(f"    {len(result['unreadable']):>4} remarks mention a sibling and no admission number could be read.")

    if result.get("blocked_by"):
        print("\nNOTHING WAS WRITTEN.")
        for reason in result["blocked_by"]:
            print(f"  {reason}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-037-sibling-links-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result["changes"], handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
