from __future__ import annotations

import copy

from middleware.auth import create_jwt, verify_password


def _headers(user_id: str, role: str, sub_category: str | None = None) -> dict:
    payload = {"user_id": user_id, "role": role, "name": user_id}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _student_account(fake_db, *, user_id="student-user", username="student.login"):
    return {
        "id": user_id,
        "schoolId": "aaryans-joya",
        "username": username,
        "username_lower": username,
        "password_hash": "old",
        "is_active": True,
        "user_info": {
            "id": user_id,
            "name": "Demo Student",
            "role": "student",
            "sub_category": "student",
        },
    }


def test_create_student_login_requires_authentication(client):
    response = client.post(
        "/api/auth/admin/students/student-1/login",
        json={"username": "adm1", "password": "Student@123"},
    )
    assert response.status_code == 401


def test_create_student_login_rejects_wrong_role(client):
    response = client.post(
        "/api/auth/admin/students/student-1/login",
        headers=_headers("student-actor", "student", "student"),
        json={"username": "adm1", "password": "Student@123"},
    )
    assert response.status_code == 403


def test_management_creates_student_login_without_forced_change(client, fake_db):
    before = {
        "auth": copy.deepcopy(fake_db.auth_users.docs),
        "users": copy.deepcopy(fake_db.users.docs),
        "students": copy.deepcopy(fake_db.students.docs),
        "audit": copy.deepcopy(fake_db.audit_logs.docs),
    }
    try:
        student = next(row for row in fake_db.students.docs if row["id"] == "student-1")
        student.pop("user_id", None)
        response = client.post(
            "/api/auth/admin/students/student-1/login",
            headers=_headers("lalit", "admin", "management"),
            json={"username": "adm1", "password": "Student@123"},
        )
        assert response.status_code == 200
        account = response.json()["data"]
        stored = next(row for row in fake_db.auth_users.docs if row.get("id") == account["user_id"])
        assert stored["must_change_password"] is False
        assert verify_password("Student@123", stored["password_hash"])
        assert student["user_id"] == account["user_id"]
        audit = next(row for row in fake_db.audit_logs.docs if row.get("action") == "student_login_created")
        assert "Student@123" not in str(audit)
        assert "password_hash" not in str(audit)
    finally:
        fake_db.auth_users.docs[:] = before["auth"]
        fake_db.users.docs[:] = before["users"]
        fake_db.students.docs[:] = before["students"]
        fake_db.audit_logs.docs[:] = before["audit"]


def test_accountant_cannot_create_student_login(client):
    response = client.post(
        "/api/auth/admin/students/student-1/login",
        headers=_headers("sonu", "admin", "accountant"),
        json={"username": "adm1", "password": "Student@123"},
    )
    assert response.status_code == 403


def test_management_changes_only_student_password_and_revokes_sessions(client, fake_db):
    before_auth = copy.deepcopy(fake_db.auth_users.docs)
    before_refresh = copy.deepcopy(fake_db.refresh_tokens.docs)
    before_audit = copy.deepcopy(fake_db.audit_logs.docs)
    try:
        fake_db.auth_users.docs.append(_student_account(fake_db))
        fake_db.auth_users.docs.append({
            "id": "teacher-user",
            "schoolId": "aaryans-joya",
            "username": "teacher.login",
            "username_lower": "teacher.login",
            "password_hash": "old",
            "user_info": {"id": "teacher-user", "role": "teacher", "name": "Teacher"},
        })
        fake_db.refresh_tokens.docs.append({
            "id": "student-session", "user_id": "student-user", "revoked_at": None
        })
        headers = _headers("lalit", "admin", "management")
        response = client.post(
            "/api/auth/admin/users/student-user/reset-password",
            headers=headers,
            json={"new_password": "Changed@123"},
        )
        assert response.status_code == 200
        stored = next(row for row in fake_db.auth_users.docs if row.get("id") == "student-user")
        assert verify_password("Changed@123", stored["password_hash"])
        assert stored["must_change_password"] is False
        session = next(row for row in fake_db.refresh_tokens.docs if row.get("id") == "student-session")
        assert session["revoked_at"] is not None
        audit = next(row for row in fake_db.audit_logs.docs if row.get("action") == "admin_password_reset")
        assert "Changed@123" not in str(audit)
        assert "password_hash" not in str(audit)

        denied = client.post(
            "/api/auth/admin/users/teacher-user/reset-password",
            headers=headers,
            json={"new_password": "Changed@456"},
        )
        assert denied.status_code == 403
    finally:
        fake_db.auth_users.docs[:] = before_auth
        fake_db.refresh_tokens.docs[:] = before_refresh
        fake_db.audit_logs.docs[:] = before_audit


def test_principal_cannot_change_owner_password(client, fake_db):
    before = copy.deepcopy(fake_db.auth_users.docs)
    try:
        fake_db.auth_users.docs.append({
            "id": "owner-target",
            "schoolId": "aaryans-joya",
            "username": "owner.target",
            "username_lower": "owner.target",
            "password_hash": "old",
            "user_info": {"id": "owner-target", "role": "owner", "name": "Owner"},
        })
        response = client.post(
            "/api/auth/admin/users/owner-target/reset-password",
            headers=_headers("adesh", "admin", "principal"),
            json={"new_password": "Changed@123"},
        )
        assert response.status_code == 403
    finally:
        fake_db.auth_users.docs[:] = before


def test_principal_can_create_non_owner_admin_login(client, fake_db):
    before_staff = copy.deepcopy(fake_db.staff.docs)
    before_auth = copy.deepcopy(fake_db.auth_users.docs)
    before_audit = copy.deepcopy(fake_db.audit_logs.docs)
    try:
        response = client.post(
            "/api/staff/",
            headers=_headers("adesh", "admin", "principal"),
            json={
                "name": "New Office Admin",
                "staff_type": "administrator",
                "role": "admin",
                "sub_category": "management",
                "username": "new.office.admin",
                "password": "Office@123",
            },
        )
        assert response.status_code == 200
        login = next(
            row for row in fake_db.auth_users.docs
            if row.get("username_lower") == "new.office.admin"
        )
        assert login["user_info"]["role"] == "admin"
        assert login["user_info"]["sub_category"] == "management"
        assert login["must_change_password"] is False
        assert verify_password("Office@123", login["password_hash"])
    finally:
        fake_db.staff.docs[:] = before_staff
        fake_db.auth_users.docs[:] = before_auth
        fake_db.audit_logs.docs[:] = before_audit
