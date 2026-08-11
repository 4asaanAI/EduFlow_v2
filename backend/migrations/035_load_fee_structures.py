"""Release 2, step 3 - load the school's 2026-27 fee structures.

``fee_structures`` is completely empty today, so every family on the platform is on no
fee plan at all. This puts the school's real price list on it.

--------------------------------------------------------------------------------
Where every figure comes from
--------------------------------------------------------------------------------

**Three independent documents agree on all seventeen class bands, to the rupee**, and
step 1 checked them against each other (see
``_bmad-output/implementation-artifacts/release-2/step-1-fee-document-reconciliation-2026-08-11.md``):

* the school's photographed 2026-27 fee sheet
* ``Fees-log-detailed-11-08-2026-17-36.xlsx``, what the school actually charged
* ``Students-Fees-Structure-Report-06-08-2026-12-49.xlsx``, every child's own figures

Every class charges **the same amount in all four quarters**. There is no heavier quarter.

--------------------------------------------------------------------------------
What is loaded, and what is deliberately NOT
--------------------------------------------------------------------------------

**Loaded:** four quarterly instalments per class, with the school's own due dates of the
15th, and the class's band as a single composite fee head.

**Recorded but not billed:** registration and admission charges. These are for **new
students only** and every class carries exactly one value for each, with no ambiguity
anywhere in the ledger. They are written onto the structure as ``new_student_charges``
and are **deliberately kept out of the instalments**, because an instalment is billed to
every child in the class. Putting a 12,000 admission fee into an instalment would charge
it to 1,842 families, most of whom were admitted years ago.

⚠️ **Nothing on the platform reads ``new_student_charges`` yet.** It is a reconciled
record, not a working feature. Do not describe it to the school as one.

**Not loaded at all:** transport (step 4), concessions (step 5) and late fines (step 9).
Fines are held back on Abhimanyu's explicit instruction so that a wrong fine never
reaches a family while the rest of the ledger is being settled.

--------------------------------------------------------------------------------
⚠️ One child will be billed the wrong band, and it is not fixable here
--------------------------------------------------------------------------------

A fee structure is keyed by ``class_id``. For 11th and 12th the band therefore comes from
the **class's** stream. **Admission 263105 sits in 11th section A, which is a Science
section, while both of the school's documents record that child as Commerce.** A
class-keyed structure bills them 17,700 a quarter instead of 16,500, so **1,200 a quarter
and 4,800 a year too much.**

This migration does not paper over it. Either the school moves that child into a Commerce
section, or billing has to read the student's own ``stream`` rather than the class's.
**It is reported every time this runs** and it must be settled before any bill goes out.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/035_load_fee_structures.py

Then::

    ... 035_load_fee_structures.py --apply

``fee_structures`` being empty is what makes this the safest large write in the release:
the rollback is deleting exactly what was inserted, and the rollback file naming every id
is written outside the repository before anything is created::

    ... 035_load_fee_structures.py --rollback <that file>

Never run this through ``run_all.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Dict, List

SCHOOL_ID = "aaryans-joya"
ACADEMIC_YEAR = "2026-2027"

# The seven bands, per QUARTER. Confirmed by three independent documents on all
# seventeen classes (step 1). Every class charges the same in all four quarters.
BAND_BY_CLASS = {
    "NUR": 7050, "LKG": 7050, "UKG": 7050,
    "1st": 8250, "2nd": 8250,
    "3rd": 8850, "4th": 8850, "5th": 8850,
    "6th": 9750, "7th": 9750, "8th": 9750,
    "9th": 12000, "10th": 12000,
}
# 11th and 12th are charged by stream, 4,800 a year apart.
BAND_BY_STREAM = {"Commerce": 16500, "Science": 17700}

# New students only. One value per class across the whole ledger, no ambiguity.
# 10th and 12th carry none: nobody joins the school at those two classes.
NEW_STUDENT_CHARGES = {
    "NUR": (1200, 12000), "LKG": (1200, 12000), "UKG": (1200, 12000),
    "1st": (1200, 12000), "2nd": (1200, 12000),
    "3rd": (1200, 13000), "4th": (1200, 13000), "5th": (1200, 13000),
    "6th": (1200, 13000), "7th": (1200, 13000), "8th": (1200, 13000),
    "9th": (1500, 16500), "10th": None,
    "11th": (1500, 16500), "12th": None,
}

# The school's four quarters and its own due dates: the 15th, with a 15-day window.
QUARTERS = [
    ("q1", "Composite Fee 1st Quarter (April, May, June)", "2026-04-15"),
    ("q2", "Composite Fee 2nd Quarter (July, August, September)", "2026-07-15"),
    ("q3", "Composite Fee 3rd Quarter (October, November, December)", "2026-10-15"),
    ("q4", "Composite Fee 4th Quarter (January, February, March)", "2027-01-15"),
]


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def band_for(cls: dict) -> tuple[int, str]:
    """The quarterly amount for a class, and why. Refuses rather than guesses."""
    name = (cls.get("name") or "").strip()
    if name in BAND_BY_CLASS:
        return BAND_BY_CLASS[name], f"class band for {name}"
    if name in ("11th", "12th"):
        stream = (cls.get("stream") or "").strip()
        if stream not in BAND_BY_STREAM:
            raise ValueError(
                f"{name} section {cls.get('section')!r} has no stream on its record, so "
                "there is no way to know whether it is charged 16,500 or 17,700. Run "
                "migration 034 first."
            )
        return BAND_BY_STREAM[stream], f"{name} {stream}"
    raise ValueError(f"no band is known for the class {name!r}")


async def plan(db) -> dict:
    existing = await db.fee_structures.find(
        {"schoolId": SCHOOL_ID}, {"_id": 0, "id": 1, "class_id": 1}
    ).to_list(500)
    classes = await db.classes.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(500)

    already = {c["class_id"] for c in existing}
    to_create, refused = [], []
    for cls in sorted(classes, key=lambda c: (c.get("name") or "", c.get("section") or "")):
        if cls["id"] in already:
            continue
        try:
            amount, why = band_for(cls)
        except ValueError as exc:
            refused.append({"class_id": cls["id"], "reason": str(exc)})
            continue
        label = f"{cls.get('name')}-{cls.get('section')}" if cls.get("section") else cls.get("name")
        charges = NEW_STUDENT_CHARGES.get((cls.get("name") or "").strip())
        to_create.append({
            "id": str(uuid.uuid4()),
            "schoolId": SCHOOL_ID,
            "name": f"{label} fees {ACADEMIC_YEAR}",
            "class_id": cls["id"],
            "branch_id": cls.get("branch_id", ""),
            "academic_year": ACADEMIC_YEAR,
            "stream": cls.get("stream", ""),
            "quarterly_amount": amount,
            "band_reason": why,
            "fee_heads": [{"name": "Composite Fee", "amount": amount}],
            "installments": [
                {"code": code, "label": lab, "due_date": due,
                 "fee_heads": [{"name": "Composite Fee", "amount": amount}]}
                for code, lab, due in QUARTERS
            ],
            # New admissions only. Nothing reads this yet; see the docstring.
            "new_student_charges": (
                {"registration_fee": charges[0], "admission_fee": charges[1],
                 "applies_to": "new admissions only", "billed_by_the_platform": False}
                if charges else None
            ),
            "version": 1,
            "status": "active",
            "source": "school 2026-27 fee sheet, confirmed by the payment ledger and the "
                      "per-student fee report (Release 2 step 1)",
        })

    # The one child a class-keyed structure gets wrong. Reported every run.
    wrong_band = []
    seniors = await db.students.find(
        {"schoolId": SCHOOL_ID, "class_id": {"$regex": "^cls-1[12]th"}},
        {"_id": 0, "admission_number": 1, "class_id": 1, "stream": 1},
    ).to_list(500)
    by_class = {c["id"]: c for c in classes}
    for s in seniors:
        cls = by_class.get(s["class_id"]) or {}
        if s.get("stream") and cls.get("stream") and s["stream"] != cls["stream"]:
            wrong_band.append({
                "admission_number": s.get("admission_number"),
                "class_id": s["class_id"],
                "class_stream": cls["stream"],
                "student_stream": s["stream"],
                "over_or_under": BAND_BY_STREAM[cls["stream"]] - BAND_BY_STREAM[s["stream"]],
            })

    return {
        "existing": len(existing),
        "to_create": to_create,
        "refused": refused,
        "wrong_band": wrong_band,
        "classes": len(classes),
    }


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if result["refused"]:
        result["blocked_by"] = [r["reason"] for r in result["refused"]]
        return result
    if dry_run:
        return result
    now = datetime.now(timezone.utc).isoformat()
    for doc in result["to_create"]:
        await db.fee_structures.insert_one({**doc, "_id": doc["id"], "created_at": now})
    result["applied"] = True
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        ids = json.load(handle)
    out = await db.fee_structures.delete_many({"schoolId": SCHOOL_ID, "id": {"$in": ids}})
    return {"deleted": out.deleted_count, "expected": len(ids)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Release 2 step 3: load fee structures.")
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
        print(f"deleted {out['deleted']} of {out['expected']} fee structures")
        return 0

    result = await apply(db, dry_run=not args.apply)

    print(f"  class records on the platform      {result['classes']:>5}")
    print(f"  fee structures already there       {result['existing']:>5}")
    print(f"  fee structures to create           {len(result['to_create']):>5}")
    print(f"  classes refused                    {len(result['refused']):>5}")

    print(f"\n  {'class':<14}{'per quarter':>13}{'per year':>11}   band from")
    print("  " + "-" * 62)
    for doc in result["to_create"]:
        label = doc["name"].replace(f" fees {ACADEMIC_YEAR}", "")
        a = doc["quarterly_amount"]
        print(f"  {label:<14}{a:>13,}{a * 4:>11,}   {doc['band_reason']}")

    if result["wrong_band"]:
        print("\n  ⚠️  A class-keyed fee structure bills these children the wrong band,")
        print("     because their own record disagrees with their section's stream:")
        for w in result["wrong_band"]:
            d = w["over_or_under"]
            word = "OVER" if d > 0 else "under"
            print(f"     admission {w['admission_number']} in {w['class_id']}: class says "
                  f"{w['class_stream']}, child says {w['student_stream']} "
                  f"-> {word}charged {abs(d):,} a quarter, {abs(d) * 4:,} a year")
        print("     Settle this before any bill goes out.")

    if result.get("blocked_by"):
        print("\nNOTHING WAS CREATED.")
        for b in result["blocked_by"]:
            print(f"  {b}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was created. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-035-fee-structures-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump([d["id"] for d in result["to_create"]], handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
