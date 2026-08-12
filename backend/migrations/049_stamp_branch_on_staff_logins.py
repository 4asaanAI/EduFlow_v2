"""Put the branch on every staff login, so branch filtering cannot hide colleagues.

Staff messaging filters colleagues by branch, which is correct and must stay. But only
**7 of 102 staff logins carried a branch at all**. Every screen that filters by branch
therefore drops the other 95, not because they are somewhere else but because nobody ever
recorded where they are.

While four people could message each other this was invisible. The moment messaging opens
to the whole staff room it becomes a colleague list with 7 names in it and 95 people
missing, and **a missing colleague looks exactly like somebody who has left**.

--------------------------------------------------------------------------------
The data is fixed, not the filter
--------------------------------------------------------------------------------

The tempting fix is to loosen the query: treat a login with no branch as "everywhere".
That works today, because the school runs one branch, and it quietly becomes a
cross-branch leak on the day it runs two. The branch belongs on the record.

Each login is stamped from **its own staff record**. The four shared desks have no staff
record, so they take the school's single branch, which is what they are.

Nothing is overwritten: a login that already carries a branch keeps it.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/049_stamp_branch_on_staff_logins.py
    ... 049_stamp_branch_on_staff_logins.py --apply
    ... 049_stamp_branch_on_staff_logins.py --rollback <the file it saved>

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
MIGRATION_ACTOR = "migration-049"
STAFF_ROLES = ("owner", "admin", "teacher")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_branch_id() -> str:
    from school_identity import default_branch_id

    return default_branch_id()


def _blank(value) -> bool:
    return value in (None, "", [], {}) or str(value).strip() == ""


async def plan(db) -> dict:
    logins = await db.auth_users.find(
        {"schoolId": SCHOOL_ID,
         "$or": [{"user_info.role": {"$in": list(STAFF_ROLES)}},
                 {"role": {"$in": list(STAFF_ROLES)}}]},
        {"_id": 0, "id": 1, "username": 1, "role": 1, "user_info": 1},
    ).to_list(5000)
    staff = await db.staff.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(5000)
    branch_by_user = {row["user_id"]: row.get("branch_id") for row in staff if row.get("user_id")}
    fallback = _default_branch_id()

    to_stamp, already, from_staff, from_default = [], 0, 0, 0
    for login in logins:
        info = login.get("user_info") or {}
        if not _blank(info.get("branch_id")):
            already += 1
            continue
        user_id = info.get("id") or login.get("id")
        branch = branch_by_user.get(user_id) or branch_by_user.get(login.get("id"))
        if branch:
            from_staff += 1
        else:
            branch = fallback
            from_default += 1
        to_stamp.append({"auth_id": login["id"], "username": login.get("username"),
                         "branch_id": branch})
    return {"logins": len(logins), "already": already, "to_stamp": to_stamp,
            "from_staff": from_staff, "from_default": from_default, "fallback": fallback}


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if dry_run:
        return result
    now = datetime.now(timezone.utc).isoformat()
    changed = 0
    for item in result["to_stamp"]:
        outcome = await db.auth_users.update_one(
            {"id": item["auth_id"], "schoolId": SCHOOL_ID},
            {"$set": {"user_info.branch_id": item["branch_id"], "updated_at": now,
                      "updated_by": MIGRATION_ACTOR}},
        )
        changed += outcome.modified_count
    result["applied"] = True
    result["changed"] = changed
    result["undo"] = [item["auth_id"] for item in result["to_stamp"]]
    if changed != len(result["to_stamp"]):
        result["warning"] = (
            f"asked to stamp {len(result['to_stamp'])} logins and changed {changed}"
        )
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        ids = json.load(handle)["undo"]
    out = await db.auth_users.update_many(
        {"schoolId": SCHOOL_ID, "id": {"$in": ids}},
        {"$unset": {"user_info.branch_id": ""}},
    )
    return {"cleared": out.modified_count, "expected": len(ids)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="A branch on every staff login.")
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
        print(f"cleared the branch from {out['cleared']} of {out['expected']} logins")
        return 0

    result = await apply(db, dry_run=not args.apply)
    print(f"  staff logins                 {result['logins']:>5}")
    print(f"  already carry a branch       {result['already']:>5}")
    print(f"  to stamp                     {len(result['to_stamp']):>5}")
    print(f"     from their staff record   {result['from_staff']:>5}")
    print(f"     shared desks, school branch {result['from_default']:>3}  ({result['fallback']})")
    if result.get("changed") is not None:
        print(f"  actually changed             {result['changed']:>5}")
    if result.get("warning"):
        print(f"  ** {result['warning']}")

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-049-branch-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"]}, handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
