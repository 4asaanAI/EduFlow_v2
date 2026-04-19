"""
Migration 001: Add branches collection and branch_id to all existing documents.
Run: python backend/migrations/001_add_branches.py
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

DEFAULT_BRANCH = {
    "id": "branch-aaryans-joya",
    "name": "The Aaryans - Joya",
    "code": "JOYA",
    "type": "school",
    "board": "CBSE",
    "city": "Joya",
    "state": "Uttar Pradesh",
    "owner_user_id": "user-owner-001",
    "academic_year": "2025-26",
    "is_active": True,
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
}

COLLECTIONS_TO_TAG = [
    "students",
    "staff",
    "classes",
    "subjects",
    "student_attendance",
    "staff_attendance",
    "fee_transactions",
    "fee_structures",
    "leave_requests",
    "announcements",
    "enquiries",
    "conversations",
    "messages",
]

BRANCH_ID = "branch-aaryans-joya"


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 001: Add branches")
        print("=" * 60)

        # 1. Create branches collection and insert default branch
        existing = await db.branches.find_one({"id": BRANCH_ID})
        if existing:
            print(f"Branch '{BRANCH_ID}' already exists, skipping insert.")
        else:
            await db.branches.insert_one(DEFAULT_BRANCH)
            print(f"Created branch: {DEFAULT_BRANCH['name']}")

        # Create index on owner_user_id
        existing_indexes = await db.branches.index_information()
        if "owner_user_id_1" not in existing_indexes:
            await db.branches.create_index("owner_user_id")
            print("Created index on branches.owner_user_id")
        else:
            print("Index on branches.owner_user_id already exists")

        # 2. Add branch_id to all existing documents in tagged collections
        for col_name in COLLECTIONS_TO_TAG:
            collection = db[col_name]

            # Count documents missing branch_id
            missing_count = await collection.count_documents({"branch_id": {"$exists": False}})
            if missing_count == 0:
                total = await collection.count_documents({})
                print(f"  {col_name}: all {total} documents already have branch_id, skipping.")
                continue

            result = await collection.update_many(
                {"branch_id": {"$exists": False}},
                {"$set": {"branch_id": BRANCH_ID}},
            )
            print(f"  Adding branch_id to {col_name}... {result.modified_count} documents updated")

            # Create index on branch_id
            col_indexes = await collection.index_information()
            if "branch_id_1" not in col_indexes:
                await collection.create_index("branch_id")
                print(f"  Created index on {col_name}.branch_id")
            else:
                print(f"  Index on {col_name}.branch_id already exists")

        print("\nMigration 001 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
