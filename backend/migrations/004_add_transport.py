"""
Migration 004: Add transport collections (vehicles, transport_routes, student_transport).
Run: python backend/migrations/004_add_transport.py
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

VEHICLES = [
    {
        "id": "vehicle-001",
        "branch_id": BRANCH_ID,
        "type": "bus",
        "registration_number": "UP-31-AT-1234",
        "make": "Tata",
        "model": "Starbus",
        "capacity": 40,
        "year": 2021,
        "driver_name": "Raju Yadav",
        "driver_phone": "9876540001",
        "driver_license": "DL-0420200987654",
        "conductor_name": "Sunil Kumar",
        "conductor_phone": "9876540002",
        "insurance_valid_till": "2027-03-31",
        "fitness_valid_till": "2027-01-15",
        "gps_enabled": True,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "vehicle-002",
        "branch_id": BRANCH_ID,
        "type": "bus",
        "registration_number": "UP-31-BT-5678",
        "make": "Ashok Leyland",
        "model": "Lynx",
        "capacity": 36,
        "year": 2022,
        "driver_name": "Mohan Singh",
        "driver_phone": "9876540003",
        "driver_license": "DL-0420210123456",
        "conductor_name": "Pappu Verma",
        "conductor_phone": "9876540004",
        "insurance_valid_till": "2027-06-30",
        "fitness_valid_till": "2027-04-20",
        "gps_enabled": True,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "vehicle-003",
        "branch_id": BRANCH_ID,
        "type": "van",
        "registration_number": "UP-31-CV-9012",
        "make": "Force",
        "model": "Traveller",
        "capacity": 16,
        "year": 2023,
        "driver_name": "Ashok Tiwari",
        "driver_phone": "9876540005",
        "driver_license": "DL-0420220567890",
        "conductor_name": None,
        "conductor_phone": None,
        "insurance_valid_till": "2027-09-15",
        "fitness_valid_till": "2027-07-10",
        "gps_enabled": False,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]

ROUTES = [
    {
        "id": "route-001",
        "branch_id": BRANCH_ID,
        "name": "Route 1 - Joya Town",
        "vehicle_id": "vehicle-001",
        "monthly_fee": 800,
        "stops": [
            {"name": "Joya Bus Stand", "pickup_time": "07:00", "drop_time": "14:30", "distance_km": 5.0, "order": 1},
            {"name": "Mohalla Sarai", "pickup_time": "07:10", "drop_time": "14:20", "distance_km": 4.0, "order": 2},
            {"name": "Subhash Chowk", "pickup_time": "07:20", "drop_time": "14:10", "distance_km": 2.5, "order": 3},
            {"name": "School Gate", "pickup_time": "07:35", "drop_time": "14:00", "distance_km": 0, "order": 4},
        ],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "route-002",
        "branch_id": BRANCH_ID,
        "name": "Route 2 - Amroha Road",
        "vehicle_id": "vehicle-002",
        "monthly_fee": 1000,
        "stops": [
            {"name": "Amroha Bypass", "pickup_time": "06:45", "drop_time": "14:45", "distance_km": 12.0, "order": 1},
            {"name": "Hasanpur Tiraha", "pickup_time": "07:00", "drop_time": "14:30", "distance_km": 8.0, "order": 2},
            {"name": "Railway Crossing", "pickup_time": "07:15", "drop_time": "14:15", "distance_km": 3.0, "order": 3},
            {"name": "School Gate", "pickup_time": "07:35", "drop_time": "14:00", "distance_km": 0, "order": 4},
        ],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "route-003",
        "branch_id": BRANCH_ID,
        "name": "Route 3 - Noorpur Side",
        "vehicle_id": "vehicle-003",
        "monthly_fee": 900,
        "stops": [
            {"name": "Noorpur Village", "pickup_time": "07:00", "drop_time": "14:40", "distance_km": 7.0, "order": 1},
            {"name": "Chandpur Mod", "pickup_time": "07:15", "drop_time": "14:25", "distance_km": 4.0, "order": 2},
            {"name": "Mandi Gate", "pickup_time": "07:25", "drop_time": "14:10", "distance_km": 1.5, "order": 3},
        ],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]

ROUTE_IDS = [r["id"] for r in ROUTES]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 004: Add transport")
        print("=" * 60)

        # 1. Insert vehicles
        for vehicle in VEHICLES:
            existing = await db.vehicles.find_one({"id": vehicle["id"]})
            if existing:
                print(f"  Vehicle '{vehicle['registration_number']}' already exists, skipping.")
            else:
                await db.vehicles.insert_one(vehicle)
                print(f"  Created vehicle: {vehicle['registration_number']} ({vehicle['type']})")

        # Indexes on vehicles
        v_indexes = await db.vehicles.index_information()
        if "branch_id_1" not in v_indexes:
            await db.vehicles.create_index("branch_id")
            print("  Created index on vehicles.branch_id")

        # 2. Insert routes
        for route in ROUTES:
            existing = await db.transport_routes.find_one({"id": route["id"]})
            if existing:
                print(f"  Route '{route['name']}' already exists, skipping.")
            else:
                await db.transport_routes.insert_one(route)
                print(f"  Created route: {route['name']} ({len(route['stops'])} stops)")

        # Indexes on routes
        r_indexes = await db.transport_routes.index_information()
        if "branch_id_1" not in r_indexes:
            await db.transport_routes.create_index("branch_id")
            print("  Created index on transport_routes.branch_id")
        if "vehicle_id_1" not in r_indexes:
            await db.transport_routes.create_index("vehicle_id")
            print("  Created index on transport_routes.vehicle_id")

        # 3. Assign ~30% of students to transport
        existing_transport = await db.student_transport.count_documents({})
        if existing_transport > 0:
            print(f"  student_transport already has {existing_transport} records, skipping assignment.")
        else:
            students = []
            cursor = db.students.find({}, {"id": 1, "name": 1})
            async for s in cursor:
                students.append(s)

            random.seed(42)  # Deterministic for reproducibility
            transport_count = max(1, int(len(students) * 0.3))
            selected = random.sample(students, transport_count)

            transport_docs = []
            for idx, student in enumerate(selected):
                route_id = ROUTE_IDS[idx % len(ROUTE_IDS)]
                route = next(r for r in ROUTES if r["id"] == route_id)
                # Pick a random stop (not the school gate)
                non_school_stops = [s for s in route["stops"] if s["distance_km"] > 0]
                stop = random.choice(non_school_stops)

                transport_docs.append({
                    "id": f"st-{idx+1:03d}",
                    "branch_id": BRANCH_ID,
                    "student_id": student["id"],
                    "route_id": route_id,
                    "vehicle_id": route["vehicle_id"],
                    "pickup_stop": stop["name"],
                    "monthly_fee": route["monthly_fee"],
                    "is_active": True,
                    "start_date": "2025-04-01",
                    "created_at": datetime.now().isoformat(),
                })

            await db.student_transport.insert_many(transport_docs)
            print(f"  Assigned {len(transport_docs)} students ({len(transport_docs)}/{len(students)}) to transport routes")

        # Indexes on student_transport
        st_indexes = await db.student_transport.index_information()
        if "branch_id_1" not in st_indexes:
            await db.student_transport.create_index("branch_id")
        if "student_id_1" not in st_indexes:
            await db.student_transport.create_index("student_id")
        if "route_id_1" not in st_indexes:
            await db.student_transport.create_index("route_id")
        print("  Ensured indexes on student_transport")

        print("\nMigration 004 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
