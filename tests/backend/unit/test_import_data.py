import pytest
from fastapi import HTTPException

from backend.routes import import_data


def _get_nested(doc, key):
    value = doc
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(doc, query):
    for key, expected in query.items():
        actual = _get_nested(doc, key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$in" and actual not in value:
                    return False
            continue
        if actual != expected:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, _limit):
        return self.docs


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def find_one(self, query, projection=None):
        for doc in self.docs:
            if _matches(doc, query):
                return {k: v for k, v in doc.items() if k != "_id"} if projection else doc
        return None

    def find(self, query, projection=None):
        docs = [doc for doc in self.docs if _matches(doc, query)]
        return FakeCursor(docs)

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("Result", (), {"inserted_id": doc.get("_id")})()

    async def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                return type("Result", (), {"modified_count": 1})()
        if upsert:
            doc = {**query, **update.get("$setOnInsert", {}), **update.get("$set", {})}
            self.docs.append(doc)
            return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()


class FakeDb:
    def __init__(self):
        self.classes = FakeCollection([{"id": "class-1", "name": "5", "section": "A"}])
        self.students = FakeCollection(
            [{"id": "student-1", "name": "Existing Student", "class_id": "class-1", "is_active": True}]
        )
        self.guardians = FakeCollection()
        self.audit_logs = FakeCollection()


class FakeUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    async def read(self):
        return self._content


@pytest.mark.asyncio
async def test_validate_import_reports_errors_and_duplicates(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(import_data, "get_db", lambda: db)
    monkeypatch.setattr(import_data, "get_current_user", lambda _request: {"id": "owner-1", "role": "owner"})
    content = (
        "name,class,section,parent_name,parent_phone\n"
        "Existing Student,5,A,Parent,9999999999\n"
        "Missing Parent,5,A,,9999999998\n"
    ).encode()

    report = await import_data.validate_import(object(), FakeUpload("students.csv", content))

    assert report["valid_count"] == 1
    assert report["error_count"] == 1
    assert report["duplicate_count"] == 1
    assert report["duplicates"][0]["student_id"] == "student-1"
    assert report["errors"][0]["field"] == "parent_name"


@pytest.mark.asyncio
async def test_commit_import_skips_duplicates_without_overwrite(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(import_data, "get_db", lambda: db)
    monkeypatch.setattr(import_data, "get_current_user", lambda _request: {"id": "owner-1", "role": "owner"})
    content = (
        "name,class,section,parent_name,parent_phone,date_of_birth,address,route_zone_id\n"
        "New Student,5,A,New Parent,9999999997,2015-01-01,Main Road,Route 1\n"
        "Existing Student,5,A,Parent,9999999999,,,\n"
    ).encode()

    result = await import_data.commit_import(
        object(),
        FakeUpload("students.csv", content),
        overwrite_duplicates=False,
    )

    assert result["imported_count"] == 1
    assert result["skipped_count"] == 1
    assert len(db.students.docs) == 2
    assert len(db.guardians.docs) == 1
    assert db.audit_logs.docs[0]["action"] == "bulk_import"


@pytest.mark.asyncio
async def test_import_is_owner_only(monkeypatch):
    monkeypatch.setattr(import_data, "get_current_user", lambda _request: {"id": "teacher-1", "role": "teacher"})

    with pytest.raises(HTTPException) as exc:
        await import_data.validate_import(object(), FakeUpload("students.csv", b"name\nAlice"))

    assert exc.value.status_code == 403
