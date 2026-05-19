"""
Seed script for EduFlow demo data — The Aaryans CBSE School
Run: python seed.py
"""
import asyncio
import os
import uuid
import bcrypt
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def gid():
    return str(uuid.uuid4())


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def today_minus(days):
    return (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")


def today_plus(days):
    return (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")


TODAY = date.today().strftime("%Y-%m-%d")

# ─── Demo credentials (displayed on login screen) ───────────────────────────
DEMO_CREDENTIALS = {
    "owner": {"username": "owner", "password": "owner@123"},
    "admin": {"username": "admin", "password": "admin@123"},
    "maintenance": {"username": "maintenance", "password": "maintenance@123"},
    "teacher": {"username": "Rajesh Kumar", "password": "teacher@123"},
    "student": {"username": "ADM20250001", "password": "student@123"},
}


async def seed():
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000, retryWrites=True)
    db = client[DB_NAME]

    # Clear existing data
    for col in ["users", "academic_years", "classes", "subjects", "students", "guardians",
                "staff", "student_attendance", "staff_attendance", "fee_structures",
                "fee_transactions", "conversations", "messages", "leave_requests",
                "enquiries", "announcements", "school_settings", "exam_results", "exams",
                "auth_users", "custom_forms", "form_responses", "login_attempts"]:
        await db[col].delete_many({})

    print("Cleared existing data...")

    # School settings
    await db.school_settings.insert_one({
        "id": "main",
        "school_name": "The Aaryans",
        "board": "CBSE",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "established": "2005",
        "principal": "Dr. Anand Sharma",
        "phone": "0522-XXXXXXX",
        "email": "info@theararyans.edu.in",
        "ai_context": {
            "grading_system": "CGPA (10 point scale)",
            "fee_structure": "Monthly tuition + quarterly exam fee",
            "class_naming": "Class 9, 10, 11, 12",
            "communication_tone": "Professional Hindi + English",
        }
    })

    # Academic year
    ay_id = gid()
    await db.academic_years.insert_one({
        "id": ay_id,
        "name": "2025-26",
        "start_date": "2025-04-01",
        "end_date": "2026-03-31",
        "is_current": True,
    })

    # Users
    owner_id = "user-owner-001"
    admin_id = "user-admin-001"
    admin_accountant_id = "user-admin-002"
    admin_transport_id = "user-admin-003"
    admin_reception_id = "user-admin-004"
    admin_it_id = "user-admin-005"
    admin_maintenance_id = "user-admin-006"
    teacher_ids = [f"user-teacher-{i:03}" for i in range(1, 8)]  # 7 teachers
    student_user_ids = [f"user-student-{i:03}" for i in range(1, 16)]

    users = [
        {"id": owner_id, "name": "Aman Sharma", "role": "owner", "phone": "9876543210", "email": "aman@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_id, "name": "Priya Sharma", "role": "admin", "phone": "9876543211", "email": "priya@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_accountant_id, "name": "Meena Gupta", "role": "admin", "phone": "9876543212", "email": "meena@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_transport_id, "name": "Suresh Yadav", "role": "admin", "phone": "9876543213", "email": "suresh@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_reception_id, "name": "Kavita Singh", "role": "admin", "phone": "9876543214", "email": "kavita@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_it_id, "name": "Rahul Tech", "role": "admin", "phone": "9876543215", "email": "rahul.tech@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_maintenance_id, "name": "Arvind Maintenance", "role": "admin", "phone": "9876543216", "email": "maintenance@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": "user-student-001", "name": "Rahul Singh", "role": "student", "phone": "9876543220", "preferred_language": "en", "is_active": True},
    ]
    teacher_names = ["Rajesh Kumar", "Sunita Devi", "Manoj Tiwari", "Deepa Verma", "Ankit Sharma", "Vikash Singh", "Nisha Verma"]
    for i, tid in enumerate(teacher_ids):
        users.append({"id": tid, "name": teacher_names[i], "role": "teacher", "phone": f"98765432{30+i}", "preferred_language": "en", "is_active": True})

    await db.users.insert_many(users)

    # ─── Auth users (ALL with bcrypt hashed passwords) ───────────────────────

    # Owner auth
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "owner",
        "username_lower": "owner",
        "password_hash": hash_pw("owner@123"),
        "role": "owner",
        "phone": "9876543210",
        "user_info": {"id": owner_id, "name": "Aman Sharma", "role": "owner", "initials": "AS"},
    })

    # Admin auth — principal (full ops)
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "admin",
        "username_lower": "admin",
        "password_hash": hash_pw("admin@123"),
        "role": "admin",
        "phone": "9876543211",
        "user_info": {"id": admin_id, "name": "Priya Sharma", "role": "admin", "sub_category": "principal", "initials": "PS"},
    })
    # Admin auth — accountant (financial data only)
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "accountant",
        "username_lower": "accountant",
        "password_hash": hash_pw("accountant@123"),
        "role": "admin",
        "phone": "9876543212",
        "user_info": {"id": admin_accountant_id, "name": "Meena Gupta", "role": "admin", "sub_category": "accountant", "initials": "MG"},
    })
    # Admin auth — transport head (transport data only)
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "transport",
        "username_lower": "transport",
        "password_hash": hash_pw("transport@123"),
        "role": "admin",
        "phone": "9876543213",
        "user_info": {"id": admin_transport_id, "name": "Suresh Yadav", "role": "admin", "sub_category": "transport_head", "initials": "SY"},
    })
    # Admin auth — receptionist (enquiries only)
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "reception",
        "username_lower": "reception",
        "password_hash": hash_pw("reception@123"),
        "role": "admin",
        "phone": "9876543214",
        "user_info": {"id": admin_reception_id, "name": "Kavita Singh", "role": "admin", "sub_category": "receptionist", "initials": "KS"},
    })
    # Admin auth — IT & Tech (query resolution + form builder)
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "ittech",
        "username_lower": "ittech",
        "password_hash": hash_pw("ittech@123"),
        "role": "admin",
        "phone": "9876543215",
        "user_info": {"id": admin_it_id, "name": "Rahul Tech", "role": "admin", "sub_category": "it_tech", "initials": "RT"},
    })
    # Admin auth — Maintenance (facility requests only)
    await db.auth_users.insert_one({
        "id": gid(),
        "username": "maintenance",
        "username_lower": "maintenance",
        "password_hash": hash_pw("maintenance@123"),
        "role": "admin",
        "phone": "9876543216",
        "user_info": {"id": admin_maintenance_id, "name": "Arvind Maintenance", "role": "admin", "sub_category": "maintenance", "initials": "AM"},
    })

    # Classes
    class_data = [
        ("Class 9", "A"), ("Class 9", "B"),
        ("Class 10", "A"), ("Class 10", "B"),
        ("Class 11", "A"), ("Class 12", "A"),
    ]
    class_ids = {}
    for name, section in class_data:
        cid = gid()
        class_ids[f"{name}-{section}"] = cid
        await db.classes.insert_one({
            "id": cid, "academic_year_id": ay_id,
            "name": name, "section": section,
            "class_teacher_id": teacher_ids[class_data.index((name, section)) % len(teacher_ids)],
        })

    # Subjects per class
    subjects_per_class = ["English", "Hindi", "Mathematics", "Science", "Social Science"]
    subject_ids = {}
    for class_key, cid in class_ids.items():
        for subj_name in subjects_per_class:
            sid = gid()
            subject_ids[f"{class_key}-{subj_name}"] = sid
            await db.subjects.insert_one({
                "id": sid, "class_id": cid, "name": subj_name,
                "teacher_id": teacher_ids[subjects_per_class.index(subj_name) % len(teacher_ids)],
                "max_marks": 100,
            })

    # Staff — with sub_category and role-specific class references
    c9a  = class_ids.get("Class 9-A")
    c9b  = class_ids.get("Class 9-B")
    c10a = class_ids.get("Class 10-A")
    c10b = class_ids.get("Class 10-B")

    staff_data = [
        # Owner acting as school head
        {"id": "staff-001", "user_id": owner_id,           "name": "Aman Sharma",  "staff_type": "principal",
         "sub_category": "principal",    "employee_id": "EMP001", "salary": 75000},
        # Admin sub-roles
        {"id": "staff-002", "user_id": admin_id,           "name": "Priya Sharma", "staff_type": "admin",
         "sub_category": "principal",    "employee_id": "EMP002", "salary": 35000},
        {"id": "staff-009", "user_id": admin_accountant_id,"name": "Meena Gupta",  "staff_type": "admin",
         "sub_category": "accountant",   "employee_id": "EMP009", "salary": 30000},
        {"id": "staff-010", "user_id": admin_transport_id, "name": "Suresh Yadav", "staff_type": "admin",
         "sub_category": "transport_head","employee_id": "EMP010", "salary": 28000},
        {"id": "staff-011", "user_id": admin_reception_id, "name": "Kavita Singh", "staff_type": "admin",
         "sub_category": "receptionist", "employee_id": "EMP011", "salary": 22000},
        # Teacher sub-roles
        {"id": "staff-003", "user_id": teacher_ids[0],     "name": "Rajesh Kumar", "staff_type": "teacher",
         "sub_category": "class_teacher","class_teacher_of": c9a,
         "subject": "Mathematics",       "employee_id": "EMP003", "salary": 32000},
        {"id": "staff-004", "user_id": teacher_ids[1],     "name": "Sunita Devi",  "staff_type": "teacher",
         "sub_category": "class_teacher","class_teacher_of": c9b,
         "subject": "English",           "employee_id": "EMP004", "salary": 30000},
        {"id": "staff-005", "user_id": teacher_ids[2],     "name": "Manoj Tiwari", "staff_type": "teacher",
         "sub_category": "subject_teacher","assigned_class_ids": [c9a, c10a],
         "subject": "Science",           "employee_id": "EMP005", "salary": 30000},
        {"id": "staff-006", "user_id": teacher_ids[3],     "name": "Deepa Verma",  "staff_type": "teacher",
         "sub_category": "coordinator",  "coordinator_range": "9-12",
         "subject": "Hindi",             "employee_id": "EMP006", "salary": 28000},
        {"id": "staff-007", "user_id": teacher_ids[4],     "name": "Ankit Sharma", "staff_type": "teacher",
         "sub_category": "subject_teacher","assigned_class_ids": [c9b, c10b],
         "subject": "Social Science",    "employee_id": "EMP007", "salary": 28000},
        {"id": "staff-012", "user_id": teacher_ids[5],     "name": "Vikash Singh", "staff_type": "teacher",
         "sub_category": "hod",          "subject": "Mathematics",
         "designation": "HOD Mathematics","employee_id": "EMP012", "salary": 36000},
        {"id": "staff-013", "user_id": teacher_ids[6],     "name": "Nisha Verma",  "staff_type": "teacher",
         "sub_category": "kg_incharge",  "is_incharge": True,
         "designation": "KG In-charge",  "employee_id": "EMP013", "salary": 25000},
        # Support staff
        {"id": "staff-014", "user_id": admin_it_id,          "name": "Rahul Tech",   "staff_type": "admin",
         "sub_category": "it_tech",      "designation": "IT & Tech", "employee_id": "EMP014", "salary": 26000},
        {"id": "staff-015", "user_id": admin_maintenance_id, "name": "Arvind Maintenance", "staff_type": "admin",
         "sub_category": "maintenance",  "designation": "Maintenance", "employee_id": "EMP015", "salary": 24000},
        {"id": "staff-008", "user_id": gid(),              "name": "Ramesh Yadav", "staff_type": "peon",
         "sub_category": "support_staff","employee_id": "EMP008", "salary": 18000},
    ]
    staff_ids = {}
    for rec in staff_data:
        staff_ids[rec["id"]] = rec["id"]
        await db.staff.insert_one({
            **rec, "is_active": True,
            "casual_leave_balance": 12, "medical_leave_balance": 10, "earned_leave_balance": 15,
            "join_date": "2020-06-01",
            "created_at": datetime.now().isoformat(),
        })

    # Auth users for teachers (bcrypt hashed, each with sub_category)
    teacher_info = [
        ("user-teacher-001", "Rajesh Kumar", "RK", "class_teacher",   "teacher@123"),
        ("user-teacher-002", "Sunita Devi",  "SD", "class_teacher",   "teacher@123"),
        ("user-teacher-003", "Manoj Tiwari", "MT", "subject_teacher", "teacher@123"),
        ("user-teacher-004", "Deepa Verma",  "DV", "coordinator",     "teacher@123"),
        ("user-teacher-005", "Ankit Sharma", "AS", "subject_teacher", "teacher@123"),
        ("user-teacher-006", "Vikash Singh", "VS", "hod",             "hod@123"),
        ("user-teacher-007", "Nisha Verma",  "NV", "kg_incharge",     "kg@123"),
    ]
    teacher_auth_docs = []
    for uid, name, initials, sub_cat, pw in teacher_info:
        teacher_auth_docs.append({
            "id": gid(),
            "username": name,
            "username_lower": name.lower(),
            "password_hash": hash_pw(pw),
            "is_active": True,
            "role": "teacher",
            "must_change_password": True,
            "user_info": {"id": uid, "name": name, "role": "teacher", "sub_category": sub_cat, "initials": initials},
        })
    await db.auth_users.insert_many(teacher_auth_docs)

    # Students — 10 per class-A, 5 per class-B
    student_names = [
        "Rahul Singh", "Sneha Kumari", "Amit Verma", "Pooja Yadav", "Vikram Raj",
        "Priya Tiwari", "Rohit Gupta", "Kavya Sharma", "Arjun Mishra", "Neha Pandey",
        "Sohail Khan", "Ananya Das", "Varun Patel", "Riya Joshi", "Karan Mehta",
        "Divya Singh", "Mohit Chauhan", "Swati Agarwal", "Nikhil Rai", "Tanvi Roy",
    ]
    student_ids = []
    idx = 0
    all_classes = list(class_ids.items())
    student_password_hash = hash_pw("student@123")
    for class_key, cid in all_classes:
        count = 10 if "A" in class_key else 6
        for j in range(count):
            sid = gid()
            uid = student_user_ids[idx % len(student_user_ids)] if idx < len(student_user_ids) else None
            sname = student_names[idx % len(student_names)]
            adm = f"ADM2025{(idx+1):04d}"
            student_ids.append((sid, cid, sname, adm, uid))
            await db.students.insert_one({
                "id": sid, "class_id": cid,
                "user_id": "user-student-001" if idx == 0 else uid,
                "name": sname, "admission_number": adm,
                "roll_number": str(j + 1),
                "dob": f"200{7 + (idx % 4)}-0{(idx % 9) + 1}-{15 + (idx % 10):02d}",
                "gender": "male" if idx % 3 != 2 else "female",
                "status": "active", "is_active": True,
                "admission_date": "2025-04-01",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            })
            # Guardian
            await db.guardians.insert_one({
                "id": gid(), "student_id": sid,
                "name": f"{sname.split()[0]}'s Father",
                "relation": "Father",
                "phone": f"98765{(10000 + idx):05d}",
                "whatsapp_phone": f"98765{(10000 + idx):05d}",
                "is_primary": True,
            })
            idx += 1

    print(f"Created {idx} students across {len(class_ids)} classes")

    # Auth users for students (all use "student@123" password, bcrypt hashed)
    student_auth_docs = []
    for sid, cid, sname, adm, uid in student_ids:
        initials = "".join(w[0] for w in sname.split())[:2].upper()
        student_auth_docs.append({
            "id": gid(),
            "username": adm,
            "username_lower": adm.lower(),
            "password_hash": student_password_hash,
            "role": "student",
            "must_change_password": True,
            "user_info": {"id": uid or sid, "name": sname, "role": "student", "initials": initials},
        })
    await db.auth_users.insert_many(student_auth_docs)
    print(f"Created {len(student_auth_docs)} student auth entries and {len(teacher_auth_docs)} teacher auth entries")

    # Create index for case-insensitive login
    await db.auth_users.create_index("username_lower")

    # Staff attendance (last 30 days)
    for days_ago in range(30):
        d = today_minus(days_ago)
        day_of_week = (date.today() - timedelta(days=days_ago)).weekday()
        if day_of_week >= 5:
            continue
        for staff_rec in staff_data:
            staff_id = staff_rec["id"]
            import random
            random.seed(days_ago * 100 + hash(staff_id) % 100)
            if days_ago > 0:
                r = random.random()
                if staff_id == "staff-004" and days_ago in [2, 4, 6, 8]:
                    status = "absent"
                elif staff_id == "staff-005" and days_ago in [1, 3, 5, 7]:
                    status = "late"
                elif r < 0.03:
                    status = "absent"
                elif r < 0.08:
                    status = "late"
                else:
                    status = "present"
            else:
                status = "present" if staff_id not in ["staff-004"] else "absent"

            await db.staff_attendance.update_one(
                {"staff_id": staff_id, "date": d},
                {"$set": {"id": gid(), "staff_id": staff_id, "date": d, "status": status, "check_in": "08:30" if status != "absent" else None}},
                upsert=True
            )

    # Student attendance (last 30 days)
    for days_ago in range(30):
        d = today_minus(days_ago)
        day_of_week = (date.today() - timedelta(days=days_ago)).weekday()
        if day_of_week >= 5:
            continue
        for sid, cid, sname, adm, uid in student_ids:
            import random
            random.seed(days_ago * 1000 + hash(sid) % 1000)
            r = random.random()
            if r < 0.88:
                status = "present"
            elif r < 0.95:
                status = "absent"
            else:
                status = "late"

            await db.student_attendance.update_one(
                {"student_id": sid, "date": d},
                {"$set": {"id": gid(), "student_id": sid, "class_id": cid, "date": d, "status": status, "marked_by": teacher_ids[0]}},
                upsert=True
            )

    print("Created attendance records...")

    # Fee structures
    for class_key, cid in class_ids.items():
        class_name = class_key.split("-")[0]
        fee_structs = [
            {"fee_type": "tuition", "amount": 2500, "frequency": "monthly", "due_day": 10},
            {"fee_type": "exam", "amount": 500, "frequency": "quarterly", "due_day": 1},
            {"fee_type": "sports", "amount": 300, "frequency": "annual", "due_day": 1},
        ]
        for fs in fee_structs:
            await db.fee_structures.insert_one({
                "id": gid(), "academic_year_id": ay_id,
                "class_name": class_name, **fs, "is_optional": False,
            })

    # Fee transactions
    months = [today_minus(90), today_minus(60), today_minus(30), today_minus(5)]
    for i, (sid, cid, sname, adm, uid) in enumerate(student_ids):
        for m_idx, due_date in enumerate(months):
            import random
            random.seed(i * 10 + m_idx)
            r = random.random()
            if m_idx < 2:
                status = "paid" if r > 0.15 else "overdue"
            elif m_idx == 2:
                status = "paid" if r > 0.25 else ("overdue" if r < 0.15 else "pending")
            else:
                status = "pending" if r > 0.4 else "paid"

            txn = {
                "id": gid(), "student_id": sid,
                "fee_type": "tuition", "amount": 2500,
                "due_date": due_date,
                "paid_date": today_minus(random.randint(1, 10)) if status == "paid" else None,
                "status": status,
                "payment_mode": "upi" if status == "paid" else None,
                "receipt_number": f"RCP{gid()[:8].upper()}" if status == "paid" else None,
                "created_at": datetime.now().isoformat(),
            }
            await db.fee_transactions.insert_one(txn)

    print("Created fee transactions...")

    # Leave requests
    leave_staff = [
        ("staff-008", "casual", today_plus(1), today_plus(3), "Family wedding", "pending"),
        ("staff-002", "medical", today_plus(2), today_plus(4), "Doctor appointment", "pending"),
        ("staff-003", "earned", today_minus(10), today_minus(7), "Vacation", "approved"),
        ("staff-004", "casual", today_minus(5), today_minus(4), "Personal work", "approved"),
    ]
    for staff_id, ltype, start, end, reason, status in leave_staff:
        await db.leave_requests.insert_one({
            "id": gid(), "staff_id": staff_id, "leave_type": ltype,
            "start_date": start, "end_date": end, "reason": reason, "status": status,
            "applied_at": datetime.now().isoformat(),
        })

    # Enquiries
    enquiries_data = [
        ("Aryan Verma", "Suresh Verma", "9876543299", "Class 6", "new", "walk_in"),
        ("Priya Nair", "Mohan Nair", "9876543298", "Class 9", "contacted", "phone"),
        ("Rohan Gupta", "Rakesh Gupta", "9876543297", "Class 11", "visit_scheduled", "referral"),
        ("Tanvi Saxena", "Pawan Saxena", "9876543296", "Class 8", "visited", "online"),
        ("Dev Sharma", "Anil Sharma", "9876543295", "Class 10", "documents_submitted", "ad"),
    ]
    for sname, pname, phone, cls, status, source in enquiries_data:
        await db.enquiries.insert_one({
            "id": gid(), "student_name": sname, "parent_name": pname,
            "phone": phone, "class_applying": cls, "status": status,
            "source": source, "assigned_to": admin_id,
            "created_at": datetime.now().isoformat(),
        })

    # Announcements
    announcements = [
        ("Annual Sports Day", "Annual Sports Day will be held on 15th April 2026. All students must participate.", "all"),
        ("PTM Schedule", "Parent Teacher Meeting is scheduled for 20th April 2026 from 10 AM to 2 PM.", "all"),
        ("Exam Notice", "Mid-term examinations will begin from 1st May 2026. Timetable attached.", "all"),
    ]
    for title, content, audience in announcements:
        await db.announcements.insert_one({
            "id": gid(), "title": title, "content": content,
            "audience_type": audience, "channels": ["push"],
            "is_draft": False, "sent_at": datetime.now().isoformat(),
            "created_by": owner_id, "created_at": datetime.now().isoformat(),
        })

    # Exams and results for student-001
    exam_id = gid()
    await db.exams.insert_one({
        "id": exam_id, "academic_year_id": ay_id,
        "name": "Mid-Term 2025", "exam_type": "mid_term",
        "start_date": today_minus(30), "end_date": today_minus(25),
        "created_at": datetime.now().isoformat(),
    })

    first_student_id = student_ids[0][0]
    for subj_key, subj_id in list(subject_ids.items())[:5]:
        if list(class_ids.values())[0] in subj_key or subj_key.startswith("Class 9-A"):
            marks = {"English": 78, "Hindi": 82, "Mathematics": 91, "Science": 85, "Social Science": 80}
            subj_name = subj_key.split("-")[-1]
            m = marks.get(subj_name, 75)
            grade = "A1" if m >= 90 else ("A2" if m >= 80 else "B1")
            await db.exam_results.insert_one({
                "id": gid(), "exam_id": exam_id,
                "student_id": first_student_id,
                "subject_id": subj_id,
                "marks_obtained": m, "max_marks": 100, "grade": grade,
                "entered_by": teacher_ids[0],
                "created_at": datetime.now().isoformat(),
            })

    # Seed conversations for owner
    conv_id_1 = gid()
    await db.conversations.insert_one({
        "id": conv_id_1, "user_id": owner_id,
        "title": "Show me today's school status",
        "is_pinned": False, "is_starred": False,
        "created_at": today_minus(2) + "T10:30:00",
        "updated_at": today_minus(2) + "T10:35:00",
    })

    conv_id_2 = gid()
    await db.conversations.insert_one({
        "id": conv_id_2, "user_id": owner_id,
        "title": "Which staff were absent this week?",
        "is_pinned": False, "is_starred": False,
        "created_at": today_minus(1) + "T14:00:00",
        "updated_at": today_minus(1) + "T14:10:00",
    })

    print("Seed complete! Demo credentials:")
    print(f"  Owner:             username=owner        password=owner@123")
    print(f"  Admin (Principal): username=admin        password=admin@123")
    print(f"  Admin (Accountant):username=accountant   password=accountant@123")
    print(f"  Admin (Transport): username=transport    password=transport@123")
    print(f"  Admin (Reception): username=reception    password=reception@123")
    print(f"  Admin (IT & Tech): username=ittech       password=ittech@123")
    print(f"  Teacher (HOD):     username=Vikash Singh password=hod@123")
    print(f"  Teacher (Coord):   username=Deepa Verma  password=teacher@123")
    print(f"  Teacher (Class):   username=Rajesh Kumar password=teacher@123")
    print(f"  Teacher (Subject): username=Manoj Tiwari password=teacher@123")
    print(f"  Teacher (KG):      username=Nisha Verma  password=kg@123")
    print(f"  Student:           username=ADM20250001  password=student@123")
    print(f"\n  Classes: {len(class_ids)}, Students: {idx}, Staff: {len(staff_data)}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
