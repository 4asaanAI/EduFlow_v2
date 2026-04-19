"""
Migration 002: Add houses and house_points collections. Assign houses to students.
Run: python backend/migrations/002_add_houses.py
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

BRANCH_ID = "branch-aaryans-joya"

HOUSES = [
    {
        "id": "house-shivaji",
        "branch_id": BRANCH_ID,
        "name": "Shivaji House",
        "color_name": "green",
        "color_hex": "#22C55E",
        "motto": "Courage and Valor",
        "captain_student_id": None,
        "vice_captain_student_id": None,
        "total_points": 0,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "house-tagore",
        "branch_id": BRANCH_ID,
        "name": "Tagore House",
        "color_name": "yellow",
        "color_hex": "#EAB308",
        "motto": "Wisdom and Creativity",
        "captain_student_id": None,
        "vice_captain_student_id": None,
        "total_points": 0,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "house-raman",
        "branch_id": BRANCH_ID,
        "name": "Raman House",
        "color_name": "red",
        "color_hex": "#EF4444",
        "motto": "Discovery and Innovation",
        "captain_student_id": None,
        "vice_captain_student_id": None,
        "total_points": 0,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "house-kalam",
        "branch_id": BRANCH_ID,
        "name": "Kalam House",
        "color_name": "blue",
        "color_hex": "#3B82F6",
        "motto": "Dreams and Dedication",
        "captain_student_id": None,
        "vice_captain_student_id": None,
        "total_points": 0,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]

HOUSE_IDS = [h["id"] for h in HOUSES]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 002: Add houses")
        print("=" * 60)

        # 1. Create houses collection and insert houses
        for house in HOUSES:
            existing = await db.houses.find_one({"id": house["id"]})
            if existing:
                print(f"  House '{house['name']}' already exists, skipping.")
            else:
                await db.houses.insert_one(house)
                print(f"  Created house: {house['name']} ({house['color_name']})")

        # Indexes on houses
        houses_indexes = await db.houses.index_information()
        if "branch_id_1" not in houses_indexes:
            await db.houses.create_index("branch_id")
            print("  Created index on houses.branch_id")

        # 2. Create house_points collection with indexes
        hp_indexes = await db.house_points.index_information()
        if "house_id_1" not in hp_indexes:
            await db.house_points.create_index("house_id")
            print("  Created index on house_points.house_id")
        if "branch_id_1" not in hp_indexes:
            await db.house_points.create_index("branch_id")
            print("  Created index on house_points.branch_id")
        compound_key = "branch_id_1_academic_year_1_house_id_1"
        if compound_key not in hp_indexes:
            await db.house_points.create_index(
                [("branch_id", 1), ("academic_year", 1), ("house_id", 1)]
            )
            print("  Created compound index on house_points (branch_id, academic_year, house_id)")

        # 3. Assign house_id to all existing students (distribute evenly)
        students_without_house = await db.students.count_documents(
            {"house_id": {"$exists": False}}
        )
        if students_without_house == 0:
            total = await db.students.count_documents({})
            print(f"  All {total} students already have house_id, skipping.")
        else:
            cursor = db.students.find(
                {"house_id": {"$exists": False}},
                {"_id": 1}
            )
            idx = 0
            async for student in cursor:
                house_id = HOUSE_IDS[idx % len(HOUSE_IDS)]
                await db.students.update_one(
                    {"_id": student["_id"]},
                    {"$set": {"house_id": house_id}},
                )
                idx += 1
            print(f"  Assigned houses to {idx} students (evenly distributed across 4 houses)")

        # 4. Add positions array to all students who don't have it
        missing_positions = await db.students.count_documents(
            {"positions": {"$exists": False}}
        )
        if missing_positions == 0:
            print("  All students already have positions field, skipping.")
        else:
            result = await db.students.update_many(
                {"positions": {"$exists": False}},
                {"$set": {"positions": []}},
            )
            print(f"  Added positions field to {result.modified_count} students")

        print("\nMigration 002 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
