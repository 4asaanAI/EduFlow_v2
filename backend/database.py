from motor.motor_asyncio import AsyncIOMotorClient
import os
import ssl

_client = None
_db = None


async def connect_db():
    global _client, _db
    mongo_url = os.environ["MONGO_URL"]

    # Connection options for MongoDB Atlas
    client_options = {
        "serverSelectionTimeoutMS": 10000,
        "tlsInsecure": True,
        "retryWrites": True,
    }

    _client = AsyncIOMotorClient(mongo_url, **client_options)
    _db = _client[os.environ["DB_NAME"]]

    # Test connection
    try:
        await _db.command("ping")
        print("✓ MongoDB connected successfully")
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")
        raise

    await _create_indexes()


async def disconnect_db():
    if _client:
        _client.close()


def get_db():
    return _db


async def _create_indexes():
    db = _db
    await db.students.create_index("class_id")
    await db.students.create_index("admission_number", unique=True, sparse=True)
    await db.student_attendance.create_index(
        [("student_id", 1), ("date", 1)], unique=True
    )
    await db.staff_attendance.create_index(
        [("staff_id", 1), ("date", 1)], unique=True
    )
    await db.fee_transactions.create_index("student_id")
    await db.fee_transactions.create_index("status")
    await db.messages.create_index("conversation_id")
    await db.conversations.create_index("user_id")
    await db.assignments.create_index("class_id")
    await db.leave_requests.create_index("staff_id")
    await db.enquiries.create_index("status")
