"""Give the office staff their own logins, and link the two that already exist.

Abhimanyu, 2026-08-12: create logins for every member of staff **except** teachers,
care takers and the office helpers (peon, aaya, guard, driver, conductor).

Twenty-two staff records had no login at all. This settles the nine that the instruction
covers. The twelve teachers and the one care taker are deliberately left alone.

--------------------------------------------------------------------------------
Who gets what, and why two of them get nothing new
--------------------------------------------------------------------------------

**Seven new personal logins:** the two assistant accountants, the two admin staff, the
social media executive, the receptionist and the transport head.

**Two links, no new login:** Adesh Singh and Lalit Thomas already sign in. Their staff
record simply was not joined to their login, so the platform did not know the person and
the account were the same. Creating a second account for either of them would have given
one person two identities and split their history down the middle.

**One staff record created:** Sonu Ruhal, the accountant head, has a live login and no
staff record at all. He therefore appeared in no staff list, could be assigned nothing,
and had no attendance. The login is the one already in production; nothing about it
changes here.

**The four desk accounts stay as they are.** ``transport``, ``reception``, ``ittech`` and
``maintenance`` are shared desks, not people. Chaman Singh and Asniya now get their own
named login beside the desk, because an action taken by a person should carry that
person's name.

--------------------------------------------------------------------------------
Passwords
--------------------------------------------------------------------------------

The standing rule was that we never invent a password for a real person. The instruction
of 2026-08-12 overrides it, so each new account gets a **random one-time password** and
``must_change_password`` is set, which the sign-in screen already enforces: the person
cannot reach the platform until they have chosen their own.

**No plaintext is written into this file or anywhere in the repository.** The passwords
are generated at run time and written to a handover file OUTSIDE the repository, for the
school to distribute. Re-running the migration does not reissue a password to somebody
who already has an account.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/041_office_staff_logins.py
    ... 041_office_staff_logins.py --apply
    ... 041_office_staff_logins.py --rollback <the file it saved>

Never run this through ``run_all.py``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import string
import sys
import uuid
from datetime import datetime, timezone

SCHOOL_ID = "aaryans-joya"
MIGRATION_ACTOR = "migration-041"

# Staff who get a NEW personal login. Matched on the exact name held on the platform.
NEW_LOGINS = (
    {"name": "SACHIN YADAV",  "username": "sachin.yadav",  "sub_category": "accountant"},
    {"name": "SHIVAM KUMAR",  "username": "shivam.kumar",  "sub_category": "accountant"},
    {"name": "SAKSHI GUPTA",  "username": "sakshi.gupta",  "sub_category": "management"},
    {"name": "SAMEER",        "username": "sameer",        "sub_category": "management"},
    {"name": "VIPIN KUMAR",   "username": "vipin.kumar",   "sub_category": "support_staff"},
    {"name": "ASNIYA",        "username": "asniya",        "sub_category": "receptionist"},
    {"name": "CHAMAN SINGH",  "username": "chaman.singh",  "sub_category": "transport_head"},
)

# Already sign in. Their staff record is joined to the existing account, nothing else.
LINK_ONLY = (
    {"name": "ADESH SINGH",  "username": "Adesh",        "sub_category": "principal"},
    {"name": "LALIT THOMAS", "username": "lalit.thomas", "sub_category": "management"},
)

# A live login with no staff record behind it.
STAFF_FOR_EXISTING_LOGIN = (
    {"name": "Sonu Ruhal", "username": "sonu.ruhal", "sub_category": "accountant",
     "designation": "ACCOUNTANT HEAD", "employee_id": "ACCOUNT-SONU"},
)

# Deliberately excluded, recorded so nobody has to work out why the list is short.
EXCLUDED = "the 12 teachers and one care taker (Sachin Sharma), per the instruction"


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _default_branch_id() -> str:
    """The single-branch fallback has exactly one definition, and this is not it."""
    from school_identity import default_branch_id

    return default_branch_id()


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


def _one_time_password() -> str:
    """Readable enough to be typed off a printed sheet, random enough to be safe."""
    alphabet = string.ascii_lowercase.replace("l", "").replace("o", "")
    digits = "23456789"
    return (
        "".join(secrets.choice(alphabet) for _ in range(4))
        + "-"
        + "".join(secrets.choice(alphabet) for _ in range(4))
        + "-"
        + "".join(secrets.choice(digits) for _ in range(3))
    )


async def plan(db) -> dict:
    staff_rows = await db.staff.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(5000)
    auth_rows = await db.auth_users.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(5000)

    by_name: dict[str, list] = {}
    for row in staff_rows:
        by_name.setdefault(_norm(row.get("name")), []).append(row)
    by_username = {
        _norm(row.get("username")): row for row in auth_rows if row.get("username")
    }

    create, link, make_staff, problems = [], [], [], []

    for spec in NEW_LOGINS:
        matches = by_name.get(_norm(spec["name"]), [])
        if len(matches) != 1:
            problems.append(
                f"{spec['name']}: expected exactly one staff record, found {len(matches)}"
            )
            continue
        staff = matches[0]
        if staff.get("user_id"):
            problems.append(f"{spec['name']}: already has a login, skipped")
            continue
        if _norm(spec["username"]) in by_username:
            problems.append(f"{spec['name']}: username {spec['username']} is taken")
            continue
        create.append({"spec": spec, "staff": staff})

    for spec in LINK_ONLY:
        matches = by_name.get(_norm(spec["name"]), [])
        auth = by_username.get(_norm(spec["username"]))
        if len(matches) != 1 or auth is None:
            problems.append(
                f"{spec['name']}: staff records {len(matches)}, login found {auth is not None}"
            )
            continue
        if matches[0].get("user_id") == auth.get("id"):
            continue
        link.append({"spec": spec, "staff": matches[0], "auth": auth})

    for spec in STAFF_FOR_EXISTING_LOGIN:
        auth = by_username.get(_norm(spec["username"]))
        if auth is None:
            problems.append(f"{spec['name']}: login {spec['username']} not found")
            continue
        if by_name.get(_norm(spec["name"])):
            continue
        make_staff.append({"spec": spec, "auth": auth})

    return {"create": create, "link": link, "make_staff": make_staff, "problems": problems}


async def apply(db, *, dry_run: bool = True) -> dict:
    from middleware.auth import hash_password

    result = await plan(db)
    if dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    issued, undo = [], {"auth_ids": [], "staff_ids": [], "staff_unset_user_id": []}

    for item in result["create"]:
        spec, staff = item["spec"], item["staff"]
        user_id = str(uuid.uuid4())
        password = _one_time_password()
        await db.auth_users.insert_one({
            "_id": user_id,
            "id": user_id,
            "schoolId": SCHOOL_ID,
            "username": spec["username"],
            "username_lower": spec["username"].casefold(),
            "password_hash": hash_password(password),
            "role": "admin",
            "is_active": True,
            "must_change_password": True,
            "user_info": {
                "id": user_id,
                "name": staff.get("name"),
                "role": "admin",
                "sub_category": spec["sub_category"],
                "branch_id": staff.get("branch_id", ""),
                "phone": staff.get("phone", ""),
                "is_active": True,
            },
            "created_at": now,
            "created_by": MIGRATION_ACTOR,
        })
        await db.staff.update_one(
            {"id": staff["id"], "schoolId": SCHOOL_ID},
            {"$set": {"user_id": user_id, "updated_at": now, "updated_by": MIGRATION_ACTOR}},
        )
        undo["auth_ids"].append(user_id)
        undo["staff_unset_user_id"].append(staff["id"])
        issued.append({
            "name": staff.get("name"),
            "designation": staff.get("designation", ""),
            "username": spec["username"],
            "one_time_password": password,
        })

    for item in result["link"]:
        await db.staff.update_one(
            {"id": item["staff"]["id"], "schoolId": SCHOOL_ID},
            {"$set": {"user_id": item["auth"]["id"], "updated_at": now,
                      "updated_by": MIGRATION_ACTOR}},
        )
        undo["staff_unset_user_id"].append(item["staff"]["id"])

    for item in result["make_staff"]:
        spec, auth = item["spec"], item["auth"]
        staff_id = str(uuid.uuid4())
        await db.staff.insert_one({
            "_id": staff_id,
            "id": staff_id,
            "schoolId": SCHOOL_ID,
            "branch_id": _default_branch_id(),
            "name": spec["name"],
            "employee_id": spec["employee_id"],
            "designation": spec["designation"],
            "role": "admin",
            "sub_category": spec["sub_category"],
            "department": "Accounts",
            "user_id": auth["id"],
            "is_active": True,
            "casual_leave_balance": 0,
            "medical_leave_balance": 0,
            "earned_leave_balance": 0,
            "created_at": now,
            "created_by": MIGRATION_ACTOR,
            "source": "migration 041: a live login that had no staff record behind it",
        })
        undo["staff_ids"].append(staff_id)

    result["applied"] = True
    result["issued"] = issued
    result["undo"] = undo
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        undo = json.load(handle)["undo"]
    auth = await db.auth_users.delete_many({"schoolId": SCHOOL_ID, "id": {"$in": undo["auth_ids"]}})
    staff = await db.staff.delete_many({"schoolId": SCHOOL_ID, "id": {"$in": undo["staff_ids"]}})
    cleared = await db.staff.update_many(
        {"schoolId": SCHOOL_ID, "id": {"$in": undo["staff_unset_user_id"]}},
        {"$unset": {"user_id": ""}},
    )
    return {"logins_removed": auth.deleted_count, "staff_removed": staff.deleted_count,
            "links_cleared": cleared.modified_count}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Office staff logins.")
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
        print(f"removed {out['logins_removed']} logins, {out['staff_removed']} staff records, "
              f"cleared {out['links_cleared']} links")
        return 0

    result = await apply(db, dry_run=not args.apply)

    print(f"  new personal logins to create      {len(result['create']):>4}")
    for item in result["create"]:
        print(f"      {item['staff'].get('name'):26s} {item['spec']['username']}")
    print(f"  staff records to link to an existing login {len(result['link']):>4}")
    for item in result["link"]:
        print(f"      {item['staff'].get('name'):26s} {item['spec']['username']}")
    print(f"  staff records to create for a live login   {len(result['make_staff']):>4}")
    for item in result["make_staff"]:
        print(f"      {item['spec']['name']}")
    print(f"\n  NOT given a login: {EXCLUDED}")

    if result["problems"]:
        print("\n  Needs a person, nothing done for these:")
        for problem in result["problems"]:
            print(f"      {problem}")

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-041-office-logins-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"]}, handle, indent=2)

    creds = os.path.join(os.path.dirname(root), f"aaryans-new-logins-{stamp}.txt")
    with open(creds, "w", encoding="utf-8") as handle:
        handle.write("The Aaryans - new office logins\n")
        handle.write("Each person must choose their own password the first time they sign in.\n\n")
        for row in result["issued"]:
            handle.write(f"{row['name']}  ({row['designation']})\n")
            handle.write(f"    login:    {row['username']}\n")
            handle.write(f"    password: {row['one_time_password']}  (one time)\n\n")

    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    print(f"Passwords written OUTSIDE the repository at:\n  {creds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
