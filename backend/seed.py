"""
Seed script for EduFlow demo data — The Aaryans CBSE School
Run: python seed.py
"""
from __future__ import annotations
import asyncio
import os
import random
import uuid
import bcrypt
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")


def gid() -> str:
    return str(uuid.uuid4())


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def dt_minus(days: int, hour: int = 9, minute: int = 0) -> str:
    d = datetime.now() - timedelta(days=days)
    return d.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat()


def today_minus(days: int) -> str:
    return (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")


def today_plus(days: int) -> str:
    return (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")


TODAY = date.today().strftime("%Y-%m-%d")


async def seed() -> None:
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000, retryWrites=True)
    db = client[DB_NAME]

    all_collections = [
        "users", "academic_years", "classes", "subjects", "students", "guardians",
        "staff", "student_attendance", "staff_attendance", "fee_structures",
        "fee_transactions", "fee_heads", "fee_payment_plans",
        "conversations", "messages", "leave_requests", "staff_availability",
        "enquiries", "announcements", "school_settings", "exam_results", "exams",
        "auth_users", "custom_forms", "form_responses", "login_attempts",
        "notifications", "queries", "facility_requests", "tech_requests",
        "maintenance_schedule", "maintenance_vendors",
        "approval_requests", "certificates", "expenses", "expense_budgets",
        "complaints", "incidents", "visitor_log", "assets",
        "transport_routes", "vehicles",
        "salary_structures", "salary_disbursements",
        "houses", "house_points_log", "student_positions", "sports_teams",
        "timetable_slots", "assignments", "branches",
        "audit_log", "tokens",
    ]
    for col in all_collections:
        await db[col].delete_many({})

    print("Cleared existing data...")

    # ── School settings ──────────────────────────────────────────────────────
    await db.school_settings.insert_one({
        "id": "main", "schoolId": SCHOOL_ID,
        "school_name": "The Aaryans",
        "board": "CBSE",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "address": "Sector 12, Jankipuram, Lucknow, UP 226021",
        "established": "2005",
        "principal": "Dr. Anand Sharma",
        "phone": "0522-4567890",
        "email": "info@theararyans.edu.in",
        "website": "www.theararyans.edu.in",
        "logo_url": None,
        "attendance_threshold": 75,
        "ai_context": {
            "grading_system": "CGPA (10 point scale)",
            "fee_structure": "Monthly tuition + quarterly exam fee",
            "class_naming": "Class 9, 10, 11, 12",
            "communication_tone": "Professional Hindi + English",
        },
    })

    # ── Academic year ─────────────────────────────────────────────────────────
    ay_id = "ay-2025-26"
    ay_prev_id = "ay-2024-25"
    await db.academic_years.insert_many([
        {
            "id": ay_prev_id, "schoolId": SCHOOL_ID,
            "name": "2024-25", "start_date": "2024-04-01", "end_date": "2025-03-31",
            "is_current": False,
        },
        {
            "id": ay_id, "schoolId": SCHOOL_ID,
            "name": "2025-26", "start_date": "2025-04-01", "end_date": "2026-03-31",
            "is_current": True,
        },
    ])

    # ── Branches ─────────────────────────────────────────────────────────────
    branch_id = "branch-joya"
    await db.branches.insert_many([
        {
            "id": branch_id, "schoolId": SCHOOL_ID,
            "name": "Joya Branch", "branch_code": "JYA",
            "location": "Joya, Lucknow", "is_active": True,
            "created_by": "user-owner-001", "created_at": dt_minus(365),
        },
        {
            "id": "branch-ald", "schoolId": SCHOOL_ID,
            "name": "Aliganj Branch", "branch_code": "ALG",
            "location": "Aliganj, Lucknow", "is_active": True,
            "created_by": "user-owner-001", "created_at": dt_minus(180),
        },
    ])

    # ── Fixed IDs ─────────────────────────────────────────────────────────────
    owner_id              = "user-owner-001"
    admin_id              = "user-admin-001"
    admin_accountant_id   = "user-admin-002"
    admin_transport_id    = "user-admin-003"
    admin_reception_id    = "user-admin-004"
    admin_it_id           = "user-admin-005"
    admin_maintenance_id  = "user-admin-006"
    admin_management_id   = "user-admin-007"
    teacher_ids           = [f"user-teacher-{i:03}" for i in range(1, 8)]
    student_user_ids      = [f"user-student-{i:03}" for i in range(1, 16)]

    # ── Users ─────────────────────────────────────────────────────────────────
    teacher_names = [
        "Rajesh Kumar", "Sunita Devi", "Manoj Tiwari",
        "Deepa Verma", "Ankit Sharma", "Vikash Singh", "Nisha Verma",
    ]
    users = [
        {"id": owner_id,             "schoolId": SCHOOL_ID, "name": "Aman Sharma",        "role": "owner",   "sub_category": None,            "phone": "9876543210", "email": "aman@theararyans.edu.in",          "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_id,             "schoolId": SCHOOL_ID, "name": "Priya Sharma",        "role": "admin",   "sub_category": "principal",     "phone": "9876543211", "email": "priya@theararyans.edu.in",         "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_accountant_id,  "schoolId": SCHOOL_ID, "name": "Meena Gupta",         "role": "admin",   "sub_category": "accountant",    "phone": "9876543212", "email": "meena@theararyans.edu.in",         "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_transport_id,   "schoolId": SCHOOL_ID, "name": "Suresh Yadav",        "role": "admin",   "sub_category": "transport_head","phone": "9876543213", "email": "suresh@theararyans.edu.in",        "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_reception_id,   "schoolId": SCHOOL_ID, "name": "Kavita Singh",        "role": "admin",   "sub_category": "receptionist",  "phone": "9876543214", "email": "kavita@theararyans.edu.in",        "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_it_id,          "schoolId": SCHOOL_ID, "name": "Rahul Tech",          "role": "admin",   "sub_category": "it_tech",       "phone": "9876543215", "email": "rahul.tech@theararyans.edu.in",    "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_maintenance_id, "schoolId": SCHOOL_ID, "name": "Arvind Maintenance",  "role": "admin",   "sub_category": "maintenance",   "phone": "9876543216", "email": "maintenance@theararyans.edu.in",   "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": admin_management_id,  "schoolId": SCHOOL_ID, "name": "Rohit Management",     "role": "admin",   "sub_category": "management",    "phone": "9876543217", "email": "management@theararyans.edu.in",    "preferred_language": "en", "theme": "light", "is_active": True},
        {"id": "user-student-001",   "schoolId": SCHOOL_ID, "name": "Rahul Singh",         "role": "student", "sub_category": None,            "phone": "9876543220", "preferred_language": "en", "theme": "light", "is_active": True},
    ]
    for i, tid in enumerate(teacher_ids):
        users.append({
            "id": tid, "schoolId": SCHOOL_ID,
            "name": teacher_names[i], "role": "teacher", "sub_category": None,
            "phone": f"98765432{30 + i}", "preferred_language": "en", "theme": "light", "is_active": True,
        })
    await db.users.insert_many(users)

    # ── Auth users ────────────────────────────────────────────────────────────
    staff_auth_docs = [
        {"username": "owner",       "username_lower": "owner",       "password": "owner@123",       "role": "owner",   "sub_category": None,            "user_id": owner_id,            "name": "Aman Sharma",       "initials": "AS", "phone": "9876543210"},
        {"username": "admin",       "username_lower": "admin",       "password": "admin@123",       "role": "admin",   "sub_category": "principal",     "user_id": admin_id,            "name": "Priya Sharma",      "initials": "PS", "phone": "9876543211"},
        {"username": "accountant",  "username_lower": "accountant",  "password": "accountant@123",  "role": "admin",   "sub_category": "accountant",    "user_id": admin_accountant_id, "name": "Meena Gupta",       "initials": "MG", "phone": "9876543212"},
        {"username": "transport",   "username_lower": "transport",   "password": "transport@123",   "role": "admin",   "sub_category": "transport_head","user_id": admin_transport_id,  "name": "Suresh Yadav",      "initials": "SY", "phone": "9876543213"},
        {"username": "reception",   "username_lower": "reception",   "password": "reception@123",   "role": "admin",   "sub_category": "receptionist",  "user_id": admin_reception_id,  "name": "Kavita Singh",      "initials": "KS", "phone": "9876543214"},
        {"username": "ittech",      "username_lower": "ittech",      "password": "ittech@123",      "role": "admin",   "sub_category": "it_tech",       "user_id": admin_it_id,         "name": "Rahul Tech",        "initials": "RT", "phone": "9876543215"},
        {"username": "maintenance", "username_lower": "maintenance", "password": "maintenance@123", "role": "admin",   "sub_category": "maintenance",   "user_id": admin_maintenance_id,"name": "Arvind Maintenance","initials": "AM", "phone": "9876543216"},
        {"username": "management",  "username_lower": "management",  "password": "management@123",  "role": "admin",   "sub_category": "management",    "user_id": admin_management_id, "name": "Rohit Management",  "initials": "RM", "phone": "9876543217"},
    ]
    teacher_auth_meta = [
        (teacher_ids[0], "Rajesh Kumar", "RK", "class_teacher",   "teacher@123"),
        (teacher_ids[1], "Sunita Devi",  "SD", "class_teacher",   "teacher@123"),
        (teacher_ids[2], "Manoj Tiwari", "MT", "subject_teacher", "teacher@123"),
        (teacher_ids[3], "Deepa Verma",  "DV", "coordinator",     "teacher@123"),
        (teacher_ids[4], "Ankit Sharma", "AS", "subject_teacher", "teacher@123"),
        (teacher_ids[5], "Vikash Singh", "VS", "hod",             "hod@123"),
        (teacher_ids[6], "Nisha Verma",  "NV", "kg_incharge",     "kg@123"),
    ]

    auth_docs = []
    for rec in staff_auth_docs:
        pw = rec.pop("password")
        uid = rec.pop("user_id")
        name = rec.pop("name")
        initials = rec.pop("initials")
        phone = rec.pop("phone")
        sub_cat = rec.pop("sub_category")
        auth_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            **rec, "phone": phone,
            "password_hash": hash_pw(pw), "is_active": True,
            "user_info": {"id": uid, "name": name, "role": rec["role"],
                          "sub_category": sub_cat, "initials": initials},
        })
    for uid, name, initials, sub_cat, pw in teacher_auth_meta:
        auth_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            "username": name, "username_lower": name.lower(),
            "password_hash": hash_pw(pw), "is_active": True,
            "role": "teacher", "must_change_password": False,
            "user_info": {"id": uid, "name": name, "role": "teacher",
                          "sub_category": sub_cat, "initials": initials},
        })
    await db.auth_users.insert_many(auth_docs)

    # ── Classes ───────────────────────────────────────────────────────────────
    class_data = [
        ("Class 9",  "A"), ("Class 9",  "B"),
        ("Class 10", "A"), ("Class 10", "B"),
        ("Class 11", "A"), ("Class 12", "A"),
    ]
    class_ids: dict[str, str] = {}
    for i, (name, section) in enumerate(class_data):
        cid = gid()
        class_ids[f"{name}-{section}"] = cid
        await db.classes.insert_one({
            "id": cid, "schoolId": SCHOOL_ID,
            "academic_year_id": ay_id, "branch_id": branch_id,
            "name": name, "section": section,
            "class_teacher_id": teacher_ids[i % len(teacher_ids)],
            "room_number": f"R-{i + 101}",
        })

    # ── Subjects ──────────────────────────────────────────────────────────────
    subjects_list = ["English", "Hindi", "Mathematics", "Science", "Social Science"]
    subject_ids: dict[str, str] = {}
    for class_key, cid in class_ids.items():
        for j, subj_name in enumerate(subjects_list):
            sid = gid()
            subject_ids[f"{class_key}-{subj_name}"] = sid
            await db.subjects.insert_one({
                "id": sid, "schoolId": SCHOOL_ID,
                "class_id": cid, "name": subj_name,
                "teacher_id": teacher_ids[j % len(teacher_ids)],
                "max_marks": 100, "pass_marks": 33,
                "created_at": dt_minus(300),
            })

    # ── Timetable slots ───────────────────────────────────────────────────────
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    periods = ["8:00-8:45", "8:45-9:30", "9:45-10:30", "10:30-11:15", "11:30-12:15"]
    timetable_docs = []
    for class_key, cid in class_ids.items():
        for day in days:
            for p_idx, period in enumerate(periods):
                subj_name = subjects_list[p_idx % len(subjects_list)]
                subj_id = subject_ids.get(f"{class_key}-{subj_name}", "")
                t_id = teacher_ids[p_idx % len(teacher_ids)]
                timetable_docs.append({
                    "id": gid(), "schoolId": SCHOOL_ID,
                    "class_id": cid, "teacher_id": t_id, "subject_id": subj_id,
                    "day": day, "period": period, "room": f"R-{101 + list(class_ids.keys()).index(class_key)}",
                    "academic_year_id": ay_id,
                })
    await db.timetable_slots.insert_many(timetable_docs)

    # ── Staff ─────────────────────────────────────────────────────────────────
    c9a  = class_ids["Class 9-A"]
    c9b  = class_ids["Class 9-B"]
    c10a = class_ids["Class 10-A"]
    c10b = class_ids["Class 10-B"]

    staff_records = [
        {"id": "staff-001", "user_id": owner_id,            "name": "Aman Sharma",       "staff_type": "principal",  "sub_category": "principal",     "employee_id": "EMP001", "designation": "School Owner",      "department": "Management",    "salary": 75000, "branch_id": branch_id},
        {"id": "staff-002", "user_id": admin_id,            "name": "Priya Sharma",       "staff_type": "admin",      "sub_category": "principal",     "employee_id": "EMP002", "designation": "Principal",         "department": "Administration","salary": 45000, "branch_id": branch_id},
        {"id": "staff-009", "user_id": admin_accountant_id, "name": "Meena Gupta",        "staff_type": "admin",      "sub_category": "accountant",    "employee_id": "EMP009", "designation": "Senior Accountant", "department": "Finance",       "salary": 32000, "branch_id": branch_id},
        {"id": "staff-010", "user_id": admin_transport_id,  "name": "Suresh Yadav",       "staff_type": "admin",      "sub_category": "transport_head","employee_id": "EMP010", "designation": "Transport Head",    "department": "Transport",     "salary": 30000, "branch_id": branch_id},
        {"id": "staff-011", "user_id": admin_reception_id,  "name": "Kavita Singh",       "staff_type": "admin",      "sub_category": "receptionist",  "employee_id": "EMP011", "designation": "Receptionist",      "department": "Administration","salary": 22000, "branch_id": branch_id},
        {"id": "staff-014", "user_id": admin_it_id,         "name": "Rahul Tech",         "staff_type": "admin",      "sub_category": "it_tech",       "employee_id": "EMP014", "designation": "IT & Tech Officer", "department": "IT",            "salary": 28000, "branch_id": branch_id},
        {"id": "staff-015", "user_id": admin_maintenance_id,"name": "Arvind Maintenance",  "staff_type": "admin",      "sub_category": "maintenance",   "employee_id": "EMP015", "designation": "Maintenance Head",  "department": "Facilities",    "salary": 24000, "branch_id": branch_id},
        {"id": "staff-017", "user_id": admin_management_id, "name": "Rohit Management",     "staff_type": "admin",      "sub_category": "management",    "employee_id": "EMP017", "designation": "Management Officer","department": "Management",    "salary": 40000, "branch_id": branch_id},
        {"id": "staff-003", "user_id": teacher_ids[0],      "name": "Rajesh Kumar",        "staff_type": "teacher",    "sub_category": "class_teacher", "employee_id": "EMP003", "designation": "Class Teacher",     "department": "Mathematics",   "salary": 34000, "subject": "Mathematics", "class_teacher_of": c9a,  "branch_id": branch_id},
        {"id": "staff-004", "user_id": teacher_ids[1],      "name": "Sunita Devi",         "staff_type": "teacher",    "sub_category": "class_teacher", "employee_id": "EMP004", "designation": "Class Teacher",     "department": "English",       "salary": 32000, "subject": "English",     "class_teacher_of": c9b,  "branch_id": branch_id},
        {"id": "staff-005", "user_id": teacher_ids[2],      "name": "Manoj Tiwari",        "staff_type": "teacher",    "sub_category": "subject_teacher","employee_id": "EMP005", "designation": "Science Teacher",   "department": "Science",       "salary": 30000, "subject": "Science",     "assigned_class_ids": [c9a, c10a], "branch_id": branch_id},
        {"id": "staff-006", "user_id": teacher_ids[3],      "name": "Deepa Verma",         "staff_type": "teacher",    "sub_category": "coordinator",   "employee_id": "EMP006", "designation": "Academic Coordinator","department": "Hindi",       "salary": 30000, "subject": "Hindi",       "coordinator_range": "9-12", "branch_id": branch_id},
        {"id": "staff-007", "user_id": teacher_ids[4],      "name": "Ankit Sharma",        "staff_type": "teacher",    "sub_category": "subject_teacher","employee_id": "EMP007", "designation": "SST Teacher",       "department": "Social Science","salary": 28000, "subject": "Social Science","assigned_class_ids": [c9b, c10b], "branch_id": branch_id},
        {"id": "staff-012", "user_id": teacher_ids[5],      "name": "Vikash Singh",        "staff_type": "teacher",    "sub_category": "hod",           "employee_id": "EMP012", "designation": "HOD Mathematics",   "department": "Mathematics",   "salary": 38000, "subject": "Mathematics", "branch_id": branch_id},
        {"id": "staff-013", "user_id": teacher_ids[6],      "name": "Nisha Verma",         "staff_type": "teacher",    "sub_category": "kg_incharge",   "employee_id": "EMP013", "designation": "KG In-charge",      "department": "Primary",       "salary": 26000, "subject": "General",     "branch_id": branch_id},
        {"id": "staff-008", "user_id": gid(),               "name": "Ramesh Yadav",        "staff_type": "peon",       "sub_category": "support_staff", "employee_id": "EMP008", "designation": "Office Boy",        "department": "Support",       "salary": 18000, "branch_id": branch_id},
        {"id": "staff-016", "user_id": gid(),               "name": "Geeta Kumari",        "staff_type": "peon",       "sub_category": "support_staff", "employee_id": "EMP016", "designation": "Ayah",              "department": "Support",       "salary": 16000, "branch_id": branch_id},
    ]
    for rec in staff_records:
        await db.staff.insert_one({
            **rec, "schoolId": SCHOOL_ID, "is_active": True,
            "casual_leave_balance": 12, "medical_leave_balance": 10, "earned_leave_balance": 15,
            "join_date": "2020-06-01", "phone": f"987654{3200 + int(rec['employee_id'][3:])  }",
            "email": f"{rec['name'].lower().replace(' ', '.')}@theararyans.edu.in",
            "address": "Lucknow, UP",
            "created_at": dt_minus(300),
        })

    staff_id_list = [r["id"] for r in staff_records]

    # ── Students ─────────────────────────────────────────────────────────────
    student_names = [
        "Rahul Singh", "Sneha Kumari", "Amit Verma", "Pooja Yadav", "Vikram Raj",
        "Priya Tiwari", "Rohit Gupta", "Kavya Sharma", "Arjun Mishra", "Neha Pandey",
        "Sohail Khan", "Ananya Das", "Varun Patel", "Riya Joshi", "Karan Mehta",
        "Divya Singh", "Mohit Chauhan", "Swati Agarwal", "Nikhil Rai", "Tanvi Roy",
        "Aditya Rao", "Simran Kaur", "Harsh Tiwari", "Meena Devi", "Sachin Yadav",
    ]
    blood_groups = ["A+", "B+", "O+", "AB+", "A-", "B-"]
    student_ids: list[tuple[str, str, str, str, str | None]] = []
    idx = 0
    student_password_hash = hash_pw("student@123")

    for class_key, cid in class_ids.items():
        count = 10 if "A" in class_key else 6
        for j in range(count):
            sid = gid()
            uid = student_user_ids[idx % len(student_user_ids)] if idx < len(student_user_ids) else None
            sname = student_names[idx % len(student_names)]
            adm = f"ADM2025{(idx + 1):04d}"
            student_ids.append((sid, cid, sname, adm, uid))
            await db.students.insert_one({
                "id": sid, "schoolId": SCHOOL_ID,
                "class_id": cid, "academic_year_id": ay_id, "branch_id": branch_id,
                "user_id": "user-student-001" if idx == 0 else uid,
                "name": sname, "admission_number": adm,
                "roll_number": str(j + 1),
                "dob": f"200{7 + (idx % 4)}-{(idx % 9) + 1:02d}-{15 + (idx % 10):02d}",
                "gender": "male" if idx % 3 != 2 else "female",
                "blood_group": blood_groups[idx % len(blood_groups)],
                "status": "active", "is_active": True,
                "admission_date": "2025-04-01",
                "address": f"{10 + idx} Sector Road, Lucknow",
                "transport_opted": idx % 4 == 0,
                "route_id": "route-001" if idx % 4 == 0 else None,
                "house": ["Atulya", "Agrim", "Agamya", "Aprajit"][idx % 4],
                "created_at": dt_minus(300),
                "updated_at": dt_minus(1),
            })
            await db.guardians.insert_one({
                "id": gid(), "schoolId": SCHOOL_ID,
                "student_id": sid,
                "name": f"{sname.split()[0]}'s Father",
                "relation": "Father",
                "phone": f"98765{(10000 + idx):05d}",
                "whatsapp_phone": f"98765{(10000 + idx):05d}",
                "email": f"parent{idx + 1}@gmail.com",
                "occupation": "Business",
                "is_primary": True,
            })
            idx += 1

    print(f"Created {idx} students across {len(class_ids)} classes")

    # Auth for students
    student_auth_docs = []
    for sid, cid, sname, adm, uid in student_ids:
        initials = "".join(w[0] for w in sname.split())[:2].upper()
        student_auth_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            "username": adm, "username_lower": adm.lower(),
            "password_hash": student_password_hash,
            "role": "student", "is_active": True, "must_change_password": False,
            "user_info": {"id": uid or sid, "name": sname, "role": "student", "initials": initials},
        })
    await db.auth_users.insert_many(student_auth_docs)
    await db.auth_users.create_index("username_lower")
    print(f"Created {len(student_auth_docs)} student + {len(teacher_auth_meta)} teacher auth entries")

    # ── Attendance — staff (60 days) ─────────────────────────────────────────
    staff_att_docs = []
    for days_ago in range(60):
        d = today_minus(days_ago)
        if (date.today() - timedelta(days=days_ago)).weekday() >= 5:
            continue
        for rec in staff_records:
            sid2 = rec["id"]
            random.seed(days_ago * 100 + hash(sid2) % 100)
            r = random.random()
            if sid2 == "staff-004" and days_ago in [2, 4, 6, 8, 12, 15]:
                status = "absent"
            elif sid2 == "staff-005" and days_ago in [1, 3, 5, 7, 10]:
                status = "late"
            elif r < 0.04:
                status = "absent"
            elif r < 0.09:
                status = "late"
            else:
                status = "present"
            staff_att_docs.append({
                "id": gid(), "schoolId": SCHOOL_ID,
                "staff_id": sid2, "date": d, "status": status,
                "check_in": "08:30" if status != "absent" else None,
                "check_out": "16:30" if status == "present" else None,
                "marked_by": admin_id,
            })
    if staff_att_docs:
        await db.staff_attendance.insert_many(staff_att_docs)

    # ── Attendance — students (60 days) ──────────────────────────────────────
    student_att_docs = []
    for days_ago in range(60):
        d = today_minus(days_ago)
        if (date.today() - timedelta(days=days_ago)).weekday() >= 5:
            continue
        for sid2, cid, sname, adm, uid in student_ids:
            random.seed(days_ago * 1000 + hash(sid2) % 1000)
            r = random.random()
            status = "present" if r < 0.88 else ("absent" if r < 0.95 else "late")
            student_att_docs.append({
                "id": gid(), "schoolId": SCHOOL_ID,
                "student_id": sid2, "class_id": cid,
                "date": d, "status": status,
                "marked_by": teacher_ids[0],
                "created_at": d + "T09:00:00",
            })
    if student_att_docs:
        await db.student_attendance.insert_many(student_att_docs)

    print("Created attendance records...")

    # ── Fee heads ─────────────────────────────────────────────────────────────
    fee_head_ids = {}
    fee_heads_data = [
        ("tuition",    "Tuition Fee",        2500, "monthly"),
        ("exam",       "Examination Fee",     500,  "quarterly"),
        ("sports",     "Sports Fee",          300,  "annual"),
        ("transport",  "Transport Fee",       800,  "monthly"),
        ("lab",        "Laboratory Fee",      400,  "quarterly"),
        ("library",    "Library Fee",         200,  "annual"),
        ("misc",       "Miscellaneous",       150,  "monthly"),
    ]
    for fh_key, fh_name, fh_amt, fh_freq in fee_heads_data:
        fhid = gid()
        fee_head_ids[fh_key] = fhid
        await db.fee_heads.insert_one({
            "id": fhid, "schoolId": SCHOOL_ID,
            "name": fh_name, "amount": fh_amt,
            "frequency": fh_freq, "is_optional": fh_key in ("transport", "lab"),
            "academic_year_id": ay_id,
            "created_at": dt_minus(300),
        })

    # ── Fee structures ────────────────────────────────────────────────────────
    for class_key, cid in class_ids.items():
        class_name = class_key.split("-")[0]
        for fh_key, fh_name, fh_amt, fh_freq in fee_heads_data[:3]:
            await db.fee_structures.insert_one({
                "id": gid(), "schoolId": SCHOOL_ID,
                "academic_year_id": ay_id, "class_name": class_name,
                "fee_type": fh_key, "fee_head_id": fee_head_ids[fh_key],
                "amount": fh_amt, "frequency": fh_freq,
                "due_day": 10, "is_optional": False,
            })

    # ── Fee transactions (4 months, all students) ─────────────────────────────
    fee_txn_docs = []
    months_back = [90, 60, 30, 5]
    for i, (sid2, cid, sname, adm, uid) in enumerate(student_ids):
        for m_idx, days_back in enumerate(months_back):
            random.seed(i * 10 + m_idx)
            r = random.random()
            status = ("paid" if m_idx < 2 and r > 0.1
                      else "overdue" if m_idx < 2 and r <= 0.1
                      else "paid" if m_idx == 2 and r > 0.3
                      else "pending" if m_idx == 3 and r > 0.35
                      else "overdue")
            due_date = today_minus(days_back)
            fee_txn_docs.append({
                "id": gid(), "schoolId": SCHOOL_ID,
                "student_id": sid2, "fee_type": "tuition",
                "fee_head_id": fee_head_ids["tuition"],
                "amount": 2500,
                "due_date": due_date,
                "paid_date": today_minus(random.randint(1, 10)) if status == "paid" else None,
                "status": status,
                "payment_mode": random.choice(["upi", "cash", "bank_transfer"]) if status == "paid" else None,
                "receipt_number": f"RCP{gid()[:8].upper()}" if status == "paid" else None,
                "collected_by": admin_accountant_id if status == "paid" else None,
                "notes": "",
                "created_at": dt_minus(days_back),
            })
    await db.fee_transactions.insert_many(fee_txn_docs)
    print("Created fee transactions...")

    # ── Leave requests ────────────────────────────────────────────────────────
    leave_data = [
        ("staff-008", "casual",  today_plus(1),   today_plus(3),   "Family wedding",       "pending"),
        ("staff-002", "medical", today_plus(2),   today_plus(4),   "Doctor appointment",   "pending"),
        ("staff-003", "earned",  today_minus(10), today_minus(7),  "Annual vacation",      "approved"),
        ("staff-004", "casual",  today_minus(5),  today_minus(4),  "Personal work",        "approved"),
        ("staff-005", "medical", today_minus(20), today_minus(18), "Illness",              "approved"),
        ("staff-006", "earned",  today_plus(7),   today_plus(12),  "Family function",      "pending"),
        ("staff-007", "casual",  today_minus(3),  today_minus(3),  "Child sick",           "rejected"),
        ("staff-012", "casual",  today_plus(3),   today_plus(5),   "Personal commitment",  "pending"),
    ]
    for staff_id2, ltype, start, end, reason, status in leave_data:
        await db.leave_requests.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "staff_id": staff_id2, "leave_type": ltype,
            "start_date": start, "end_date": end,
            "reason": reason, "status": status,
            "applied_at": dt_minus(random.randint(1, 15)),
            "reviewed_by": admin_id if status in ("approved", "rejected") else None,
            "reviewed_at": dt_minus(random.randint(1, 5)) if status in ("approved", "rejected") else None,
        })

    # ── Enquiries ─────────────────────────────────────────────────────────────
    enquiry_data = [
        ("Aryan Verma",  "Suresh Verma",  "9876543299", "Class 6",  "new",                "walk_in",  18),
        ("Priya Nair",   "Mohan Nair",    "9876543298", "Class 9",  "contacted",          "phone",    14),
        ("Rohan Gupta",  "Rakesh Gupta",  "9876543297", "Class 11", "visit_scheduled",    "referral", 10),
        ("Tanvi Saxena", "Pawan Saxena",  "9876543296", "Class 8",  "visited",            "online",    7),
        ("Dev Sharma",   "Anil Sharma",   "9876543295", "Class 10", "documents_submitted","ad",        4),
        ("Riya Patel",   "Sunil Patel",   "9876543294", "Class 7",  "admitted",           "walk_in",   2),
        ("Manish Rao",   "Ramesh Rao",    "9876543293", "Class 9",  "new",                "online",    1),
        ("Sana Sheikh",  "Farhan Sheikh", "9876543292", "Class 11", "contacted",          "phone",     0),
    ]
    for sname2, pname, phone, cls, status, source, days_back in enquiry_data:
        await db.enquiries.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "student_name": sname2, "parent_name": pname, "phone": phone,
            "class_applying": cls, "status": status, "source": source,
            "assigned_to": admin_reception_id,
            "notes": f"Interested in {cls}. Good academic background.",
            "follow_up_date": today_plus(3) if status in ("new", "contacted") else None,
            "created_at": dt_minus(days_back),
        })

    # ── Announcements ─────────────────────────────────────────────────────────
    announcement_data = [
        ("Annual Sports Day",      "Annual Sports Day will be held on 15th April 2026. All students must participate in at least one event.", ["owner", "admin", "teacher", "student"], False, 5),
        ("PTM Schedule",           "Parent Teacher Meeting scheduled for 20th April 2026 from 10 AM to 2 PM. Attendance mandatory.", ["owner", "admin", "teacher"], False, 3),
        ("Mid-Term Exam Notice",   "Mid-term examinations begin 1st May 2026. Detailed timetable to be shared via class teachers.", ["teacher", "student"], False, 2),
        ("Holiday Notice",         "School will remain closed on 14th April (Dr. Ambedkar Jayanti). Classes resume 15th April.", ["owner", "admin", "teacher", "student"], False, 1),
        ("Fee Reminder",           "Last date for May tuition fee payment is 10th May. Late fee of ₹50/day will be charged after due date.", ["admin", "student"], False, 0),
        ("Staff Meeting",          "Mandatory staff meeting on Friday 25th April at 3 PM in the conference room.", ["owner", "admin", "teacher"], False, 0),
        ("Draft: Welcome Letter",  "Draft welcome letter for new admissions 2025-26 batch.", ["owner"], True, 1),
    ]
    for title, content, audience_roles, is_draft, days_back in announcement_data:
        await db.announcements.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "title": title, "content": content,
            "audience_roles": audience_roles, "audience_type": "role_based",
            "channels": ["push", "sms"] if not is_draft else [],
            "is_draft": is_draft,
            "sent_at": dt_minus(days_back) if not is_draft else None,
            "created_by": owner_id,
            "created_at": dt_minus(days_back),
        })

    # ── Exams & results ───────────────────────────────────────────────────────
    exam_ids = {}
    for exam_name, etype, start_offset, end_offset in [
        ("Unit Test 1 2025",    "unit_test",  90, 88),
        ("Mid-Term 2025",       "mid_term",   60, 55),
        ("Unit Test 2 2025",    "unit_test",  30, 28),
        ("Pre-Final 2026",      "pre_final",   5,  0),
    ]:
        eid = gid()
        exam_ids[exam_name] = eid
        await db.exams.insert_one({
            "id": eid, "schoolId": SCHOOL_ID,
            "academic_year_id": ay_id, "branch_id": branch_id,
            "name": exam_name, "exam_type": etype,
            "start_date": today_minus(start_offset),
            "end_date": today_minus(end_offset),
            "is_published": etype != "pre_final",
            "created_by": admin_id,
            "created_at": dt_minus(start_offset + 5),
        })

    # Results for all Class 9-A students in Mid-Term
    mid_term_id = exam_ids["Mid-Term 2025"]
    marks_map = {"English": [78, 82, 65, 71, 88, 75, 90, 68, 77, 83],
                 "Hindi":   [82, 79, 70, 85, 74, 80, 88, 73, 78, 90],
                 "Mathematics": [91, 60, 55, 72, 95, 65, 88, 70, 75, 82],
                 "Science": [85, 73, 68, 80, 78, 82, 76, 69, 84, 87],
                 "Social Science": [80, 75, 70, 84, 79, 77, 83, 71, 76, 88]}
    c9a_students = [(sid2, cid, sname, adm, uid) for sid2, cid, sname, adm, uid in student_ids if cid == c9a]
    for s_idx, (sid2, cid, sname, adm, uid) in enumerate(c9a_students[:10]):
        for subj_name in subjects_list:
            subj_id = subject_ids.get(f"Class 9-A-{subj_name}", "")
            m = marks_map.get(subj_name, [75] * 10)[s_idx % 10]
            grade = "A1" if m >= 90 else "A2" if m >= 80 else "B1" if m >= 70 else "B2" if m >= 60 else "C1"
            await db.exam_results.insert_one({
                "id": gid(), "schoolId": SCHOOL_ID,
                "exam_id": mid_term_id, "student_id": sid2,
                "subject_id": subj_id, "class_id": cid,
                "marks_obtained": m, "max_marks": 100, "pass_marks": 33,
                "grade": grade, "percentage": m,
                "entered_by": teacher_ids[0],
                "created_at": dt_minus(50),
            })

    # ── Assignments ───────────────────────────────────────────────────────────
    assignment_data = [
        ("Class 9-A",  "Mathematics",    "Algebra Practice Set",          teacher_ids[0], 5,  today_plus(3)),
        ("Class 9-A",  "Science",        "Chapter 3 Questions",           teacher_ids[2], 3,  today_plus(5)),
        ("Class 9-B",  "English",        "Essay on Environment",          teacher_ids[1], 7,  today_plus(2)),
        ("Class 10-A", "Mathematics",    "Quadratic Equations Worksheet", teacher_ids[5], 4,  today_plus(4)),
        ("Class 10-A", "Social Science", "Map Work — India Rivers",       teacher_ids[4], 6,  today_plus(6)),
        ("Class 11-A", "Mathematics",    "Differentiation Problems",      teacher_ids[5], 2,  today_plus(7)),
        ("Class 9-A",  "Hindi",          "पत्र लेखन अभ्यास",              teacher_ids[3], 8,  today_minus(1)),
    ]
    for class_key2, subj_name, title, t_id, max_marks, due in assignment_data:
        cid = class_ids.get(class_key2, "")
        sid3 = subject_ids.get(f"{class_key2}-{subj_name}", "")
        await db.assignments.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "class_id": cid, "subject_id": sid3,
            "teacher_id": t_id, "title": title,
            "description": f"Complete {title} and submit by due date.",
            "max_marks": max_marks, "due_date": due,
            "is_published": True,
            "academic_year_id": ay_id,
            "created_at": dt_minus(random.randint(1, 10)),
        })

    # ── Notifications ─────────────────────────────────────────────────────────
    notif_data = [
        (owner_id,           "Fee Collection Update",    "₹1,25,000 collected today across all classes.",              "fee",       False, 0),
        (owner_id,           "Staff Leave Request",      "Ramesh Yadav has requested 3 days casual leave.",            "leave",     False, 1),
        (owner_id,           "New Enquiry",              "New admission enquiry received for Class 9.",                "enquiry",   True,  2),
        (admin_id,           "Attendance Alert",         "Class 10-B attendance below 75% today.",                    "attendance",False, 0),
        (admin_id,           "Leave Approved",           "Manoj Tiwari's medical leave has been approved.",           "leave",     True,  1),
        (admin_accountant_id,"Fee Due Reminder",         "15 students have overdue fees for April.",                  "fee",       False, 0),
        (admin_accountant_id,"Payment Received",         "₹2,500 received from Rahul Singh (ADM20250001).",           "fee",       True,  0),
        (admin_reception_id, "New Walk-in Enquiry",      "Aryan Verma's parents visited for Class 6 admission.",      "enquiry",   False, 0),
        (teacher_ids[0],     "Assignment Due Today",     "Algebra Practice Set is due today — 8/10 submitted.",       "assignment",False, 0),
        (teacher_ids[0],     "Low Attendance",           "3 students in Class 9-A have attendance below 75%.",        "attendance",True,  1),
        (teacher_ids[5],     "Result Entry Pending",     "Pre-Final marks entry pending for Class 10-A Mathematics.", "exam",      False, 0),
        ("user-student-001", "Fee Due",                  "Your April tuition fee of ₹2,500 is due on 10th May.",      "fee",       False, 0),
        ("user-student-001", "Exam Timetable",           "Mid-Term exam timetable has been published.",               "exam",      True,  2),
    ]
    notif_docs = []
    for user_id2, title, body, ntype, read, days_back in notif_data:
        notif_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            "user_id": user_id2, "title": title, "body": body,
            "type": ntype, "read": read,
            "created_at": dt_minus(days_back),
        })
    await db.notifications.insert_many(notif_docs)

    # ── Queries (IT helpdesk) ─────────────────────────────────────────────────
    query_data = [
        (owner_id,          "owner",   "Projector in Conference Room not working",         "hardware", "open",       "high",   3),
        (admin_id,          "admin",   "Cannot access student report PDF export",           "software", "in_progress","medium", 5),
        (teacher_ids[0],    "teacher", "Smartboard in Class 9-A needs calibration",         "hardware", "resolved",   "low",    10),
        (teacher_ids[2],    "teacher", "Email login issue — password reset needed",         "account",  "open",       "high",    1),
        (admin_reception_id,"admin",   "Printer in reception not printing double-sided",    "hardware", "open",       "medium",  2),
        (teacher_ids[3],    "teacher", "Unable to upload assignment PDF via portal",        "software", "in_progress","medium",  4),
    ]
    for uid2, role2, desc, cat, status, priority, days_back in query_data:
        await db.queries.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "title": desc, "description": desc,
            "priority": priority, "status": status, "category": cat,
            "created_by": uid2, "created_by_role": role2,
            "assigned_to": admin_it_id,
            "attachment_url": None, "attachment_type": None,
            "created_at": dt_minus(days_back),
            "updated_at": dt_minus(max(0, days_back - 1)),
        })

    # ── Facility requests ─────────────────────────────────────────────────────
    facility_data = [
        ("Broken window in Class 9-B",       "Class 9-B",        "civil",      "high",   "open",       2),
        ("Water leakage in boys' washroom",  "Ground Floor",     "plumbing",   "urgent", "in_progress", 5),
        ("Fan not working in Class 10-A",    "Class 10-A",       "electrical", "medium", "done",        15),
        ("Whiteboard replacement needed",    "Class 11-A",       "carpentry",  "low",    "open",        1),
        ("Door lock broken — Library",       "Library",          "civil",      "medium", "open",        3),
        ("AC maintenance required",          "Staff Room",       "hvac",       "medium", "accepted",    7),
        ("Painting peeling off — Corridor",  "Main Corridor",    "painting",   "low",    "open",        0),
    ]
    for desc, location, cat, priority, status, days_back in facility_data:
        await db.facility_requests.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID, "type": "facility",
            "description": desc, "location": location,
            "category": cat, "priority": priority, "status": status,
            "photos": [], "notes": [],
            "logged_by": admin_maintenance_id,
            "assigned_to": admin_maintenance_id,
            "due_at": today_plus(3) if status == "open" else None,
            "created_at": dt_minus(days_back),
            "updated_at": dt_minus(max(0, days_back - 1)),
        })

    # ── Tech requests ─────────────────────────────────────────────────────────
    tech_req_data = [
        ("New laptop request for HOD Math",  "Staff Room",    "hardware", "open",       2),
        ("Install Tally on accountant PC",   "Accounts Room", "software", "in_progress",4),
        ("WiFi dead zone in Library",        "Library",       "network",  "open",       1),
        ("Projector bulb replacement",       "Conference",    "hardware", "resolved",  12),
        ("CCTV camera not recording",        "Main Gate",     "hardware", "in_progress",3),
    ]
    for desc, location, cat, status, days_back in tech_req_data:
        await db.tech_requests.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID, "type": "tech",
            "description": desc, "location": location,
            "category": cat, "status": status, "notes": [],
            "created_by": admin_it_id,
            "assigned_to": admin_it_id,
            "created_at": dt_minus(days_back),
            "updated_at": dt_minus(max(0, days_back - 1)),
        })

    # ── Maintenance schedule ───────────────────────────────────────────────────
    maint_sched_data = [
        ("Annual Generator Service",     "Preventive maintenance of DG set",        today_plus(5),  "one_time",   "scheduled", "EXT-001"),
        ("Fire Safety Inspection",       "Annual fire extinguisher check",           today_plus(10), "one_time",   "scheduled", "EXT-002"),
        ("AC Filter Cleaning",           "Monthly AC filter cleaning — all rooms",   today_plus(2),  "monthly",    "scheduled", None),
        ("Pest Control — Full Campus",   "Quarterly pest control treatment",         today_plus(15), "quarterly",  "scheduled", "EXT-003"),
        ("Water Tank Cleaning",          "Biannual overhead tank cleaning",          today_minus(2), "biannual",   "completed", None),
        ("Electrical Safety Audit",      "Annual wiring and panel inspection",       today_minus(10),"one_time",   "completed", "EXT-001"),
    ]
    for title, desc, sched_date, recurrence, status, vendor_ref in maint_sched_data:
        await db.maintenance_schedule.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "title": title, "description": desc,
            "scheduled_date": sched_date, "recurrence": recurrence,
            "status": status,
            "assigned_to": admin_maintenance_id,
            "vendor_id": vendor_ref,
            "notes": [],
            "created_at": dt_minus(30),
        })

    # ── Maintenance vendors ────────────────────────────────────────────────────
    vendor_data = [
        ("EXT-001", "Sharma Electricals",      "electrical",  "Raju Sharma",  "9876500001", 4.2),
        ("EXT-002", "FireSafe Solutions",      "fire_safety", "Mohan Lal",    "9876500002", 4.5),
        ("EXT-003", "GreenShield Pest Ctrl",   "pest_control","Amit Kumar",   "9876500003", 4.0),
        ("EXT-004", "AquaClean Services",      "plumbing",    "Dinesh Yadav", "9876500004", 3.8),
        ("EXT-005", "BuildRight Civil Works",  "civil",       "Rakesh Gupta", "9876500005", 4.3),
    ]
    for vid, name, cat, contact, phone, rating in vendor_data:
        await db.maintenance_vendors.insert_one({
            "id": vid, "schoolId": SCHOOL_ID,
            "name": name, "category": cat,
            "contact_person": contact, "phone": phone,
            "email": f"vendor{vid[-3:]}@example.com",
            "rating": rating, "is_active": True,
            "created_at": dt_minus(180),
        })

    # ── Approval requests ─────────────────────────────────────────────────────
    approval_data = [
        ("Purchase Request: Printer Paper (10 reams)", "admin",   "owner",  "pending",  1),
        ("Budget Approval: Sports Equipment ₹15,000",  "owner",   "owner",  "approved", 5),
        ("Event Permission: Science Exhibition",        "teacher", "admin",  "pending",  2),
        ("Leave Substitution: Sunita Devi 3 days",     "teacher", "admin",  "approved", 8),
        ("Vendor Payment: Sharma Electricals ₹8,500",  "admin",   "owner",  "pending",  0),
    ]
    for title, submitted_role, routing, status, days_back in approval_data:
        await db.approval_requests.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "title": title, "description": title,
            "submitted_by": admin_id if submitted_role == "admin" else owner_id if submitted_role == "owner" else teacher_ids[0],
            "submitted_by_role": submitted_role,
            "routing": routing, "status": status,
            "unread_for": [owner_id] if status == "pending" else [],
            "submitted_at": dt_minus(days_back),
            "reviewed_by": owner_id if status == "approved" else None,
            "reviewed_at": dt_minus(max(0, days_back - 1)) if status == "approved" else None,
        })

    # ── Certificates ──────────────────────────────────────────────────────────
    first_sid = student_ids[0][0]
    second_sid = student_ids[1][0]
    cert_data = [
        (first_sid,  "character",   "approved", f"CERT{gid()[:6].upper()}", 5),
        (first_sid,  "bonafide",    "approved", f"CERT{gid()[:6].upper()}", 10),
        (second_sid, "transfer",    "pending",  None,                        1),
        (student_ids[2][0], "character", "pending", None,                   0),
        (student_ids[3][0], "bonafide",  "approved", f"CERT{gid()[:6].upper()}", 7),
    ]
    for sid2, cert_type, status, serial, days_back in cert_data:
        await db.certificates.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "student_id": sid2, "cert_type": cert_type,
            "status": status, "serial_number": serial,
            "requested_by": admin_id,
            "issued_by": admin_id if status == "approved" else None,
            "issued_at": dt_minus(days_back) if status == "approved" else None,
            "created_at": dt_minus(days_back),
        })

    # ── Expenses ──────────────────────────────────────────────────────────────
    expense_data = [
        ("stationery",    3200,  "Naveen Stationery",       "EMP009",  "approved", 5),
        ("electricity",   12500, "UPPCL",                   "EMP001",  "approved", 10),
        ("maintenance",   8500,  "Sharma Electricals",      "EMP015",  "approved", 7),
        ("transport",     4500,  "Fuel — School Bus",       "EMP010",  "approved", 3),
        ("stationery",    1800,  "Office Depot",            "EMP009",  "pending",  1),
        ("sports",        15000, "Star Sports Equipment",   "EMP001",  "approved", 15),
        ("maintenance",   2200,  "Plumbing Repair — Block B","EMP015", "approved", 2),
        ("miscellaneous", 3500,  "Guest Refreshments — PTM","EMP009",  "approved", 20),
        ("salary_advance",10000, "Salary Advance — Staff",  "EMP001",  "approved", 12),
        ("internet",      2800,  "Airtel Business Plan",    "EMP014",  "approved", 8),
    ]
    for cat, amount, vendor, recorded_by_emp, status, days_back in expense_data:
        approver = owner_id if amount > 5000 else admin_id
        await db.expenses.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "category": cat, "amount": amount, "vendor": vendor,
            "date": today_minus(days_back), "status": status,
            "recorded_by": recorded_by_emp,
            "approved_by": approver if status == "approved" else None,
            "receipt_url": None,
            "notes": f"Payment for {vendor}",
            "created_at": dt_minus(days_back),
        })

    # ── Expense budgets ────────────────────────────────────────────────────────
    budget_data = [
        ("stationery",    15000, 9000),
        ("electricity",   60000, 35000),
        ("maintenance",   40000, 22000),
        ("transport",     30000, 18000),
        ("sports",        25000, 10000),
        ("miscellaneous", 20000, 13500),
        ("salary_advance",50000, 10000),
        ("internet",      15000, 8400),
    ]
    for cat, monthly_limit, spent in budget_data:
        await db.expense_budgets.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "category": cat,
            "monthly_limit": monthly_limit,
            "spent_this_month": spent,
            "remaining_amount": monthly_limit - spent,
            "academic_year_id": ay_id,
            "updated_at": dt_minus(0),
        })

    # ── Complaints ────────────────────────────────────────────────────────────
    complaint_data = [
        (owner_id,          "owner",   "Teacher absence not covered — Class 10-A",      "staff",       "high",   "open",       1),
        (admin_id,          "admin",   "Student bullying incident near canteen",         "discipline",  "urgent", "in_progress",3),
        (teacher_ids[0],    "teacher", "Classroom furniture damaged repeatedly",         "facility",    "medium", "open",       2),
        (admin_reception_id,"admin",   "Parent complaint: rude behaviour by peon",       "staff",       "medium", "resolved",   8),
        (teacher_ids[2],    "teacher", "Students using phones during lunch break",       "discipline",  "low",    "closed",    12),
    ]
    for uid2, role2, cat_val, category, priority, status, days_back in complaint_data:
        await db.complaints.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "submitted_by": uid2, "submitted_by_role": role2,
            "category": category, "description": cat_val,
            "priority": priority, "status": status,
            "on_behalf_of_phone": None,
            "assigned_to": admin_id,
            "created_at": dt_minus(days_back),
            "updated_at": dt_minus(max(0, days_back - 1)),
        })

    # ── Incidents ─────────────────────────────────────────────────────────────
    incident_data = [
        ("Minor injury during PT class",     "A student twisted ankle during PT. First aid given.",   "low",    "closed",    10),
        ("Water pipe burst — Block B",       "Pipe burst in Block B corridor. Plumber called.",       "medium", "resolved",   7),
        ("Bus breakdown — Morning route",    "School bus broke down. Alternate arranged.",            "medium", "resolved",   5),
        ("Power outage — 3 hours",           "UPPCL power cut from 10 AM to 1 PM.",                  "low",    "closed",    20),
        ("Parent altercation at gate",       "Verbal dispute between two parents at main gate.",      "high",   "in_progress",2),
        ("Fire alarm triggered",             "False alarm triggered in lab wing. No fire. Checked.",  "medium", "closed",    15),
    ]
    for title, desc, severity, status, days_back in incident_data:
        await db.incidents.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "title": title, "description": desc,
            "severity": severity, "status": status,
            "logged_by": admin_id,
            "thread": [{"author": admin_id, "message": desc, "timestamp": dt_minus(days_back)}],
            "created_at": dt_minus(days_back),
            "updated_at": dt_minus(max(0, days_back - 1)),
        })

    # ── Visitor log ───────────────────────────────────────────────────────────
    visitor_data = [
        ("Dr. Ramesh Sharma",    "Parent Meeting",           "Kavita Singh",  "08:45", "09:30", 0),
        ("Suresh Verma",         "Admission Enquiry",        "Kavita Singh",  "10:15", "11:00", 0),
        ("Pooja Electrical",     "Vendor — Electrical",      "Arvind Maint",  "11:30", "13:00", 0),
        ("Inspector CBSE",       "Inspection Visit",         "Priya Sharma",  "09:00", "16:00", 1),
        ("Meena Singh (Parent)", "Complaint — Fee Receipt",  "Kavita Singh",  "14:00", "14:30", 1),
        ("Delivery — Amazon",    "Package Delivery",         "Ramesh Yadav",  "12:00", "12:15", 2),
        ("Alumni — Batch 2020",  "Alumni Meet",              "Aman Sharma",   "15:00", None,    0),
    ]
    for vname, purpose, met_with, time_in, time_out, days_back in visitor_data:
        await db.visitor_log.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "visitor_name": vname, "purpose": purpose,
            "met_with": met_with, "phone": "9876500099",
            "time_in": f"{today_minus(days_back)}T{time_in}:00",
            "time_out": f"{today_minus(days_back)}T{time_out}:00" if time_out else None,
            "force_override": False,
            "logged_by": admin_reception_id,
            "created_at": dt_minus(days_back),
        })

    # ── Assets ────────────────────────────────────────────────────────────────
    asset_data = [
        ("Projector — Epson EB-X41",   "electronics", 1,  "Class 9-A",    "working",    "2023-06-01"),
        ("Projector — Epson EB-X41",   "electronics", 1,  "Class 10-A",   "working",    "2023-06-01"),
        ("Smartboard 75\"",            "electronics", 1,  "Conference",   "working",    "2024-01-15"),
        ("Desktop PC — HP i5",         "electronics", 5,  "Computer Lab", "working",    "2022-04-01"),
        ("Printer — Canon LBP6030",    "electronics", 2,  "Office",       "working",    "2021-08-01"),
        ("Office Chairs",              "furniture",   30, "Staff Room",   "working",    "2020-04-01"),
        ("Student Benches (2-seater)", "furniture",   80, "Classrooms",   "working",    "2019-04-01"),
        ("Whiteboards",                "furniture",   6,  "Classrooms",   "working",    "2020-06-01"),
        ("Fire Extinguisher",          "safety",      12, "Campus",       "working",    "2024-01-01"),
        ("CCTV Camera",                "electronics", 8,  "Campus",       "partial",    "2022-09-01"),
        ("Generator — 30KVA",          "equipment",   1,  "Generator Room","working",   "2021-01-01"),
        ("Water Cooler",               "equipment",   3,  "Corridors",    "working",    "2022-03-01"),
    ]
    for name, cat, qty, location, status, purchase_date in asset_data:
        await db.assets.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "name": name, "category": cat, "quantity": qty,
            "location": location, "status": status,
            "purchase_date": purchase_date,
            "last_service_date": today_minus(60),
            "created_at": dt_minus(200),
        })

    # ── Transport routes & vehicles ───────────────────────────────────────────
    route_data = [
        ("route-001", "Jankipuram Route",  ["Jankipuram", "Sector 7", "Viram Khand", "School"], 600, "Ram Singh",  "9876511001"),
        ("route-002", "Gomti Nagar Route", ["Gomti Nagar", "Sector 14", "Viram Khand", "School"],700, "Shyam Lal",  "9876511002"),
        ("route-003", "Alambagh Route",    ["Alambagh", "Charbagh", "Hazratganj", "School"],     650, "Mohan Das",  "9876511003"),
    ]
    for rid, rname, stops, fare, driver, dphone in route_data:
        await db.transport_routes.insert_one({
            "id": rid, "schoolId": SCHOOL_ID,
            "route_name": rname, "stops": stops, "fare": fare,
            "is_active": True,
            "driver_name": driver, "driver_phone": dphone,
            "vehicle_number": f"UP32AB{900 + int(rid[-1])}0",
            "centroid": {"lat": 26.85, "lng": 80.95},
            "created_at": dt_minus(300),
        })

    vehicle_data = [
        ("VEH-001", "UP32AB9001", "Bus",      45, "Ram Singh",  "9876511001", "route-001"),
        ("VEH-002", "UP32AB9002", "Bus",      40, "Shyam Lal",  "9876511002", "route-002"),
        ("VEH-003", "UP32AB9003", "Mini Bus", 25, "Mohan Das",  "9876511003", "route-003"),
        ("VEH-004", "UP32CD1234", "Car",       5, "Govind",     "9876511004", None),
    ]
    for vid, vnum, vtype, capacity, driver, dphone, route_id in vehicle_data:
        await db.vehicles.insert_one({
            "id": vid, "schoolId": SCHOOL_ID,
            "vehicle_number": vnum, "vehicle_type": vtype,
            "capacity": capacity,
            "driver_name": driver, "driver_phone": dphone,
            "route_id": route_id, "is_active": True,
            "insurance_expiry": today_plus(180),
            "fitness_expiry": today_plus(90),
            "last_service_date": today_minus(30),
            "created_at": dt_minus(300),
        })

    # ── Salary structures ─────────────────────────────────────────────────────
    salary_docs = []
    for rec in staff_records:
        base = rec["salary"]
        salary_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            "staff_id": rec["id"],
            "designation": rec.get("designation", rec["staff_type"]),
            "base_salary": base,
            "allowances": {
                "hra": round(base * 0.20),
                "ta": round(base * 0.10),
                "da": round(base * 0.05),
            },
            "deductions": {
                "pf": round(base * 0.12),
                "pt": 200,
            },
            "effective_from": "2025-04-01",
            "created_by": admin_accountant_id,
            "created_at": dt_minus(60),
        })
    await db.salary_structures.insert_many(salary_docs)

    # Disbursements — last 3 months
    months_salary = [
        ("2025-02", today_minus(75)),
        ("2025-03", today_minus(45)),
        ("2025-04", today_minus(15)),
    ]
    disb_docs = []
    for rec in staff_records:
        base = rec["salary"]
        gross = round(base * 1.35)
        deductions = round(base * 0.12) + 200
        net = gross - deductions
        for month_str, disb_date in months_salary:
            disb_docs.append({
                "id": gid(), "schoolId": SCHOOL_ID,
                "staff_id": rec["id"],
                "month": month_str,
                "gross": gross, "deductions": deductions, "net": net,
                "status": "disbursed",
                "disbursed_by": admin_accountant_id,
                "disbursed_at": disb_date,
                "created_at": dt_minus(80),
            })
    await db.salary_disbursements.insert_many(disb_docs)

    # ── Houses (activities) ────────────────────────────────────────────────────
    house_data = [
        ("house-atulya",  "Atulya",  "#E53E3E", 1250),
        ("house-agrim",   "Agrim",   "#3182CE", 1180),
        ("house-agamya",  "Agamya",  "#38A169", 1320),
        ("house-aprajit", "Aprajit", "#D69E2E", 1100),
    ]
    for hid, hname, colour, points in house_data:
        await db.houses.insert_one({
            "id": hid, "schoolId": SCHOOL_ID,
            "name": hname, "colour": colour, "points": points,
            "created_at": dt_minus(300),
        })

    hp_docs = []
    for hid, hname, colour, points in house_data:
        events = [
            ("Annual Sports Day — 100m Race",      50, 20),
            ("Science Quiz Competition",           30, 15),
            ("Art Exhibition",                     20, 10),
            ("Cleanliness Drive",                  15,  5),
        ]
        running = 0
        for event, delta, days_back in events:
            running += delta
            hp_docs.append({
                "id": gid(), "schoolId": SCHOOL_ID,
                "house_id": hid, "house_name": hname,
                "delta": delta, "new_total": running,
                "event": event,
                "awarded_by": admin_id,
                "created_at": dt_minus(days_back),
            })
    await db.house_points_log.insert_many(hp_docs)

    # Student positions (prefects etc.)
    position_data = [
        (student_ids[0][0],  student_ids[0][2],  "Head Boy",           "2025-26"),
        (student_ids[1][0],  student_ids[1][2],  "Head Girl",          "2025-26"),
        (student_ids[2][0],  student_ids[2][2],  "House Captain — Atulya", "2025-26"),
        (student_ids[5][0],  student_ids[5][2],  "House Captain — Agrim",  "2025-26"),
        (student_ids[9][0],  student_ids[9][2],  "Class Monitor 9-A",  "2025-26"),
    ]
    for sid2, sname, position, ay_name in position_data:
        await db.student_positions.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "student_id": sid2, "student_name": sname,
            "position": position, "is_active": True,
            "academic_year": ay_name,
            "assigned_by": admin_id,
            "created_at": dt_minus(30),
        })

    # Sports teams
    sports_data = [
        ("Cricket Team 2025",    "cricket",    student_ids[0][0], [s[0] for s in student_ids[:11]]),
        ("Football Team 2025",   "football",   student_ids[5][0], [s[0] for s in student_ids[5:16]]),
        ("Badminton Team 2025",  "badminton",  student_ids[9][0], [s[0] for s in student_ids[9:15]]),
        ("Chess Team 2025",      "chess",      student_ids[2][0], [s[0] for s in student_ids[2:10]]),
    ]
    for tname, sport, captain_id, members in sports_data:
        await db.sports_teams.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "name": tname, "sport": sport,
            "captain_student_id": captain_id,
            "members": members, "is_active": True,
            "coach_staff_id": teacher_ids[0],
            "created_by": admin_id,
            "created_at": dt_minus(60),
        })

    # ── Custom forms ──────────────────────────────────────────────────────────
    form_id = gid()
    await db.custom_forms.insert_one({
        "id": form_id, "schoolId": SCHOOL_ID,
        "title": "PTM Feedback Form 2025",
        "fields": [
            {"id": "f1", "type": "rating", "label": "Overall satisfaction with teacher meeting", "required": True},
            {"id": "f2", "type": "textarea", "label": "What went well?", "required": False},
            {"id": "f3", "type": "textarea", "label": "Suggestions for improvement", "required": False},
        ],
        "audience": ["parent", "student"],
        "public_slug": "ptm-feedback-2025",
        "is_active": True,
        "created_by": admin_id,
        "created_at": dt_minus(10),
    })
    form_resp_docs = []
    for i in range(5):
        form_resp_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            "form_id": form_id,
            "submitted_by": student_ids[i][4] or student_ids[i][0],
            "answers": {"f1": random.randint(3, 5), "f2": "Good experience overall.", "f3": "More time per parent."},
            "submitted_at": dt_minus(random.randint(1, 5)),
        })
    await db.form_responses.insert_many(form_resp_docs)

    # ── Conversations (AI chat) ───────────────────────────────────────────────
    conv_data = [
        (owner_id,           "Today's school overview",                    2),
        (owner_id,           "Which staff were absent this week?",         1),
        (owner_id,           "Fee collection summary for April",           0),
        (admin_id,           "Show attendance for Class 10-B",             1),
        (admin_id,           "Pending leave requests",                     0),
        (admin_accountant_id,"Overdue fee list",                           0),
        (teacher_ids[0],     "My class attendance today",                  0),
        (teacher_ids[5],     "Result entry status for mid-term",           1),
        ("user-student-001", "My fee dues and upcoming exams",             0),
    ]
    for uid2, title, days_back in conv_data:
        await db.conversations.insert_one({
            "id": gid(), "schoolId": SCHOOL_ID,
            "user_id": uid2, "title": title,
            "is_pinned": False, "is_starred": False,
            "created_at": dt_minus(days_back),
            "updated_at": dt_minus(days_back),
        })

    print("Seed complete!")
    print()
    print("  Owner:             username=owner          password=owner@123")
    print("  Admin (Principal): username=admin          password=admin@123")
    print("  Admin (Accountant):username=accountant     password=accountant@123")
    print("  Admin (Transport): username=transport      password=transport@123")
    print("  Admin (Reception): username=reception      password=reception@123")
    print("  Admin (IT & Tech): username=ittech         password=ittech@123")
    print("  Admin (Maintenance):username=maintenance   password=maintenance@123")
    print("  Teacher (HOD):     username=Vikash Singh   password=hod@123")
    print("  Teacher (Coord):   username=Deepa Verma    password=teacher@123")
    print("  Teacher (Class):   username=Rajesh Kumar   password=teacher@123")
    print("  Teacher (Subject): username=Manoj Tiwari   password=teacher@123")
    print("  Teacher (KG):      username=Nisha Verma    password=kg@123")
    print("  Student:           username=ADM20250001    password=student@123")
    print()
    print(f"  Classes: {len(class_ids)}, Students: {idx}, Staff: {len(staff_records)}")
    print(f"  Exams: {len(exam_ids)}, Assignments: {len(assignment_data)}")
    print(f"  Expenses: {len(expense_data)}, Salary disbursements: {len(disb_docs)}")
    print(f"  Transport routes: {len(route_data)}, Vehicles: {len(vehicle_data)}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
