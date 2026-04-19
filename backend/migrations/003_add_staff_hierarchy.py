"""
Migration 003: Add staff hierarchy fields (sub_category, designation, wing, etc.)
Run: python backend/migrations/003_add_staff_hierarchy.py
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Mapping from staff_type to hierarchy fields
STAFF_TYPE_MAP = {
    "principal": {
        "sub_category": "principal",
        "designation": "principal",
        "wing": "senior",
    },
    "admin": {
        "sub_category": "admin",
        "designation": "staff",
        "wing": "senior",
    },
    "teacher": {
        "sub_category": "senior_teacher",
        "designation": "teacher",
        "wing": "senior",
    },
    "accountant": {
        "sub_category": "accountant",
        "designation": "staff",
        "wing": "senior",
    },
    "peon": {
        "sub_category": "peon",
        "designation": "support",
        "wing": "senior",
    },
}


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 003: Add staff hierarchy")
        print("=" * 60)

        # Find the principal's staff_id for reports_to
        principal = await db.staff.find_one({"staff_type": "principal"})
        principal_staff_id = principal["id"] if principal else None
        if principal_staff_id:
            print(f"  Found principal: {principal['name']} (id: {principal_staff_id})")
        else:
            print("  WARNING: No principal found in staff collection")

        # Build set of class teacher IDs from classes collection
        class_teacher_ids = set()
        class_teacher_map = {}
        cursor = db.classes.find({}, {"class_teacher_id": 1, "id": 1, "name": 1, "section": 1})
        async for cls in cursor:
            ct_id = cls.get("class_teacher_id")
            if ct_id:
                class_teacher_ids.add(ct_id)
                class_teacher_map[ct_id] = cls["id"]

        print(f"  Found {len(class_teacher_ids)} class teachers from classes collection")

        # Process each staff member
        staff_cursor = db.staff.find({})
        updated_count = 0
        skipped_count = 0

        async for staff in staff_cursor:
            # Check if already migrated
            if staff.get("sub_category") is not None:
                skipped_count += 1
                continue

            staff_type = staff.get("staff_type", "peon")
            mapping = STAFF_TYPE_MAP.get(staff_type, STAFF_TYPE_MAP["peon"])

            staff_id = staff["id"]
            user_id = staff.get("user_id")

            is_class_teacher = user_id in class_teacher_ids or staff_id in class_teacher_ids
            class_teacher_of = None
            if is_class_teacher:
                class_teacher_of = class_teacher_map.get(user_id) or class_teacher_map.get(staff_id)

            # Principal doesn't report to anyone; everyone else reports to principal
            reports_to = None if staff_type == "principal" else principal_staff_id

            update_fields = {
                "sub_category": mapping["sub_category"],
                "designation": mapping["designation"],
                "wing": mapping["wing"],
                "subject": None,
                "coordinator_range": None,
                "is_class_teacher": is_class_teacher,
                "class_teacher_of": class_teacher_of,
                "is_incharge": False,
                "incharge_of": None,
                "reports_to": reports_to,
            }

            await db.staff.update_one(
                {"_id": staff["_id"]},
                {"$set": update_fields},
            )
            updated_count += 1

        print(f"  Updated {updated_count} staff documents with hierarchy fields")
        if skipped_count:
            print(f"  Skipped {skipped_count} already-migrated staff documents")

        # Update auth_users to add sub_category
        auth_cursor = db.auth_users.find({})
        auth_updated = 0
        async for auth_user in auth_cursor:
            if auth_user.get("sub_category") is not None:
                continue

            role = auth_user.get("role", "")
            user_info = auth_user.get("user_info", {})
            user_id = user_info.get("id", "")

            # Look up the staff record for this user
            staff_record = await db.staff.find_one({"user_id": user_id})
            if staff_record:
                sub_cat = staff_record.get("sub_category", role)
            else:
                # For students, sub_category is just "student"
                sub_cat = role

            await db.auth_users.update_one(
                {"_id": auth_user["_id"]},
                {"$set": {"sub_category": sub_cat}},
            )
            auth_updated += 1

        print(f"  Updated {auth_updated} auth_users with sub_category")

        # Create indexes
        index_fields = ["sub_category", "designation", "wing", "reports_to"]
        staff_indexes = await db.staff.index_information()
        for field in index_fields:
            idx_name = f"{field}_1"
            if idx_name not in staff_indexes:
                await db.staff.create_index(field)
                print(f"  Created index on staff.{field}")
            else:
                print(f"  Index on staff.{field} already exists")

        print("\nMigration 003 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
