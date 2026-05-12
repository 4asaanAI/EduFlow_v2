from datetime import datetime

import pytest
from fastapi import HTTPException

from backend.routes import auth


def _get_nested(doc, key):
    value = doc
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(doc, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(doc, option) for option in expected):
                return False
            continue

        actual = _get_nested(doc, key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$gt" and not actual > value:
                    return False
                if op == "$gte" and not actual >= value:
                    return False
            continue

        if actual != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    async def count_documents(self, query):
        return sum(1 for doc in self.docs if _matches(doc, query))

    async def insert_one(self, doc):
        inserted = {**doc, "_id": len(self.docs) + 1}
        self.docs.append(inserted)
        return type("Result", (), {"inserted_id": inserted["_id"]})()

    async def find_one(self, query):
        for doc in self.docs:
            if _matches(doc, query):
                return doc
        return None

    async def update_one(self, query, update):
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()

    async def update_many(self, query, update):
        modified = 0
        for doc in self.docs:
            if _matches(doc, query):
                doc.update(update.get("$set", {}))
                modified += 1
        return type("Result", (), {"modified_count": modified})()


class FakeDb:
    def __init__(self):
        self.auth_users = FakeCollection(
            [
                {
                    "email": "owner@example.com",
                    "password_hash": "old-hash",
                    "user_info": {"id": "owner-1", "role": "owner", "email": "owner@example.com"},
                }
            ]
        )
        self.password_reset_requests = FakeCollection()
        self.password_reset_tokens = FakeCollection()
        self.refresh_tokens = FakeCollection(
            [{"user_id": "owner-1", "revoked_at": None, "revoked_reason": None}]
        )


@pytest.mark.asyncio
async def test_forgot_password_creates_token_and_sends_email(monkeypatch):
    db = FakeDb()
    sent = {}
    monkeypatch.setattr(auth, "get_db", lambda: db)
    monkeypatch.setattr(
        auth,
        "send_password_reset_email",
        lambda email, link: sent.update({"email": email, "link": link}),
    )
    monkeypatch.setenv("FRONTEND_URL", "https://app.eduflow.example")

    response = await auth.forgot_password(auth.ForgotPasswordRequest(email="Owner@Example.com"))

    assert response["success"] is True
    assert response["message"] == "If that email exists, a reset link has been sent."
    assert len(db.password_reset_tokens.docs) == 1
    reset_doc = db.password_reset_tokens.docs[0]
    assert reset_doc["user_id"] == "owner-1"
    assert reset_doc["used"] is False
    assert reset_doc["expires_at"] > datetime.now(reset_doc["expires_at"].tzinfo)
    assert sent["email"] == "owner@example.com"
    assert sent["link"].startswith("https://app.eduflow.example/reset-password?token=")


@pytest.mark.asyncio
async def test_reset_password_is_single_use_and_revokes_sessions(monkeypatch):
    db = FakeDb()
    monkeypatch.setattr(auth, "get_db", lambda: db)
    monkeypatch.setattr(auth, "hash_password", lambda password: f"hashed:{password}")

    await db.password_reset_tokens.insert_one(
        {
            "token": "reset-token",
            "user_id": "owner-1",
            "email": "owner@example.com",
            "expires_at": datetime.now().astimezone().replace(year=2099),
            "used": False,
        }
    )

    response = await auth.reset_password(
        auth.ResetPasswordRequest(token="reset-token", new_password="new-password")
    )

    assert response == {"success": True}
    assert db.password_reset_tokens.docs[0]["used"] is True
    assert db.auth_users.docs[0]["password_hash"] == "hashed:new-password"
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "password_reset"

    with pytest.raises(HTTPException) as exc:
        await auth.reset_password(
            auth.ResetPasswordRequest(token="reset-token", new_password="new-password")
        )
    assert exc.value.status_code == 400
