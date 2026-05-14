"""
Migration 016: Backfill admin sub_category for legacy rows.

Story: Part 1 (Auth + RBAC hardening) — closes the "no sub_category → type=all"
permissive fallback in scope_resolver. Before this change, an admin row that
predates the sub_category field would silently get full operational access.
After this change, scope_resolver denies-by-default for missing sub_category,
so any legacy row MUST be backfilled or the user will see nothing.

Strategy: any auth_users / staff row where role=admin AND sub_category is
absent/empty/null gets sub_category="support_staff" (self-only scope). An
operator can manually promote them later via the regular admin tooling.

Run: python backend/migrations/016_admin_sub_category_default.py
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

LEGACY_QUERY = {
    "user_info.role": "admin",
    "$or": [
        {"user_info.sub_category": {"$exists": False}},
        {"user_info.sub_category": None},
        {"user_info.sub_category": ""},
    ],
}

STAFF_QUERY = {
    "role": "admin",
    "$or": [
        {"sub_category": {"$exists": False}},
        {"sub_category": None},
        {"sub_category": ""},
    ],
}


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 016: Backfill admin sub_category (legacy → support_staff)")
        print("=" * 60)

        # auth_users.user_info.sub_category
        auth_res = await db.auth_users.update_many(
            LEGACY_QUERY,
            {"$set": {
                "user_info.sub_category": "support_staff",
                "user_info.sub_category_backfilled_at": "2026-05-15T00:00:00Z",
                "user_info.sub_category_backfilled_by": "migration-016",
            }},
        )
        print(f"  OK auth_users: matched={auth_res.matched_count} modified={auth_res.modified_count}")

        # staff.sub_category (top-level — separate document model)
        staff_res = await db.staff.update_many(
            STAFF_QUERY,
            {"$set": {
                "sub_category": "support_staff",
                "sub_category_backfilled_at": "2026-05-15T00:00:00Z",
                "sub_category_backfilled_by": "migration-016",
            }},
        )
        print(f"  OK staff: matched={staff_res.matched_count} modified={staff_res.modified_count}")

        # Audit row so this is visible later
        await db.audit_logs.insert_one({
            "id": "migration-016-admin-sub-category-default",
            "entity_type": "migration",
            "entity_id": "016_admin_sub_category_default",
            "action": "backfill",
            "changes": {
                "auth_users_modified": auth_res.modified_count,
                "staff_modified": staff_res.modified_count,
            },
            "created_at": "2026-05-15T00:00:00Z",
        })

        print("Migration 016 complete")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
