"""
Migration 006: Add inventory_items, vendors, and purchase_orders collections.
Run: python backend/migrations/006_add_inventory_vendors.py
"""
import asyncio
import os
from pathlib import Path
from datetime import datetime, date, timedelta

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

BRANCH_ID = "branch-aaryans-joya"

VENDORS = [
    {
        "id": "vendor-001",
        "branch_id": BRANCH_ID,
        "name": "Sharma Furniture Works",
        "contact_person": "Rajendra Sharma",
        "phone": "9876541001",
        "email": "sharma.furniture@example.com",
        "address": "Industrial Area, Moradabad, UP",
        "gst_number": "09ABCDE1234F1Z5",
        "category": "furniture",
        "rating": 4.2,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "vendor-002",
        "branch_id": BRANCH_ID,
        "name": "TechWorld Solutions",
        "contact_person": "Vikas Agarwal",
        "phone": "9876541002",
        "email": "techworld@example.com",
        "address": "Nehru Place, Delhi",
        "gst_number": "07FGHIJ5678K2L6",
        "category": "it_equipment",
        "rating": 4.5,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "vendor-003",
        "branch_id": BRANCH_ID,
        "name": "Sports India Enterprises",
        "contact_person": "Mohammad Asif",
        "phone": "9876541003",
        "email": "sportsindia@example.com",
        "address": "Jalandhar, Punjab",
        "gst_number": "03MNOPQ9012R3S7",
        "category": "sports",
        "rating": 4.0,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "vendor-004",
        "branch_id": BRANCH_ID,
        "name": "National Stationery Mart",
        "contact_person": "Anil Gupta",
        "phone": "9876541004",
        "email": "nationalstationery@example.com",
        "address": "Joya, Amroha, UP",
        "gst_number": "09TUVWX3456Y4Z8",
        "category": "stationery",
        "rating": 3.8,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "vendor-005",
        "branch_id": BRANCH_ID,
        "name": "Green Valley Electricals",
        "contact_person": "Suresh Yadav",
        "phone": "9876541005",
        "email": "greenvalley@example.com",
        "address": "Amroha, UP",
        "gst_number": "09ABCXY7890Z5A9",
        "category": "electrical",
        "rating": 4.1,
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]

INVENTORY_ITEMS = [
    # Furniture
    {"id": "inv-001", "name": "Student Desk (Wooden)", "category": "furniture", "quantity": 120, "unit": "piece", "min_stock": 10, "unit_price": 2500, "location": "Classrooms", "condition": "good"},
    {"id": "inv-002", "name": "Student Chair (Wooden)", "category": "furniture", "quantity": 130, "unit": "piece", "min_stock": 10, "unit_price": 1800, "location": "Classrooms", "condition": "good"},
    {"id": "inv-003", "name": "Teacher Desk (Large)", "category": "furniture", "quantity": 12, "unit": "piece", "min_stock": 2, "unit_price": 5500, "location": "Classrooms", "condition": "good"},
    {"id": "inv-004", "name": "Blackboard (Slate)", "category": "furniture", "quantity": 10, "unit": "piece", "min_stock": 2, "unit_price": 3000, "location": "Classrooms", "condition": "good"},
    {"id": "inv-005", "name": "Whiteboard (4x6 ft)", "category": "furniture", "quantity": 6, "unit": "piece", "min_stock": 1, "unit_price": 4500, "location": "Classrooms", "condition": "good"},
    # IT Equipment
    {"id": "inv-006", "name": "Desktop Computer", "category": "it_equipment", "quantity": 15, "unit": "piece", "min_stock": 2, "unit_price": 35000, "location": "Computer Lab", "condition": "good"},
    {"id": "inv-007", "name": "Printer (Laser)", "category": "it_equipment", "quantity": 3, "unit": "piece", "min_stock": 1, "unit_price": 18000, "location": "Admin Office", "condition": "good"},
    {"id": "inv-008", "name": "Projector (HD)", "category": "it_equipment", "quantity": 4, "unit": "piece", "min_stock": 1, "unit_price": 45000, "location": "AV Room", "condition": "good"},
    {"id": "inv-009", "name": "UPS (1KVA)", "category": "it_equipment", "quantity": 8, "unit": "piece", "min_stock": 2, "unit_price": 5500, "location": "Computer Lab", "condition": "good"},
    {"id": "inv-010", "name": "WiFi Router", "category": "it_equipment", "quantity": 4, "unit": "piece", "min_stock": 1, "unit_price": 3500, "location": "Server Room", "condition": "good"},
    # Sports
    {"id": "inv-011", "name": "Cricket Kit (Full)", "category": "sports", "quantity": 4, "unit": "set", "min_stock": 2, "unit_price": 8000, "location": "Sports Room", "condition": "good"},
    {"id": "inv-012", "name": "Football", "category": "sports", "quantity": 10, "unit": "piece", "min_stock": 3, "unit_price": 800, "location": "Sports Room", "condition": "good"},
    {"id": "inv-013", "name": "Volleyball", "category": "sports", "quantity": 6, "unit": "piece", "min_stock": 2, "unit_price": 600, "location": "Sports Room", "condition": "good"},
    {"id": "inv-014", "name": "Badminton Set", "category": "sports", "quantity": 8, "unit": "set", "min_stock": 2, "unit_price": 1200, "location": "Sports Room", "condition": "good"},
    {"id": "inv-015", "name": "Athletics Kit (Relay Batons, Shots)", "category": "sports", "quantity": 2, "unit": "set", "min_stock": 1, "unit_price": 3500, "location": "Sports Room", "condition": "fair"},
    # Stationery
    {"id": "inv-016", "name": "A4 Paper Ream (500 sheets)", "category": "stationery", "quantity": 50, "unit": "ream", "min_stock": 10, "unit_price": 350, "location": "Store Room", "condition": "good"},
    {"id": "inv-017", "name": "Whiteboard Marker (Box of 10)", "category": "stationery", "quantity": 25, "unit": "box", "min_stock": 5, "unit_price": 250, "location": "Store Room", "condition": "good"},
    {"id": "inv-018", "name": "Chalk Box (100 sticks)", "category": "stationery", "quantity": 40, "unit": "box", "min_stock": 10, "unit_price": 80, "location": "Store Room", "condition": "good"},
    {"id": "inv-019", "name": "Register (200 pages)", "category": "stationery", "quantity": 100, "unit": "piece", "min_stock": 20, "unit_price": 60, "location": "Store Room", "condition": "good"},
    {"id": "inv-020", "name": "Duster (Foam)", "category": "stationery", "quantity": 20, "unit": "piece", "min_stock": 5, "unit_price": 40, "location": "Store Room", "condition": "good"},
]

today = date.today()

PURCHASE_ORDERS = [
    {
        "id": "po-001",
        "branch_id": BRANCH_ID,
        "vendor_id": "vendor-002",
        "vendor_name": "TechWorld Solutions",
        "order_number": "PO-2026-001",
        "status": "delivered",
        "order_date": (today - timedelta(days=45)).strftime("%Y-%m-%d"),
        "expected_delivery": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
        "actual_delivery": (today - timedelta(days=28)).strftime("%Y-%m-%d"),
        "items": [
            {"inventory_id": "inv-006", "name": "Desktop Computer", "quantity": 5, "unit_price": 35000, "total": 175000},
            {"inventory_id": "inv-009", "name": "UPS (1KVA)", "quantity": 5, "unit_price": 5500, "total": 27500},
        ],
        "subtotal": 202500,
        "gst_amount": 36450,
        "total_amount": 238950,
        "payment_status": "paid",
        "payment_date": (today - timedelta(days=25)).strftime("%Y-%m-%d"),
        "notes": "Computer lab expansion - 5 new workstations",
        "created_by": "user-admin-001",
        "created_at": (today - timedelta(days=45)).isoformat(),
    },
    {
        "id": "po-002",
        "branch_id": BRANCH_ID,
        "vendor_id": "vendor-003",
        "vendor_name": "Sports India Enterprises",
        "order_number": "PO-2026-002",
        "status": "ordered",
        "order_date": (today - timedelta(days=5)).strftime("%Y-%m-%d"),
        "expected_delivery": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
        "actual_delivery": None,
        "items": [
            {"inventory_id": "inv-011", "name": "Cricket Kit (Full)", "quantity": 2, "unit_price": 8000, "total": 16000},
            {"inventory_id": "inv-012", "name": "Football", "quantity": 5, "unit_price": 800, "total": 4000},
            {"inventory_id": "inv-013", "name": "Volleyball", "quantity": 4, "unit_price": 600, "total": 2400},
        ],
        "subtotal": 22400,
        "gst_amount": 4032,
        "total_amount": 26432,
        "payment_status": "pending",
        "payment_date": None,
        "notes": "Sports Day preparation order",
        "created_by": "user-admin-001",
        "created_at": (today - timedelta(days=5)).isoformat(),
    },
    {
        "id": "po-003",
        "branch_id": BRANCH_ID,
        "vendor_id": "vendor-004",
        "vendor_name": "National Stationery Mart",
        "order_number": "PO-2026-003",
        "status": "draft",
        "order_date": today.strftime("%Y-%m-%d"),
        "expected_delivery": None,
        "actual_delivery": None,
        "items": [
            {"inventory_id": "inv-016", "name": "A4 Paper Ream (500 sheets)", "quantity": 20, "unit_price": 350, "total": 7000},
            {"inventory_id": "inv-017", "name": "Whiteboard Marker (Box of 10)", "quantity": 10, "unit_price": 250, "total": 2500},
            {"inventory_id": "inv-018", "name": "Chalk Box (100 sticks)", "quantity": 15, "unit_price": 80, "total": 1200},
        ],
        "subtotal": 10700,
        "gst_amount": 1926,
        "total_amount": 12626,
        "payment_status": "pending",
        "payment_date": None,
        "notes": "Monthly stationery restock - pending approval",
        "created_by": "user-admin-001",
        "created_at": today.isoformat(),
    },
]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 006: Add inventory & vendors")
        print("=" * 60)

        # 1. Insert vendors
        inserted_v = 0
        for vendor in VENDORS:
            existing = await db.vendors.find_one({"id": vendor["id"]})
            if existing:
                continue
            await db.vendors.insert_one(vendor)
            inserted_v += 1
        print(f"  Inserted {inserted_v} vendors (skipped {len(VENDORS) - inserted_v})")

        # 2. Insert inventory items
        inserted_i = 0
        for item in INVENTORY_ITEMS:
            existing = await db.inventory_items.find_one({"id": item["id"]})
            if existing:
                continue
            doc = {
                **item,
                "branch_id": BRANCH_ID,
                "last_restocked": (today - timedelta(days=30)).strftime("%Y-%m-%d"),
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            }
            await db.inventory_items.insert_one(doc)
            inserted_i += 1
        print(f"  Inserted {inserted_i} inventory items (skipped {len(INVENTORY_ITEMS) - inserted_i})")

        # 3. Insert purchase orders
        inserted_po = 0
        for po in PURCHASE_ORDERS:
            existing = await db.purchase_orders.find_one({"id": po["id"]})
            if existing:
                continue
            await db.purchase_orders.insert_one(po)
            inserted_po += 1
        print(f"  Inserted {inserted_po} purchase orders (skipped {len(PURCHASE_ORDERS) - inserted_po})")

        # 4. Create indexes
        # vendors
        vi = await db.vendors.index_information()
        if "branch_id_1" not in vi:
            await db.vendors.create_index("branch_id")
            print("  Created index on vendors.branch_id")
        if "category_1" not in vi:
            await db.vendors.create_index("category")
            print("  Created index on vendors.category")

        # inventory_items
        ii = await db.inventory_items.index_information()
        if "branch_id_1" not in ii:
            await db.inventory_items.create_index("branch_id")
            print("  Created index on inventory_items.branch_id")
        if "category_1" not in ii:
            await db.inventory_items.create_index("category")
            print("  Created index on inventory_items.category")

        # purchase_orders
        pi = await db.purchase_orders.index_information()
        if "branch_id_1" not in pi:
            await db.purchase_orders.create_index("branch_id")
            print("  Created index on purchase_orders.branch_id")
        if "vendor_id_1" not in pi:
            await db.purchase_orders.create_index("vendor_id")
            print("  Created index on purchase_orders.vendor_id")
        if "status_1" not in pi:
            await db.purchase_orders.create_index("status")
            print("  Created index on purchase_orders.status")

        print("\nMigration 006 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
