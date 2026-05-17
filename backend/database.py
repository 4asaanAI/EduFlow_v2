from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import time
from tenant import add_school_id, get_school_id, scoped_filter
from logging_config import request_id_ctx

_client = None
_db = None
logger = logging.getLogger(__name__)
SLOW_QUERY_MS = int(os.environ.get("SLOW_QUERY_MS", "100"))


SYSTEM_COLLECTIONS = {
    "_migrations",
    "auth_users",
    "login_attempts",
    "refresh_tokens",
}


def _slow_query_threshold_ms() -> int:
    try:
        return int(os.environ.get("SLOW_QUERY_MS", str(SLOW_QUERY_MS)))
    except ValueError:
        return SLOW_QUERY_MS


class TimedQuery:
    def __init__(self, *, collection_name: str, operation: str, query_shape: str = ""):
        self.collection_name = collection_name
        self.operation = operation
        self.query_shape = query_shape or operation
        self.elapsed_ms = 0.0
        self._started = 0.0

    async def __aenter__(self):
        self._started = time.time()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.elapsed_ms = round((time.time() - self._started) * 1000, 1)
        threshold = _slow_query_threshold_ms()
        if self.elapsed_ms > threshold:
            logger.debug(
                "slow_query",
                extra={
                    "collection": self.collection_name,
                    "operation": self.operation,
                    "elapsed_ms": self.elapsed_ms,
                    "query_shape": self.query_shape,
                    "slow_query": True,
                    "event_loop_congestion": self.elapsed_ms > threshold * 3,
                    "request_id": request_id_ctx.get(),
                },
            )
        return False


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
        "maxPoolSize": 50,    # EC-16.3: explicit pool limit before load tests
        "minPoolSize": 5,
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
    # Token budget indexes
    await db.token_balances.create_index("branch_id", unique=True)
    await db.token_usage.create_index([("branch_id", 1), ("user_id", 1), ("month", 1)])
    await db.token_usage.create_index("created_at")
    await db.token_purchases.create_index("payment_id", unique=True, sparse=True)
    await db.token_purchases.create_index(
        [("stripe_session_id", 1)],
        unique=True,
        sparse=True,
        name="token_purchases_stripe_session_id",
    )
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("user_id")
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token", unique=True)
    await db.password_reset_tokens.create_index("user_id")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_requests.create_index([("email", 1), ("created_at", 1)])
    await db.confirm_tokens.create_index("token", unique=True)
    await db.confirm_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.idempotency_keys.create_index("key", unique=True)
    await db.idempotency_keys.create_index("expires_at", expireAfterSeconds=0)
    await db.notifications.create_index(
        [("schoolId", 1), ("user_id", 1), ("read", 1), ("created_at", -1)]
    )
    await db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    await db.audit_logs.create_index([("schoolId", 1), ("created_at", -1)])
    await db.audit_logs.create_index([("schoolId", 1), ("entity_id", 1), ("created_at", -1)])
    # Part 9 pre-infra: missing indexes for role-vertical queries
    await db.exam_results.create_index([("student_id", 1), ("exam_id", 1)])
    await db.exam_results.create_index([("exam_id", 1), ("student_id", 1), ("subject_id", 1)])
    await db.audit_logs.create_index([("actor_id", 1), ("created_at", -1)])
    await db.audit_logs.create_index([("entity_type", 1), ("entity_id", 1)])
    await db.lesson_plans.create_index([("class_id", 1), ("week", 1)])
    await db.sms_logs.create_index("created_at", expireAfterSeconds=7776000)
    await db.notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    # Part 10: Payroll disbursement unique index (EC-10.4 — prevents concurrent double-disbursement)
    try:
        await db.salary_disbursements.create_index(
            [("schoolId", 1), ("staff_id", 1), ("month", 1)], unique=True
        )
    except Exception:
        pass  # Index may already exist
    # Part 13: Branch code unique index — prevents concurrent branch creation race condition (EC-13.2)
    try:
        await db.branches.create_index(
            [("schoolId", 1), ("branch_code", 1)], unique=True
        )
    except Exception:
        pass  # Index may already exist
    # Part 16: Performance indexes for teacher-facing queries
    await db.ptm_notes.create_index([("teacher_id", 1), ("student_id", 1)])
    await db.question_papers.create_index([("teacher_id", 1), ("created_at", -1)])
    await db.lesson_plans.create_index([("teacher_id", 1), ("created_at", -1)])
    # curriculum_progress unique compound index
    try:
        await db.curriculum_progress.create_index(
            [("class_id", 1), ("subject_id", 1), ("topic", 1)], unique=True
        )
    except Exception:
        pass
