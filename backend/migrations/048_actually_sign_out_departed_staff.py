"""The 21 departed staff can still sign in. Migration 043 only thought it stopped them.

--------------------------------------------------------------------------------
What went wrong, because it is the same fault three times in one day
--------------------------------------------------------------------------------

043 looked up each leaver's login with ``auth_users.find_one({"id": staff.user_id})``.
For these accounts the login's own ``id`` is **not** the id the staff record points at:
the person is identified by ``user_info.id``. So the lookup matched nothing, found no
login to switch off, and reported success. **All 21 logins are still active.**

That is the third appearance today of one mistake: an ``auth_users`` row can be found by
two different ids, and code that knows only one of them fails silently rather than
loudly. It hid Sonu Ruhal's duplicate profile, it broke the join between three office
staff and their own records, and here it left people who have left the school able to
sign in to it.

**A lookup that matches nobody looks exactly like a lookup with nothing to do.** Every
one of these was a no-op that printed a success line. This migration counts what it
changed and says so.

--------------------------------------------------------------------------------
Why it matters more from today
--------------------------------------------------------------------------------

Staff messaging has just been opened to the whole staff room, and it builds its colleague
list from active logins. Left as it is, all 21 people who no longer work at the school
would appear in every colleague's contact list as somebody to message, and could read
what was sent to them.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/048_actually_sign_out_departed_staff.py
    ... 048_actually_sign_out_departed_staff.py --apply
    ... 048_actually_sign_out_departed_staff.py --rollback <the file it saved>

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
MIGRATION_ACTOR = "migration-048"


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def plan(db) -> dict:
    leavers = await db.staff.find(
        {"schoolId": SCHOOL_ID, "status": "left"}, {"_id": 0, "id": 1, "name": 1, "user_id": 1}
    ).to_list(1000)

    to_disable, already_off, no_login = [], 0, []
    for person in leavers:
        user_id = person.get("user_id")
        if not user_id:
            no_login.append(person.get("name"))
            continue
        # BOTH ids, which is the whole point of this migration.
        auth = await db.auth_users.find_one(
            {"schoolId": SCHOOL_ID, "$or": [{"id": user_id}, {"user_info.id": user_id}]},
            {"_id": 0, "id": 1, "username": 1, "is_active": 1},
        )
        if auth is None:
            no_login.append(person.get("name"))
            continue
        if auth.get("is_active") is False:
            already_off += 1
            continue
        to_disable.append({"name": person.get("name"), "auth_id": auth["id"],
                           "username": auth.get("username")})

    return {"leavers": len(leavers), "to_disable": to_disable,
            "already_off": already_off, "no_login": no_login}


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    changed = 0
    for item in result["to_disable"]:
        outcome = await db.auth_users.update_one(
            {"id": item["auth_id"], "schoolId": SCHOOL_ID},
            {"$set": {"is_active": False, "deactivated_at": now,
                      "deactivated_by": MIGRATION_ACTOR,
                      "deactivated_reason": "left the school, confirmed 2026-08-12"}},
        )
        changed += outcome.modified_count

    # A count that does not match is the failure this migration exists to catch.
    result["applied"] = True
    result["changed"] = changed
    result["undo"] = [item["auth_id"] for item in result["to_disable"]]
    if changed != len(result["to_disable"]):
        result["warning"] = (
            f"asked to switch off {len(result['to_disable'])} logins and actually changed "
            f"{changed}. Do not treat this run as done."
        )
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        ids = json.load(handle)["undo"]
    out = await db.auth_users.update_many(
        {"schoolId": SCHOOL_ID, "id": {"$in": ids}},
        {"$set": {"is_active": True},
         "$unset": {"deactivated_at": "", "deactivated_by": "", "deactivated_reason": ""}},
    )
    return {"restored": out.modified_count, "expected": len(ids)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Actually sign out the departed staff.")
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
        print(f"switched {out['restored']} of {out['expected']} logins back on")
        return 0

    result = await apply(db, dry_run=not args.apply)
    print(f"  staff recorded as departed        {result['leavers']:>4}")
    print(f"  logins still active, to switch off {len(result['to_disable']):>4}")
    print(f"  already switched off               {result['already_off']:>4}")
    print(f"  no login found                     {len(result['no_login']):>4}")
    for item in result["to_disable"][:30]:
        print(f"      {item['name']:22s} {item['username']}")
    if result.get("changed") is not None:
        print(f"\n  actually changed                   {result['changed']:>4}")
    if result.get("warning"):
        print(f"  ** {result['warning']}")

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-048-signouts-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"]}, handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
