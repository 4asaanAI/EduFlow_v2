"""
Migration 014: Ensure the maintenance demo account exists (upsert).
Creates or updates the maintenance admin user + staff record so the demo
login always works even if seed.py was not re-run.

Run: python backend/migrations/014_ensure_maintenance_user.py
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Adjust to match your school's school_id
SCHOOL_ID = os.environ.get("DEFAULT_SCHOOL_ID", "school-aaryans")

ADMIN_MAINTENANCE_ID = "user-admin-006"
STAFF_MAINTENANCE_ID = "staff-015"


def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        # ── Upsert auth record ────────────────────────────────────────────────
        existing_auth = await db.auth.find_one({"username_lower": "maintenance"})
        if not existing_auth:
            auth_doc = {
                "username": "maintenance",
                "username_lower": "maintenance",
                "password_hash": hash_pw("maintenance@123"),
                "school_id": SCHOOL_ID,
                "user_info": {
                    "id": ADMIN_MAINTENANCE_ID,
                    "name": "Arvind Maintenance",
                    "role": "admin",
                    "sub_category": "maintenance",
                    "initials": "AM",
                },
                "created_at": datetime.now().isoformat(),
            }
            await db.auth.insert_one(auth_doc)
            print("  Created auth record for maintenance user")
        else:
            # Ensure sub_category is set correctly
            await db.auth.update_one(
                {"username_lower": "maintenance"},
                {"$set": {"user_info.sub_category": "maintenance"}}
            )
            print("  Auth record for maintenance user already exists — ensured sub_category")

        # ── Upsert user profile ───────────────────────────────────────────────
        existing_user = await db.users.find_one({"id": ADMIN_MAINTENANCE_ID})
        if not existing_user:
            user_doc = {
                "id": ADMIN_MAINTENANCE_ID,
                "name": "Arvind Maintenance",
                "role": "admin",
                "sub_category": "maintenance",
                "phone": "9876543216",
                "email": "maintenance@theararyans.edu.in",
                "preferred_language": "en",
                "is_active": True,
                "school_id": SCHOOL_ID,
                "created_at": datetime.now().isoformat(),
            }
            await db.users.insert_one(user_doc)
            print("  Created users record for maintenance user")
        else:
            await db.users.update_one(
                {"id": ADMIN_MAINTENANCE_ID},
                {"$set": {"sub_category": "maintenance", "is_active": True}}
            )
            print("  Users record for maintenance already exists — updated sub_category")

        # ── Upsert staff record ───────────────────────────────────────────────
        existing_staff = await db.staff.find_one({"id": STAFF_MAINTENANCE_ID})
        if not existing_staff:
            staff_doc = {
                "id": STAFF_MAINTENANCE_ID,
                "user_id": ADMIN_MAINTENANCE_ID,
                "name": "Arvind Maintenance",
                "staff_type": "admin",
                "sub_category": "maintenance",
                "designation": "Maintenance",
                "employee_id": "EMP015",
                "salary": 24000,
                "school_id": SCHOOL_ID,
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            }
            await db.staff.insert_one(staff_doc)
            print("  Created staff record for maintenance user")
        else:
            print("  Staff record for maintenance already exists")

        print("Migration 014 complete: maintenance user ensured.")
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
