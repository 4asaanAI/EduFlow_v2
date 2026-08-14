"""Creating a colleague is owner and principal only, and the credentials are handed back.

Abhimanyu, 2026-08-15. Two faults were closed together, and they are the same fault
seen from both ends.

1. Creating a staff record MINTS A LOGIN. The gate on it only fired for a privileged
   account (an admin role, or any sub_category), so every office desk - support staff
   included - could create a plain teacher and hand out a way into the platform they
   were never given the authority to issue.

2. The server generated a one-time password and returned it, and the screen closed
   without showing it. The colleague ended up with an account nobody could sign in to,
   and no sign that an account existed at all. The username is returned alongside it
   now: a password on its own is not a way in, and the caller cannot derive the
   username, which comes from whichever of email, phone, employee ID or name was given.

The password is deliberately NOT marked must-change (Abhimanyu, 2026-08-15). The person
can change it themselves from Settings, which every profile already reaches.
"""

from __future__ import annotations

from middleware.auth import create_jwt


def _bearer(payload: dict) -> dict:
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _payload(suffix: str) -> dict:
    return {
        "name": f"Teacher {suffix}",
        "staff_type": "teacher",
        "employee_id": f"EMP-{suffix}",
        "email": f"teacher{suffix}@school.test",
        "role": "teacher",
    }


def test_owner_creates_a_staff_login_and_is_told_the_credentials(client):
    headers = _bearer({"user_id": "sl-owner", "role": "owner", "name": "Aman Litt"})
    resp = client.post("/api/staff/", json=_payload("801"), headers=headers)

    assert resp.status_code == 200
    data = resp.json()["data"]
    # Both halves, or the account is unusable.
    assert data["username"]
    assert data["temporary_password"].startswith("EduFlow-")


def test_principal_creates_a_staff_login(client):
    headers = _bearer({
        "user_id": "sl-principal", "role": "admin",
        "sub_category": "principal", "name": "Adesh Singh",
    })
    resp = client.post("/api/staff/", json=_payload("802"), headers=headers)

    assert resp.status_code == 200
    assert resp.json()["data"]["temporary_password"]


def test_management_head_may_not_create_a_staff_login(client):
    """Lalit runs the day-to-day record. He does not issue a way into the platform."""
    headers = _bearer({
        "user_id": "sl-management", "role": "admin",
        "sub_category": "management", "name": "Lalit Thomas",
    })
    resp = client.post("/api/staff/", json=_payload("803"), headers=headers)

    assert resp.status_code == 403


def test_support_staff_may_not_create_a_staff_login(client):
    """The one that was open. A plain teacher carries no sub_category, so the old
    gate never fired and the lowest office desk could create one."""
    headers = _bearer({
        "user_id": "sl-support", "role": "admin",
        "sub_category": "support_staff", "name": "Office Desk",
    })
    resp = client.post("/api/staff/", json=_payload("804"), headers=headers)

    assert resp.status_code == 403


def test_create_staff_unauthenticated_returns_401(client):
    resp = client.post("/api/staff/", json=_payload("805"))
    assert resp.status_code == 401


def test_create_staff_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "sl-student", "role": "student", "name": "A Student"})
    resp = client.post("/api/staff/", json=_payload("806"), headers=headers)
    assert resp.status_code == 403


def test_the_issued_password_is_not_forced_to_change(client, fake_db):
    """Abhimanyu, 2026-08-15: the password issued stands until the person changes it
    themselves. If this ever flips, it is a decision, not a tidy-up."""
    headers = _bearer({"user_id": "sl-owner-2", "role": "owner", "name": "Aman Litt"})
    resp = client.post("/api/staff/", json=_payload("807"), headers=headers)
    user_id = resp.json()["data"]["user_id"]

    login = next(u for u in fake_db.auth_users.docs if u["id"] == user_id)
    assert login["must_change_password"] is False
