"""
Migration 027: Upgrade all role AI token limits to 1,000,000 per month.
Run: python backend/migrations/027_upgrade_role_token_limits_to_1m.py
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
        result = await db.token_balances.update_many(
            {},
            {
                "$set": {
                    "role_limits.owner": 1_000_000,
                    "role_limits.admin": 1_000_000,
                    "role_limits.teacher": 1_000_000,
                    "role_limits.student": 1_000_000,
                    "sub_category_limits.principal": 1_000_000,
                    "updated_at": now_iso,
                }
            },
        )
        print(
            "  Updated token role limits to 1,000,000 for "
            f"{getattr(result, 'modified_count', 0)} token balance document(s)."
        )
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
