"""
Migration 013: Add schoolId to existing documents.

Run:
    python backend/migrations/013_add_school_id.py

Idempotent: only documents missing schoolId are updated.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent.parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")

SKIP_COLLECTIONS = {"_migrations"}


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 013: Add schoolId")
        print("=" * 60)
        print(f"  schoolId: {SCHOOL_ID}")

        total_matched = 0
        total_modified = 0
        collection_names = await db.list_collection_names()
        for name in sorted(collection_names):
            if name in SKIP_COLLECTIONS or name.startswith("system."):
                continue
            result = await db[name].update_many(
                {"schoolId": {"$exists": False}},
                {"$set": {"schoolId": SCHOOL_ID}},
            )
            total_matched += result.matched_count
            total_modified += result.modified_count
            print(f"  {name}: matched={result.matched_count}, modified={result.modified_count}")

            indexes = await db[name].index_information()
            if "schoolId_1" not in indexes:
                await db[name].create_index("schoolId")

        print(f"\n  Total matched: {total_matched}")
        print(f"  Total modified: {total_modified}")
        print("\nMigration 013 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
