"""
Seed real teachers + subjects + period-links for The Aaryans.

Sources (cross-checked by hand, 2026-06-27):
  * Teacher_Directory.pdf            → 83 teachers (canonical staff list)
  * Subjects_and_PeriodLinks_Only.pdf → 303 class x subject x teacher rows

What it writes:
  * users / auth_users  — 83 directory teachers + 5 allocation-only teachers
                          (Yachika, Sapna Pandey, Pramod, B S Yadav, Shilpa)
  * subjects            — one row per Part-A assignment (293 of 303; PGT/Phy skipped)
  * period_links        — one row per seeded subject (schedule columns left blank,
                          matching the source — populate once the timetable is set)

Decisions baked in (confirmed by Shubham):
  * PGT / Phy rows (placeholders, 10 rows) are NOT seeded.
  * Shalini (Science) & Kirti (GK) are ambiguous → seeded with teacher_id = None.
  * Auth username  = teacher name verbatim from the directory ("ditto", caps preserved).
  * Auth password  = mobile number; if a teacher has no mobile → "rkoY2J619730".

Classes are matched to the EXISTING `classes` collection (ids like cls-8th-a).
Roman numerals in the source map to ordinal class names: VIII -> "8th".

Idempotent: re-running deletes only what this script created
(users/auth_users tagged source="teacher_directory_seed", and ALL subjects/period_links).

Usage:  python seed_subjects_teachers.py
"""
from __future__ import annotations
import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path

import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
BRANCH_ID = "branch-joya"
NOW = datetime.now().isoformat()
SEED_TAG = "teacher_directory_seed"
FALLBACK_PW = "rkoY2J619730"


def gid() -> str:
    return str(uuid.uuid4())


def hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=8)).decode("utf-8")


def initials(name: str) -> str:
    return "".join(w[0] for w in name.split() if w)[:2].upper()


# ─────────────────────────────────────────────────────────────────────────────
# Teacher directory — 83 rows: (first, last, mobile, gender, class_teacher)
# Transcribed verbatim from Teacher_Directory.pdf. "" = blank cell in source.
# ─────────────────────────────────────────────────────────────────────────────
DIRECTORY = [
    ("RUQAYYA", "", "8014646146", "female", False),         # 1
    ("SHALINI", "VERMA", "8014646146", "female", True),      # 2
    ("NAHID", "NAQVI", "9990883464", "female", False),       # 3
    ("SAKSHI", "", "8014646146", "female", True),            # 4
    ("NEHA", "KHAN", "9837621706", "female", True),          # 5
    ("NITURAJ", "", "8014646146", "female", True),           # 6
    ("HUMA", "PARVEEN", "8850092128", "female", True),       # 7
    ("PREETI", "", "8881057626", "female", True),            # 8
    ("PRIYANKA", "DEVI", "8014646146", "", True),            # 9
    ("NAHID", "RAHMAN", "8014646146", "", False),            # 10
    ("SHIVANI", "GUPTA", "8014646146", "female", True),      # 11
    ("SARITA", "YADAV", "8126968888", "female", True),       # 12
    ("SUCHITRA", "", "8126965555", "female", True),          # 13
    ("MAMTA", "", "8126965555", "female", True),             # 14
    ("RUCHI", "", "9870564399", "female", False),            # 15
    ("RACHNA", "", "8126965555", "female", True),            # 16
    ("TRIPTI", "", "8126965555", "female", True),            # 17
    ("SURBHI", "", "8449047229", "female", True),            # 18
    ("CHANDNI", "MATHUR", "8126965555", "female", True),     # 19
    ("PRERNA", "", "8126968888", "female", True),            # 20
    ("KUMUD", "", "8126965555", "female", True),             # 21
    ("HUMA", "BABY", "8954791800", "female", True),          # 22
    ("MUSKAN", "", "8126965555", "female", True),            # 23
    ("SHIKHA", "ANAND", "8126965555", "female", True),       # 24
    ("ISTEKHAR", "AHMAD", "9412864132", "male", True),       # 25
    ("FURQAN", "", "8126965555", "male", True),              # 26
    ("RAHUL", "", "8126965555", "male", False),              # 27
    ("ANUJ", "", "8445959679", "male", True),                # 28
    ("PRAGATI", "TANDON", "8909406732", "female", True),     # 29
    ("ASHWANI", "", "8126965555", "male", True),             # 30
    ("SHUBHAM", "SHARMA", "7042815490", "male", True),       # 31
    ("RAMAN", "BALA", "8126965555", "female", True),         # 32
    ("PRERITA", "", "8126965555", "female", True),           # 33
    ("SUMIT", "", "8126965555", "male", True),               # 34
    ("SHAGUFTA", "HAMID", "8126965555", "female", True),     # 35
    ("AJEET", "", "8126965555", "male", False),              # 36
    ("VINEET", "", "8126965555", "male", True),              # 37
    ("ROHIT", "", "9410676692", "male", True),               # 38
    ("SHEETAL", "YADAV", "8126965555", "female", False),     # 39
    ("SWATI", "CHOUDHARY", "8126968888", "female", True),    # 40
    ("SHAILJA", "", "9568282736", "female", True),           # 41
    ("CHANDNI", "BATRA", "8881057626", "female", False),     # 42
    ("SONU", "RUHAL", "8014646146", "male", False),          # 43
    ("CHIRANJEEV", "KAUR", "9759477489", "female", True),    # 44
    ("GULAFSHA", "KHAN", "7055729062", "female", True),      # 45
    ("SHIVANI", "SHIDHU", "8218088144", "female", False),    # 46
    ("KRITIKA", "", "6397195589", "female", True),           # 47
    ("SHALINI", "BHARDWAJ", "9368281460", "female", False),  # 48
    ("SHAGUN", "SAINI", "8954875206", "", True),             # 49
    ("SUNITA", "CHOUDHARY", "8979637816", "", False),        # 50
    ("DEEPANSHI", "", "9528747621", "", False),              # 51
    ("ADITI", "KASHYAP", "7300969109", "", False),           # 52
    ("RENU", "RAJPUT", "9716728947", "", False),             # 53
    ("MONIKA", "YADAV", "8279713802", "", False),            # 54
    ("SANTOSH", "KUMAR", "8410965259", "", False),           # 55
    ("ANJANA", "DEVI", "8126741473", "female", False),       # 56
    ("PRATEEK", "KUMAR", "9897683573", "", False),           # 57
    ("JAGRITI", "KAUSHIK", "9412842003", "", False),         # 58
    ("MOHINI", "VERMA", "9389611055", "", False),            # 59
    ("NEHA", "", "9105011851", "", False),                   # 60
    ("KHUSBOO", "CHOUDHARY", "9012312138", "", False),       # 61
    ("DR PERMENDRA", "KUMAR", "9410499396", "", True),       # 62
    ("MONIKA", "CHAUDHARY", "8218361968", "female", False),  # 63
    ("MONIKA", "VISNOI", "8410489446", "", True),            # 64
    ("DHEERAJ", "MAHALAWAR", "8923821656", "", False),       # 65
    ("ABHISHEK", "SUMAN", "7906514462", "male", False),      # 66
    ("SHIVANI", "THOMAS", "9536356508", "female", True),     # 67
    ("MEENA", "AGARWAL", "9917806155", "", True),            # 68
    ("LAIBA", "QURESHI", "8279866639", "", False),           # 69
    ("PRIYANSHI", "AGARWAL", "9358251473", "female", False), # 70
    ("VIDHI", "MAHESHWARI", "8077254612", "female", True),   # 71
    ("PRANAV", "MISHRA", "8218028991", "male", False),       # 72
    ("ANJALI", "CHAUDHARY", "9109881546", "female", True),   # 73
    ("FAISAL", "AHMED", "9760300291", "male", True),         # 74
    ("NEHA", "KHANNA", "8791291432", "", False),             # 75
    ("TOSHI", "YADAV", "9568000483", "female", True),        # 76
    ("SHUBHAM", "PANDEY", "7456835053", "", False),          # 77
    ("ANOOD", "TAYYAB", "9897892811", "female", False),      # 78
    ("RAZIA", "KHAN", "8218998752", "female", False),        # 79
    ("PAYAL", "", "8264754752", "female", False),            # 80
    ("AAFREEN", "JAHAN", "9568320724", "female", True),      # 81
    ("ARISHA", "MAM", "8218027290", "female", True),         # 82
    ("SOFIYA", "MAM", "8126968888", "female", True),         # 83
]

# Allocation-only teachers (not in directory) — confirmed: create records too.
EXTRA_TEACHERS = ["Yachika", "Sapna Pandey", "Pramod", "B S Yadav", "Shilpa"]

# Subject-doc short name -> directory row (1-based index above).
NAME_TO_DIR = {
    "Vidhi Maheshwari": 71, "Arisha": 82, "Prerna": 20, "Afreen": 81,
    "Raman": 32, "Ashwani": 30, "Shagufta": 35, "Surbhi": 18, "Sofia": 83,
    "Shikha": 24, "Meena": 68, "Vineet": 37, "Anjali Ch": 73, "Kumud": 21,
    "Istekhar": 25, "Anuj": 28, "Sumit Kr": 34, "Chandni M": 19,
    "Huma Boby": 22, "Furqaan": 26, "Anood": 78, "Rahul": 27, "Shubham P": 77,
    "Priyanshi": 70, "Monika Yadav": 54, "Abhishek": 66, "Anjana": 56,
    "Santosh": 55, "Deepanshi": 51, "Razia": 79, "Payal": 80,
    "Mohini Verma": 59, "Aditi": 52, "Khushboo": 61, "Dheeraj": 65,
    "Sakshi": 4, "Sunita": 50, "Sheetal": 39, "Shubham": 31, "Ajeet Singh": 36,
}
# Subject-doc short name -> extra teacher.
NAME_TO_EXTRA = {n: n for n in EXTRA_TEACHERS}
# Seed the row but leave teacher_id = None (ambiguous against directory).
BLANK_TEACHERS = {"Shalini", "Kirti"}
# Do not seed these rows at all (role placeholders, not people).
SKIP_TEACHERS = {"PGT", "Phy"}

ROMAN_TO_NAME = {
    "I": "1st", "II": "2nd", "III": "3rd", "IV": "4th", "V": "5th", "VI": "6th",
    "VII": "7th", "VIII": "8th", "IX": "9th", "X": "10th", "XI": "11th", "XII": "12th",
}

# ─────────────────────────────────────────────────────────────────────────────
# Part A subject rows — (roman_class | None, section | None, teacher_short_name)
# grouped by subject name. None class => Social Science / Commerce (class_id blank).
# ─────────────────────────────────────────────────────────────────────────────
SUBJECTS: dict[str, list[tuple]] = {
    "English": [
        ("III", "A", "Vidhi Maheshwari"), ("III", "B", "Vidhi Maheshwari"),
        ("III", "C", "Vidhi Maheshwari"), ("III", "D", "Vidhi Maheshwari"),
        ("IV", "A", "Arisha"), ("IV", "B", "Arisha"), ("V", "A", "Arisha"),
        ("V", "B", "Prerna"), ("V", "C", "Prerna"), ("VI", "A", "Afreen"),
        ("VI", "B", "Prerna"), ("VI", "C", "Raman"), ("VII", "A", "Afreen"),
        ("VII", "B", "Ashwani"), ("VII", "C", "Afreen"), ("VIII", "A", "Ashwani"),
        ("VIII", "B", "Ashwani"), ("IX", "A", "Shagufta"), ("IX", "B", "Raman"),
        ("X", "A", "Raman"), ("X", "B", "Raman"), ("XI", "A", "Shagufta"),
        ("XI", "B", "Shagufta"), ("XI", "C", "Shagufta"), ("XII", "A", "Shagufta"),
        ("XII", "B", "Shagufta"), ("XII", "C", "Shagufta"),
    ],
    "Hindi": [
        ("III", "A", "Surbhi"), ("III", "B", "Surbhi"), ("III", "C", "Surbhi"),
        ("III", "D", "Surbhi"), ("IV", "A", "Sofia"), ("IV", "B", "Yachika"),
        ("V", "A", "Yachika"), ("V", "B", "Shikha"), ("V", "C", "Shikha"),
        ("VI", "A", "Shikha"), ("VI", "B", "Shikha"), ("VI", "C", "Meena"),
        ("VII", "A", "Meena"), ("VII", "B", "Meena"), ("VII", "C", "Meena"),
        ("VIII", "A", "Yachika"), ("VIII", "A", "Sofia"), ("VIII", "B", "Yachika"),
        ("VIII", "B", "Sofia"), ("IX", "A", "Vineet"), ("IX", "B", "Vineet"),
        ("X", "A", "Sofia"), ("X", "B", "Sofia"), ("XI", "C", "Vineet"),
        ("XII", "C", "Vineet"),
    ],
    "Mathematics": [
        ("III", "A", "Anjali Ch"), ("III", "B", "Anjali Ch"), ("III", "C", "Anjali Ch"),
        ("III", "D", "Anjali Ch"), ("IV", "A", "Kumud"), ("IV", "B", "Kumud"),
        ("V", "A", "Kumud"), ("V", "B", "Istekhar"), ("V", "C", "Istekhar"),
        ("VI", "A", "Anuj"), ("VI", "B", "Istekhar"), ("VI", "C", "Anuj"),
        ("VII", "A", "Anuj"), ("VII", "B", "Anuj"), ("VII", "C", "Istekhar"),
        ("VIII", "A", "Sumit Kr"), ("VIII", "B", "Sumit Kr"), ("IX", "A", "PGT"),
        ("IX", "B", "Sumit Kr"), ("X", "A", "PGT"), ("X", "B", "Sumit Kr"),
        ("XI", "A", "PGT"), ("XII", "A", "PGT"),
    ],
    "Science": [
        ("III", "A", "Chandni M"), ("III", "B", "Chandni M"), ("III", "C", "Chandni M"),
        ("III", "D", "Chandni M"), ("IV", "A", "Huma Boby"), ("IV", "B", "Huma Boby"),
        ("V", "A", "Huma Boby"), ("V", "B", "Furqaan"), ("V", "C", "Furqaan"),
        ("VI", "A", "Anood"), ("VI", "B", "Furqaan"), ("VI", "B", "Rahul"),
        ("VI", "C", "Rahul"), ("VI", "C", "Anood"), ("VII", "A", "Furqaan"),
        ("VIII", "A", "Anood"), ("VIII", "B", "Rahul"),
        ("IX", "A", "Shalini"), ("IX", "A", "Phy"), ("IX", "A", "Shubham P"),
        ("IX", "B", "Shalini"), ("IX", "B", "Phy"), ("IX", "B", "Shubham P"),
        ("X", "A", "Shalini"), ("X", "A", "Phy"), ("X", "A", "Shubham P"),
        ("X", "B", "Shalini"), ("X", "B", "Phy"), ("X", "B", "Shubham P"),
        ("XI", "A", "Shalini"), ("XI", "A", "Phy"), ("XI", "A", "Shubham P"),
        ("XII", "A", "Shalini"), ("XII", "A", "Phy"), ("XII", "A", "Shubham P"),
    ],
    "Computer": [
        ("II", "A", "Priyanshi"), ("II", "B", "Priyanshi"), ("II", "C", "Priyanshi"),
        ("II", "D", "Priyanshi"), ("III", "A", "Priyanshi"), ("III", "B", "Priyanshi"),
        ("III", "C", "Priyanshi"), ("III", "D", "Priyanshi"), ("IV", "A", "Priyanshi"),
        ("IV", "B", "Priyanshi"), ("V", "A", "Monika Yadav"), ("V", "B", "Monika Yadav"),
        ("V", "C", "Monika Yadav"), ("VI", "A", "Monika Yadav"), ("VI", "B", "Monika Yadav"),
        ("VI", "C", "Monika Yadav"), ("VII", "A", "Monika Yadav"), ("VII", "A", "Sapna Pandey"),
        ("VII", "B", "Monika Yadav"), ("VII", "B", "Sapna Pandey"), ("VII", "C", "Sapna Pandey"),
        ("VIII", "A", "Abhishek"), ("VIII", "B", "Abhishek"), ("IX", "A", "Abhishek"),
        ("IX", "B", "Abhishek"), ("X", "A", "Abhishek"), ("X", "B", "Abhishek"),
        ("XI", "A", "Abhishek"), ("XI", "B", "Abhishek"), ("XI", "C", "Abhishek"),
    ],
    "Art": [
        ("I", "A", "Anjana"), ("I", "B", "Anjana"), ("I", "C", "Anjana"),
        ("II", "A", "Anjana"), ("II", "B", "Anjana"), ("II", "C", "Anjana"),
        ("II", "D", "Anjana"), ("II", "E", "Anjana"), ("III", "A", "Anjana"),
        ("III", "B", "Anjana"), ("III", "C", "Anjana"), ("III", "D", "Anjana"),
        ("IV", "A", "Anjana"), ("IV", "B", "Anjana"), ("IV", "C", "Anjana"),
        ("V", "A", "Anjana"), ("V", "B", "Anjana"), ("V", "C", "Anjana"),
        ("VI", "A", "Santosh"), ("VI", "B", "Santosh"), ("VI", "C", "Santosh"),
        ("VII", "A", "Santosh"), ("VII", "B", "Santosh"), ("VII", "C", "Santosh"),
        ("VIII", "A", "Santosh"), ("VIII", "B", "Santosh"), ("XI", "A", "Santosh"),
        ("XI", "B", "Santosh"), ("XI", "C", "Santosh"), ("XII", "A", "Santosh"),
        ("XII", "B", "Santosh"), ("XII", "C", "Santosh"),
    ],
    "Sports": [
        ("I", "A", "Deepanshi"), ("I", "B", "Deepanshi"), ("I", "C", "Deepanshi"),
        ("II", "A", "Deepanshi"), ("II", "B", "Deepanshi"), ("II", "C", "Deepanshi"),
        ("II", "D", "Deepanshi"), ("II", "E", "Deepanshi"), ("III", "A", "Deepanshi"),
        ("III", "B", "Deepanshi"), ("III", "C", "Deepanshi"), ("IV", "A", "Deepanshi"),
        ("IV", "B", "Deepanshi"), ("V", "A", "Deepanshi"), ("V", "B", "Deepanshi"),
        ("V", "C", "Pramod"), ("VI", "A", "Pramod"), ("VI", "B", "Pramod"),
        ("VI", "C", "Pramod"), ("VII", "A", "Pramod"), ("VII", "B", "Pramod"),
        ("VIII", "A", "Pramod"), ("VIII", "B", "Pramod"), ("IX", "A", "Pramod"),
        ("IX", "B", "Pramod"), ("X", "A", "B S Yadav"), ("X", "B", "B S Yadav"),
    ],
    "General Knowledge": [
        ("I", "A", "Razia"), ("I", "B", "Razia"), ("I", "C", "Razia"),
        ("II", "C", "Razia"), ("III", "A", "Payal"), ("III", "C", "Kirti"),
        ("IV", "B", "Kirti"),
    ],
    "Music": [
        ("I", "A", "Mohini Verma"), ("I", "B", "Mohini Verma"), ("I", "C", "Mohini Verma"),
        ("II", "A", "Mohini Verma"), ("II", "B", "Mohini Verma"), ("II", "C", "Mohini Verma"),
        ("II", "D", "Mohini Verma"), ("II", "E", "Mohini Verma"), ("III", "A", "Mohini Verma"),
        ("III", "B", "Mohini Verma"), ("III", "C", "Mohini Verma"), ("III", "D", "Mohini Verma"),
        ("IV", "A", "Mohini Verma"), ("IV", "B", "Mohini Verma"), ("IV", "C", "Mohini Verma"),
        ("V", "A", "Mohini Verma"), ("V", "B", "Mohini Verma"), ("V", "C", "Mohini Verma"),
        ("VI", "A", "Mohini Verma"), ("VI", "B", "Mohini Verma"), ("VI", "C", "Mohini Verma"),
        ("VII", "A", "Mohini Verma"), ("VII", "B", "Mohini Verma"), ("VII", "C", "Mohini Verma"),
        ("VIII", "A", "Mohini Verma"), ("VIII", "B", "Mohini Verma"), ("IX", "A", "Mohini Verma"),
        ("IX", "B", "Mohini Verma"), ("X", "A", "Mohini Verma"), ("X", "B", "Mohini Verma"),
        ("XI", "A", "Mohini Verma"), ("XI", "B", "Mohini Verma"), ("XI", "C", "Mohini Verma"),
        ("XII", "A", "Mohini Verma"), ("XII", "B", "Mohini Verma"), ("XII", "C", "Mohini Verma"),
    ],
    "Dance": [
        ("I", "A", "Aditi"), ("I", "B", "Aditi"), ("I", "C", "Aditi"),
        ("II", "A", "Aditi"), ("II", "B", "Aditi"), ("II", "C", "Aditi"),
        ("II", "D", "Aditi"), ("II", "E", "Aditi"), ("III", "A", "Aditi"),
        ("III", "B", "Aditi"), ("III", "C", "Aditi"), ("III", "D", "Aditi"),
        ("IV", "A", "Aditi"), ("IV", "B", "Aditi"), ("IV", "C", "Aditi"),
        ("V", "A", "Aditi"), ("V", "B", "Aditi"), ("V", "C", "Aditi"),
    ],
    "Library": [
        ("I", "A", "Khushboo"), ("I", "B", "Khushboo"), ("I", "C", "Khushboo"),
        ("II", "A", "Khushboo"), ("II", "B", "Khushboo"), ("II", "C", "Khushboo"),
        ("II", "D", "Khushboo"), ("II", "E", "Khushboo"), ("III", "A", "Khushboo"),
        ("III", "B", "Khushboo"), ("III", "C", "Khushboo"), ("III", "D", "Khushboo"),
        ("IV", "A", "Khushboo"), ("IV", "B", "Khushboo"), ("IV", "C", "Khushboo"),
        ("V", "A", "Khushboo"), ("V", "B", "Khushboo"), ("V", "C", "Khushboo"),
        ("VI", "A", "Khushboo"), ("VI", "B", "Khushboo"), ("VI", "C", "Khushboo"),
        ("VII", "A", "Khushboo"), ("VII", "B", "Khushboo"), ("VII", "C", "Khushboo"),
        ("VIII", "A", "Khushboo"), ("VIII", "B", "Khushboo"), ("IX", "A", "Khushboo"),
        ("IX", "B", "Khushboo"), ("X", "A", "Khushboo"), ("X", "B", "Khushboo"),
        ("XI", "A", "Khushboo"), ("XI", "B", "Khushboo"), ("XI", "C", "Khushboo"),
        ("XII", "A", "Khushboo"), ("XII", "B", "Khushboo"), ("XII", "C", "Khushboo"),
    ],
    "Social Science": [
        (None, None, "Dheeraj"), (None, None, "Sakshi"), (None, None, "Sunita"),
        (None, None, "Shilpa"), (None, None, "Sheetal"), (None, None, "Shubham"),
    ],
    "Commerce": [
        (None, None, "Ajeet Singh"),
    ],
}


async def seed() -> None:
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=15_000, retryWrites=True)
    db = client[DB_NAME]

    # ── Sanity: row count must equal 303 ─────────────────────────────────────
    total_rows = sum(len(v) for v in SUBJECTS.values())
    assert total_rows == 303, f"Expected 303 source rows, encoded {total_rows}"
    print(f"Encoded {total_rows} subject rows from the source.")

    # ── Build class lookup from the EXISTING classes collection ──────────────
    classes = await db.classes.find(
        {"schoolId": SCHOOL_ID, "branch_id": BRANCH_ID}, {"_id": 0}
    ).to_list(500)
    class_by_key: dict[tuple[str, str], str] = {
        (c["name"], c["section"]): c["id"] for c in classes
    }
    print(f"Loaded {len(class_by_key)} existing classes.")

    # ── Validate every teacher name + class up front (fail loud, change nothing) ─
    missing_classes: set[tuple[str, str]] = set()
    unknown_names: set[str] = set()
    for subj, rows in SUBJECTS.items():
        for roman, section, tname in rows:
            if (tname not in NAME_TO_DIR and tname not in NAME_TO_EXTRA
                    and tname not in BLANK_TEACHERS and tname not in SKIP_TEACHERS):
                unknown_names.add(tname)
            if roman is not None:
                key = (ROMAN_TO_NAME[roman], section)
                if key not in class_by_key:
                    missing_classes.add(key)
    if unknown_names:
        raise SystemExit(f"ABORT — teacher names with no mapping: {sorted(unknown_names)}")
    if missing_classes:
        raise SystemExit(f"ABORT — class+section not found in DB: {sorted(missing_classes)}")
    print("Validation passed: all teachers mapped, all classes resolve.")

    # ── 1. Wipe previous output of this script ───────────────────────────────
    d1 = await db.users.delete_many({"source": SEED_TAG})
    d2 = await db.auth_users.delete_many({"source": SEED_TAG})
    d3 = await db.subjects.delete_many({})
    d4 = await db.period_links.delete_many({})
    d5 = await db.staff.delete_many({"source": SEED_TAG})
    print(f"Cleared: users={d1.deleted_count} auth={d2.deleted_count} "
          f"subjects={d3.deleted_count} period_links={d4.deleted_count} "
          f"staff={d5.deleted_count}")

    # ── 1b. Remove the 7 demo/dummy teachers (user-teacher-001..007) ─────────
    demo = {"user_id": {"$regex": "^user-teacher-"}}
    demo_uid = {"id": {"$regex": "^user-teacher-"}}
    demo_auth = {"user_info.id": {"$regex": "^user-teacher-"}}
    r1 = await db.users.delete_many(demo_uid)
    r2 = await db.auth_users.delete_many(demo_auth)
    r3 = await db.staff.delete_many(demo)
    print(f"Removed demo teachers: users={r1.deleted_count} "
          f"auth={r2.deleted_count} staff={r3.deleted_count}")

    # ── 2. Create teacher users + auth_users ─────────────────────────────────
    # Usernames must be unique on (username_lower, schoolId) across ALL auth_users
    # (students/staff included). Load the existing names so we can disambiguate.
    existing_auth = await db.auth_users.find(
        {"schoolId": SCHOOL_ID, "source": {"$ne": SEED_TAG}}, {"_id": 0, "username_lower": 1}
    ).to_list(20_000)
    taken_lower: set[str] = {d["username_lower"] for d in existing_auth}

    # dir_uuid[i] = uuid for directory row i (1-based); extra_uuid[name] for extras.
    dir_uuid: dict[int, str] = {}
    extra_uuid: dict[str, str] = {}
    user_docs: list[dict] = []
    auth_docs: list[dict] = []
    staff_docs: list[dict] = []
    renamed: list[tuple[str, str]] = []
    emp_seq = 0

    def unique_username(name: str) -> str:
        """Keep the name verbatim; only on a clash (vs a student/staff of the same
        name) append a ' (Teacher)' marker so the unique index is satisfied."""
        if name.lower() not in taken_lower:
            taken_lower.add(name.lower())
            return name
        for suffix in [" (Teacher)"] + [f" (Teacher {i})" for i in range(2, 20)]:
            cand = name + suffix
            if cand.lower() not in taken_lower:
                taken_lower.add(cand.lower())
                renamed.append((name, cand))
                return cand
        raise SystemExit(f"ABORT — cannot disambiguate username {name!r}")

    def add_teacher(name: str, mobile: str, gender: str, is_ct: bool) -> str:
        nonlocal emp_seq
        uid = gid()
        uname = unique_username(name)
        password = mobile if mobile else FALLBACK_PW
        sub_cat = "class_teacher" if is_ct else "subject_teacher"
        user_docs.append({
            "id": uid, "schoolId": SCHOOL_ID, "name": name, "role": "teacher",
            "sub_category": sub_cat, "phone": mobile or None,
            "gender": gender or None, "is_class_teacher": is_ct,
            "preferred_language": "en", "theme": "light", "is_active": True,
            "source": SEED_TAG,
        })
        auth_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID,
            "username": uname, "username_lower": uname.lower(),
            "password_hash": hash_pw(password),
            "role": "teacher", "is_active": True, "must_change_password": False,
            "source": SEED_TAG,
            "user_info": {"id": uid, "name": name, "role": "teacher",
                          "sub_category": sub_cat, "initials": initials(name)},
        })
        emp_seq += 1
        staff_docs.append({
            "id": gid(), "schoolId": SCHOOL_ID, "user_id": uid,
            "name": name, "staff_type": "teacher", "role": "teacher",
            "sub_category": sub_cat,
            "employee_id": f"TCH-{emp_seq:04d}",
            "designation": "Class Teacher" if is_ct else "Teacher",
            "department": None, "subject": None, "salary": None,
            "branch_id": BRANCH_ID, "is_active": True,
            "phone": mobile or None, "gender": gender or None,
            "email": None, "address": None,
            "casual_leave_balance": 12, "medical_leave_balance": 10,
            "earned_leave_balance": 15,
            "join_date": None, "created_at": NOW, "source": SEED_TAG,
        })
        return uid

    print(f"Hashing {len(DIRECTORY) + len(EXTRA_TEACHERS)} teacher passwords...")
    for idx, (first, last, mobile, gender, is_ct) in enumerate(DIRECTORY, start=1):
        full = f"{first} {last}".strip() if last else first
        dir_uuid[idx] = add_teacher(full, mobile, gender, is_ct)
    for name in EXTRA_TEACHERS:
        extra_uuid[name] = add_teacher(name, "", "", False)

    await db.users.insert_many(user_docs)
    await db.auth_users.insert_many(auth_docs)
    await db.staff.insert_many(staff_docs)
    await db.auth_users.create_index("username_lower")
    print(f"  ✓ {len(user_docs)} teacher users, {len(auth_docs)} auth_users, "
          f"{len(staff_docs)} staff "
          f"({len(DIRECTORY)} directory + {len(EXTRA_TEACHERS)} allocation-only)")
    for orig, new in renamed:
        print(f"    ⚠ username clash: {orig!r} already taken → login as {new!r} "
              f"(name field unchanged; password = mobile)")

    # ── 3. Resolve a subject-doc teacher name -> teacher_id (or None) ────────
    def teacher_id_for(tname: str) -> str | None:
        if tname in BLANK_TEACHERS:
            return None
        if tname in NAME_TO_DIR:
            return dir_uuid[NAME_TO_DIR[tname]]
        if tname in NAME_TO_EXTRA:
            return extra_uuid[tname]
        raise SystemExit(f"ABORT — unresolved teacher {tname!r}")

    # ── 4. Build subjects + matching period_links ────────────────────────────
    subject_docs: list[dict] = []
    period_docs: list[dict] = []
    skipped = 0
    blank_count = 0

    for subj_name, rows in SUBJECTS.items():
        for roman, section, tname in rows:
            if tname in SKIP_TEACHERS:
                skipped += 1
                continue
            class_id = class_by_key[(ROMAN_TO_NAME[roman], section)] if roman else None
            tid = teacher_id_for(tname)
            if tid is None:
                blank_count += 1

            sid = gid()
            subject_docs.append({
                "id": sid, "schoolId": SCHOOL_ID,
                "class_id": class_id, "name": subj_name,
                "teacher_id": tid, "max_marks": 100, "pass_marks": 33,
                "created_by": None, "created_at": NOW,
            })
            period_docs.append({
                "id": gid(), "schoolId": SCHOOL_ID,
                "class_id": class_id, "subject_id": sid, "teacher_id": tid,
                "day_of_week": None, "period_number": None,
                "start_time": None, "end_time": None,
                "room": None, "academic_year_id": None,
            })

    CHUNK = 500
    for s in range(0, len(subject_docs), CHUNK):
        await db.subjects.insert_many(subject_docs[s:s + CHUNK])
    for s in range(0, len(period_docs), CHUNK):
        await db.period_links.insert_many(period_docs[s:s + CHUNK])

    print(f"  ✓ {len(subject_docs)} subjects + {len(period_docs)} period_links")
    print(f"    (skipped {skipped} PGT/Phy placeholder rows; "
          f"{blank_count} rows seeded with teacher_id=None for Shalini/Kirti)")

    client.close()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(seed())
