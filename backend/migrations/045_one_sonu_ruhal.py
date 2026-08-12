"""There is one Sonu Ruhal and he is the accounts head. Make the platform say that.

Abhimanyu, 2026-08-12: there is only one Sonu Ruhal, the accounts head. Remove the one
marked as a teacher; if such a teacher does turn out to exist, the school can add him.

--------------------------------------------------------------------------------
What was actually on the platform, which changes what "remove" should mean
--------------------------------------------------------------------------------

One staff record, ``TCH-0043``, named SONU RUHAL, labelled a subject teacher. Checked
before touching it:

* it teaches **no subject**
* it is class teacher of **no class**
* the login it points at **does not exist**, so nobody can sign in as it
* it carries **his photograph and his telephone number**
* it carries **103 days of his attendance**

So it is not a second person. It is the accounts head's own record wearing the wrong
label, and the instruction says there is only one of him.

**Deleting it would therefore delete the accounts head's own record**, including 103 days
of attendance that feed his leave and his salary, and would leave the live ``sonu.ruhal``
login with no staff record behind it again, which is the hole this was meant to close.

So the teacher record is **ended, and the person is kept**: the label "subject teacher"
is gone, the record becomes the accounts head, and it is joined to the login he already
uses. After this the platform holds exactly one Sonu Ruhal, an accountant, and no teacher
of that name, which is what was asked for.

The record as it stood is written to the rollback file first, so the teacher version can
be put back exactly if that is ever wanted.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/045_one_sonu_ruhal.py
    ... 045_one_sonu_ruhal.py --apply
    ... 045_one_sonu_ruhal.py --rollback <the file it saved>

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
MIGRATION_ACTOR = "migration-045"

STAFF_NAME = "SONU RUHAL"
LOGIN_USERNAME = "sonu.ruhal"

BECOMES = {
    "name": "Sonu Ruhal",
    "staff_type": "accountant",
    "role": "admin",
    "sub_category": "accountant",
    "designation": "ACCOUNTANT HEAD",
    "department": "Accounts",
    "employee_id": "ACCOUNT-SONU",
    "source": ("migration 045: one Sonu Ruhal, the accounts head. This record was labelled "
               "a subject teacher by the old system's teacher seed and taught nothing."),
}


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def plan(db) -> dict:
    staff = await db.staff.find(
        {"schoolId": SCHOOL_ID, "name": {"$regex": "^\\s*sonu\\s+ruhal\\s*$", "$options": "i"}},
        {"_id": 0},
    ).to_list(50)
    auth = await db.auth_users.find_one(
        {"schoolId": SCHOOL_ID, "username": LOGIN_USERNAME}, {"_id": 0, "password_hash": 0}
    )

    problems = []
    if len(staff) != 1:
        problems.append(f"expected exactly one staff record named {STAFF_NAME}, found {len(staff)}")
    if auth is None:
        problems.append(f"the {LOGIN_USERNAME} login was not found")

    attached = {}
    if len(staff) == 1:
        row = staff[0]
        for label, collection, field in (
            ("subjects", db.subjects, "teacher_id"),
            ("classes as class teacher", db.classes, "class_teacher_id"),
            ("assignments", db.assignments, "teacher_id"),
            ("lesson plans", db.lesson_plans, "teacher_id"),
        ):
            attached[label] = await collection.count_documents(
                {"schoolId": SCHOOL_ID, field: {"$in": [row.get("user_id"), row["id"]]}}
            )
        attached["attendance days"] = await db.staff_attendance.count_documents(
            {"schoolId": SCHOOL_ID, "staff_id": row["id"]}
        )
        teaching = sum(attached[key] for key in
                       ("subjects", "classes as class teacher", "assignments", "lesson plans"))
        if teaching:
            problems.append(
                f"this record is still teaching ({teaching} items attached). It is not the "
                "empty teacher label this migration was written for, so nothing is changed."
            )

    return {"staff": staff, "auth": auth, "attached": attached, "problems": problems}


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if result["problems"] or dry_run:
        return result

    row = result["staff"][0]
    now = datetime.now(timezone.utc).isoformat()
    await db.staff.update_one(
        {"id": row["id"], "schoolId": SCHOOL_ID},
        {"$set": {**BECOMES, "user_id": result["auth"]["id"], "is_active": True,
                  "updated_at": now, "updated_by": MIGRATION_ACTOR}},
    )
    result["applied"] = True
    result["undo"] = {"id": row["id"], "before": row}
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        undo = json.load(handle)["undo"]
    before = {key: value for key, value in undo["before"].items() if key not in ("_id",)}
    out = await db.staff.replace_one({"id": undo["id"], "schoolId": SCHOOL_ID}, before)
    return {"restored": out.modified_count}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="One Sonu Ruhal, the accounts head.")
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
        print(f"put the teacher record back ({out['restored']} record)")
        return 0

    result = await apply(db, dry_run=not args.apply)

    if result["staff"]:
        row = result["staff"][0]
        print(f"  record found      {row.get('employee_id')}  {row.get('name')}  "
              f"currently {row.get('role')}/{row.get('sub_category')}")
    print(f"  login found       {(result['auth'] or {}).get('username')}")
    for label, count in result["attached"].items():
        print(f"  {label:26s} {count:>4}")
    print("\n  becomes: the accounts head, joined to his own login. His attendance,")
    print("  photograph and telephone number are kept. No teacher of this name remains.")

    if result["problems"]:
        print("\nNOTHING WAS WRITTEN.")
        for problem in result["problems"]:
            print(f"  {problem}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-045-sonu-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"]}, handle, indent=2, default=str)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
