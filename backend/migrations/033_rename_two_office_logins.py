"""R2-11 - rename the two office logins, and nothing else.

    accountant  ->  sonu.ruhal
    management  ->  lalit.thomas

Plus Adesh's DISPLAY NAME gains "Singh". His login is not touched, and **Aman's login is
not touched at all**.

⚠️ THIS HAS NOT BEEN RUN. It writes to the live school database and it signs people out.
It needs Abhimanyu's explicit yes, on the day, and it is deliberately the LAST thing in
Release 2. Read all of the following before running it.

--------------------------------------------------------------------------------
Why this is last, and why it is a migration rather than a quiet update
--------------------------------------------------------------------------------

**It revokes sessions.** Anyone signed in as `accountant` or `management` is signed out
the moment their username changes, and their old login stops working. If it runs while
Sonu is mid-way through recording fees, he loses what he was typing and cannot get back
in with the credentials he was given an hour earlier.

**Something in this codebase already joined on username.** Staff messaging did, and
matched nobody, which is why the colleague list read "0 colleagues available". R2-10
fixed that by asking who somebody IS instead. **Assume there is more.** Before running
this, search the codebase again for anything that looks somebody up by their login name
rather than their id.

**Migration 031 is wrong about this and the instruction wins.** 031 declares the dotted
form for all four accounts. The final decision of 2026-08-10 is that only these two
change: Aman keeps whatever login he has, and Adesh keeps his. Do not "tidy" 031 to
match; it has already run its course and rewriting history in a migration file is how
the next person ends up trusting the wrong document.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

1. **Deploy first.** The renamed logins and the code that no longer cares about login
   names should land together. Renaming before the deploy leaves the school with new
   credentials and the old behaviour.
2. **Dry run, and read every line of it.** ``--dry-run`` is the default and it changes
   nothing::

       backend/.venv/Scripts/python.exe backend/migrations/033_rename_two_office_logins.py

3. **Save the rollback file it prints.** It records the exact previous values.
4. **Run it for real, with both people signed out and standing next to you**, so they can
   sign in again immediately and confirm it worked::

       ... 033_rename_two_office_logins.py --apply

5. **Undo, if needed**, using the saved rollback file::

       ... 033_rename_two_office_logins.py --rollback rollback-033-<timestamp>.json

Passwords are NOT touched. They stay as they are, which is Abhimanyu's recorded decision
of 2026-08-10 (decision 11), taken knowingly: changing them would lock him out of the
accounts he uses to check the work. Raise it again at handover, not here.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

SCHOOL_ID = "aaryans-joya"

# The whole change, in one table. `display_name` is set only where it changes.
RENAMES = (
    {
        "from_username": "accountant",
        "to_username": "sonu.ruhal",
        "display_name": "Sonu Ruhal",
        "expect_sub_category": "accountant",
    },
    {
        "from_username": "management",
        "to_username": "lalit.thomas",
        "display_name": "Lalit Thomas",
        "expect_sub_category": "management",
    },
)

# Adesh's login is NOT renamed. Only what people see on screen.
DISPLAY_NAME_ONLY = (
    {"sub_category": "principal", "display_name": "Adesh Singh"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _find(db, username: str) -> Dict[str, Any] | None:
    return await db.auth_users.find_one(
        {"schoolId": SCHOOL_ID, "username_lower": username.lower()}, {"_id": 0}
    )


async def preflight(db) -> List[dict]:
    """What WOULD happen. Reads only."""
    report = []
    for spec in RENAMES:
        current = await _find(db, spec["from_username"])
        target = await _find(db, spec["to_username"])
        problem = ""
        if current is None:
            problem = f"no account with the login '{spec['from_username']}' - nothing to rename"
        elif target is not None:
            problem = (
                f"an account with the login '{spec['to_username']}' ALREADY EXISTS. "
                "Renaming into it would create two accounts answering to one name. Stop "
                "and work out which is real."
            )
        else:
            info = current.get("user_info") or {}
            actual = info.get("sub_category") or current.get("sub_category")
            if actual != spec["expect_sub_category"]:
                problem = (
                    f"'{spec['from_username']}' is a '{actual}' account, not a "
                    f"'{spec['expect_sub_category']}' one. This is not the person you think."
                )
        report.append({
            "from": spec["from_username"],
            "to": spec["to_username"],
            "found": current is not None,
            "current_name": ((current or {}).get("user_info") or {}).get("name"),
            "new_name": spec["display_name"],
            "problem": problem,
        })
    return report


async def apply(db, *, dry_run: bool = True) -> dict:
    report = await preflight(db)
    blocking = [row for row in report if row["problem"]]
    if blocking:
        return {"applied": False, "report": report, "blocked_by": [r["problem"] for r in blocking]}

    rollback: List[dict] = []
    for spec in RENAMES:
        current = await _find(db, spec["from_username"])
        info = current.get("user_info") or {}
        rollback.append({
            "id": current.get("id"),
            "username": current.get("username"),
            "username_lower": current.get("username_lower"),
            "name": info.get("name"),
        })
        if dry_run:
            continue
        await db.auth_users.update_one(
            {"schoolId": SCHOOL_ID, "id": current.get("id")},
            {"$set": {
                "username": spec["to_username"],
                "username_lower": spec["to_username"].lower(),
                "user_info.name": spec["display_name"],
                "renamed_at": _now(),
            }},
        )
        # The person's own record carries the name shown around the platform.
        if info.get("id"):
            await db.users.update_one(
                {"schoolId": SCHOOL_ID, "id": info["id"]},
                {"$set": {"name": spec["display_name"]}},
            )

    for spec in DISPLAY_NAME_ONLY:
        row = await db.auth_users.find_one(
            {"schoolId": SCHOOL_ID, "user_info.sub_category": spec["sub_category"]}, {"_id": 0}
        )
        if not row:
            continue
        info = row.get("user_info") or {}
        rollback.append({"id": row.get("id"), "username": row.get("username"),
                         "username_lower": row.get("username_lower"), "name": info.get("name")})
        if dry_run:
            continue
        await db.auth_users.update_one(
            {"schoolId": SCHOOL_ID, "id": row.get("id")},
            {"$set": {"user_info.name": spec["display_name"]}},
        )
        if info.get("id"):
            await db.users.update_one(
                {"schoolId": SCHOOL_ID, "id": info["id"]},
                {"$set": {"name": spec["display_name"]}},
            )

    return {"applied": not dry_run, "report": report, "rollback": rollback}


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        saved = json.load(handle)
    for row in saved:
        await db.auth_users.update_one(
            {"schoolId": SCHOOL_ID, "id": row["id"]},
            {"$set": {
                "username": row["username"],
                "username_lower": row["username_lower"],
                "user_info.name": row["name"],
            }},
        )
    return {"restored": len(saved)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually write. Default is a dry run.")
    parser.add_argument("--rollback", help="path to a rollback file written by a previous --apply")
    args = parser.parse_args()

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from database import get_db  # imported late so --help works without a DB

    db = get_db()

    if args.rollback:
        result = await rollback_from(db, args.rollback)
        print(f"restored {result['restored']} accounts from {args.rollback}")
        return 0

    result = await apply(db, dry_run=not args.apply)
    for row in result["report"]:
        state = row["problem"] or "ok"
        print(f"  {row['from']:12} -> {row['to']:14} {state}")
    if result.get("blocked_by"):
        print("\nNOTHING WAS CHANGED. Fix the above first.")
        return 1
    if not args.apply:
        print("\nDry run. Nothing was changed. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = f"rollback-033-{stamp}.json"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(result["rollback"], handle, indent=2)
    print(f"\nDone. Rollback saved to {path} - keep it until both people have signed in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
