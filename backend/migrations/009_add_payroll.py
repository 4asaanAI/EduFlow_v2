"""
Migration 009: Add salary_structures, salary_disbursements, and expenses collections.
Run: python backend/migrations/009_add_payroll.py
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

# Salary breakup percentages (of gross)
# Basic: 40%, HRA: 20%, DA: 10%, Conveyance: 5%, Medical: 5%, Special: 20%
# Deductions: PF: 12% of basic, PT: Rs 200 (if salary > 15000)

def compute_salary_structure(staff_id, name, designation, gross_salary):
    basic = round(gross_salary * 0.40)
    hra = round(gross_salary * 0.20)
    da = round(gross_salary * 0.10)
    conveyance = round(gross_salary * 0.05)
    medical_allowance = round(gross_salary * 0.05)
    special_allowance = gross_salary - basic - hra - da - conveyance - medical_allowance

    pf_deduction = round(basic * 0.12)
    pt_deduction = 200 if gross_salary > 15000 else 0
    total_deductions = pf_deduction + pt_deduction
    net_salary = gross_salary - total_deductions

    return {
        "id": f"sal-{staff_id}",
        "branch_id": BRANCH_ID,
        "staff_id": staff_id,
        "staff_name": name,
        "designation": designation,
        "academic_year": "2025-26",
        "gross_salary": gross_salary,
        "earnings": {
            "basic": basic,
            "hra": hra,
            "da": da,
            "conveyance_allowance": conveyance,
            "medical_allowance": medical_allowance,
            "special_allowance": special_allowance,
        },
        "deductions": {
            "pf": pf_deduction,
            "professional_tax": pt_deduction,
            "tds": 0,
            "other": 0,
        },
        "total_earnings": gross_salary,
        "total_deductions": total_deductions,
        "net_salary": net_salary,
        "bank_account": None,
        "pan_number": None,
        "is_active": True,
        "effective_from": "2025-04-01",
        "created_at": datetime.now().isoformat(),
    }


EXPENSES = [
    {
        "id": "exp-001",
        "branch_id": BRANCH_ID,
        "category": "utilities",
        "sub_category": "electricity",
        "description": "Electricity bill - March 2026",
        "amount": 18500,
        "date": "2026-03-10",
        "vendor_name": "UPPCL",
        "payment_mode": "online",
        "receipt_number": "UPPCL-2026-03-JOY-4521",
        "approved_by": "user-owner-001",
        "status": "paid",
    },
    {
        "id": "exp-002",
        "branch_id": BRANCH_ID,
        "category": "utilities",
        "sub_category": "water",
        "description": "Water tanker charges - March 2026 (4 tankers)",
        "amount": 4000,
        "date": "2026-03-15",
        "vendor_name": "Local Municipal Supply",
        "payment_mode": "cash",
        "receipt_number": "WTR-2026-03-001",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
    {
        "id": "exp-003",
        "branch_id": BRANCH_ID,
        "category": "stationery",
        "sub_category": "office_supplies",
        "description": "Printer cartridges, A4 paper, files for admin office",
        "amount": 3200,
        "date": "2026-03-05",
        "vendor_name": "National Stationery Mart",
        "payment_mode": "upi",
        "receipt_number": "NSM-2026-1234",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
    {
        "id": "exp-004",
        "branch_id": BRANCH_ID,
        "category": "maintenance",
        "sub_category": "building",
        "description": "Classroom whitewashing and minor repairs (Room 3, 4, 7)",
        "amount": 25000,
        "date": "2026-03-02",
        "vendor_name": "Ramesh Painter & Sons",
        "payment_mode": "cash",
        "receipt_number": "MNT-2026-03-001",
        "approved_by": "user-owner-001",
        "status": "paid",
    },
    {
        "id": "exp-005",
        "branch_id": BRANCH_ID,
        "category": "maintenance",
        "sub_category": "plumbing",
        "description": "Toilet block plumbing repair - Boys' washroom",
        "amount": 3500,
        "date": "2026-03-12",
        "vendor_name": "Local Plumber",
        "payment_mode": "cash",
        "receipt_number": "MNT-2026-03-002",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
    {
        "id": "exp-006",
        "branch_id": BRANCH_ID,
        "category": "transport",
        "sub_category": "fuel",
        "description": "Diesel for school buses - March 2026",
        "amount": 22000,
        "date": "2026-03-20",
        "vendor_name": "Indian Oil Petrol Pump, Joya",
        "payment_mode": "card",
        "receipt_number": "FUEL-2026-03-001",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
    {
        "id": "exp-007",
        "branch_id": BRANCH_ID,
        "category": "transport",
        "sub_category": "vehicle_maintenance",
        "description": "Bus servicing and oil change (Bus UP-31-AT-1234)",
        "amount": 8500,
        "date": "2026-03-08",
        "vendor_name": "Sharma Auto Garage",
        "payment_mode": "cash",
        "receipt_number": "VEH-2026-03-001",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
    {
        "id": "exp-008",
        "branch_id": BRANCH_ID,
        "category": "events",
        "sub_category": "sports_day",
        "description": "Sports Day prizes, medals, certificates and refreshments",
        "amount": 15000,
        "date": "2026-02-14",
        "vendor_name": "Multiple vendors",
        "payment_mode": "cash",
        "receipt_number": "EVT-2026-02-001",
        "approved_by": "user-owner-001",
        "status": "paid",
    },
    {
        "id": "exp-009",
        "branch_id": BRANCH_ID,
        "category": "utilities",
        "sub_category": "internet",
        "description": "Broadband internet bill - March 2026 (50 Mbps plan)",
        "amount": 1500,
        "date": "2026-03-01",
        "vendor_name": "Airtel Broadband",
        "payment_mode": "online",
        "receipt_number": "NET-2026-03-001",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
    {
        "id": "exp-010",
        "branch_id": BRANCH_ID,
        "category": "miscellaneous",
        "sub_category": "cleaning",
        "description": "Cleaning supplies - phenyl, brooms, dustbins, hand wash",
        "amount": 2800,
        "date": "2026-03-18",
        "vendor_name": "Local Market",
        "payment_mode": "cash",
        "receipt_number": "CLN-2026-03-001",
        "approved_by": "user-admin-001",
        "status": "paid",
    },
]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 009: Add payroll & expenses")
        print("=" * 60)

        # 1. Build salary structures from existing staff
        existing_structures = await db.salary_structures.count_documents({})
        if existing_structures > 0:
            print(f"  salary_structures already has {existing_structures} records, skipping.")
        else:
            staff_cursor = db.staff.find({}, {"id": 1, "name": 1, "staff_type": 1, "salary": 1})
            structures = []
            async for staff in staff_cursor:
                structure = compute_salary_structure(
                    staff_id=staff["id"],
                    name=staff["name"],
                    designation=staff.get("staff_type", "staff"),
                    gross_salary=staff.get("salary", 20000),
                )
                structures.append(structure)

            if structures:
                await db.salary_structures.insert_many(structures)
            print(f"  Created {len(structures)} salary structures")

        # 2. Create March 2026 salary disbursements
        existing_disbursements = await db.salary_disbursements.count_documents(
            {"month": "2026-03"}
        )
        if existing_disbursements > 0:
            print(f"  March 2026 disbursements already exist ({existing_disbursements}), skipping.")
        else:
            sal_cursor = db.salary_structures.find({"is_active": True})
            disbursements = []
            idx = 0
            async for sal in sal_cursor:
                idx += 1
                # Compute working days (assume 26 working days in March, minus leaves)
                leaves_taken = 0
                staff_id = sal["staff_id"]
                # Check leave data from staff_attendance for March
                absent_count = await db.staff_attendance.count_documents({
                    "staff_id": staff_id,
                    "date": {"$gte": "2026-03-01", "$lte": "2026-03-31"},
                    "status": "absent",
                })
                leaves_taken = absent_count

                working_days = 26
                days_present = working_days - leaves_taken
                # Pro-rate if absent without leave (simple: deduct per day for absences > 2)
                loss_of_pay_days = max(0, leaves_taken - 2)
                per_day = round(sal["gross_salary"] / 30)
                lop_deduction = loss_of_pay_days * per_day

                net_payable = sal["net_salary"] - lop_deduction

                disbursements.append({
                    "id": f"disb-2026-03-{idx:03d}",
                    "branch_id": BRANCH_ID,
                    "staff_id": staff_id,
                    "staff_name": sal["staff_name"],
                    "salary_structure_id": sal["id"],
                    "month": "2026-03",
                    "year": 2026,
                    "working_days": working_days,
                    "days_present": days_present,
                    "leaves_taken": leaves_taken,
                    "loss_of_pay_days": loss_of_pay_days,
                    "gross_salary": sal["gross_salary"],
                    "earnings": sal["earnings"],
                    "deductions": {
                        **sal["deductions"],
                        "loss_of_pay": lop_deduction,
                    },
                    "total_deductions": sal["total_deductions"] + lop_deduction,
                    "net_payable": net_payable,
                    "payment_mode": "bank_transfer",
                    "payment_status": "paid",
                    "payment_date": "2026-03-31",
                    "created_at": datetime.now().isoformat(),
                })

            if disbursements:
                await db.salary_disbursements.insert_many(disbursements)
            print(f"  Created {len(disbursements)} salary disbursements for March 2026")

        # 3. Insert expense entries
        inserted_exp = 0
        for expense in EXPENSES:
            existing = await db.expenses.find_one({"id": expense["id"]})
            if existing:
                continue
            doc = {
                **expense,
                "academic_year": "2025-26",
                "created_by": expense["approved_by"],
                "created_at": datetime.now().isoformat(),
            }
            await db.expenses.insert_one(doc)
            inserted_exp += 1
        print(f"  Inserted {inserted_exp} expense entries (skipped {len(EXPENSES) - inserted_exp})")

        total_expenses = sum(e["amount"] for e in EXPENSES)
        print(f"  Total expenses recorded: Rs {total_expenses:,}")

        # 4. Create indexes
        ss_indexes = await db.salary_structures.index_information()
        if "staff_id_1" not in ss_indexes:
            await db.salary_structures.create_index("staff_id")
        if "branch_id_1" not in ss_indexes:
            await db.salary_structures.create_index("branch_id")
        print("  Ensured indexes on salary_structures")

        sd_indexes = await db.salary_disbursements.index_information()
        if "staff_id_1" not in sd_indexes:
            await db.salary_disbursements.create_index("staff_id")
        if "month_1" not in sd_indexes:
            await db.salary_disbursements.create_index("month")
        if "branch_id_1" not in sd_indexes:
            await db.salary_disbursements.create_index("branch_id")
        print("  Ensured indexes on salary_disbursements")

        exp_indexes = await db.expenses.index_information()
        if "branch_id_1" not in exp_indexes:
            await db.expenses.create_index("branch_id")
        if "category_1" not in exp_indexes:
            await db.expenses.create_index("category")
        if "date_1" not in exp_indexes:
            await db.expenses.create_index("date")
        print("  Ensured indexes on expenses")

        print("\nMigration 009 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
