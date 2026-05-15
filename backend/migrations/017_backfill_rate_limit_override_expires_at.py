"""
Migration 017: Backfill expires_at on ai_rate_limit_overrides rows.

Part 2 (AI Layer) Wave 2 — P10 E11.

The operator override route now requires an explicit `expires_at` value (null
for permanent, ISO timestamp for time-bounded). Existing rows that pre-date
this requirement may have the field missing (not set) rather than null. Mongo's
query `expires_at: null` matches *null* but NOT a missing field, so rows with
no `expires_at` field would be invisible to the resolver's non-expiry check.

This migration sets `expires_at: null` explicitly on every override row where
the field is absent. That makes them permanent (never expiring) and visible to
resolve_limit.

Idempotent: safe to re-run.
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


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        now_iso = datetime.now(timezone.utc).isoformat()

        print("=" * 60)
        print("Migration 017: Backfill expires_at on ai_rate_limit_overrides")
        print("=" * 60)

        result = await db.ai_rate_limit_overrides.update_many(
            {"expires_at": {"$exists": False}},
            {"$set": {"expires_at": None, "expires_at_backfilled_at": now_iso}},
        )
        print(f"  OK: matched={result.matched_count} modified={result.modified_count}")

        await db.audit_logs.update_one(
            {"id": "migration-017-rate-limit-override-expires-at"},
            {
                "$set": {
                    "entity_type": "migration",
                    "entity_id": "017_backfill_rate_limit_override_expires_at",
                    "action": "backfill",
                    "last_run_at": now_iso,
                    "last_run_changes": {"modified": result.modified_count},
                },
                "$setOnInsert": {"first_run_at": now_iso, "created_at": now_iso},
            },
            upsert=True,
        )

        print("Migration 017 complete")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
