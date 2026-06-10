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
    # AI Layer Hardening D.2: every op forwards arbitrary *args/**kwargs (notably
    # `session=`) through to the underlying Motor collection AFTER injecting the
    # tenant filter/`schoolId`. So a write performed inside the plan executor's
    # transaction still gets `schoolId` scoping — there is no tenant-leaking
    # "raw" write path inside a txn (the executor never uses get_raw_db()).
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


class _NoopTransaction:
    """No-op async-context transaction for environments without a replica set
    (FakeDb test tier, single-node dev Mongo). Asserts nothing about atomicity —
    real all-or-nothing is verified only on the @pytest.mark.mongo_real tier."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # Never swallow the exception — the executor relies on it propagating so it
        # can run saga compensation / report failure exactly as with a real abort.
        return False


class _NoopSession:
    """Stand-in for a Motor client session when no replica set is available.

    Mirrors the slice of the Motor session API the executor uses
    (`start_transaction()` context manager, `end_session()`), and is accepted by
    `ScopedCollection`/`FakeCollection` as an inert `session=` value.
    """

    in_transaction = False

    def start_transaction(self, *args, **kwargs):
        return _NoopTransaction()

    async def commit_transaction(self):
        return None

    async def abort_transaction(self):
        return None

    async def end_session(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def get_txn_session():
    """Return a client session for a multi-document transaction (AD4 / Story D.2).

    On a real replica set this is ``_client.start_session()`` — a genuine session
    whose `session=` is forwarded through `ScopedCollection` so tenant scoping is
    preserved inside the transaction. When no replica-set client is configured
    (FakeDb test tier / single-node dev), returns a `_NoopSession` so the executor
    has ONE code path and never branches on environment. Never use `get_raw_db()`
    inside a transaction — that would bypass `schoolId` injection.
    """
    if _client is None:
        return _NoopSession()
    try:
        return await _client.start_session()
    except Exception:
        logger.warning("start_session unavailable; falling back to no-op session", exc_info=True)
        return _NoopSession()


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
    await db.token_balances.create_index("subscription_id", sparse=True)
    await db.token_usage.create_index([("branch_id", 1), ("user_id", 1), ("month", 1)])
    await db.token_usage.create_index("created_at")
    # Migrate: drop old non-sparse payment_id_1 index if it was created without sparse=True
    try:
        idx_info = await db.token_purchases.index_information()
        existing = idx_info.get("payment_id_1", {})
        if existing and not existing.get("sparse"):
            await db.token_purchases.drop_index("payment_id_1")
        await db.token_purchases.create_index("payment_id", unique=True, sparse=True)
    except Exception:
        pass
    await db.token_purchases.create_index(
        [("razorpay_reference_id", 1)],
        unique=True,
        sparse=True,
        name="token_purchases_razorpay_reference_id",
    )
    await db.refresh_tokens.create_index("token_hash", unique=True)
    await db.refresh_tokens.create_index("user_id")
    await db.refresh_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.confirm_tokens.create_index("token", unique=True)
    await db.confirm_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.idempotency_keys.create_index("key", unique=True)
    await db.idempotency_keys.create_index("expires_at", expireAfterSeconds=0)
    # AI Layer Hardening D.4 (AD6): per-step idempotency for confirmed AI plan
    # execution. Key = f"{plan_token}:{step_idx}". The UNIQUE index is what makes
    # two concurrent confirms of the same plan produce exactly one effect — the
    # loser's in-transaction claim insert hits DuplicateKey and aborts.
    await db.ai_write_idempotency.create_index("idempotency_key", unique=True)
    # Epic G (AI self-learning): per-owner memory + skills indexes. Scoped by
    # (schoolId, user_id) for tenant + owner isolation; a TTL index on
    # updated_at enforces retention (G.7) server-side as the primary bound.
    await db.ai_memories.create_index([("schoolId", 1), ("user_id", 1), ("updated_at_ts", -1)])
    await db.ai_memories.create_index([("schoolId", 1), ("student_refs", 1)])
    try:
        # Retention (G.7): a Date `expire_at` field set RETENTION_DAYS ahead is the
        # TTL anchor (TTL needs a real BSON Date — our other timestamps are ISO
        # strings). expireAfterSeconds=0 → Mongo deletes once `expire_at` passes.
        await db.ai_memories.create_index("expire_at", expireAfterSeconds=0)
    except Exception:
        logger.warning("ai_memories TTL index creation failed", exc_info=True)
    await db.ai_skills.create_index([("schoolId", 1), ("user_id", 1), ("updated_at_ts", -1)])
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
    # Story 7-44: School onboarding — unique index on school_id slug
    try:
        await db.schools.create_index("school_id", unique=True)
    except Exception:
        logger.warning("schools.school_id unique index creation failed", exc_info=True)
    # Compound unique index so multiple schools can each have id="main" but not duplicate (schoolId, id)
    try:
        await db.school_settings.create_index([("id", 1), ("schoolId", 1)], unique=True)
    except Exception:
        logger.warning("school_settings compound index creation failed", exc_info=True)
    # Story 7-45: same email can own multiple schools (different schoolId), but must be unique within one school
    try:
        await db.auth_users.create_index(
            [("username_lower", 1), ("schoolId", 1)],
            unique=True,
            name="auth_users_username_school_unique",
        )
    except Exception:
        logger.warning("auth_users compound unique index creation failed", exc_info=True)
