"""
Migration 010: Add token_usage, token_balance, and token_recharges collections.
Run: python backend/migrations/010_add_tokens.py
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime, date

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

BRANCH_ID = "branch-aaryans-joya"


def get_billing_cycle():
    """Return first and last day of the current month."""
    today = date.today()
    first_of_month = today.replace(day=1)
    # Last day: go to next month's first day and subtract 1
    if today.month == 12:
        last_of_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        last_of_month = today.replace(month=today.month + 1, day=1)
    from datetime import timedelta
    last_of_month = last_of_month - timedelta(days=1)
    return first_of_month.strftime("%Y-%m-%d"), last_of_month.strftime("%Y-%m-%d")


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 010: Add token management")
        print("=" * 60)

        billing_start, billing_end = get_billing_cycle()

        # 1. Insert default token balance
        existing_balance = await db.token_balance.find_one({"branch_id": BRANCH_ID})
        if existing_balance:
            print(f"  Token balance for {BRANCH_ID} already exists, skipping.")
        else:
            token_balance = {
                "id": "tb-001",
                "branch_id": BRANCH_ID,
                "plan_id": "growth",
                "plan_name": "Growth",
                "monthly_included": 2000000,
                "monthly_used": 0,
                "purchased_topup": 0,
                "topup_used": 0,
                "billing_cycle_start": billing_start,
                "billing_cycle_end": billing_end,
                "per_role_limits": {
                    "owner": -1,
                    "admin": 100000,
                    "teacher": 50000,
                    "student": 20000,
                },
                "self_recharge_enabled": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
            await db.token_balance.insert_one(token_balance)
            print(f"  Created token balance: Growth plan, {token_balance['monthly_included']:,} tokens/month")
            print(f"  Billing cycle: {billing_start} to {billing_end}")

        # 2. Create indexes on token_usage
        tu_indexes = await db.token_usage.index_information()
        if "branch_id_1" not in tu_indexes:
            await db.token_usage.create_index("branch_id")
            print("  Created index on token_usage.branch_id")
        if "user_id_1" not in tu_indexes:
            await db.token_usage.create_index("user_id")
            print("  Created index on token_usage.user_id")
        compound_key = "branch_id_1_date_1"
        if compound_key not in tu_indexes:
            await db.token_usage.create_index([("branch_id", 1), ("date", 1)])
            print("  Created compound index on token_usage (branch_id, date)")

        # 3. Create indexes on token_balance
        tb_indexes = await db.token_balance.index_information()
        if "branch_id_1" not in tb_indexes:
            await db.token_balance.create_index("branch_id", unique=True)
            print("  Created unique index on token_balance.branch_id")

        # 4. Create indexes on token_recharges
        tr_indexes = await db.token_recharges.index_information()
        if "branch_id_1" not in tr_indexes:
            await db.token_recharges.create_index("branch_id")
            print("  Created index on token_recharges.branch_id")
        if "created_at_1" not in tr_indexes:
            await db.token_recharges.create_index("created_at")
            print("  Created index on token_recharges.created_at")

        print("\nMigration 010 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
