"""Remove the four SHARED DESK logins. Abhimanyu's instruction, 2026-08-15.

    transport   (Transport Desk,   user-admin-003, sub_category transport_head)
    reception   (Reception Desk,   user-admin-004, sub_category receptionist)
    ittech      (IT Desk,          user-admin-005, sub_category it_tech)
    maintenance (Maintenance Desk, user-admin-006, sub_category maintenance)

These are accounts that stand for a whole department rather than a person. They are the
last of that kind on the platform: 033 renamed ``accountant`` and ``management`` into
Sonu and Lalit, and the seven unused 041 office logins were deleted on 2026-08-15.

--------------------------------------------------------------------------------
Why removing them is safe, and why it is also necessary
--------------------------------------------------------------------------------

**Safe.** Proven read-only against the live database before this file was written:
zero sessions ever, zero refresh tokens, and **zero documents anywhere in the database**
reference any of the eight ids (four ``auth_users.id`` plus four ``user_info.id``) through
any authorship, actor, approval, assignment or messaging field. They own nothing. Nothing
in the running backend or frontend reads these usernames or ids either; the only hits in
the repository are test fixtures with their own made-up ids, and a documentation note.

**Necessary.** ``Transport Desk`` carries ``sub_category: transport_head`` - the very same
profile Chaman Singh was given on 2026-08-15. Two accounts answering to one profile is the
confusion this removes: a decision recorded by "the transport desk" can never be traced to
the person who took it, and the release plan builds one profile per person.

The four ``sub_category`` values stay in the code. This deletes accounts, not profiles.

--------------------------------------------------------------------------------
What it touches
--------------------------------------------------------------------------------

* 4 rows from ``auth_users``
* the 4 matching rows from ``users`` (the list the platform reads to decide who to tell;
  a profile with no login behind it keeps being addressed by notifications nobody reads)

It clears no staff link, because none of the four is joined to a staff record. There are
no staff records for these desks at all.

⚠️ ``users.id`` is NOT ``auth_users.id``. It is the id inside ``auth_users.user_info``.
A check joining on ``auth_users.id`` finds nothing and reads exactly like every profile
being orphaned. That is a wrong query, not a wrong database.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/050_remove_shared_desk_logins.py
    ... 050_remove_shared_desk_logins.py --apply
    ... 050_remove_shared_desk_logins.py --rollback <the file it saved>

The rollback file is written OUTSIDE this repository, under your home folder. It DOES hold
the bcrypt password hash, which is what makes a rollback restore a login that actually
works. **This repository is public. Never copy that file into it.**

Never run this through ``run_all.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SCHOOL_ID = "aaryans-joya"

DESK_USERNAMES = ("transport", "reception", "ittech", "maintenance")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _backup_dir() -> str:
    """Outside the repository. This repo is PUBLIC."""
    target = os.path.join(os.path.expanduser("~"), "eduflow-migration-backups")
    os.makedirs(target, exist_ok=True)
    return target


async def _connect():
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client, client[os.environ["DB_NAME"]]


async def _gather(db) -> list:
    """The four desk logins, each with its profile row, or None if absent."""
    found = []
    for username in DESK_USERNAMES:
        auth = await db.auth_users.find_one(
            {"username_lower": username, "schoolId": SCHOOL_ID}, {"_id": 0}
        )
        if auth is None:
            found.append({"username": username, "auth": None, "profile": None})
            continue
        profile_id = (auth.get("user_info") or {}).get("id")
        profile = None
        if profile_id:
            profile = await db.users.find_one(
                {"id": profile_id, "schoolId": SCHOOL_ID}, {"_id": 0}
            )
        found.append({"username": username, "auth": auth, "profile": profile})
    return found


async def _safety_check(db, rows) -> list:
    """Refuse to delete anything that has been used or owns a record."""
    fields = [
        "user_id", "created_by", "updated_by", "recorded_by", "actor_id", "approved_by",
        "sender_id", "uploaded_by", "assigned_to", "owner_id", "author_id", "deleted_by",
        "decided_by", "raised_by", "marked_by", "collected_by", "performed_by",
        "requested_by", "acted_by", "from_user_id", "to_user_id", "participants",
    ]
    ids = []
    for row in rows:
        if row["auth"]:
            ids.append(row["auth"]["id"])
            profile_id = (row["auth"].get("user_info") or {}).get("id")
            if profile_id:
                ids.append(profile_id)
    if not ids:
        return []

    problems = []
    query = {"$or": [{field: {"$in": ids}} for field in fields]}
    for name in await db.list_collection_names():
        if name in ("auth_users", "users"):
            continue
        try:
            count = await db[name].count_documents(query)
        except Exception as exc:  # a collection with an odd shape must not pass silently
            problems.append(f"{name}: could not be checked ({exc})")
            continue
        if count:
            problems.append(f"{name}: {count} document(s) reference a desk account")
    return problems


async def run(apply: bool) -> None:
    client, db = await _connect()
    try:
        rows = await _gather(db)

        print(f"\nDesk logins found on {os.environ['DB_NAME']}:")
        for row in rows:
            if row["auth"] is None:
                print(f"  {row['username']:<12} ALREADY GONE")
                continue
            info = row["auth"].get("user_info") or {}
            print(
                f"  {row['username']:<12} auth_id={row['auth']['id']}  "
                f"profile={info.get('id')}  name={info.get('name')}  "
                f"sub_category={info.get('sub_category')}  "
                f"profile_row={'present' if row['profile'] else 'MISSING'}"
            )

        present = [r for r in rows if r["auth"]]
        if not present:
            print("\nNothing to do. All four are already removed.")
            return

        problems = await _safety_check(db, present)
        if problems:
            print("\nREFUSING TO DELETE. These accounts are referenced by real records:")
            for line in problems:
                print(f"  - {line}")
            print("Nothing was changed.")
            return
        print("\nSafety check passed: no record anywhere references these accounts.")

        if not apply:
            print("\nDRY RUN. Nothing was changed. Re-run with --apply to remove them.")
            return

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = os.path.join(_backup_dir(), f"rollback-050-{stamp}.json")
        payload = {
            "migration": "050_remove_shared_desk_logins",
            "removed_at": _now(),
            "schoolId": SCHOOL_ID,
            "rows": [
                {
                    "username": r["username"],
                    "auth_user": r["auth"],
                    "profile": r["profile"],
                }
                for r in present
            ],
        }
        with open(backup_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        print(f"\nBackup written to {backup_path}")
        print("It holds the bcrypt hash so a rollback restores a WORKING login.")
        print("It is outside this PUBLIC repository. Do not move it inside, ever.")

        removed_auth = 0
        removed_profiles = 0
        for row in present:
            result = await db.auth_users.delete_one(
                {"id": row["auth"]["id"], "schoolId": SCHOOL_ID}
            )
            removed_auth += result.deleted_count
            profile_id = (row["auth"].get("user_info") or {}).get("id")
            if profile_id:
                result = await db.users.delete_one(
                    {"id": profile_id, "schoolId": SCHOOL_ID}
                )
                removed_profiles += result.deleted_count

        print(f"Removed {removed_auth} login(s) and {removed_profiles} profile row(s).")

        left = await db.auth_users.count_documents(
            {"username_lower": {"$in": list(DESK_USERNAMES)}, "schoolId": SCHOOL_ID}
        )
        print(f"Desk logins remaining: {left} (expected 0)")
        for username in ("Aman Litt", "Adesh", "sonu.ruhal", "lalit.thomas", "chaman.singh"):
            still = await db.auth_users.count_documents(
                {"username": username, "schoolId": SCHOOL_ID}
            )
            print(f"  {username}: {still} (expected 1)")

        # ``db._migrations`` raises on Motor: a leading underscore is read as an attribute,
        # not a collection name. Index into the database instead.
        await db["_migrations"].update_one(
            {"name": "050_remove_shared_desk_logins"},
            {
                "$set": {
                    "name": "050_remove_shared_desk_logins",
                    "applied_at": _now(),
                    "category": "data",
                    "evidence": f"removed {removed_auth} desk logins, {removed_profiles} profiles",
                }
            },
            upsert=True,
        )
    finally:
        client.close()


async def rollback(path: str) -> None:
    client, db = await _connect()
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        restored = 0
        for row in payload["rows"]:
            auth = row.get("auth_user")
            if auth:
                await db.auth_users.update_one(
                    {"id": auth["id"]}, {"$set": auth}, upsert=True
                )
                restored += 1
            profile = row.get("profile")
            if profile:
                await db.users.update_one(
                    {"id": profile["id"]}, {"$set": profile}, upsert=True
                )
        print(f"Restored {restored} login(s), password included. They can sign in again.")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually remove them")
    parser.add_argument("--rollback", metavar="FILE", help="restore from a backup file")
    args = parser.parse_args()
    if args.rollback:
        asyncio.run(rollback(args.rollback))
    else:
        asyncio.run(run(apply=args.apply))


async def migrate(db=None):
    raise RuntimeError(
        "050 removes live logins and must be run on its own, never through run_all.py."
    )


if __name__ == "__main__":
    main()
