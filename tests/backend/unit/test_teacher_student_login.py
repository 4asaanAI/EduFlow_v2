from __future__ import annotations

import pytest
from fastapi import HTTPException

from middleware.auth import decode_jwt, hash_password
from backend.routes import auth as auth_module

pytestmark = pytest.mark.asyncio


# ─── Minimal fakes (isolated from global fake_db) ────────────────────────────

class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    async def find_one(self, query=None):
        from tests.backend.conftest import _matches
        for doc in self.docs:
            if _matches(doc, query or {}):
                return doc
        return None

    async def update_one(self, query, update, upsert=False):
        from tests.backend.conftest import _matches, _set_nested
        for doc in self.docs:
            if _matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    _set_nested(doc, key, value)
                return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()

    async def delete_one(self, query):
        before = len(self.docs)
        from tests.backend.conftest import _matches
        self.docs[:] = [d for d in self.docs if not _matches(d, query)]
        return type("Result", (), {"deleted_count": before - len(self.docs)})()

    async def update_many(self, query, update):
        from tests.backend.conftest import _matches, _set_nested
        count = 0
        for doc in self.docs:
            if _matches(doc, query):
                for key, value in update.get("$set", {}).items():
                    _set_nested(doc, key, value)
                count += 1
        return type("Result", (), {"modified_count": count})()


class _FakeDb:
    def __init__(self, auth_docs):
        self.auth_users = _FakeCollection(auth_docs)
        self.login_attempts = _FakeCollection()
        self.refresh_tokens = _FakeCollection()


class _FakeRequest:
    def __init__(self):
        self.headers = {}
        self.client = None
        self.cookies = {}


class _FakeResponse:
    def set_cookie(self, *args, **kwargs):
        pass


# ─── Fixtures / helpers ───────────────────────────────────────────────────────

def _teacher_auth():
    return {
        "id": "auth-teacher-001",
        "username": "Rajesh Kumar",
        "username_lower": "rajesh kumar",
        "password_hash": hash_password("teacher@123"),
        "is_active": True,
        "role": "teacher",
        "user_info": {
            "id": "user-teacher-001",
            "name": "Rajesh Kumar",
            "role": "teacher",
            "sub_category": "class_teacher",
            "initials": "RK",
        },
    }


def _student_auth():
    return {
        "id": "auth-student-001",
        "username": "ADM20250001",
        "username_lower": "adm20250001",
        "password_hash": hash_password("student@123"),
        "is_active": True,
        "role": "student",
        "user_info": {
            "id": "user-student-001",
            "name": "Rahul Singh",
            "role": "student",
            "initials": "RS",
        },
    }


async def _fake_issue_refresh_token(db, uid, req=None):
    return "fake-refresh-token"


async def _do_login(monkeypatch, auth_doc, username, password):
    db = _FakeDb([auth_doc])
    monkeypatch.setattr(auth_module, "get_db", lambda: db)
    monkeypatch.setattr(auth_module, "issue_refresh_token", _fake_issue_refresh_token)
    monkeypatch.setattr(auth_module, "set_refresh_cookie", lambda res, tok: None)
    body = auth_module.LoginRequest(username=username, password=password)
    return await auth_module.login(body, _FakeRequest(), _FakeResponse()), db


# ─── AC1: Teacher login JWT ────────────────────────────────────────────────────

async def test_teacher_login_jwt_contains_correct_role_and_sub_category(monkeypatch):
    response, _ = await _do_login(monkeypatch, _teacher_auth(), "Rajesh Kumar", "teacher@123")

    assert response["success"] is True
    payload = decode_jwt(response["access_token"])
    assert payload["role"] == "teacher"
    assert payload["sub_category"] == "class_teacher"
    assert payload["id"] == "user-teacher-001"


# ─── AC2: Student login JWT ────────────────────────────────────────────────────

async def test_student_login_jwt_contains_correct_role(monkeypatch):
    response, _ = await _do_login(monkeypatch, _student_auth(), "ADM20250001", "student@123")

    assert response["success"] is True
    payload = decode_jwt(response["access_token"])
    assert payload["role"] == "student"
    assert payload["id"] == "user-student-001"


# ─── AC3: must_change_password flag in login response ─────────────────────────

async def test_login_returns_must_change_password_flag_when_set(monkeypatch):
    doc = {**_teacher_auth(), "must_change_password": True}
    response, _ = await _do_login(monkeypatch, doc, "Rajesh Kumar", "teacher@123")

    assert response.get("must_change_password") is True


async def test_login_does_not_return_flag_when_not_set(monkeypatch):
    # No must_change_password key → flag should not appear in response
    response, _ = await _do_login(monkeypatch, _teacher_auth(), "Rajesh Kumar", "teacher@123")

    assert response.get("must_change_password") is None or response.get("must_change_password") is False


# ─── AC4: change-password clears the flag ─────────────────────────────────────

async def _noop_revoke(db, uid, reason=None):
    pass


async def test_change_password_clears_flag(monkeypatch):
    doc = {**_teacher_auth(), "must_change_password": True}
    db = _FakeDb([doc])
    monkeypatch.setattr(auth_module, "get_db", lambda: db)
    monkeypatch.setattr(auth_module, "revoke_user_refresh_tokens", _noop_revoke)
    monkeypatch.setattr(auth_module, "issue_refresh_token", _fake_issue_refresh_token)
    monkeypatch.setattr(auth_module, "set_refresh_cookie", lambda res, tok: None)

    current_user = {"user_id": "user-teacher-001"}
    body = auth_module.ChangePasswordRequest(
        current_password="teacher@123", new_password="newpassword99"
    )
    result = await auth_module.change_password(body, _FakeRequest(), _FakeResponse(), current_user)

    assert result == {"success": True}
    assert db.auth_users.docs[0].get("must_change_password") is False


# ─── AC5: wrong current password → 400 ───────────────────────────────────────

async def test_change_password_wrong_current_password_returns_400(monkeypatch):
    db = _FakeDb([_teacher_auth()])
    monkeypatch.setattr(auth_module, "get_db", lambda: db)
    monkeypatch.setattr(auth_module, "revoke_user_refresh_tokens", _noop_revoke)
    monkeypatch.setattr(auth_module, "issue_refresh_token", _fake_issue_refresh_token)
    monkeypatch.setattr(auth_module, "set_refresh_cookie", lambda res, tok: None)

    current_user = {"user_id": "user-teacher-001"}
    body = auth_module.ChangePasswordRequest(
        current_password="wrongpassword", new_password="newpassword99"
    )
    with pytest.raises(HTTPException) as exc:
        await auth_module.change_password(body, _FakeRequest(), _FakeResponse(), current_user)

    assert exc.value.status_code == 400
    assert "incorrect" in exc.value.detail.lower()


# ─── Security: unauthenticated returns 401 ────────────────────────────────────

def test_change_password_requires_auth(client):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "old", "new_password": "newpassword99"},
    )
    assert resp.status_code == 401
