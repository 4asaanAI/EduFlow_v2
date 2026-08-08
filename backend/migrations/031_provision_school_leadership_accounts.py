"""Provision the four named Aaryans leadership/office accounts.

This migration is intentionally data-changing and school-specific. Run it only after
reviewing its preflight output against a production copy, then execute this file by
itself. Never invoke ``migrations/run_all.py`` against the live school database.

No plaintext password is stored here. The one-time credential handoff is kept outside
the repository; only bcrypt hashes are committed. Re-running the migration is
idempotent and deliberately keeps ``must_change_password`` disabled.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from school_identity import default_branch_id


SCHOOL_ID = "aaryans-joya"
BRANCH_ID = default_branch_id()
MIGRATION_ACTOR = "migration-031"


ACCOUNT_SPECS = (
    {
        "key": "aman",
        "name": "Aman Litt",
        "username": "aman.litt",
        "role": "owner",
        "sub_category": "owner",
        "password_hash": "$2b$12$fW3jRMQdmjmHkZ5kIElQt.s.Ne0czXmmjoglDec0xFE9D9rU/peLC",
        "match_owner": True,
    },
    {
        "key": "adesh",
        "name": "Adesh Singh",
        "username": "adesh.singh",
        "role": "admin",
        "sub_category": "principal",
        "password_hash": "$2b$12$VNA0fNhHUzmAfGAptXPpz.L.PzVZfoIL/XPJmUDpqHFDxrr8AU7WW",
        "require_staff": True,
    },
    {
        "key": "sonu",
        "name": "Sonu Ruhal",
        "username": "sonu.ruhal",
        "role": "admin",
        "sub_category": "accountant",
        "password_hash": "$2b$12$KjNdteFT/1UTCNi417.YTOzkkrM/GNwrvVk8UNvmO8zVfvIpqE/.G",
        "phone": "8014646146",
        "designation": "ACCOUNTANT HEAD",
        "create_staff_if_missing": True,
    },
    {
        "key": "lalit",
        "name": "Lalit Thomas",
        "username": "lalit.thomas",
        "role": "admin",
        "sub_category": "management",
        "password_hash": "$2b$12$qgP6Kcp/.Q.wYj18zHujSuT1RWmS9LV5eDWrLfdQP1v9MtLTNYtGO",
        "require_staff": True,
    },
)


def _normalise_name(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def _without_id(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None
    return {key: value for key, value in doc.items() if key != "_id"}


async def _tenant_rows(collection) -> List[dict]:
    return await collection.find({"schoolId": SCHOOL_ID}, {"_id": 0}).to_list(10000)


def _exact_named(rows: Iterable[dict], name: str) -> List[dict]:
    wanted = _normalise_name(name)
    return [row for row in rows if _normalise_name(row.get("name")) == wanted]


def _auth_named(rows: Iterable[dict], name: str) -> List[dict]:
    wanted = _normalise_name(name)
    return [
        row for row in rows
        if _normalise_name((row.get("user_info") or {}).get("name")) == wanted
    ]


def _stable_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"eduflow:{SCHOOL_ID}:{kind}:{key}"))


def _one_or_none(rows: List[dict], label: str) -> Optional[dict]:
    if len(rows) > 1:
        raise RuntimeError(f"Migration 031 preflight found multiple {label} records")
    return rows[0] if rows else None


async def _resolve_accounts(db) -> List[dict]:
    staff_rows = await _tenant_rows(db.staff)
    auth_rows = await _tenant_rows(db.auth_users)
    resolved = []

    for spec in ACCOUNT_SPECS:
        staff = _one_or_none(
            _exact_named(staff_rows, spec["name"]),
            f"staff rows for {spec['name']}",
        )
        if spec.get("require_staff") and staff is None:
            raise RuntimeError(
                f"Migration 031 requires exactly one existing staff row for {spec['name']}"
            )

        auth_candidates = []
        if staff and staff.get("user_id"):
            auth_candidates.extend(
                row for row in auth_rows if row.get("id") == staff.get("user_id")
            )
        auth_candidates.extend(_auth_named(auth_rows, spec["name"]))
        if spec.get("match_owner"):
            auth_candidates.extend(
                row for row in auth_rows
                if (row.get("user_info") or {}).get("role", row.get("role")) == "owner"
            )

        deduped = {row.get("id") or row.get("user_id"): row for row in auth_candidates}
        deduped.pop(None, None)
        auth = _one_or_none(list(deduped.values()), f"login rows for {spec['name']}")
        if spec.get("match_owner") and auth is None:
            raise RuntimeError("Migration 031 requires exactly one existing school owner login")

        user_id = (auth or {}).get("id") or (staff or {}).get("user_id") or _stable_id("user", spec["key"])
        resolved.append({"spec": spec, "staff": staff, "auth": auth, "user_id": user_id})

    target_ids = {item["user_id"] for item in resolved}
    for item in resolved:
        wanted = item["spec"]["username"].casefold()
        collisions = [
            row for row in auth_rows
            if str(row.get("username_lower") or row.get("username") or "").casefold() == wanted
            and row.get("id") not in target_ids
        ]
        if collisions:
            raise RuntimeError(
                f"Migration 031 username collision for {item['spec']['username']}"
            )
    return resolved


def _staff_changes(spec: dict, user_id: str, now: str) -> dict:
    changes = {
        "user_id": user_id,
        "role": spec["role"],
        "sub_category": spec["sub_category"],
        "is_active": True,
        "updated_at": now,
        "updated_by": MIGRATION_ACTOR,
    }
    for field in ("phone", "email", "designation", "qualification", "gender", "dob"):
        if spec.get(field):
            changes[field] = spec[field]
    if spec["key"] == "sonu":
        changes.update({"staff_type": "accountant", "department": "Accounts"})
    return changes


async def _upsert_profile(db, item: dict, now: str) -> None:
    spec = item["spec"]
    user_id = item["user_id"]
    staff = item["staff"]

    if staff is not None:
        await db.staff.update_one(
            {"id": staff["id"], "schoolId": SCHOOL_ID},
            {"$set": _staff_changes(spec, user_id, now)},
        )
    elif spec.get("create_staff_if_missing"):
        staff_id = _stable_id("staff", spec["key"])
        staff_doc = {
            "_id": staff_id,
            "id": staff_id,
            "schoolId": SCHOOL_ID,
            "branch_id": BRANCH_ID,
            "name": spec["name"],
            "employee_id": "ACCOUNT-SONU",
            "created_at": now,
            "created_by": MIGRATION_ACTOR,
            **_staff_changes(spec, user_id, now),
        }
        await db.staff.insert_one(staff_doc)

    existing_auth = item["auth"]
    existing_info = (existing_auth or {}).get("user_info") or {}
    user_info = {
        **existing_info,
        "id": user_id,
        "name": spec["name"],
        "role": spec["role"],
        "sub_category": spec["sub_category"],
        "branch_id": BRANCH_ID,
        "is_active": True,
    }
    if spec.get("phone"):
        user_info["phone"] = spec["phone"]

    auth_set = {
        "schoolId": SCHOOL_ID,
        "username": spec["username"],
        "username_lower": spec["username"].casefold(),
        "password_hash": spec["password_hash"],
        "role": spec["role"],
        "is_active": True,
        "must_change_password": False,
        "user_info": user_info,
        "updated_at": now,
        "updated_by": MIGRATION_ACTOR,
    }
    if existing_auth is not None:
        await db.auth_users.update_one(
            {"id": existing_auth["id"], "schoolId": SCHOOL_ID},
            {"$set": auth_set},
        )
    else:
        await db.auth_users.insert_one({
            "_id": user_id,
            "id": user_id,
            "created_at": now,
            "created_by": MIGRATION_ACTOR,
            **auth_set,
        })

    profile_set = {
        "schoolId": SCHOOL_ID,
        "name": spec["name"],
        "role": spec["role"],
        "sub_category": spec["sub_category"],
        "branch_id": BRANCH_ID,
        "is_active": True,
        "updated_at": now,
    }
    if spec.get("phone"):
        profile_set["phone"] = spec["phone"]
    await db.users.update_one(
        {"id": user_id, "schoolId": SCHOOL_ID},
        {"$set": profile_set, "$setOnInsert": {"_id": user_id, "id": user_id, "created_at": now}},
        upsert=True,
    )

    await db.refresh_tokens.update_many(
        {"user_id": user_id, "revoked_at": None},
        {"$set": {"revoked_at": now, "revoked_reason": "credential_provisioning"}},
    )
    audit_id = str(uuid.uuid4())
    await db.audit_logs.insert_one({
        "_id": audit_id,
        "id": audit_id,
        "schoolId": SCHOOL_ID,
        "branch_id": BRANCH_ID,
        "entity_type": "auth_users",
        "collection": "auth_users",
        "entity_id": user_id,
        "record_id": user_id,
        "action": "leadership_account_provisioned",
        "changed_by": MIGRATION_ACTOR,
        "changed_by_role": "platform_migration",
        "changes": {
            "username": spec["username"],
            "role": spec["role"],
            "sub_category": spec["sub_category"],
            "must_change_password": False,
        },
        "reason": "Approved four-profile Flo access rollout",
        "created_at": now,
        "timestamp": now,
    })


async def migrate(db=None) -> None:
    if db is None:
        raise RuntimeError("Run migration 031 explicitly with a reviewed database handle")

    resolved = await _resolve_accounts(db)
    now = datetime.now(timezone.utc).isoformat()
    for item in resolved:
        await _upsert_profile(db, item, now)


if __name__ == "__main__":
    raise SystemExit(
        "Import this migration and run migrate(db) explicitly; never use run_all.py on production"
    )
