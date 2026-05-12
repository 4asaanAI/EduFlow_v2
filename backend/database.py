from motor.motor_asyncio import AsyncIOMotorClient
import os
from tenant import add_school_id, get_school_id, scoped_filter

_client = None
_db = None


SYSTEM_COLLECTIONS = {
    "_migrations",
    "auth_users",
    "login_attempts",
    "otps",
    "refresh_tokens",
}


class ScopedCollection:
    def __init__(self, collection, school_id: str):
        self._collection = collection
        self._school_id = school_id

    def __getattr__(self, name):
        return getattr(self._collection, name)

    def find(self, filter=None, *args, **kwargs):
        return self._collection.find(scoped_filter(filter, self._school_id), *args, **kwargs)

    async def find_one(self, filter=None, *args, **kwargs):
        return await self._collection.find_one(scoped_filter(filter, self._school_id), *args, **kwargs)

    async def count_documents(self, filter, *args, **kwargs):
        return await self._collection.count_documents(scoped_filter(filter, self._school_id), *args, **kwargs)

    async def insert_one(self, document, *args, **kwargs):
        return await self._collection.insert_one(add_school_id(document, self._school_id), *args, **kwargs)

    async def insert_many(self, documents, *args, **kwargs):
        return await self._collection.insert_many(
            [add_school_id(doc, self._school_id) for doc in documents],
            *args,
            **kwargs,
        )

    async def update_one(self, filter, update, *args, **kwargs):
        query = {**(filter or {}), "schoolId": self._school_id} if kwargs.get("upsert") else scoped_filter(filter, self._school_id)
        if kwargs.get("upsert"):
            update = {**update, "$setOnInsert": {**update.get("$setOnInsert", {}), "schoolId": self._school_id}}
        return await self._collection.update_one(query, update, *args, **kwargs)

    async def update_many(self, filter, update, *args, **kwargs):
        return await self._collection.update_many(scoped_filter(filter, self._school_id), update, *args, **kwargs)

    async def delete_one(self, filter, *args, **kwargs):
        return await self._collection.delete_one(scoped_filter(filter, self._school_id), *args, **kwargs)

    async def delete_many(self, filter, *args, **kwargs):
        return await self._collection.delete_many(scoped_filter(filter, self._school_id), *args, **kwargs)

    def aggregate(self, pipeline, *args, **kwargs):
        if pipeline and pipeline[0].get("$match", {}).get("schoolId"):
            scoped_pipeline = pipeline
        else:
            scoped_pipeline = [{"$match": scoped_filter({}, self._school_id)}, *(pipeline or [])]
        return self._collection.aggregate(scoped_pipeline, *args, **kwargs)


class ScopedDatabase:
    def __init__(self, db, school_id: str):
        self._db = db
        self._school_id = school_id

    def __getattr__(self, name):
        collection = getattr(self._db, name)
        if callable(collection) or name.startswith("_"):
            return collection
        if name in SYSTEM_COLLECTIONS:
            return collection
        return ScopedCollection(collection, self._school_id)

    def __getitem__(self, name):
        collection = self._db[name]
        if name in SYSTEM_COLLECTIONS:
            return collection
        return ScopedCollection(collection, self._school_id)


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
    return ScopedDatabase(_db, get_school_id())


def get_raw_db():
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
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("user_id")
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("user_id")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_requests.create_index([("email", 1), ("created_at", 1)])
