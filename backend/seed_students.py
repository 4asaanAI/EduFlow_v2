"""
Seed real student data for The Aaryans.
Reads Student_List.pdf and populates: users, auth_users, students, guardians, classes.

Usage:
    python seed_students.py [/path/to/Student_List.pdf]

Defaults to ../Student_List.pdf relative to this script.

WARNING: Deletes all student records before inserting. Staff/settings are untouched.
"""
from __future__ import annotations
import asyncio
import os
import sys
import uuid
from datetime import date
from pathlib import Path

import bcrypt
import pdfplumber
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
BRANCH_ID = "branch-joya"
AY_ID = "ay-2025-26"
TODAY = date.today().isoformat()

STREAM_WORDS = {"Commerce", "Science", "Arts", "Humanities"}


def gid() -> str:
    return str(uuid.uuid4())


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=8)).decode("utf-8")


def parse_grade(raw_class: str) -> str:
    """Strip stream suffix: '11th Commerce' → '11th', '12th Science' → '12th'."""
    parts = raw_class.strip().replace("\n", " ").split()
    return " ".join(p for p in parts if p not in STREAM_WORDS).strip()


def make_cls_id(grade: str, section: str) -> str:
    return f"cls-{grade.lower().replace(' ', '-')}-{section.lower()}"


def initials(name: str) -> str:
    words = name.split()
    return "".join(w[0] for w in words if w)[:2].upper()


def extract_rows(pdf_path: Path) -> list[dict]:
    rows = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            for row in tables[0]:
                if not row[0] or not row[0].strip().isdigit():
                    continue
                raw_cls = (row[5] or "").strip().replace("\n", " ")
                if "PASS OUT" in raw_cls.upper():
                    continue
                rows.append({
                    "name":         (row[2] or "").strip(),
                    "mobile":       (row[3] or "").strip(),
                    "admission_no": (row[4] or "").strip(),
                    "grade":        parse_grade(raw_cls),
                    "section":      (row[6] or "").strip().upper(),
                    "address":      (row[7] or "").strip(),
                    "mothers_name": (row[8] or "").strip(),
                    "fathers_name": (row[9] or "").strip(),
                })
    return rows


async def seed(pdf_path: Path) -> None:
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10_000, retryWrites=True)
    db = client[DB_NAME]

    # ── 1. Clear student-related data ────────────────────────────────────────
    print("Clearing existing student records...")
    await db.users.delete_many({"role": "student"})
    await db.auth_users.delete_many({"role": "student"})
    await db.students.delete_many({})
    await db.guardians.delete_many({})
    await db.classes.delete_many({})
    await db.student_attendance.delete_many({})

    # ── 2. Parse PDF ─────────────────────────────────────────────────────────
    print(f"Parsing {pdf_path} ...")
    rows = extract_rows(pdf_path)
    print(f"  → {len(rows)} students found")

    # ── 3. Create classes (deterministic IDs) ────────────────────────────────
    grade_sections: set[tuple[str, str]] = {(r["grade"], r["section"]) for r in rows}
    class_docs = []
    for grade, section in sorted(grade_sections):
        cid = make_cls_id(grade, section)
        class_docs.append({
            "id": cid,
            "schoolId": SCHOOL_ID,
            "academic_year_id": AY_ID,
            "branch_id": BRANCH_ID,
            "name": grade,
            "section": section,
            "class_teacher_id": None,
            "room_number": None,
        })
    await db.classes.insert_many(class_docs)
    print(f"  → {len(class_docs)} classes created")

    # ── 4. Seed students ─────────────────────────────────────────────────────
    print("Hashing passwords and building student documents (this takes ~30s)...")

    # Build unique usernames: if name appears more than once, append admission number
    from collections import Counter
    name_counts = Counter(r["name"].lower() for r in rows)
    name_seen: Counter = Counter()

    user_docs = []
    auth_docs = []
    student_docs = []
    guardian_docs = []

    for i, row in enumerate(rows, 1):
        if i % 200 == 0:
            print(f"  → {i}/{len(rows)} processed...")

        user_id = gid()
        student_id = gid()
        cid = make_cls_id(row["grade"], row["section"])
        inits = initials(row["name"])
        pw_hash = hash_pw(row["admission_no"])

        # Make username unique when duplicate names exist
        name_lower = row["name"].lower()
        name_seen[name_lower] += 1
        if name_counts[name_lower] > 1:
            username = f"{row['name']} ({row['admission_no']})"
        else:
            username = row["name"]

        # users
        user_docs.append({
            "id": user_id,
            "schoolId": SCHOOL_ID,
            "name": row["name"],
            "role": "student",
            "sub_category": None,
            "phone": row["mobile"],
            "preferred_language": "en",
            "theme": "dark",
            "is_active": True,
        })

        # auth_users — username = student name (+ admission no if duplicate), password = admission number
        auth_docs.append({
            "id": gid(),
            "schoolId": SCHOOL_ID,
            "username": username,
            "username_lower": username.lower(),
            "password_hash": pw_hash,
            "role": "student",
            "is_active": True,
            "must_change_password": True,
            "user_info": {
                "id": user_id,
                "name": row["name"],
                "role": "student",
                "sub_category": None,
                "initials": inits,
            },
        })

        # students
        student_docs.append({
            "id": student_id,
            "schoolId": SCHOOL_ID,
            "class_id": cid,
            "academic_year_id": AY_ID,
            "branch_id": BRANCH_ID,
            "user_id": user_id,
            "name": row["name"],
            "admission_number": row["admission_no"],
            "roll_number": str(i),
            "phone": row["mobile"],
            "address": row["address"],
            "dob": None,
            "gender": None,
            "blood_group": None,
            "status": "active",
            "is_active": True,
            "admission_date": None,
            "transport_opted": False,
            "route_id": None,
            "house": None,
            "created_at": TODAY,
            "updated_at": TODAY,
        })

        # guardians
        if row["fathers_name"]:
            guardian_docs.append({
                "id": gid(),
                "schoolId": SCHOOL_ID,
                "student_id": student_id,
                "name": row["fathers_name"],
                "relation": "Father",
                "phone": row["mobile"],
                "whatsapp_phone": row["mobile"],
                "email": "",
                "occupation": "",
                "is_primary": True,
            })
        if row["mothers_name"]:
            guardian_docs.append({
                "id": gid(),
                "schoolId": SCHOOL_ID,
                "student_id": student_id,
                "name": row["mothers_name"],
                "relation": "Mother",
                "phone": row["mobile"],
                "whatsapp_phone": row["mobile"],
                "email": "",
                "occupation": "",
                "is_primary": not bool(row["fathers_name"]),
            })

    # ── 5. Bulk insert ───────────────────────────────────────────────────────
    print("Inserting into MongoDB...")
    CHUNK = 500

    for start in range(0, len(user_docs), CHUNK):
        await db.users.insert_many(user_docs[start:start + CHUNK])
    print(f"  ✓ {len(user_docs)} user docs")

    for start in range(0, len(auth_docs), CHUNK):
        await db.auth_users.insert_many(auth_docs[start:start + CHUNK])
    await db.auth_users.create_index("username_lower")
    print(f"  ✓ {len(auth_docs)} auth_user docs")

    for start in range(0, len(student_docs), CHUNK):
        await db.students.insert_many(student_docs[start:start + CHUNK])
    print(f"  ✓ {len(student_docs)} student docs")

    for start in range(0, len(guardian_docs), CHUNK):
        await db.guardians.insert_many(guardian_docs[start:start + CHUNK])
    print(f"  ✓ {len(guardian_docs)} guardian docs")

    client.close()
    print(f"\nDone. {len(rows)} students seeded across {len(class_docs)} classes.")


if __name__ == "__main__":
    default_pdf = Path(__file__).parent.parent / "Student_List.pdf"
    pdf_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else default_pdf
    if not pdf_arg.exists():
        pdf_arg = Path("/Users/shashisharma/Downloads/Student_List.pdf")
    if not pdf_arg.exists():
        print(f"ERROR: PDF not found. Pass path as argument: python seed_students.py /path/to/Student_List.pdf")
        sys.exit(1)
    asyncio.run(seed(pdf_arg))
