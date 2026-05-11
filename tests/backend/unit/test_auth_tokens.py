from datetime import timedelta

import pytest
from fastapi import HTTPException

from backend.services import auth_tokens


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.modified_count = 0

    async def insert_one(self, doc):
        doc = {**doc, "_id": len(self.docs) + 1}
        self.docs.append(doc)

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    async def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                self.modified_count = 1
                return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()

    async def update_many(self, query, update):
        count = 0
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                count += 1
        return type("Result", (), {"modified_count": count})()


class FakeDb:
    def __init__(self):
        self.refresh_tokens = FakeCollection()


@pytest.mark.asyncio
async def test_refresh_token_is_single_use():
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-1")

    record = await auth_tokens.consume_refresh_token(db, raw)

    assert record["user_id"] == "user-1"
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "rotated"
    with pytest.raises(HTTPException) as exc:
        await auth_tokens.consume_refresh_token(db, raw)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_refresh_token_rejected():
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-1")
    db.refresh_tokens.docs[0]["expires_at"] = auth_tokens.utc_now() - timedelta(seconds=1)

    with pytest.raises(HTTPException) as exc:
        await auth_tokens.consume_refresh_token(db, raw)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_user_refresh_tokens():
    db = FakeDb()
    await auth_tokens.issue_refresh_token(db, "user-1")
    await auth_tokens.issue_refresh_token(db, "user-2")

    count = await auth_tokens.revoke_user_refresh_tokens(db, "user-1")

    assert count == 1
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "user_deactivated"
    assert db.refresh_tokens.docs[1]["revoked_at"] is None
