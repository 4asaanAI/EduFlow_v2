"""
Migration 016: Backfill admin sub_category for legacy rows.

Story: Part 1 (Auth + RBAC hardening) — closes the "no sub_category → type=all"
permissive fallback in scope_resolver. Before this change, an admin row that
predates the sub_category field would silently get full operational access.
After this change, scope_resolver denies-by-default for missing sub_category,
so any legacy row MUST be backfilled or the user will see nothing.

Strategy:
  1. For legacy admin rows where designation maps to a known sub_category
     (e.g. designation="Principal"), promote designation→sub_category first
     (Part 1.5 Patch J — scope_resolver no longer reads designation).
  2. Any remaining admin row with no sub_category gets "support_staff"
     (self-only scope). An operator can manually promote later.

Idempotent: safe to re-run. Audit row uses upsert; timestamps are real.

Run: python backend/migrations/016_admin_sub_category_default.py
"""
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Known designation values → canonical sub_category. Lowercased before match.
DESIGNATION_TO_SUB_CATEGORY = {
    "principal": "principal",
    "vice principal": "principal",
    "vice-principal": "principal",
    "accountant": "accountant",
    "accounts": "accountant",
    "transport head": "transport_head",
    "transport_head": "transport_head",
    "transport": "transport_head",
    "receptionist": "receptionist",
    "front desk": "receptionist",
    "front_desk": "receptionist",
    "support staff": "support_staff",
    "support_staff": "support_staff",
    "support": "support_staff",
    "peon": "support_staff",
    "helper": "support_staff",
}

LEGACY_QUERY_AUTH = {
    "user_info.role": "admin",
    "$or": [
        {"user_info.sub_category": {"$exists": False}},
        {"user_info.sub_category": None},
        {"user_info.sub_category": ""},
    ],
}

LEGACY_QUERY_STAFF = {
    "role": "admin",
    "$or": [
        {"sub_category": {"$exists": False}},
        {"sub_category": None},
        {"sub_category": ""},
    ],
}


async def _promote_designation(db, now_iso: str) -> dict:
    """Promote designation→sub_category for legacy admin rows. Returns counts per mapping."""
    counts = {}

    # auth_users: designation lives under user_info.designation
    for des_value, sub_cat in DESIGNATION_TO_SUB_CATEGORY.items():
        q = {
            **LEGACY_QUERY_AUTH,
            "user_info.designation": {"$regex": f"^{des_value}$", "$options": "i"},
        }
        res = await db.auth_users.update_many(
            q,
            {"$set": {
                "user_info.sub_category": sub_cat,
                "user_info.sub_category_backfilled_at": now_iso,
                "user_info.sub_category_backfilled_by": "migration-016-designation-promo",
            }},
        )
        if res.modified_count:
            counts[f"auth_users:{des_value}->{sub_cat}"] = res.modified_count

    # staff: designation top-level
    for des_value, sub_cat in DESIGNATION_TO_SUB_CATEGORY.items():
        q = {
            **LEGACY_QUERY_STAFF,
            "designation": {"$regex": f"^{des_value}$", "$options": "i"},
        }
        res = await db.staff.update_many(
            q,
            {"$set": {
                "sub_category": sub_cat,
                "sub_category_backfilled_at": now_iso,
                "sub_category_backfilled_by": "migration-016-designation-promo",
            }},
        )
        if res.modified_count:
            counts[f"staff:{des_value}->{sub_cat}"] = res.modified_count

    return counts


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        print("=" * 60)
        print("Migration 016: Backfill admin sub_category (legacy → support_staff)")
        print("=" * 60)

        # Step 1: promote known designation values to sub_category first.
        promo_counts = await _promote_designation(db, now_iso)
        if promo_counts:
            print("  Designation→sub_category promotions:")
            for k, v in promo_counts.items():
                print(f"    {k}: {v}")
        else:
            print("  No designation→sub_category promotions needed")

        # Step 2: remaining rows with still-empty sub_category get support_staff.
        auth_res = await db.auth_users.update_many(
            LEGACY_QUERY_AUTH,
            {"$set": {
                "user_info.sub_category": "support_staff",
                "user_info.sub_category_backfilled_at": now_iso,
                "user_info.sub_category_backfilled_by": "migration-016",
            }},
        )
        print(f"  OK auth_users: matched={auth_res.matched_count} modified={auth_res.modified_count}")

        staff_res = await db.staff.update_many(
            LEGACY_QUERY_STAFF,
            {"$set": {
                "sub_category": "support_staff",
                "sub_category_backfilled_at": now_iso,
                "sub_category_backfilled_by": "migration-016",
            }},
        )
        print(f"  OK staff: matched={staff_res.matched_count} modified={staff_res.modified_count}")

        # Audit row: idempotent upsert so re-run does not raise / duplicate.
        await db.audit_logs.update_one(
            {"id": "migration-016-admin-sub-category-default"},
            {
                "$set": {
                    "entity_type": "migration",
                    "entity_id": "016_admin_sub_category_default",
                    "action": "backfill",
                    "last_run_at": now_iso,
                    "last_run_changes": {
                        "auth_users_modified": auth_res.modified_count,
                        "staff_modified": staff_res.modified_count,
                        "designation_promotions": promo_counts,
                    },
                },
                "$setOnInsert": {"first_run_at": now_iso, "created_at": now_iso},
            },
            upsert=True,
        )

        print("Migration 016 complete")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
