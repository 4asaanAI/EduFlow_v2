"""
Migration 008: Add school_events, sports_teams, and clubs collections.
Run: python backend/migrations/008_add_events_sports.py
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

EVENTS = [
    {
        "id": "event-001",
        "name": "Republic Day Celebration",
        "type": "national_day",
        "description": "Flag hoisting ceremony, patriotic song performances, and speech competition",
        "start_date": "2026-01-26",
        "end_date": "2026-01-26",
        "start_time": "08:00",
        "end_time": "11:00",
        "venue": "School Ground",
        "chief_guest": "Block Education Officer",
        "is_holiday": False,
        "audience": "all",
    },
    {
        "id": "event-002",
        "name": "Basant Panchami Celebration",
        "type": "cultural",
        "description": "Saraswati Puja and cultural program celebrating the onset of spring",
        "start_date": "2026-02-01",
        "end_date": "2026-02-01",
        "start_time": "09:00",
        "end_time": "12:00",
        "venue": "School Auditorium",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "all",
    },
    {
        "id": "event-003",
        "name": "Annual PTM - I",
        "type": "ptm",
        "description": "First Parent Teacher Meeting for academic year 2025-26. Report card distribution and parent counselling.",
        "start_date": "2025-07-15",
        "end_date": "2025-07-15",
        "start_time": "10:00",
        "end_time": "14:00",
        "venue": "Respective Classrooms",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "parents",
    },
    {
        "id": "event-004",
        "name": "Mid-Term Examination Week",
        "type": "exam",
        "description": "Mid-term examinations for all classes (9-12). No regular classes during this week.",
        "start_date": "2025-09-15",
        "end_date": "2025-09-22",
        "start_time": "09:00",
        "end_time": "12:00",
        "venue": "Examination Halls",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "students",
    },
    {
        "id": "event-005",
        "name": "Diwali Vacation",
        "type": "holiday",
        "description": "School closed for Diwali celebrations",
        "start_date": "2025-10-18",
        "end_date": "2025-10-27",
        "start_time": None,
        "end_time": None,
        "venue": None,
        "chief_guest": None,
        "is_holiday": True,
        "audience": "all",
    },
    {
        "id": "event-006",
        "name": "Annual PTM - II",
        "type": "ptm",
        "description": "Second Parent Teacher Meeting. Mid-term result discussion and progress review.",
        "start_date": "2025-11-08",
        "end_date": "2025-11-08",
        "start_time": "10:00",
        "end_time": "14:00",
        "venue": "Respective Classrooms",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "parents",
    },
    {
        "id": "event-007",
        "name": "Science Exhibition",
        "type": "academic",
        "description": "Inter-house science project exhibition. Working models and poster presentations.",
        "start_date": "2025-11-28",
        "end_date": "2025-11-28",
        "start_time": "09:00",
        "end_time": "15:00",
        "venue": "School Hall",
        "chief_guest": "Dr. Pradeep Mishra (District Science Officer)",
        "is_holiday": False,
        "audience": "all",
    },
    {
        "id": "event-008",
        "name": "Winter Break",
        "type": "holiday",
        "description": "Winter vacation for all students and staff",
        "start_date": "2025-12-25",
        "end_date": "2026-01-05",
        "start_time": None,
        "end_time": None,
        "venue": None,
        "chief_guest": None,
        "is_holiday": True,
        "audience": "all",
    },
    {
        "id": "event-009",
        "name": "Annual Sports Day",
        "type": "sports",
        "description": "Annual athletics meet with inter-house competitions, track and field events, and prize distribution",
        "start_date": "2026-02-14",
        "end_date": "2026-02-15",
        "start_time": "08:00",
        "end_time": "16:00",
        "venue": "School Ground",
        "chief_guest": "SDM Amroha",
        "is_holiday": False,
        "audience": "all",
    },
    {
        "id": "event-010",
        "name": "Holi Holiday",
        "type": "holiday",
        "description": "School closed for Holi festival",
        "start_date": "2026-03-10",
        "end_date": "2026-03-11",
        "start_time": None,
        "end_time": None,
        "venue": None,
        "chief_guest": None,
        "is_holiday": True,
        "audience": "all",
    },
    {
        "id": "event-011",
        "name": "Pre-Board Examinations",
        "type": "exam",
        "description": "Pre-board examinations for Class 10 and 12 students",
        "start_date": "2026-01-05",
        "end_date": "2026-01-15",
        "start_time": "09:00",
        "end_time": "12:00",
        "venue": "Examination Halls",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "students",
    },
    {
        "id": "event-012",
        "name": "Annual Function & Prize Distribution",
        "type": "cultural",
        "description": "Grand annual cultural program with drama, dance, music performances and annual prize distribution ceremony",
        "start_date": "2026-03-20",
        "end_date": "2026-03-20",
        "start_time": "10:00",
        "end_time": "16:00",
        "venue": "School Auditorium & Ground",
        "chief_guest": "District Magistrate, Amroha",
        "is_holiday": False,
        "audience": "all",
    },
    {
        "id": "event-013",
        "name": "Final Examination Week",
        "type": "exam",
        "description": "End-of-year final examinations for classes 9 and 11",
        "start_date": "2026-03-01",
        "end_date": "2026-03-10",
        "start_time": "09:00",
        "end_time": "12:00",
        "venue": "Examination Halls",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "students",
    },
    {
        "id": "event-014",
        "name": "Independence Day Celebration",
        "type": "national_day",
        "description": "Flag hoisting, march past, cultural performances and independence day quiz",
        "start_date": "2025-08-15",
        "end_date": "2025-08-15",
        "start_time": "07:30",
        "end_time": "10:30",
        "venue": "School Ground",
        "chief_guest": "Sarpanch, Joya",
        "is_holiday": False,
        "audience": "all",
    },
    {
        "id": "event-015",
        "name": "Annual PTM - III (Final)",
        "type": "ptm",
        "description": "Final Parent Teacher Meeting. Annual result discussion and next year admission guidance.",
        "start_date": "2026-03-28",
        "end_date": "2026-03-28",
        "start_time": "10:00",
        "end_time": "14:00",
        "venue": "Respective Classrooms",
        "chief_guest": None,
        "is_holiday": False,
        "audience": "parents",
    },
]

SPORTS_TEAMS = [
    {
        "id": "team-cricket",
        "branch_id": BRANCH_ID,
        "sport": "Cricket",
        "category": "boys",
        "age_group": "U-17",
        "coach_staff_id": "staff-005",
        "coach_name": "Manoj Tiwari",
        "captain_student_id": None,
        "max_members": 15,
        "members": [],
        "practice_schedule": "Tuesday & Thursday, 3:30 PM - 5:00 PM",
        "achievements": ["District runners-up 2024-25"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "team-football",
        "branch_id": BRANCH_ID,
        "sport": "Football",
        "category": "boys",
        "age_group": "U-17",
        "coach_staff_id": "staff-007",
        "coach_name": "Ankit Sharma",
        "captain_student_id": None,
        "max_members": 18,
        "members": [],
        "practice_schedule": "Monday & Wednesday, 3:30 PM - 5:00 PM",
        "achievements": [],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "team-volleyball",
        "branch_id": BRANCH_ID,
        "sport": "Volleyball",
        "category": "mixed",
        "age_group": "U-19",
        "coach_staff_id": "staff-005",
        "coach_name": "Manoj Tiwari",
        "captain_student_id": None,
        "max_members": 12,
        "members": [],
        "practice_schedule": "Friday, 3:30 PM - 5:00 PM",
        "achievements": ["Block level champions 2024-25"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "team-kabaddi",
        "branch_id": BRANCH_ID,
        "sport": "Kabaddi",
        "category": "boys",
        "age_group": "U-17",
        "coach_staff_id": "staff-007",
        "coach_name": "Ankit Sharma",
        "captain_student_id": None,
        "max_members": 12,
        "members": [],
        "practice_schedule": "Saturday, 8:00 AM - 10:00 AM",
        "achievements": ["District level participants 2024-25"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]

CLUBS = [
    {
        "id": "club-science",
        "branch_id": BRANCH_ID,
        "name": "Science Club",
        "description": "Hands-on experiments, science projects, quiz competitions and exhibition preparation",
        "incharge_staff_id": "staff-003",
        "incharge_name": "Rajesh Kumar",
        "meeting_schedule": "Every Wednesday, 2:30 PM - 3:30 PM",
        "max_members": 30,
        "members": [],
        "achievements": ["Best Science Project - District Science Fair 2024"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "club-art",
        "branch_id": BRANCH_ID,
        "name": "Art & Craft Club",
        "description": "Drawing, painting, poster making, clay modelling and craft activities",
        "incharge_staff_id": "staff-006",
        "incharge_name": "Deepa Verma",
        "meeting_schedule": "Every Tuesday, 2:30 PM - 3:30 PM",
        "max_members": 25,
        "members": [],
        "achievements": [],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "club-music",
        "branch_id": BRANCH_ID,
        "name": "Music Club",
        "description": "Vocal music, instrumental practice, patriotic songs and cultural performance preparation",
        "incharge_staff_id": "staff-004",
        "incharge_name": "Sunita Devi",
        "meeting_schedule": "Every Thursday, 2:30 PM - 3:30 PM",
        "max_members": 20,
        "members": [],
        "achievements": ["Best Group Song - Block Cultural Fest 2024"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "club-debate",
        "branch_id": BRANCH_ID,
        "name": "Debate & Elocution Club",
        "description": "Debate, extempore, declamation, essay writing and public speaking practice",
        "incharge_staff_id": "staff-003",
        "incharge_name": "Rajesh Kumar",
        "meeting_schedule": "Every Friday, 2:30 PM - 3:30 PM",
        "max_members": 25,
        "members": [],
        "achievements": ["Inter-school debate finalist 2024"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
    {
        "id": "club-eco",
        "branch_id": BRANCH_ID,
        "name": "Eco Club",
        "description": "Environment awareness, tree plantation drives, waste management and cleanliness campaigns",
        "incharge_staff_id": "staff-006",
        "incharge_name": "Deepa Verma",
        "meeting_schedule": "Every Saturday, 9:00 AM - 10:00 AM",
        "max_members": 30,
        "members": [],
        "achievements": ["Green School Award - District 2024"],
        "is_active": True,
        "created_at": datetime.now().isoformat(),
    },
]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 008: Add events, sports teams & clubs")
        print("=" * 60)

        # 1. Insert events
        inserted_e = 0
        for event in EVENTS:
            existing = await db.school_events.find_one({"id": event["id"]})
            if existing:
                continue
            doc = {
                **event,
                "branch_id": BRANCH_ID,
                "academic_year": "2025-26",
                "status": "scheduled",
                "created_by": "user-owner-001",
                "created_at": datetime.now().isoformat(),
            }
            await db.school_events.insert_one(doc)
            inserted_e += 1
        print(f"  Inserted {inserted_e} school events (skipped {len(EVENTS) - inserted_e})")

        # 2. Insert sports teams with student members
        students = []
        cursor = db.students.find({}, {"id": 1, "name": 1, "gender": 1})
        async for s in cursor:
            students.append(s)

        random.seed(88)
        male_students = [s for s in students if s.get("gender") == "male"]
        female_students = [s for s in students if s.get("gender") == "female"]

        inserted_t = 0
        for team in SPORTS_TEAMS:
            existing = await db.sports_teams.find_one({"id": team["id"]})
            if existing:
                inserted_t += 0
                continue

            # Assign some members
            pool = male_students if team["category"] == "boys" else students
            member_count = min(len(pool), random.randint(8, team["max_members"]))
            selected = random.sample(pool, member_count)
            team["members"] = [{"student_id": s["id"], "name": s["name"], "joined_date": "2025-04-15"} for s in selected]
            if selected:
                team["captain_student_id"] = selected[0]["id"]

            await db.sports_teams.insert_one(team)
            inserted_t += 1
            print(f"  Created team: {team['sport']} ({len(team['members'])} members)")

        # 3. Insert clubs with student members
        inserted_c = 0
        for club in CLUBS:
            existing = await db.clubs.find_one({"id": club["id"]})
            if existing:
                continue

            member_count = min(len(students), random.randint(10, club["max_members"]))
            selected = random.sample(students, member_count)
            club["members"] = [{"student_id": s["id"], "name": s["name"], "joined_date": "2025-04-20"} for s in selected]

            await db.clubs.insert_one(club)
            inserted_c += 1
            print(f"  Created club: {club['name']} ({len(club['members'])} members)")

        # 4. Create indexes
        se_indexes = await db.school_events.index_information()
        if "branch_id_1" not in se_indexes:
            await db.school_events.create_index("branch_id")
        if "type_1" not in se_indexes:
            await db.school_events.create_index("type")
        if "start_date_1" not in se_indexes:
            await db.school_events.create_index("start_date")
        print("  Ensured indexes on school_events")

        st_indexes = await db.sports_teams.index_information()
        if "branch_id_1" not in st_indexes:
            await db.sports_teams.create_index("branch_id")
        print("  Ensured indexes on sports_teams")

        cl_indexes = await db.clubs.index_information()
        if "branch_id_1" not in cl_indexes:
            await db.clubs.create_index("branch_id")
        print("  Ensured indexes on clubs")

        print("\nMigration 008 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
