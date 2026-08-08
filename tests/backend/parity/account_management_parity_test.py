"""REST/Flo parity for student login creation and direct password changes."""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2


pytestmark = pytest.mark.asyncio

OWNER = {"id": "admin-1", "role": "owner", "name": "Admin User"}
VOLATILE = {
    "_id", "id", "user_id", "entity_id", "record_id", "created_at", "updated_at",
    "timestamp", "password_hash", "password_reset_at", "revoked_at",
}


def _scrub(value):
    if isinstance(value, list):
        return sorted((_scrub(item) for item in value), key=str)
    if not isinstance(value, dict):
        return value
    return {key: _scrub(item) for key, item in value.items() if key not in VOLATILE}


def _snapshot(fake_db):
    return _scrub({
        "auth_users": [row for row in fake_db.auth_users.docs if row.get("username") == "parity.student"],
        "users": [row for row in fake_db.users.docs if row.get("role") == "student" and row.get("name") == "Demo Student"],
        "students": [row for row in fake_db.students.docs if row.get("id") == "student-1"],
        "refresh_tokens": [row for row in fake_db.refresh_tokens.docs if row.get("user_id") == "parity-student-user"],
        "audit_logs": [row for row in fake_db.audit_logs.docs if row.get("action") in {"student_login_created", "admin_password_reset"}],
    })


@pytest.fixture
def clean_state(fake_db):
    state = {
        name: copy.deepcopy(getattr(fake_db, name).docs)
        for name in ("auth_users", "users", "students", "refresh_tokens", "audit_logs")
    }
    if not any(row.get("id") == "student-1" for row in fake_db.students.docs):
        fake_db.students.docs.append({
            "id": "student-1",
            "schoolId": "aaryans-joya",
            "name": "Demo Student",
            "class_id": "class-1",
            "admission_number": "ADM1",
            "is_active": True,
            "status": "active",
        })
    yield
    for name, docs in state.items():
        getattr(fake_db, name).docs[:] = docs


async def test_create_student_login_ai_and_rest_are_identical(
    client, auth_headers, fake_db, monkeypatch, clean_state,
):
    student = next(row for row in fake_db.students.docs if row.get("id") == "student-1")
    student.pop("user_id", None)
    payload = {"username": "parity.student", "password": "Parity@123"}
    response = client.post(
        "/api/auth/admin/students/student-1/login", headers=auth_headers, json=payload
    )
    assert response.status_code == 200
    rest_state = _snapshot(fake_db)

    fake_db.auth_users.docs[:] = [row for row in fake_db.auth_users.docs if row.get("username") != "parity.student"]
    fake_db.users.docs[:] = [row for row in fake_db.users.docs if not (row.get("role") == "student" and row.get("name") == "Demo Student")]
    fake_db.audit_logs.docs[:] = [row for row in fake_db.audit_logs.docs if row.get("action") != "student_login_created"]
    student.pop("user_id", None)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    result = await tool_functions_v2.tool_create_student_login(
        {"student_id": "student-1", **payload}, OWNER, None
    )
    assert result["success"] is True
    assert _snapshot(fake_db) == rest_state


async def test_set_profile_password_ai_and_rest_are_identical(
    client, auth_headers, fake_db, monkeypatch, clean_state,
):
    account = {
        "id": "parity-student-user",
        "schoolId": "aaryans-joya",
        "username": "parity.student",
        "username_lower": "parity.student",
        "password_hash": "old",
        "must_change_password": False,
        "user_info": {"id": "parity-student-user", "name": "Demo Student", "role": "student"},
    }
    session = {"id": "parity-session", "user_id": "parity-student-user", "revoked_at": None}
    fake_db.auth_users.docs.append(copy.deepcopy(account))
    fake_db.refresh_tokens.docs.append(copy.deepcopy(session))
    payload = {"new_password": "Changed@123"}
    response = client.post(
        "/api/auth/admin/users/parity-student-user/reset-password",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    rest_state = _snapshot(fake_db)

    fake_db.auth_users.docs[:] = [row for row in fake_db.auth_users.docs if row.get("id") != "parity-student-user"]
    fake_db.auth_users.docs.append(copy.deepcopy(account))
    fake_db.refresh_tokens.docs[:] = [row for row in fake_db.refresh_tokens.docs if row.get("id") != "parity-session"]
    fake_db.refresh_tokens.docs.append(copy.deepcopy(session))
    fake_db.audit_logs.docs[:] = [row for row in fake_db.audit_logs.docs if row.get("action") != "admin_password_reset"]
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    result = await tool_functions_v2.tool_set_profile_password(
        {"user_id": "parity-student-user", **payload}, OWNER, None
    )
    assert result["success"] is True
    assert _snapshot(fake_db) == rest_state
