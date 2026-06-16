"""Idempotently add the 'management' admin sub-role account to a live database.

Creates (or refreshes) the user, auth login, and staff record for the Management
admin sub-role without wiping any existing data. Safe to run repeatedly.

Run:  python backend/scripts/add_management_account.py
Login: username 'management' / password 'management@123'
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")

USER_ID = "user-admin-007"
STAFF_ID = "staff-017"
USERNAME = "management"
PASSWORD = "management@123"
NAME = "Rohit Management"


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


async def main() -> None:
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000, retryWrites=True)
    db = client[DB_NAME]

    branch = await db.branches.find_one({"schoolId": SCHOOL_ID}, {"_id": 0, "id": 1})
    branch_id = branch["id"] if branch else None

    await db.users.update_one(
        {"id": USER_ID},
        {"$set": {
            "id": USER_ID, "schoolId": SCHOOL_ID, "name": NAME,
            "role": "admin", "sub_category": "management",
            "phone": "9876543217", "email": "management@theararyans.edu.in",
            "preferred_language": "en", "theme": "light", "is_active": True,
        }},
        upsert=True,
    )

    await db.auth_users.update_one(
        {"username_lower": USERNAME, "schoolId": SCHOOL_ID},
        {"$set": {
            "schoolId": SCHOOL_ID,
            "username": USERNAME, "username_lower": USERNAME,
            "password_hash": hash_pw(PASSWORD),
            "role": "admin", "is_active": True, "must_change_password": False,
            "phone": "9876543217",
            "user_info": {
                "id": USER_ID, "name": NAME, "role": "admin",
                "sub_category": "management", "initials": "RM",
            },
        }, "$setOnInsert": {"id": USER_ID}},
        upsert=True,
    )

    await db.staff.update_one(
        {"id": STAFF_ID},
        {"$set": {
            "id": STAFF_ID, "schoolId": SCHOOL_ID, "user_id": USER_ID, "name": NAME,
            "staff_type": "admin", "sub_category": "management",
            "employee_id": "EMP017", "designation": "Management Officer",
            "department": "Management", "salary": 40000, "branch_id": branch_id,
            "is_active": True,
            "casual_leave_balance": 12, "medical_leave_balance": 10, "earned_leave_balance": 15,
            "join_date": "2020-06-01", "phone": "9876543217",
            "email": "management@theararyans.edu.in", "address": "Lucknow, UP",
        }},
        upsert=True,
    )

    print(f"✅ Management account ready — login '{USERNAME}' / '{PASSWORD}' (school {SCHOOL_ID})")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
