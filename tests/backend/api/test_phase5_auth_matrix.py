"""
API Tests: Phase 5 auth matrix, tenant isolation, and guarded routes.
"""

import pytest

from middleware.auth import create_jwt


def _headers(role="owner", sub_category=None, user_id="user-1"):
    payload = {"user_id": user_id, "role": role, "name": "Phase 5 User"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


class TestPhase5AuthMatrix:
    @pytest.mark.parametrize(
        ("headers", "expected_status"),
        [
            (_headers("owner", user_id="owner-1"), 200),
            (_headers("admin", "principal", "principal-1"), 200),
            (_headers("admin", "accountant", "accountant-1"), 403),
            (_headers("teacher", user_id="teacher-1"), 403),
            (_headers("student", user_id="student-user-1"), 403),
        ],
    )
    def test_manual_attendance_is_limited_to_owner_and_principal(
        self, client, fake_db, monkeypatch, headers, expected_status
    ):
        fake_db.student_attendance.docs.clear()
        monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "false")

        response = client.post(
            "/api/attendance",
            json={
                "student_id": "student-1",
                "class_id": "class-1",
                "date": "2026-05-12",
                "status": "present",
                "reason": "Phase 5 auth matrix check",
            },
            headers=headers,
        )

        assert response.status_code == expected_status

    @pytest.mark.parametrize("path", ["/api/attendance", "/api/fees/transactions"])
    def test_guarded_routes_reject_missing_auth(self, client, path, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "false")

        if path == "/api/attendance":
            response = client.post(
                path,
                json={
                    "student_id": "student-1",
                    "class_id": "class-1",
                    "date": "2026-05-12",
                    "status": "present",
                    "reason": "Missing auth check",
                },
            )
        else:
            response = client.get(path)

        assert response.status_code == 401

    def test_principal_can_read_fee_transactions_but_teacher_cannot(self, client, fake_db):
        fake_db.fee_transactions.docs[:] = [
            {
                "_id": "fee-1",
                "id": "fee-1",
                "schoolId": "aaryans-joya",
                "student_id": "student-1",
                "fee_period": "2026-05",
                "fee_head": "tuition",
                "fee_type": "tuition",
                "amount": 1500,
                "status": "paid",
                "created_at": "2026-05-12T10:00:00",
            }
        ]

        principal = client.get(
            "/api/fees/transactions",
            headers=_headers("admin", "principal", "principal-1"),
        )
        teacher = client.get(
            "/api/fees/transactions",
            headers=_headers("teacher", user_id="teacher-1"),
        )

        assert principal.status_code == 200
        assert principal.json()["data"][0]["id"] == "fee-1"
        assert teacher.status_code == 403

    def test_fee_summary_is_namespaced_to_current_school(self, client, fake_db):
        fake_db.fee_transactions.docs[:] = [
            {
                "_id": "current-school-fee",
                "id": "current-school-fee",
                "schoolId": "aaryans-joya",
                "student_id": "student-1",
                "fee_period": "2026-05",
                "fee_head": "tuition",
                "amount": 100,
                "status": "paid",
            },
            {
                "_id": "other-school-fee",
                "id": "other-school-fee",
                "schoolId": "other-school",
                "student_id": "student-2",
                "fee_period": "2026-05",
                "fee_head": "tuition",
                "amount": 999,
                "status": "paid",
            },
        ]

        response = client.get(
            "/api/fees/summary?fee_period=2026-05",
            headers=_headers("owner", user_id="owner-1"),
        )

        assert response.status_code == 200
        assert response.json()["data"]["total_collected"] == 100
        assert response.json()["data"]["transactions"] == 1
