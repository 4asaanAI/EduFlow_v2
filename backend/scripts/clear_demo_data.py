"""
Clear seeded demo data from EduFlow.
SAFE — never touches: users, auth_users, students, staff, classes, subjects,
period_links, guardians, school_settings, branches, academic_years.
"""
from __future__ import annotations
import asyncio
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")

SECTIONS = {
    "Fees": ["fee_transactions", "fee_structures", "fee_heads", "fee_payment_plans", "fee_discounts", "student_fee_profiles"],
    "Announcements": ["announcements"],
    "Chat / Conversations": ["conversations", "messages"],
    "Notifications": ["notifications"],
    "Attendance": ["student_attendance", "staff_attendance"],
    "Exams & Assignments": ["exams", "exam_results", "assignments"],
    "Timetable": ["timetable_slots"],
    "Leave Requests": ["leave_requests", "staff_availability"],
    "Staff Salary": ["salary_structures", "salary_disbursements"],
    "Financial Reports & Expenses": ["expenses", "expense_budgets"],
    "School Activities": ["houses", "house_points_log", "student_positions", "sports_teams"],
    "Vendor Log / Maintenance Schedule": ["maintenance_vendors", "maintenance_schedule"],
    "Faculty & Tech Requests": ["tech_requests"],
    "AI Usage (reset limits)": ["token_usage"],
    "Query & Support": ["queries"],
    "Certificates": ["certificates"],
    "Enquiry Register": ["enquiries"],
    "Transport": ["transport_routes", "vehicles"],
    "Incidents & Reports": ["incidents", "complaints"],
    "Facility Requests": ["facility_requests"],
    "Assets & Visitors": ["assets", "visitor_log"],
    "Forms": ["custom_forms", "form_responses"],
    "Misc": ["login_attempts", "approval_requests", "audit_log"],
}


async def clear() -> None:
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    total_deleted = 0
    for section, collections in SECTIONS.items():
        section_count = 0
        for col in collections:
            result = await db[col].delete_many({"schoolId": SCHOOL_ID})
            section_count += result.deleted_count
            print(f"  [{col}] deleted {result.deleted_count} docs")
        print(f"✓ {section}: {section_count} docs removed\n")
        total_deleted += section_count

    print(f"Done. Total documents removed: {total_deleted}")
    client.close()


if __name__ == "__main__":
    asyncio.run(clear())
