"""
API Tests: Staff — EduFlow Backend

Tests staff profile CRUD and session invalidation behavior.
"""


def _staff_payload(suffix="001"):
    return {
        "name": f"Teacher {suffix}",
        "staff_type": "teacher",
        "employee_id": f"EMP-{suffix}",
        "phone": f"9000000{suffix}",
        "email": f"teacher{suffix}@school.test",
        "department": "Mathematics",
        "qualification": "M.Sc",
        "role": "teacher",
    }


class TestStaffCrud:
    def test_create_staff_creates_user_account(self, client, auth_headers, fake_db):
        response = client.post("/api/staff/", json=_staff_payload("101"), headers=auth_headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["name"] == "Teacher 101"
        assert data["user_id"]
        assert data["temporary_password"].startswith("EduFlow-")
        assert any(user["id"] == data["user_id"] for user in fake_db.auth_users.docs)

    def test_get_staff_returns_role_and_leave_balances(self, client, auth_headers):
        create = client.post("/api/staff/", json=_staff_payload("102"), headers=auth_headers)
        staff_id = create.json()["data"]["id"]

        response = client.get(f"/api/staff/{staff_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["role"] == "teacher"
        assert data["casual_leave_balance"] == 12
        assert data["medical_leave_balance"] == 10
        assert data["earned_leave_balance"] == 15

    def test_list_staff_paginates_and_sorts(self, client, auth_headers):
        response = client.get("/api/staff/?limit=200&sort=department", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        # per_page honours the requested limit (capped at 500). The frontend
        # relies on large page sizes (e.g. TimetableBuilder requests limit=100),
        # so the endpoint must not silently clamp to a small default.
        assert data["meta"]["per_page"] == 200
        assert data["meta"]["sort"] == "department"

    def test_patch_staff_logs_changes_and_updates_role(self, client, auth_headers, fake_db):
        create = client.post("/api/staff/", json=_staff_payload("103"), headers=auth_headers)
        staff_id = create.json()["data"]["id"]

        response = client.patch(
            f"/api/staff/{staff_id}",
            json={"department": "Science", "casual_leave_balance": 8, "sub_category": "class_teacher"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["department"] == "Science"
        assert data["casual_leave_balance"] == 8
        audits = [a for a in fake_db.audit_logs.docs if a["entity_id"] == staff_id and a["action"] == "update"]
        assert audits
        assert audits[-1]["changes"]["department"]["previous"] == "Mathematics"
        assert audits[-1]["changes"]["department"]["new"] == "Science"

    def test_delete_staff_soft_deactivates_and_revokes_sessions(self, client, auth_headers, fake_db):
        create = client.post("/api/staff/", json=_staff_payload("104"), headers=auth_headers)
        staff = create.json()["data"]
        # Seed token using canonical schema (revoked_at: None = active token)
        fake_db.refresh_tokens.docs.append({"id": "rt-1", "user_id": staff["user_id"], "revoked_at": None})

        response = client.delete(f"/api/staff/{staff['id']}", headers=auth_headers)

        assert response.status_code == 200
        staff_doc = next(doc for doc in fake_db.staff.docs if doc["id"] == staff["id"])
        auth_doc = next(doc for doc in fake_db.auth_users.docs if doc["id"] == staff["user_id"])
        assert staff_doc["is_active"] is False
        assert auth_doc["is_active"] is False
        # revoke_user_refresh_tokens (canonical helper) sets revoked_at, not revoked field
        token_doc = next(doc for doc in fake_db.refresh_tokens.docs if doc.get("id") == "rt-1")
        assert token_doc.get("revoked_at") is not None
