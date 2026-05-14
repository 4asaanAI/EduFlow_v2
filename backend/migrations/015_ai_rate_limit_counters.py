"""
Migration 015: AI rate-limit counters + overrides.

Creates two collections backing Story 7-48 (AI Write Rate Limiting):

  * ai_rate_limit_counters — per (user_id, session_id, hour_bucket) counter
    rows. Auto-purged ~5 min after the bucket closes via TTL on expires_at.

  * ai_rate_limit_overrides — operator-set per-school role ceilings that
    win over the YAML defaults. Rows with expires_at in the past are
    auto-purged via TTL; rows with expires_at=null persist forever.

Run: python backend/migrations/015_ai_rate_limit_counters.py
"""
import asyncio
import os
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
        print("=" * 60)
        print("Migration 015: AI rate-limit counters + overrides")
        print("=" * 60)

        # ── counters ──────────────────────────────────────────────────────
        # Counter key is (user_id, hour_bucket) — per-user, NOT per-session,
        # so session_id rotation cannot bypass the limit.
        await db.ai_rate_limit_counters.create_index(
            [("user_id", 1), ("hour_bucket", 1)],
            unique=True,
            name="user_bucket_unique",
        )
        await db.ai_rate_limit_counters.create_index(
            "expires_at",
            expireAfterSeconds=0,
            name="counters_ttl",
        )
        print("  OK ai_rate_limit_counters indexes")

        # ── overrides ─────────────────────────────────────────────────────
        await db.ai_rate_limit_overrides.create_index(
            [("school_id", 1), ("role", 1), ("created_at", -1)],
            name="school_role_recent",
        )
        # sparse TTL — only rows with expires_at set are auto-purged
        await db.ai_rate_limit_overrides.create_index(
            "expires_at",
            expireAfterSeconds=0,
            sparse=True,
            name="overrides_ttl_sparse",
        )
        print("  OK ai_rate_limit_overrides indexes")
        print("Migration 015 complete")
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
