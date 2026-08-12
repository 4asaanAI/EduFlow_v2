"""Fold Sonu Ruhal's teacher profile into his accounts head profile, and delete it.

Abhimanyu, 2026-08-12: move the details from the teacher profile onto the head accountant
profile and delete the teacher profile, so there is no duplication.

Migration 045 corrected the STAFF record. It did not go far enough: his teacher profile
also existed in two other places, and one of them was a **second working login**.

===================  ================================================================
where                what was there
===================  ================================================================
``staff``            already corrected by 045. One record, the accounts head.
``users``            a profile saying SONU RUHAL, subject teacher. His ONLY one.
``auth_users``       a **second active login**, username ``SONU RUHAL``, role teacher.
===================  ================================================================

--------------------------------------------------------------------------------
The second login is the part that mattered
--------------------------------------------------------------------------------

The accounts head could sign in as a teacher and be treated as one by every permission
check on the platform. Nobody had to do anything wrong for that to happen; both accounts
were his own name.

--------------------------------------------------------------------------------
The join that was broken, and why deleting alone would not have fixed it
--------------------------------------------------------------------------------

When somebody signs in, the platform decides who they are from ``user_info.id``, and it
finds their staff record with ``staff.user_id``. For Sonu those two were different values,
so **signing in as the accounts head reached no staff record at all.** His profile, his
attendance and his leave belonged to nobody he could sign in as.

His only ``users`` profile was the teacher one. Deleting it and stopping there would have
left him with no profile at all, and he would then have been missed by every notification,
digest and approval list, all of which read that collection.

So the details are moved first and the teacher profile deleted second:

* his ``users`` profile is rewritten as the accounts head, under the identity he actually
  signs in as, carrying his telephone number, gender and settings across
* his staff record is pointed at that same identity, so the join works
* the teacher ``users`` profile and the teacher login are then deleted

**Adesh Singh and Lalit Thomas had the same broken join** and are fixed in the same pass.
Migration 041 linked their staff records to the login's own id rather than the identity
they sign in as, which reads correct in the database and does not work in the product.

--------------------------------------------------------------------------------
How to run it
--------------------------------------------------------------------------------

Dry run first. It is the default and changes nothing::

    backend/.venv/Scripts/python.exe backend/migrations/046_merge_sonu_teacher_profile.py
    ... 046_merge_sonu_teacher_profile.py --apply
    ... 046_merge_sonu_teacher_profile.py --rollback <the file it saved>

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
MIGRATION_ACTOR = "migration-046"

ACCOUNTANT_LOGIN = "sonu.ruhal"
TEACHER_LOGIN = "SONU RUHAL"

# Details worth carrying from the teacher profile onto the accounts head profile.
CARRY_OVER = ("phone", "gender", "preferred_language", "theme")

# Logins whose staff record points at the login's id instead of the identity the person
# actually becomes when they sign in. Left that way, the person reaches no staff record.
REJOIN = (ACCOUNTANT_LOGIN, "Adesh", "lalit.thomas")


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _blank(value) -> bool:
    return value in (None, "", [], {}) or str(value).strip() == ""


def _sign_in_id(auth: dict) -> str:
    """Exactly what routes/auth.py does, so this cannot drift from the real login."""
    info = auth.get("user_info") or {}
    return info.get("id") or auth.get("id") or auth.get("user_id") or ""


async def plan(db) -> dict:
    accountant = await db.auth_users.find_one(
        {"schoolId": SCHOOL_ID, "username": ACCOUNTANT_LOGIN}, {"_id": 0}
    )
    teacher_login = await db.auth_users.find_one(
        {"schoolId": SCHOOL_ID, "username": TEACHER_LOGIN}, {"_id": 0}
    )
    problems = []
    if accountant is None:
        problems.append(f"the {ACCOUNTANT_LOGIN} login was not found")
    if teacher_login is None:
        problems.append(f"no teacher login named {TEACHER_LOGIN}; it may already be gone")

    teacher_profile = None
    attached = {}
    if teacher_login is not None:
        teacher_user_id = _sign_in_id(teacher_login)
        teacher_profile = await db.users.find_one(
            {"schoolId": SCHOOL_ID, "id": teacher_user_id}, {"_id": 0}
        )
        ids = [teacher_user_id, teacher_login.get("id")]
        for label, collection, field in (
            ("subjects", db.subjects, "teacher_id"),
            ("classes", db.classes, "class_teacher_id"),
            ("assignments", db.assignments, "teacher_id"),
            ("lesson plans", db.lesson_plans, "teacher_id"),
            ("staff records", db.staff, "user_id"),
        ):
            attached[label] = await collection.count_documents(
                {"schoolId": SCHOOL_ID, field: {"$in": ids}}
            )
        if any(attached.values()):
            problems.append(
                "the teacher profile still has work attached to it, so it is not the empty "
                f"duplicate this migration was written for: {attached}"
            )

    accountant_id = _sign_in_id(accountant) if accountant else ""
    accountant_profile = None
    if accountant_id:
        accountant_profile = await db.users.find_one(
            {"schoolId": SCHOOL_ID, "id": accountant_id}, {"_id": 0}
        )

    rejoin = []
    for username in REJOIN:
        auth = await db.auth_users.find_one({"schoolId": SCHOOL_ID, "username": username}, {"_id": 0})
        if auth is None:
            continue
        wanted = _sign_in_id(auth)
        staff = await db.staff.find_one(
            {"schoolId": SCHOOL_ID, "user_id": {"$in": [auth.get("id"), wanted]}}, {"_id": 0}
        )
        if staff and staff.get("user_id") != wanted:
            rejoin.append({"username": username, "staff_id": staff["id"],
                           "name": staff.get("name"), "from": staff.get("user_id"),
                           "to": wanted})

    return {
        "accountant": accountant,
        "accountant_id": accountant_id,
        "accountant_profile": accountant_profile,
        "teacher_login": teacher_login,
        "teacher_profile": teacher_profile,
        "attached": attached,
        "rejoin": rejoin,
        "problems": problems,
    }


async def apply(db, *, dry_run: bool = True) -> dict:
    result = await plan(db)
    if result["problems"] or dry_run:
        return result

    now = datetime.now(timezone.utc).isoformat()
    teacher_profile = result["teacher_profile"] or {}
    accountant = result["accountant"]
    accountant_id = result["accountant_id"]

    undo = {
        "teacher_profile": teacher_profile or None,
        "teacher_login": result["teacher_login"],
        "accountant_profile": result["accountant_profile"],
        "accountant_user_info": (accountant or {}).get("user_info"),
        "rejoin": result["rejoin"],
        "created_accountant_profile": result["accountant_profile"] is None,
    }

    # 1. the accounts head profile, carrying his details across
    profile = {
        "id": accountant_id,
        "schoolId": SCHOOL_ID,
        "name": "Sonu Ruhal",
        "role": "admin",
        "sub_category": "accountant",
        "is_active": True,
        "updated_at": now,
        "updated_by": MIGRATION_ACTOR,
        "source": ("migration 046: his teacher profile's details, moved onto the accounts "
                   "head profile before the teacher profile was deleted"),
    }
    for field in CARRY_OVER:
        value = teacher_profile.get(field)
        if not _blank(value):
            profile[field] = value
    await db.users.update_one({"id": accountant_id, "schoolId": SCHOOL_ID},
                              {"$set": profile}, upsert=True)

    # 2. his telephone number onto the login, which held a placeholder
    info = {**(accountant.get("user_info") or {}), "name": "Sonu Ruhal", "initials": "SR"}
    if not _blank(teacher_profile.get("phone")):
        info["phone"] = teacher_profile["phone"]
    await db.auth_users.update_one(
        {"id": accountant["id"], "schoolId": SCHOOL_ID}, {"$set": {"user_info": info}}
    )

    # 3. make the join work, for all three
    for item in result["rejoin"]:
        await db.staff.update_one(
            {"id": item["staff_id"], "schoolId": SCHOOL_ID},
            {"$set": {"user_id": item["to"], "updated_at": now, "updated_by": MIGRATION_ACTOR}},
        )

    # 4. the duplicate goes
    if teacher_profile:
        await db.users.delete_one({"id": teacher_profile["id"], "schoolId": SCHOOL_ID})
    await db.auth_users.delete_one({"id": result["teacher_login"]["id"], "schoolId": SCHOOL_ID})

    result["applied"] = True
    result["undo"] = undo
    return result


async def rollback_from(db, path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        undo = json.load(handle)["undo"]
    if undo.get("teacher_profile"):
        await db.users.replace_one({"id": undo["teacher_profile"]["id"]},
                                   undo["teacher_profile"], upsert=True)
    if undo.get("teacher_login"):
        await db.auth_users.replace_one({"id": undo["teacher_login"]["id"]},
                                        undo["teacher_login"], upsert=True)
    if undo.get("created_accountant_profile"):
        await db.users.delete_one({"id": undo["teacher_login"] and
                                   (undo.get("accountant_user_info") or {}).get("id")})
    elif undo.get("accountant_profile"):
        await db.users.replace_one({"id": undo["accountant_profile"]["id"]},
                                   undo["accountant_profile"], upsert=True)
    for item in undo.get("rejoin", []):
        await db.staff.update_one({"id": item["staff_id"], "schoolId": SCHOOL_ID},
                                  {"$set": {"user_id": item["from"]}})
    return {"restored": True}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Merge and delete Sonu's teacher profile.")
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
        await rollback_from(db, args.rollback)
        print("the teacher profile and login have been put back")
        return 0

    result = await apply(db, dry_run=not args.apply)

    teacher = result["teacher_profile"] or {}
    print(f"  teacher profile found   {teacher.get('name')} / {teacher.get('sub_category')}")
    print(f"  teacher login found     {(result['teacher_login'] or {}).get('username')}"
          f"   active={(result['teacher_login'] or {}).get('is_active')}")
    print(f"  work attached to it     {result['attached'] or 'none'}")
    print(f"  details carried across  "
          f"{[f for f in CARRY_OVER if not _blank(teacher.get(f))] or 'none'}")
    print(f"\n  staff records rejoined to the identity the person signs in as: "
          f"{len(result['rejoin'])}")
    for item in result["rejoin"]:
        print(f"      {item['name']:14s} {str(item['from'])[:12]} -> {item['to']}")

    if result["problems"]:
        print("\nNOTHING WAS WRITTEN.")
        for problem in result["problems"]:
            print(f"  {problem}")
        return 1

    if not args.apply:
        print("\nDry run. Nothing was written. Re-run with --apply when you mean it.")
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = os.path.join(os.path.dirname(root), f"rollback-046-sonu-merge-{stamp}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"undo": result["undo"]}, handle, indent=2, default=str)
    print(f"\nDone. Rollback saved OUTSIDE the repository at:\n  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
