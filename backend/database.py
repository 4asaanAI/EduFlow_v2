from motor.motor_asyncio import AsyncIOMotorClient
import os

_client = None
_db = None


async def connect_db():
    global _client, _db
    mongo_url = os.environ.get("MONGO_URL")

    if not mongo_url:
        raise ValueError("MONGO_URL environment variable is required")

    if not mongo_url.startswith("mongodb+srv://") and not mongo_url.startswith("mongodb://"):
        raise ValueError("MONGO_URL must be a valid MongoDB connection string (mongodb:// or mongodb+srv://)")

    client_options = {
        "serverSelectionTimeoutMS": 10000,
        "retryWrites": True,
    }

    _client = AsyncIOMotorClient(mongo_url, **client_options)
    _db = _client[os.environ["DB_NAME"]]

    # Test connection
    try:
        await _db.command("ping")
        print("✓ MongoDB connected successfully")
        await _create_indexes()
    except Exception as e:
        print(f"✗ MongoDB connection failed: {e}")


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
    # OTP TTL index — auto-deletes expired OTP documents
    await db.otps.create_index("expires_at", expireAfterSeconds=0)
    await db.otps.create_index("phone")
    # Token budget indexes
    await db.token_balances.create_index("branch_id", unique=True)
    await db.token_usage.create_index([("branch_id", 1), ("user_id", 1), ("month", 1)])
    await db.token_usage.create_index("created_at")
    await db.token_purchases.create_index("payment_id", unique=True)
