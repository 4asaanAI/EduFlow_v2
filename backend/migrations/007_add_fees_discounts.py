"""
Migration 007: Add fee_discounts and student_fee_profiles collections.
Run: python backend/migrations/007_add_fees_discounts.py
"""
import asyncio
import os
import random
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

BRANCH_ID = "branch-aaryans-joya"

DISCOUNT_RULES = [
    {
        "id": "disc-sibling",
        "branch_id": BRANCH_ID,
        "name": "Sibling Discount",
        "code": "SIBLING",
        "type": "percentage",
        "value": 10,
        "description": "10% discount on tuition for second and subsequent siblings enrolled in the school",
        "applicable_fee_types": ["tuition"],
        "eligibility": "sibling",
        "auto_apply": True,
        "max_discount_amount": None,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "disc-staff-child",
        "branch_id": BRANCH_ID,
        "name": "Staff Child Discount",
        "code": "STAFFCHILD",
        "type": "percentage",
        "value": 50,
        "description": "50% discount on tuition for children of school staff members",
        "applicable_fee_types": ["tuition", "exam", "sports"],
        "eligibility": "staff_child",
        "auto_apply": True,
        "max_discount_amount": None,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "disc-merit",
        "branch_id": BRANCH_ID,
        "name": "Merit Scholarship",
        "code": "MERIT",
        "type": "percentage",
        "value": 25,
        "description": "25% scholarship for students scoring above 90% in previous year exams",
        "applicable_fee_types": ["tuition"],
        "eligibility": "merit",
        "auto_apply": False,
        "max_discount_amount": None,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "disc-early",
        "branch_id": BRANCH_ID,
        "name": "Early Payment Discount",
        "code": "EARLYPAY",
        "type": "percentage",
        "value": 5,
        "description": "5% discount for fees paid before the 5th of each month",
        "applicable_fee_types": ["tuition"],
        "eligibility": "early_payment",
        "auto_apply": False,
        "max_discount_amount": 200,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "disc-custom",
        "branch_id": BRANCH_ID,
        "name": "Custom / Management Quota",
        "code": "CUSTOM",
        "type": "fixed",
        "value": 0,
        "description": "Custom discount amount approved by management on case-by-case basis",
        "applicable_fee_types": ["tuition", "exam", "sports", "transport"],
        "eligibility": "custom",
        "auto_apply": False,
        "max_discount_amount": None,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 007: Add fee discounts & student fee profiles")
        print("=" * 60)

        # 1. Insert discount rules
        inserted_d = 0
        for rule in DISCOUNT_RULES:
            existing = await db.fee_discounts.find_one({"id": rule["id"]})
            if existing:
                continue
            await db.fee_discounts.insert_one(rule)
            inserted_d += 1
        print(f"  Inserted {inserted_d} discount rules (skipped {len(DISCOUNT_RULES) - inserted_d})")

        # 2. Create student fee profiles
        existing_profiles = await db.student_fee_profiles.count_documents({})
        if existing_profiles > 0:
            print(f"  student_fee_profiles already has {existing_profiles} records, skipping.")
        else:
            students = []
            cursor = db.students.find({}, {"id": 1, "name": 1, "class_id": 1})
            async for s in cursor:
                students.append(s)

            random.seed(77)

            # Get staff user_ids to check if any student is a staff child
            staff_user_ids = set()
            staff_cursor = db.staff.find({}, {"user_id": 1})
            async for st in staff_cursor:
                staff_user_ids.add(st.get("user_id"))

            profiles = []
            sibling_assigned = 0
            staff_child_assigned = 0
            merit_assigned = 0

            for idx, student in enumerate(students):
                discounts = []
                discount_total_pct = 0

                # Simulate: ~8% are siblings, ~3% are staff children, ~5% have merit
                r = random.random()
                if r < 0.08 and sibling_assigned < 6:
                    discounts.append({
                        "discount_id": "disc-sibling",
                        "discount_name": "Sibling Discount",
                        "type": "percentage",
                        "value": 10,
                        "approved_by": "user-owner-001",
                        "applied_from": "2025-04-01",
                    })
                    discount_total_pct += 10
                    sibling_assigned += 1
                elif r < 0.11 and staff_child_assigned < 2:
                    discounts.append({
                        "discount_id": "disc-staff-child",
                        "discount_name": "Staff Child Discount",
                        "type": "percentage",
                        "value": 50,
                        "approved_by": "user-owner-001",
                        "applied_from": "2025-04-01",
                    })
                    discount_total_pct += 50
                    staff_child_assigned += 1
                elif r < 0.16 and merit_assigned < 4:
                    discounts.append({
                        "discount_id": "disc-merit",
                        "discount_name": "Merit Scholarship",
                        "type": "percentage",
                        "value": 25,
                        "approved_by": "user-owner-001",
                        "applied_from": "2025-04-01",
                    })
                    discount_total_pct += 25
                    merit_assigned += 1

                base_monthly = 2500
                effective_monthly = base_monthly * (1 - discount_total_pct / 100)

                profile = {
                    "id": f"sfp-{idx+1:03d}",
                    "branch_id": BRANCH_ID,
                    "student_id": student["id"],
                    "class_id": student.get("class_id"),
                    "academic_year": "2025-26",
                    "base_tuition_monthly": base_monthly,
                    "discounts": discounts,
                    "effective_tuition_monthly": effective_monthly,
                    "transport_fee": 0,
                    "other_fees": {},
                    "fee_category": "discounted" if discounts else "full",
                    "created_at": datetime.now().isoformat(),
                }
                profiles.append(profile)

            await db.student_fee_profiles.insert_many(profiles)
            discounted = sum(1 for p in profiles if p["discounts"])
            print(f"  Created {len(profiles)} student fee profiles")
            print(f"    - Full price: {len(profiles) - discounted}")
            print(f"    - Sibling discount: {sibling_assigned}")
            print(f"    - Staff child discount: {staff_child_assigned}")
            print(f"    - Merit scholarship: {merit_assigned}")

        # 3. Create indexes
        fd_indexes = await db.fee_discounts.index_information()
        if "branch_id_1" not in fd_indexes:
            await db.fee_discounts.create_index("branch_id")
            print("  Created index on fee_discounts.branch_id")

        sfp_indexes = await db.student_fee_profiles.index_information()
        if "student_id_1" not in sfp_indexes:
            await db.student_fee_profiles.create_index("student_id")
            print("  Created index on student_fee_profiles.student_id")
        if "branch_id_1" not in sfp_indexes:
            await db.student_fee_profiles.create_index("branch_id")
            print("  Created index on student_fee_profiles.branch_id")

        print("\nMigration 007 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
