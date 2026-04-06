"""
Seed script for EduFlow demo data — The Aaryans CBSE School
Run: python seed.py
"""
import asyncio
import os
import uuid
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def gid():
    return str(uuid.uuid4())


def today_minus(days):
    return (date.today() - timedelta(days=days)).strftime("%Y-%m-%d")


def today_plus(days):
    return (date.today() + timedelta(days=days)).strftime("%Y-%m-%d")


TODAY = date.today().strftime("%Y-%m-%d")


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Clear existing data
    for col in ["users", "academic_years", "classes", "subjects", "students", "guardians",
                "staff", "student_attendance", "staff_attendance", "fee_structures",
                "fee_transactions", "conversations", "messages", "leave_requests",
                "enquiries", "announcements", "school_settings", "exam_results", "exams",
                "auth_users", "custom_forms", "form_responses"]:
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
    teacher_ids = [f"user-teacher-{i:03}" for i in range(1, 6)]
    student_user_ids = [f"user-student-{i:03}" for i in range(1, 16)]

    users = [
        {"id": owner_id, "name": "Aman Sharma", "role": "owner", "phone": "9876543210", "email": "aman@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": admin_id, "name": "Priya Sharma", "role": "admin", "phone": "9876543211", "email": "priya@theararyans.edu.in", "preferred_language": "en", "is_active": True},
        {"id": "user-student-001", "name": "Rahul Singh", "role": "student", "phone": "9876543220", "preferred_language": "en", "is_active": True},
    ]
    for i, tid in enumerate(teacher_ids):
        users.append({"id": tid, "name": ["Rajesh Kumar", "Sunita Devi", "Manoj Tiwari", "Deepa Verma", "Ankit Sharma"][i],
                       "role": "teacher", "phone": f"98765432{30+i}", "preferred_language": "en", "is_active": True})

    await db.users.insert_many(users)

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

    # Staff
    staff_data = [
        ("staff-001", owner_id, "Aman Sharma", "principal", "EMP001", 75000),
        ("staff-002", admin_id, "Priya Sharma", "admin", "EMP002", 35000),
        ("staff-003", teacher_ids[0], "Rajesh Kumar", "teacher", "EMP003", 32000),
        ("staff-004", teacher_ids[1], "Sunita Devi", "teacher", "EMP004", 30000),
        ("staff-005", teacher_ids[2], "Manoj Tiwari", "teacher", "EMP005", 30000),
        ("staff-006", teacher_ids[3], "Deepa Verma", "teacher", "EMP006", 28000),
        ("staff-007", teacher_ids[4], "Ankit Sharma", "teacher", "EMP007", 28000),
        ("staff-008", gid(), "Ramesh Yadav", "peon", "EMP008", 18000),
    ]
    staff_ids = {}
    for staff_id, uid, name, stype, empid, salary in staff_data:
        staff_ids[staff_id] = staff_id
        await db.staff.insert_one({
            "id": staff_id, "user_id": uid, "name": name, "staff_type": stype,
            "employee_id": empid, "salary": salary, "is_active": True,
            "casual_leave_balance": 12, "medical_leave_balance": 10, "earned_leave_balance": 15,
            "join_date": "2020-06-01",
            "created_at": datetime.now().isoformat(),
        })

    # Auth users for teachers
    teacher_info = [
        ("user-teacher-001", "Rajesh Kumar", "RK"),
        ("user-teacher-002", "Sunita Devi",  "SD"),
        ("user-teacher-003", "Manoj Tiwari", "MT"),
        ("user-teacher-004", "Deepa Verma",  "DV"),
        ("user-teacher-005", "Ankit Sharma", "AS"),
    ]
    teacher_auth_docs = []
    for uid, name, initials in teacher_info:
        teacher_auth_docs.append({
            "id": gid(), "username": name, "password": "teacher@123",
            "role": "teacher",
            "user_info": {"id": uid, "name": name, "role": "teacher", "initials": initials}
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

    # Auth users for students (password = admission number)
    student_auth_docs = []
    for sid, cid, sname, adm, uid in student_ids:
        initials = "".join(w[0] for w in sname.split())[:2].upper()
        student_auth_docs.append({
            "id": gid(), "username": adm, "password": adm,
            "role": "student",
            "user_info": {"id": uid or sid, "name": sname, "role": "student", "initials": initials}
        })
    await db.auth_users.insert_many(student_auth_docs)
    print(f"Created {len(student_auth_docs)} student auth entries and {len(teacher_auth_docs)} teacher auth entries")

    # Staff attendance (last 30 days)
    for days_ago in range(30):
        d = today_minus(days_ago)
        day_of_week = (date.today() - timedelta(days=days_ago)).weekday()
        if day_of_week >= 5:  # skip weekends
            continue
        for staff_rec in staff_data:
            staff_id = staff_rec[0]
            # Occasional absences/late
            import random
            random.seed(days_ago * 100 + hash(staff_id) % 100)
            if days_ago > 0:
                r = random.random()
                if staff_id == "staff-004" and days_ago in [2, 4, 6, 8]:
                    status = "absent"  # Sunita Devi pattern
                elif staff_id == "staff-005" and days_ago in [1, 3, 5, 7]:
                    status = "late"   # Manoj Kumar late pattern
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
            if m_idx < 2:  # older months mostly paid
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

    first_class_id = list(class_ids.values())[0]
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

    conv_id_3 = gid()
    await db.conversations.insert_one({
        "id": conv_id_3, "user_id": owner_id,
        "title": "Fee collection report for March",
        "is_pinned": False, "is_starred": False,
        "created_at": today_minus(1) + "T16:00:00",
        "updated_at": today_minus(1) + "T16:05:00",
    })

    print("✅ Seed complete! Summary:")
    print(f"  - Academic Year: 2025-26")
    print(f"  - Classes: {len(class_ids)}")
    print(f"  - Students: {idx}")
    print(f"  - Staff: {len(staff_data)}")
    print(f"  - Attendance records created for last 30 days")
    print(f"  - Fee transactions created")
    print(f"  - Leave requests: {len(leave_staff)}")
    print(f"  - Enquiries: {len(enquiries_data)}")

    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
