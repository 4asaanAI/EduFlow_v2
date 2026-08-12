"""Take the 21 departed staff off the roll, and hand their classes to the new teachers.

Abhimanyu, 2026-08-12: the 22 staff missing from the school's teacher list have indeed
left, apart from the one who is also on the current staff list.

**That one is Adesh Singh**, and he is not a departure at all: he is the principal. He was
only ever on this list because he is an administrator and a teacher list does not contain
administrators. He is excluded here and nothing about his record changes.

--------------------------------------------------------------------------------
Marked as left, never deleted
--------------------------------------------------------------------------------

Each of the 21 keeps their record, their history and their attendance. What changes is
``is_active``, a ``left_on`` date and a reason. Their login is switched off, because
somebody who has left the school should not be able to sign in to it, and switching a
login off is undone in a second if any of this turns out to be wrong.

--------------------------------------------------------------------------------
Five classes would otherwise have a departed class teacher
--------------------------------------------------------------------------------

Five of the 21 are the class teacher of a live class. Marking them as left and stopping
there would leave 4th A, 4th B, 8th A, 9th A and 11th A with a teacher who no longer works
here, which is worse than either state on its own.

The school has already said who replaces them. Its own new-joiners list, the one the 12
teachers were created from, names a class against five of them, and they are exactly these
five classes:

===================  =====================  =================
class                who is leaving         who takes it on
===================  =====================  =================
4th A                KUMUD                  SHIVA TANTON
4th B                ARISHA MAM             AYUSHI YADAV
8th A                ASHWANI                SAKSHI PANDEY
9th A                FAISAL AHMED           DEEPAK KUMAR
11th A (Science)     DR PERMENDRA KUMAR     KAPIL KUMAR GUPTA
===================  =====================  =================

So the handover is the school's own statement, not our inference. It is written out in
full here because it is the part of this migration that changes what a parent sees.

--------------------------------------------------------------------------------
What this does NOT do
--------------------------------------------------------------------------------

**29 subject slots taught by the departing staff are left exactly as they are**, and
reported instead. The only source for who teaches what now is a typed summary of
photographs of a wall chart, which names people by first name only and still lists several
of the leavers. Reassigning a subject on that would be a guess about a real timetable.
They are in the handover file for the school to settle.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/043_staff_departures.py
    ... 043_staff_departures.py --apply
    ... 043_staff_departures.py --rollback <the file it saved>

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
MIGRATION_ACTOR = "migration-043"
LEFT_ON = "2026-08-12"
REASON = ("absent from the school's own teacher list of 6 August 2026; confirmed as "
          "departed by Abhimanyu on 12 August 2026")

# The 22 queried on 6 August, minus Adesh Singh, who is the principal and has not left.
DEPARTED = (
    "ARISHA MAM", "ASHWANI", "B S Yadav", "DR PERMENDRA KUMAR", "FAISAL AHMED", "KUMUD",
    "LAIBA QURESHI", "MONIKA CHAUDHARY", "MUSKAN", "NEHA", "PRAGATI TANDON",
    "PRATEEK KUMAR", "PRERITA", "Pramod", "RACHNA", "RAZIA KHAN", "ROHIT", "RUCHI",
    "Sapna Pandey", "Shilpa", "TRIPTI",
)
STAYING = "ADESH SINGH"

# class name, section, who is leaving, who the school named as the new class teacher
HANDOVERS = (
    ("4th",  "A", "KUMUD",              "SHIVA TANTON"),
    ("4th",  "B", "ARISHA MAM",         "AYUSHI YADAV"),
    ("8th",  "A", "ASHWANI",            "SAKSHI PANDEY"),
    ("9th",  "A", "FAISAL AHMED",       "DEEPAK KUMAR"),
    ("11th", "A", "DR PERMENDRA KUMAR", "KAPIL KUMAR GUPTA"),
)


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


async def plan(db) -> dict:
    staff = await db.staff.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(5000)
    classes = await db.classes.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(500)
    subjects = await db.subjects.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(5000)

    by_name: dict[str, list] = {}
    for row in staff:
        by_name.setdefault(_norm(row.get("name")), []).append(row)

    leaving, problems = [], []
    for name in DEPARTED:
        matches = by_name.get(_norm(name), [])
        if len(matches) != 1:
            problems.append(f"{name}: expected one staff record, found {len(matches)}")
            continue
        leaving.append(matches[0])

    if by_name.get(_norm(STAYING)) is None:
        problems.append(f"{STAYING}: not found, so the exclusion cannot be verified")

    leaving_ids = {row["id"] for row in leaving}
    leaving_user_ids = {row.get("user_id") for row in leaving if row.get("user_id")}

    handovers = []
    for class_name, section, outgoing, incoming in HANDOVERS:
        target = next((row for row in classes
                       if row.get("name") == class_name and row.get("section") == section), None)
        replacement = by_name.get(_norm(incoming), [])
        if target is None or len(replacement) != 1:
            problems.append(
                f"{class_name}-{section}: class found {target is not None}, "
                f"records for {incoming}: {len(replacement)}"
            )
            continue
        new_teacher = replacement[0]
        new_id = new_teacher.get("user_id") or new_teacher["id"]
        if target.get("class_teacher_id") == new_id:
            continue
        handovers.append({
            "class_id": target["id"], "label": f"{class_name}-{section}",
            "from": outgoing, "to": incoming,
            "before": target.get("class_teacher_id"), "after": new_id,
        })

    orphan_subjects = [
        {"subject": row.get("name"), "class_id": row.get("class_id"),
         "teacher_id": row.get("teacher_id")}
        for row in subjects if row.get("teacher_id") in leaving_user_ids
    ]

    still_class_teacher = [
        f'{row.get("name")}-{row.get("section")}'
        for row in classes
        if row.get("class_teacher_id") in leaving_user_ids | leaving_ids
        and not any(item["class_id"] == row["id"] for item in handovers)
    ]

    return {
        "leaving": leaving,
        "handovers": handovers,
        "orphan_subjects": orphan_subjects,
        "still_class_teacher": still_class_teacher,
        "problems": problems,
    }


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if result["problems"]:
        return result
    if dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    undo = {"staff": [], "auth": [], "classes": []}

    for row in result["leaving"]:
        undo["staff"].append({"id": row["id"], "is_active": row.get("is_active")})
        await db.staff.update_one(
            {"id": row["id"], "schoolId": SCHOOL_ID},
            {"$set": {"is_active": False, "status": "left", "left_on": LEFT_ON,
                      "left_reason": REASON, "updated_at": now,
                      "updated_by": MIGRATION_ACTOR}},
        )
        if row.get("user_id"):
            auth = await db.auth_users.find_one(
                {"id": row["user_id"], "schoolId": SCHOOL_ID}, {"_id": 0, "is_active": 1}
            )
            if auth is not None:
                undo["auth"].append({"id": row["user_id"], "is_active": auth.get("is_active")})
                await db.auth_users.update_one(
                    {"id": row["user_id"], "schoolId": SCHOOL_ID},
                    {"$set": {"is_active": False}},
                )

    for item in result["handovers"]:
        undo["classes"].append({"id": item["class_id"], "before": item["before"]})
        await db.classes.update_one(
            {"id": item["class_id"], "schoolId": SCHOOL_ID},
            {"$set": {"class_teacher_id": item["after"], "updated_at": now,
                      "updated_by": MIGRATION_ACTOR}},
        )

    result["applied"] = True
    result["undo"] = undo
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        undo = json.load(handle)["undo"]
    staff = 0
    for row in undo["staff"]:
        staff += (await db.staff.update_one(
            {"id": row["id"], "schoolId": SCHOOL_ID},
            {"$set": {"is_active": row.get("is_active", True)},
             "$unset": {"status": "", "left_on": "", "left_reason": ""}},
        )).modified_count
    for row in undo["auth"]:
        await db.auth_users.update_one({"id": row["id"], "schoolId": SCHOOL_ID},
                                       {"$set": {"is_active": row.get("is_active", True)}})
    for row in undo["classes"]:
        await db.classes.update_one({"id": row["id"], "schoolId": SCHOOL_ID},
                                    {"$set": {"class_teacher_id": row.get("before")}})
    return {"staff": staff, "classes": len(undo["classes"])}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Staff departures and class handover.")
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
        print(f"put {out['staff']} staff back on the roll and restored {out['classes']} classes")
        return 0

    result = await apply(db, dry_run=not args.apply)

    print(f"  staff to mark as left                  {len(result['leaving']):>4}")
    print(f"  NOT marked, the principal              {STAYING}")
    print(f"  classes handed to the new teacher      {len(result['handovers']):>4}")
    for item in result["handovers"]:
        print(f"      {item['label']:8s} {item['from']:20s} -> {item['to']}")
    print(f"\n  subject slots left with a departed teacher, reported only "
          f"{len(result['orphan_subjects']):>4}")
    if result["still_class_teacher"]:
        print(f"  ** classes STILL holding a departed class teacher: "
              f"{result['still_class_teacher']}")

    if result["problems"]:
        print("\nNOTHING WAS WRITTEN.")
        for problem in result["problems"]:
            print(f"  {problem}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-043-departures-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"],
                   "orphan_subjects": result["orphan_subjects"]}, handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
