"""
Migration 005: Add library_books and library_transactions collections.
Run: python backend/migrations/005_add_library.py
"""
import asyncio
import os
import random
from pathlib import Path
from datetime import datetime, date, timedelta

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

BRANCH_ID = "branch-aaryans-joya"

BOOKS = [
    # NCERT Textbooks
    {"id": "book-001", "title": "Mathematics - Class 9 (NCERT)", "author": "NCERT", "isbn": "978-81-7450-489-1", "category": "textbook", "subject": "Mathematics", "class_level": "9", "publisher": "NCERT", "copies_total": 30, "copies_available": 26, "rack_number": "A-1", "price": 120},
    {"id": "book-002", "title": "Mathematics - Class 10 (NCERT)", "author": "NCERT", "isbn": "978-81-7450-490-7", "category": "textbook", "subject": "Mathematics", "class_level": "10", "publisher": "NCERT", "copies_total": 25, "copies_available": 22, "rack_number": "A-1", "price": 130},
    {"id": "book-003", "title": "Science - Class 9 (NCERT)", "author": "NCERT", "isbn": "978-81-7450-491-4", "category": "textbook", "subject": "Science", "class_level": "9", "publisher": "NCERT", "copies_total": 30, "copies_available": 28, "rack_number": "A-2", "price": 140},
    {"id": "book-004", "title": "Science - Class 10 (NCERT)", "author": "NCERT", "isbn": "978-81-7450-492-1", "category": "textbook", "subject": "Science", "class_level": "10", "publisher": "NCERT", "copies_total": 25, "copies_available": 23, "rack_number": "A-2", "price": 150},
    {"id": "book-005", "title": "English - Beehive (Class 9)", "author": "NCERT", "isbn": "978-81-7450-493-8", "category": "textbook", "subject": "English", "class_level": "9", "publisher": "NCERT", "copies_total": 30, "copies_available": 27, "rack_number": "A-3", "price": 100},
    {"id": "book-006", "title": "English - First Flight (Class 10)", "author": "NCERT", "isbn": "978-81-7450-494-5", "category": "textbook", "subject": "English", "class_level": "10", "publisher": "NCERT", "copies_total": 25, "copies_available": 24, "rack_number": "A-3", "price": 110},
    {"id": "book-007", "title": "Hindi Kshitij Bhag-1 (Class 9)", "author": "NCERT", "isbn": "978-81-7450-495-2", "category": "textbook", "subject": "Hindi", "class_level": "9", "publisher": "NCERT", "copies_total": 30, "copies_available": 29, "rack_number": "A-4", "price": 95},
    {"id": "book-008", "title": "Hindi Kshitij Bhag-2 (Class 10)", "author": "NCERT", "isbn": "978-81-7450-496-9", "category": "textbook", "subject": "Hindi", "class_level": "10", "publisher": "NCERT", "copies_total": 25, "copies_available": 24, "rack_number": "A-4", "price": 100},
    {"id": "book-009", "title": "Social Science - India and Contemporary World (Class 9)", "author": "NCERT", "isbn": "978-81-7450-497-6", "category": "textbook", "subject": "Social Science", "class_level": "9", "publisher": "NCERT", "copies_total": 30, "copies_available": 28, "rack_number": "A-5", "price": 115},
    {"id": "book-010", "title": "Social Science - Understanding Economic Development (Class 10)", "author": "NCERT", "isbn": "978-81-7450-498-3", "category": "textbook", "subject": "Social Science", "class_level": "10", "publisher": "NCERT", "copies_total": 25, "copies_available": 23, "rack_number": "A-5", "price": 120},
    {"id": "book-011", "title": "Physics Part-I (Class 11)", "author": "NCERT", "isbn": "978-81-7450-499-0", "category": "textbook", "subject": "Physics", "class_level": "11", "publisher": "NCERT", "copies_total": 15, "copies_available": 14, "rack_number": "B-1", "price": 160},
    {"id": "book-012", "title": "Chemistry Part-I (Class 12)", "author": "NCERT", "isbn": "978-81-7450-500-3", "category": "textbook", "subject": "Chemistry", "class_level": "12", "publisher": "NCERT", "copies_total": 15, "copies_available": 13, "rack_number": "B-2", "price": 170},

    # Fiction
    {"id": "book-013", "title": "The Story of My Experiments with Truth", "author": "Mahatma Gandhi", "isbn": "978-01-4044-978-1", "category": "biography", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 5, "copies_available": 3, "rack_number": "C-1", "price": 250},
    {"id": "book-014", "title": "Wings of Fire", "author": "A.P.J. Abdul Kalam", "isbn": "978-81-7371-146-6", "category": "biography", "subject": None, "class_level": None, "publisher": "Universities Press", "copies_total": 5, "copies_available": 3, "rack_number": "C-1", "price": 280},
    {"id": "book-015", "title": "The Alchemist", "author": "Paulo Coelho", "isbn": "978-00-6112-008-4", "category": "fiction", "subject": None, "class_level": None, "publisher": "HarperOne", "copies_total": 4, "copies_available": 2, "rack_number": "C-2", "price": 300},
    {"id": "book-016", "title": "Godan", "author": "Munshi Premchand", "isbn": "978-81-2670-524-7", "category": "fiction", "subject": None, "class_level": None, "publisher": "Rajkamal Prakashan", "copies_total": 5, "copies_available": 4, "rack_number": "C-2", "price": 180},
    {"id": "book-017", "title": "Panch Parmeshwar", "author": "Munshi Premchand", "isbn": "978-81-2670-525-4", "category": "fiction", "subject": None, "class_level": None, "publisher": "Rajkamal Prakashan", "copies_total": 5, "copies_available": 5, "rack_number": "C-2", "price": 150},
    {"id": "book-018", "title": "The Discovery of India", "author": "Jawaharlal Nehru", "isbn": "978-01-4303-103-4", "category": "biography", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 3, "copies_available": 2, "rack_number": "C-1", "price": 350},
    {"id": "book-019", "title": "Gitanjali", "author": "Rabindranath Tagore", "isbn": "978-93-5064-857-0", "category": "fiction", "subject": None, "class_level": None, "publisher": "Fingerprint Classics", "copies_total": 4, "copies_available": 4, "rack_number": "C-3", "price": 199},
    {"id": "book-020", "title": "Raag Darbari", "author": "Shrilal Shukla", "isbn": "978-81-7178-127-9", "category": "fiction", "subject": None, "class_level": None, "publisher": "Rajkamal", "copies_total": 3, "copies_available": 3, "rack_number": "C-2", "price": 220},
    {"id": "book-021", "title": "The White Tiger", "author": "Aravind Adiga", "isbn": "978-14-1603-621-3", "category": "fiction", "subject": None, "class_level": None, "publisher": "Free Press", "copies_total": 3, "copies_available": 2, "rack_number": "C-3", "price": 350},
    {"id": "book-022", "title": "Train to Pakistan", "author": "Khushwant Singh", "isbn": "978-01-4303-564-3", "category": "fiction", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 4, "copies_available": 3, "rack_number": "C-3", "price": 250},
    {"id": "book-023", "title": "Malgudi Days", "author": "R.K. Narayan", "isbn": "978-01-4118-054-3", "category": "fiction", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 5, "copies_available": 4, "rack_number": "C-3", "price": 230},

    # Reference
    {"id": "book-024", "title": "Oxford English-Hindi Dictionary", "author": "S.K. Verma", "isbn": "978-01-9564-510-0", "category": "reference", "subject": "English", "class_level": None, "publisher": "Oxford University Press", "copies_total": 3, "copies_available": 3, "rack_number": "D-1", "price": 500},
    {"id": "book-025", "title": "Encyclopaedia Britannica - Students Edition", "author": "Britannica", "isbn": "978-15-9339-292-5", "category": "reference", "subject": None, "class_level": None, "publisher": "Encyclopaedia Britannica", "copies_total": 2, "copies_available": 2, "rack_number": "D-1", "price": 1200},
    {"id": "book-026", "title": "Concise Oxford Dictionary", "author": "Oxford", "isbn": "978-01-9968-113-7", "category": "reference", "subject": "English", "class_level": None, "publisher": "Oxford", "copies_total": 3, "copies_available": 3, "rack_number": "D-1", "price": 700},
    {"id": "book-027", "title": "Atlas of the World", "author": "National Geographic", "isbn": "978-14-2621-860-2", "category": "reference", "subject": "Geography", "class_level": None, "publisher": "National Geographic", "copies_total": 2, "copies_available": 2, "rack_number": "D-2", "price": 900},
    {"id": "book-028", "title": "R.D. Sharma Mathematics Class 9", "author": "R.D. Sharma", "isbn": "978-93-5274-480-1", "category": "reference", "subject": "Mathematics", "class_level": "9", "publisher": "Dhanpat Rai", "copies_total": 10, "copies_available": 8, "rack_number": "B-3", "price": 450},
    {"id": "book-029", "title": "R.D. Sharma Mathematics Class 10", "author": "R.D. Sharma", "isbn": "978-93-5274-481-8", "category": "reference", "subject": "Mathematics", "class_level": "10", "publisher": "Dhanpat Rai", "copies_total": 10, "copies_available": 9, "rack_number": "B-3", "price": 480},
    {"id": "book-030", "title": "HC Verma - Concepts of Physics Vol-1", "author": "H.C. Verma", "isbn": "978-81-7709-187-2", "category": "reference", "subject": "Physics", "class_level": "11", "publisher": "Bharati Bhawan", "copies_total": 8, "copies_available": 7, "rack_number": "B-1", "price": 400},

    # More fiction / general
    {"id": "book-031", "title": "Diary of a Young Girl", "author": "Anne Frank", "isbn": "978-01-4303-601-5", "category": "biography", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 4, "copies_available": 3, "rack_number": "C-1", "price": 275},
    {"id": "book-032", "title": "I Am Malala", "author": "Malala Yousafzai", "isbn": "978-03-1632-240-8", "category": "biography", "subject": None, "class_level": None, "publisher": "Little Brown", "copies_total": 3, "copies_available": 2, "rack_number": "C-1", "price": 320},
    {"id": "book-033", "title": "The Jungle Book", "author": "Rudyard Kipling", "isbn": "978-01-4106-734-1", "category": "fiction", "subject": None, "class_level": None, "publisher": "Penguin Classics", "copies_total": 5, "copies_available": 5, "rack_number": "C-4", "price": 180},
    {"id": "book-034", "title": "Treasure Island", "author": "R.L. Stevenson", "isbn": "978-01-4132-760-1", "category": "fiction", "subject": None, "class_level": None, "publisher": "Penguin Classics", "copies_total": 4, "copies_available": 4, "rack_number": "C-4", "price": 190},
    {"id": "book-035", "title": "Alice in Wonderland", "author": "Lewis Carroll", "isbn": "978-01-4143-976-4", "category": "fiction", "subject": None, "class_level": None, "publisher": "Penguin Classics", "copies_total": 5, "copies_available": 5, "rack_number": "C-4", "price": 170},
    {"id": "book-036", "title": "A Brief History of Time", "author": "Stephen Hawking", "isbn": "978-05-5338-016-3", "category": "reference", "subject": "Science", "class_level": None, "publisher": "Bantam", "copies_total": 2, "copies_available": 2, "rack_number": "D-2", "price": 450},
    {"id": "book-037", "title": "Sapiens", "author": "Yuval Noah Harari", "isbn": "978-00-6231-609-7", "category": "reference", "subject": "History", "class_level": None, "publisher": "Harper", "copies_total": 3, "copies_available": 2, "rack_number": "D-2", "price": 500},
    {"id": "book-038", "title": "India After Gandhi", "author": "Ramachandra Guha", "isbn": "978-03-3039-611-0", "category": "reference", "subject": "History", "class_level": None, "publisher": "Picador", "copies_total": 2, "copies_available": 2, "rack_number": "D-2", "price": 550},
    {"id": "book-039", "title": "Chanakya's Chant", "author": "Ashwin Sanghi", "isbn": "978-93-8065-835-4", "category": "fiction", "subject": None, "class_level": None, "publisher": "Westland", "copies_total": 3, "copies_available": 3, "rack_number": "C-3", "price": 225},
    {"id": "book-040", "title": "Five Point Someone", "author": "Chetan Bhagat", "isbn": "978-81-2910-367-3", "category": "fiction", "subject": None, "class_level": None, "publisher": "Rupa", "copies_total": 5, "copies_available": 4, "rack_number": "C-4", "price": 175},
    {"id": "book-041", "title": "Chemistry - Class 11 (NCERT)", "author": "NCERT", "isbn": "978-81-7450-501-0", "category": "textbook", "subject": "Chemistry", "class_level": "11", "publisher": "NCERT", "copies_total": 15, "copies_available": 14, "rack_number": "B-2", "price": 165},
    {"id": "book-042", "title": "Biology - Class 11 (NCERT)", "author": "NCERT", "isbn": "978-81-7450-502-7", "category": "textbook", "subject": "Biology", "class_level": "11", "publisher": "NCERT", "copies_total": 15, "copies_available": 14, "rack_number": "B-2", "price": 155},
    {"id": "book-043", "title": "Accountancy Part-I (Class 11)", "author": "NCERT", "isbn": "978-81-7450-503-4", "category": "textbook", "subject": "Accountancy", "class_level": "11", "publisher": "NCERT", "copies_total": 10, "copies_available": 10, "rack_number": "B-3", "price": 140},
    {"id": "book-044", "title": "Business Studies (Class 12)", "author": "NCERT", "isbn": "978-81-7450-504-1", "category": "textbook", "subject": "Business Studies", "class_level": "12", "publisher": "NCERT", "copies_total": 10, "copies_available": 10, "rack_number": "B-3", "price": 135},
    {"id": "book-045", "title": "Computer Science with Python (Class 11)", "author": "Sumita Arora", "isbn": "978-93-5274-482-5", "category": "textbook", "subject": "Computer Science", "class_level": "11", "publisher": "Dhanpat Rai", "copies_total": 10, "copies_available": 9, "rack_number": "B-4", "price": 380},
    {"id": "book-046", "title": "Nirmala", "author": "Munshi Premchand", "isbn": "978-81-2670-526-1", "category": "fiction", "subject": None, "class_level": None, "publisher": "Rajkamal", "copies_total": 4, "copies_available": 4, "rack_number": "C-2", "price": 160},
    {"id": "book-047", "title": "Madhushala", "author": "Harivansh Rai Bachchan", "isbn": "978-81-7119-295-0", "category": "fiction", "subject": None, "class_level": None, "publisher": "Rajpal & Sons", "copies_total": 3, "copies_available": 3, "rack_number": "C-2", "price": 125},
    {"id": "book-048", "title": "Ignited Minds", "author": "A.P.J. Abdul Kalam", "isbn": "978-01-4302-877-5", "category": "biography", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 4, "copies_available": 3, "rack_number": "C-1", "price": 260},
    {"id": "book-049", "title": "Swami and Friends", "author": "R.K. Narayan", "isbn": "978-81-8515-020-5", "category": "fiction", "subject": None, "class_level": None, "publisher": "Indian Thought", "copies_total": 5, "copies_available": 4, "rack_number": "C-3", "price": 195},
    {"id": "book-050", "title": "The Guide", "author": "R.K. Narayan", "isbn": "978-01-4118-953-9", "category": "fiction", "subject": None, "class_level": None, "publisher": "Penguin", "copies_total": 4, "copies_available": 3, "rack_number": "C-3", "price": 210},
]


async def migrate(db=None):
    client = None
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
        db = client[DB_NAME]

    try:
        print("=" * 60)
        print("Migration 005: Add library")
        print("=" * 60)

        # 1. Insert books
        inserted = 0
        skipped = 0
        for book in BOOKS:
            existing = await db.library_books.find_one({"id": book["id"]})
            if existing:
                skipped += 1
                continue

            doc = {
                **book,
                "branch_id": BRANCH_ID,
                "is_active": True,
                "created_at": datetime.now().isoformat(),
            }
            await db.library_books.insert_one(doc)
            inserted += 1

        print(f"  Inserted {inserted} books, skipped {skipped} already existing")

        # 2. Create sample transactions
        existing_txns = await db.library_transactions.count_documents({})
        if existing_txns > 0:
            print(f"  library_transactions already has {existing_txns} records, skipping.")
        else:
            # Get some student IDs for borrowers
            students = []
            cursor = db.students.find({}, {"id": 1, "name": 1})
            async for s in cursor:
                students.append(s)

            random.seed(55)

            today = date.today()
            transactions = []

            # 8 issued (active) transactions
            issued_books = ["book-013", "book-014", "book-015", "book-021", "book-028", "book-031", "book-032", "book-037"]
            for i, book_id in enumerate(issued_books):
                student = students[i % len(students)]
                issue_date = today - timedelta(days=random.randint(3, 12))
                due_date = issue_date + timedelta(days=14)
                transactions.append({
                    "id": f"lt-{i+1:03d}",
                    "branch_id": BRANCH_ID,
                    "book_id": book_id,
                    "borrower_id": student["id"],
                    "borrower_name": student["name"],
                    "borrower_type": "student",
                    "issue_date": issue_date.strftime("%Y-%m-%d"),
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "return_date": None,
                    "status": "issued",
                    "fine_amount": 0,
                    "issued_by": "staff-002",
                    "created_at": datetime.now().isoformat(),
                })

            # 2 overdue transactions
            overdue_books = ["book-040", "book-050"]
            for i, book_id in enumerate(overdue_books):
                student = students[(i + 10) % len(students)]
                issue_date = today - timedelta(days=random.randint(20, 30))
                due_date = issue_date + timedelta(days=14)
                days_overdue = (today - due_date).days
                fine = days_overdue * 2  # Rs 2 per day fine
                transactions.append({
                    "id": f"lt-{len(issued_books)+i+1:03d}",
                    "branch_id": BRANCH_ID,
                    "book_id": book_id,
                    "borrower_id": student["id"],
                    "borrower_name": student["name"],
                    "borrower_type": "student",
                    "issue_date": issue_date.strftime("%Y-%m-%d"),
                    "due_date": due_date.strftime("%Y-%m-%d"),
                    "return_date": None,
                    "status": "overdue",
                    "fine_amount": fine,
                    "issued_by": "staff-002",
                    "created_at": datetime.now().isoformat(),
                })

            await db.library_transactions.insert_many(transactions)
            print(f"  Created {len(transactions)} library transactions (8 issued, 2 overdue)")

        # 3. Create indexes
        lb_indexes = await db.library_books.index_information()
        if "category_1" not in lb_indexes:
            await db.library_books.create_index("category")
            print("  Created index on library_books.category")
        if "branch_id_1" not in lb_indexes:
            await db.library_books.create_index("branch_id")
            print("  Created index on library_books.branch_id")

        lt_indexes = await db.library_transactions.index_information()
        if "borrower_id_1" not in lt_indexes:
            await db.library_transactions.create_index("borrower_id")
            print("  Created index on library_transactions.borrower_id")
        if "status_1" not in lt_indexes:
            await db.library_transactions.create_index("status")
            print("  Created index on library_transactions.status")
        if "branch_id_1" not in lt_indexes:
            await db.library_transactions.create_index("branch_id")
            print("  Created index on library_transactions.branch_id")

        print("\nMigration 005 complete.")

    finally:
        if client:
            client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
