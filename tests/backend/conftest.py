"""
pytest Configuration — EduFlow Backend Tests

Shared fixtures for all backend tests:
  - `client` — FastAPI TestClient (sync, no real DB)
  - `async_client` — httpx AsyncClient (async tests)
  - `auth_headers` — pre-authenticated admin Bearer token headers
  - `db` — async Motor test database (isolated per test session)

Usage:
    from tests.backend.conftest import ...  # fixtures auto-discovered by pytest
"""

import os
import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator

# ─── Override environment before importing app ─────────────────────────────
# Set test environment variables before any app import
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/eduflow_test")
os.environ.setdefault("DB_NAME", "eduflow_test")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-key-not-for-production")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000")

# ─── App imports (after env setup) ─────────────────────────────────────────
try:
    from fastapi.testclient import TestClient
    import httpx
    # Import the FastAPI app — adjust path if needed
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
    from server import app
    import server
    import routes.chat as chat_routes
    import routes.auth as auth_routes
    import routes.students as student_routes
    import routes.staff as staff_routes
    import routes.attendance as attendance_routes
    import routes.fees as fees_routes
    import routes.settings as settings_routes
    import routes.activities as activities_routes
    import routes.operations as operations_routes
    import routes.notifications as notifications_routes
    import routes.academics as academics_routes
    import routes.issues as issues_routes
    import routes.audit as audit_routes
    import routes.upload as upload_routes
    import routes.chat_upload as chat_upload_routes
    import routes.image_gen as image_gen_routes
    import routes.operator as operator_routes
    import routes.reports as reports_routes
    import routes.exports as exports_routes
    from middleware.auth import hash_password
    APP_AVAILABLE = True
except (ImportError, TypeError) as e:
    APP_AVAILABLE = False
    _import_error = str(e)


def _get_nested(doc, key):
    value = doc
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _set_nested(doc, key, value):
    parts = key.split(".")
    target = doc
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _inc_nested(doc, key, value):
    current = _get_nested(doc, key) or 0
    _set_nested(doc, key, current + value)


def _matches(doc, query):
    for key, expected in (query or {}).items():
        if key == "$and":
            if not all(_matches(doc, option) for option in expected):
                return False
            continue
        if key == "$or":
            if not any(_matches(doc, option) for option in expected):
                return False
            continue
        actual = _get_nested(doc, key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$in" and actual not in value:
                    return False
                if op == "$nin" and actual in value:
                    return False
                if op == "$ne" and actual == value:
                    return False
                if op == "$gte" and (actual is None or actual < value):
                    return False
                if op == "$lte" and (actual is None or actual > value):
                    return False
                if op == "$gt" and (actual is None or actual <= value):
                    return False
                if op == "$lt" and (actual is None or actual >= value):
                    return False
                if op == "$exists":
                    # Proper $exists: check key presence, not value nullness
                    parts = key.split(".")
                    target = doc
                    key_present = True
                    for part in parts:
                        if not isinstance(target, dict) or part not in target:
                            key_present = False
                            break
                        target = target[part]
                    if bool(value) != key_present:
                        return False
                if op == "$regex":
                    import re
                    flags = re.I if expected.get("$options") == "i" else 0
                    if re.search(value, str(actual or ""), flags) is None:
                        return False
                if op == "$options":
                    continue
            continue
        if actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list):
            for k, d in reversed(key_or_list):
                self.docs.sort(key=lambda doc, _k=k: doc.get(_k) or "", reverse=d < 0)
        else:
            self.docs.sort(key=lambda doc: doc.get(key_or_list) or "", reverse=direction < 0)
        return self

    def skip(self, count):
        self.docs = self.docs[count:]
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    async def to_list(self, _limit):
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in self.docs]

    def __aiter__(self):
        self._iter_index = 0
        return self

    async def __anext__(self):
        if self._iter_index >= len(self.docs):
            raise StopAsyncIteration
        doc = {k: v for k, v in self.docs[self._iter_index].items() if k != "_id"}
        self._iter_index += 1
        return doc


class FakeAggregateCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    async def to_list(self, limit):
        return self.docs[:limit] if limit else self.docs


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query=None, projection=None, sort=None):
        docs = [doc for doc in self.docs if _matches(doc, query or {})]
        if sort:
            for key, direction in reversed(sort):
                docs.sort(key=lambda doc: _get_nested(doc, key) or "", reverse=direction < 0)
        for doc in docs:
            if _matches(doc, query or {}):
                return {k: v for k, v in doc.items() if k != "_id"} if projection else doc
        return None

    def find(self, query=None, projection=None):
        return FakeCursor([doc for doc in self.docs if _matches(doc, query or {})])

    async def count_documents(self, query=None):
        return sum(1 for doc in self.docs if _matches(doc, query or {}))

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("Result", (), {"inserted_id": doc.get("_id")})()

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    _set_nested(doc, key, value)
                for key, value in update.get("$inc", {}).items():
                    _inc_nested(doc, key, value)
                for key, value in update.get("$push", {}).items():
                    current = _get_nested(doc, key) or []
                    if not isinstance(current, list):
                        current = [current]
                    current.append(value)
                    _set_nested(doc, key, current)
                return type("Result", (), {"matched_count": 1, "modified_count": 1})()
        if upsert:
            doc = {**query, **update.get("$setOnInsert", {}), **update.get("$set", {})}
            for key, value in update.get("$inc", {}).items():
                _inc_nested(doc, key, value)
            for key, value in update.get("$push", {}).items():
                current = _get_nested(doc, key) or []
                if not isinstance(current, list):
                    current = [current]
                current.append(value)
                _set_nested(doc, key, current)
            self.docs.append(doc)
            return type("Result", (), {"matched_count": 1, "modified_count": 1})()
        return type("Result", (), {"matched_count": 0, "modified_count": 0})()

    async def find_one_and_update(self, query, update, upsert=False, return_document=None, sort=None):
        # Minimal stand-in for Motor's find_one_and_update covering the cases
        # the rate limiter exercises: upsert + $inc + $setOnInsert.
        matched_doc = None
        for doc in self.docs:
            if _matches(doc, query):
                matched_doc = doc
                break

        if matched_doc is None and upsert:
            matched_doc = {**query, **update.get("$setOnInsert", {})}
            self.docs.append(matched_doc)

        if matched_doc is None:
            return None

        for key, value in update.get("$set", {}).items():
            _set_nested(matched_doc, key, value)
        for key, value in update.get("$inc", {}).items():
            _inc_nested(matched_doc, key, value)
        return {k: v for k, v in matched_doc.items() if k != "_id"}

    async def update_many(self, query, update):
        count = 0
        for doc in self.docs:
            if _matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    _set_nested(doc, key, value)
                for key, value in update.get("$inc", {}).items():
                    _inc_nested(doc, key, value)
                for key, value in update.get("$push", {}).items():
                    existing = _get_nested(doc, key)
                    if isinstance(existing, list):
                        existing.append(value)
                    else:
                        _set_nested(doc, key, [value])
                count += 1
        return type("Result", (), {"modified_count": count})()

    async def delete_one(self, query):
        before = len(self.docs)
        self.docs[:] = [doc for doc in self.docs if not _matches(doc, query)]
        return type("Result", (), {"deleted_count": before - len(self.docs)})()

    async def delete_many(self, query):
        before = len(self.docs)
        self.docs[:] = [doc for doc in self.docs if not _matches(doc, query)]
        return type("Result", (), {"deleted_count": before - len(self.docs)})()

    async def create_index(self, *args, **kwargs):
        return kwargs.get("name") or str(args[0] if args else "index")

    async def index_information(self):
        return {}

    def aggregate(self, pipeline):
        docs = [doc.copy() for doc in self.docs]
        for stage in pipeline:
            if "$match" in stage:
                docs = [doc for doc in docs if _matches(doc, stage["$match"])]
            elif "$group" in stage:
                group = stage["$group"]
                grouped = {}
                for doc in docs:
                    key_expr = group.get("_id")
                    if key_expr is None:
                        key = None
                    elif isinstance(key_expr, str) and key_expr.startswith("$"):
                        key = _get_nested(doc, key_expr[1:])
                    elif isinstance(key_expr, dict) and "$substr" in key_expr:
                        source, start, length = key_expr["$substr"]
                        raw = _get_nested(doc, source[1:]) if isinstance(source, str) and source.startswith("$") else source
                        key = str(raw or "")[start:start + length]
                    else:
                        key = key_expr
                    bucket = grouped.setdefault(key, {"_id": key})
                    for out_key, expr in group.items():
                        if out_key == "_id":
                            continue
                        if "$sum" in expr:
                            sum_expr = expr["$sum"]
                            if isinstance(sum_expr, str) and sum_expr.startswith("$"):
                                bucket[out_key] = bucket.get(out_key, 0) + (_get_nested(doc, sum_expr[1:]) or 0)
                            elif isinstance(sum_expr, dict) and "$cond" in sum_expr:
                                condition, true_value, false_value = sum_expr["$cond"]
                                left, right = condition.get("$eq", [None, None])
                                left_value = _get_nested(doc, left[1:]) if isinstance(left, str) and left.startswith("$") else left
                                bucket[out_key] = bucket.get(out_key, 0) + (true_value if left_value == right else false_value)
                            else:
                                bucket[out_key] = bucket.get(out_key, 0) + sum_expr
                        elif "$addToSet" in expr:
                            set_expr = expr["$addToSet"]
                            value = _get_nested(doc, set_expr[1:]) if isinstance(set_expr, str) and set_expr.startswith("$") else set_expr
                            bucket.setdefault(out_key, set()).add(value)
                docs = list(grouped.values())
                for doc in docs:
                    for key, value in list(doc.items()):
                        if isinstance(value, set):
                            doc[key] = list(value)
            elif "$sort" in stage:
                for key, direction in reversed(list(stage["$sort"].items())):
                    docs.sort(key=lambda doc: _get_nested(doc, key) or "", reverse=direction < 0)
        return FakeAggregateCursor(docs)


class FakeDb:
    def __init__(self):
        self.auth_users = FakeCollection([
            {
                "id": "admin-1",
                "username": "admin",
                "username_lower": "admin",
                "password_hash": hash_password("admin123"),
                "is_active": True,
                "user_info": {"id": "admin-1", "role": "owner", "name": "Admin User"},
            }
        ])
        self.login_attempts = FakeCollection()
        self.refresh_tokens = FakeCollection()
        self.students = FakeCollection([
            {
                "id": "student-1",
                "schoolId": "aaryans-joya",
                "name": "Demo Student",
                "class_id": "class-1",
                "admission_number": "ADM1",
                "is_active": True,
                "status": "active",
                "created_at": "2026-01-01T00:00:00",
            }
        ])
        self.academic_years = FakeCollection([
            {"id": "year-1", "schoolId": "aaryans-joya", "name": "2026-27", "is_current": True}
        ])
        self.classes = FakeCollection([
            {"id": "class-1", "schoolId": "aaryans-joya", "academic_year_id": "year-1", "name": "Class 5", "section": "A"},
            {"id": "class-2", "schoolId": "aaryans-joya", "academic_year_id": "year-1", "name": "5", "section": "A"},
        ])
        self.guardians = FakeCollection()
        self.staff = FakeCollection()
        self.leave_requests = FakeCollection()
        self.staff_availability = FakeCollection()
        self.approval_requests = FakeCollection()
        self.notifications = FakeCollection()
        self.audit_logs = FakeCollection()
        self.file_uploads = FakeCollection()
        self.orphaned_s3_keys = FakeCollection()
        self.users = FakeCollection()
        self.user_settings = FakeCollection()
        self.school_settings = FakeCollection()
        self.custom_forms = FakeCollection()
        self.form_responses = FakeCollection()
        self.expenses = FakeCollection()
        self.visitor_log = FakeCollection()
        self.assets = FakeCollection()
        self.enquiries = FakeCollection()
        self.student_attendance = FakeCollection()
        self.staff_attendance = FakeCollection()
        self.attendance_corrections = FakeCollection()
        self.incidents = FakeCollection()
        self.fee_transactions = FakeCollection()
        self.fee_idempotency_keys = FakeCollection()
        self.fee_transaction_corrections = FakeCollection()
        self.fee_contact_logs = FakeCollection()
        self.fee_structures = FakeCollection()
        self.fee_discount_types = FakeCollection()
        self.fee_discounts = FakeCollection()
        self.fee_sync_jobs = FakeCollection()
        self.receipt_counters = FakeCollection()
        self.facility_requests = FakeCollection()
        self.tech_requests = FakeCollection()
        self.complaints = FakeCollection()
        self.maintenance_schedule = FakeCollection()
        self.maintenance_vendors = FakeCollection()
        self.transport_routes = FakeCollection()
        self.vehicles = FakeCollection()
        self.timetable_slots = FakeCollection()
        self.substitutions = FakeCollection()
        self.subjects = FakeCollection()
        self.token_balances = FakeCollection()
        self.token_usage = FakeCollection()
        self.token_purchases = FakeCollection()
        self.confirm_tokens = FakeCollection()
        self.ai_dispatch_audit_log = FakeCollection()
        self.idempotency_keys = FakeCollection()
        self.ai_rate_limit_counters = FakeCollection()
        self.ai_rate_limit_overrides = FakeCollection()
        self.messages = FakeCollection()
        self.conversations = FakeCollection()
        self.announcements = FakeCollection()
        self.exam_results = FakeCollection()
        self.exams = FakeCollection()
        self.houses = FakeCollection()
        self.house_points_log = FakeCollection()
        self.student_positions = FakeCollection()
        self.sports_teams = FakeCollection()

    async def command(self, command_name):
        if command_name == "ping":
            return {"ok": 1}
        return {"ok": 1}


if APP_AVAILABLE:
    _fake_db = FakeDb()

    async def _noop_connect():
        return None

    async def _noop_disconnect():
        return None

    server.connect_db = _noop_connect
    server.disconnect_db = _noop_disconnect
    auth_routes.get_db = lambda: _fake_db
    student_routes.get_db = lambda: _fake_db
    staff_routes.get_db = lambda: _fake_db
    attendance_routes.get_db = lambda: _fake_db
    fees_routes.get_db = lambda: _fake_db
    settings_routes.get_db = lambda: _fake_db
    activities_routes.get_db = lambda: _fake_db
    operations_routes.get_db = lambda: _fake_db
    notifications_routes.get_db = lambda: _fake_db
    academics_routes.get_db = lambda: _fake_db
    issues_routes.get_db = lambda: _fake_db
    audit_routes.get_db = lambda: _fake_db
    upload_routes.get_db = lambda: _fake_db
    image_gen_routes.get_db = lambda: _fake_db
    chat_routes.get_db = lambda: _fake_db
    operator_routes.get_db = lambda: _fake_db
    reports_routes.get_db = lambda: _fake_db
    exports_routes.get_db = lambda: _fake_db
    server.get_raw_db = lambda: _fake_db


# ─── Event loop (for async tests) ─────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop shared across the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── FastAPI test clients ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client() -> Generator:
    """
    Sync FastAPI TestClient.
    Use for simple request/response tests where async is not needed.
    """
    if not APP_AVAILABLE:
        pytest.skip(f"App not importable: {_import_error}")
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture
def fake_db():
    if not APP_AVAILABLE:
        pytest.skip(f"App not importable: {_import_error}")
    return _fake_db


@pytest_asyncio.fixture(scope="session")
async def async_client() -> AsyncGenerator:
    """
    Async httpx client for async test functions.
    Use with `pytest.mark.asyncio`.
    """
    if not APP_AVAILABLE:
        pytest.skip(f"App not importable: {_import_error}")
    base_url = os.environ.get("API_URL", "http://localhost:8000")
    async with httpx.AsyncClient(app=app, base_url=base_url) as ac:
        yield ac


# ─── Auth helpers ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def auth_token(client) -> str:
    """
    Log in as the test admin and return the JWT token.
    Cached for the session so login only happens once.
    """
    username = os.environ.get("TEST_ADMIN_USERNAME", "admin")
    password = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        pytest.fail(
            f"Auth fixture: login failed with status {response.status_code}: {response.text}"
        )
    return response.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    """
    Pre-built Authorization headers for authenticated requests.

    Usage:
        def test_something(client, auth_headers):
            resp = client.get("/api/students", headers=auth_headers)
    """
    return {"Authorization": f"Bearer {auth_token}"}


# ─── Test data factories ───────────────────────────────────────────────────

@pytest.fixture
def student_data() -> dict:
    """Build a minimal student payload for POST /api/students."""
    import random
    suffix = random.randint(1000, 9999)
    return {
        "name": f"Test Student {suffix}",
        "class_id": "class-1",
        "roll_number": f"ROLL{suffix}",
        "guardian_name": f"Parent {suffix}",
        "guardian_phone": f"9{suffix:09d}",
        "gender": "M",
    }


@pytest.fixture
def staff_data() -> dict:
    """Build a minimal staff payload for POST /api/staff."""
    import random
    suffix = random.randint(1000, 9999)
    return {
        "name": f"Test Teacher {suffix}",
        "role": "teacher",
        "subject": "Mathematics",
        "phone": f"8{suffix:09d}",
        "email": f"teacher{suffix}@testschool.edu",
        "employee_id": f"EMP{suffix}",
    }
