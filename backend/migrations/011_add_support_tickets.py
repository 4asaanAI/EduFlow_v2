"""
Migration 011: Add support_tickets collection (starts empty).
Run: python backend/migrations/011_add_support_tickets.py
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
        print("Migration 011: Add support tickets")
        print("=" * 60)

        # Ensure the collection exists by checking/creating indexes
        # (MongoDB creates the collection implicitly when an index is created)
        st_indexes = await db.support_tickets.index_information()

        if "branch_id_1" not in st_indexes:
            await db.support_tickets.create_index("branch_id")
            print("  Created index on support_tickets.branch_id")
        else:
            print("  Index on support_tickets.branch_id already exists")

        if "status_1" not in st_indexes:
            await db.support_tickets.create_index("status")
            print("  Created index on support_tickets.status")
        else:
            print("  Index on support_tickets.status already exists")

        if "created_at_1" not in st_indexes:
            await db.support_tickets.create_index("created_at")
            print("  Created index on support_tickets.created_at")
        else:
            print("  Index on support_tickets.created_at already exists")

        # Also add compound index for common query pattern
        compound_key = "branch_id_1_status_1"
        if compound_key not in st_indexes:
            await db.support_tickets.create_index([("branch_id", 1), ("status", 1)])
            print("  Created compound index on support_tickets (branch_id, status)")

        count = await db.support_tickets.count_documents({})
        print(f"  support_tickets collection ready ({count} documents)")

        print("\nMigration 011 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
