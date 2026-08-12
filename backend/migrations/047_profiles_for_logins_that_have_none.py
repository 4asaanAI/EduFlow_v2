"""Give every login a profile record, so nobody is silently skipped.

Twelve active logins had no row in ``users``: the four shared desks, Lalit Thomas, and the
seven office accounts created by migration 041.

--------------------------------------------------------------------------------
Why an empty profile is not a harmless gap
--------------------------------------------------------------------------------

``users`` is not decoration. It is the list the platform reads when it decides **who to
tell**: notifications, the daily digest, who may approve a certificate, and who is informed
of an incident all query it by role. Somebody who can sign in but has no row there is
skipped by every one of those, silently and forever. They do not see an error; nothing
arrives, and nobody knows a message was addressed to a person the platform could not see.

Being able to sign in and being visible to the platform were two different states, and
seven of the twelve were accounts this release itself had just created.

--------------------------------------------------------------------------------
Nothing here is invented
--------------------------------------------------------------------------------

Each profile is built from what the platform already holds: the identity the person signs
in as, the name and role on their login, and the telephone number and branch on their staff
record. Where there is no staff record, which is the case for the four shared desks, the
profile carries only what the login itself says.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/047_profiles_for_logins_that_have_none.py
    ... 047_profiles_for_logins_that_have_none.py --apply
    ... 047_profiles_for_logins_that_have_none.py --rollback <the file it saved>

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
MIGRATION_ACTOR = "migration-047"


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _blank(value) -> bool:
    return value in (None, "", [], {}) or str(value).strip() == ""


def _sign_in_id(auth: dict) -> str:
    """Exactly what routes/auth.py does, so this cannot drift from the real login."""
    info = auth.get("user_info") or {}
    return info.get("id") or auth.get("id") or auth.get("user_id") or ""


async def plan(db) -> dict:
    logins = await db.auth_users.find(
        {"schoolId": SCHOOL_ID, "is_active": True}, {"_id": 0, "password_hash": 0}
    ).to_list(5000)
    profile_ids = {
        row["id"] for row in await db.users.find({"schoolId": SCHOOL_ID}, {"_id": 0, "id": 1}).to_list(5000)
    }
    staff = await db.staff.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(5000)
    staff_by_user = {row["user_id"]: row for row in staff if row.get("user_id")}

    to_create = []
    for auth in logins:
        user_id = _sign_in_id(auth)
        if not user_id or user_id in profile_ids:
            continue
        info = auth.get("user_info") or {}
        member = staff_by_user.get(user_id) or {}
        profile = {
            "id": user_id,
            "schoolId": SCHOOL_ID,
            "name": info.get("name") or member.get("name") or auth.get("username"),
            "role": info.get("role") or auth.get("role"),
            "sub_category": info.get("sub_category") or member.get("sub_category"),
            "is_active": True,
            "preferred_language": "en",
            "theme": "light",
            "source": ("migration 047: a login that could sign in but was invisible to "
                       "every notification, digest and approval list"),
        }
        for field in ("phone", "gender", "email", "branch_id"):
            value = member.get(field) or info.get(field)
            if not _blank(value):
                profile[field] = value
        to_create.append({"username": auth.get("username"), "profile": profile,
                          "has_staff_record": bool(member)})
    return {"to_create": to_create, "logins": len(logins), "profiles": len(profile_ids)}


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if dry_run:
        return result
    now = datetime.now(timezone.utc).isoformat()
    for item in result["to_create"]:
        await db.users.insert_one({**item["profile"], "_id": item["profile"]["id"],
                                   "created_at": now, "created_by": MIGRATION_ACTOR})
    result["applied"] = True
    result["undo"] = [item["profile"]["id"] for item in result["to_create"]]
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        ids = json.load(handle)["undo"]
    out = await db.users.delete_many({"schoolId": SCHOOL_ID, "id": {"$in": ids}})
    return {"deleted": out.deleted_count, "expected": len(ids)}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="A profile for every login.")
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
        print(f"removed {out['deleted']} of {out['expected']} profiles")
        return 0

    result = await apply(db, dry_run=not args.apply)
    print(f"  active logins {result['logins']:>6}   profiles {result['profiles']:>6}")
    print(f"  profiles to create {len(result['to_create']):>4}")
    for item in result["to_create"]:
        print(f"      {item['username']:16s} {item['profile']['sub_category'] or '':16s} "
              f"{'has a staff record' if item['has_staff_record'] else 'shared desk, no staff record'}")

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-047-profiles-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"]}, handle, indent=2)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
