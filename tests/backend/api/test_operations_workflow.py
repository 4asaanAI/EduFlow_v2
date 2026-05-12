"""
API Tests: Operations leave and approval workflows - EduFlow Backend.
"""

from middleware.auth import create_jwt


def _headers(role="owner", sub_category=None):
    payload = {"user_id": "admin-1", "role": role, "name": "Admin User"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


def _seed_staff(fake_db):
    fake_db.staff.docs.append({
        "_id": "staff-admin-1",
        "id": "staff-admin-1",
        "schoolId": "aaryans-joya",
        "user_id": "admin-1",
        "name": "Admin User",
        "is_active": True,
    })


class TestOperationsWorkflow:
    def test_leave_request_self_submit_and_paginated_list(self, client, auth_headers, fake_db):
        _seed_staff(fake_db)
        blocked = client.post("/api/operations/leave-requests", json={
            "user_id": "other-user",
            "date_range": {"start": "2026-05-20", "end": "2026-05-21"},
            "leave_type": "casual",
            "reason": "Family function",
        }, headers=auth_headers)
        created = client.post("/api/operations/leave-requests", json={
            "date_range": {"start": "2026-05-20", "end": "2026-05-21"},
            "leave_type": "casual",
            "reason": "Family function",
        }, headers=auth_headers)
        listed = client.get("/api/operations/leave-requests?status=pending&page=1&limit=20", headers=auth_headers)

        assert blocked.status_code == 403
        assert created.status_code == 200
        assert listed.json()["meta"]["total"] == 1
        assert fake_db.audit_logs.docs[-1]["action"] == "leave_submit"

    def test_leave_decision_requires_reason_and_updates_availability(self, client, auth_headers, fake_db):
        _seed_staff(fake_db)
        leave = client.post("/api/operations/leave-requests", json={
            "date_range": {"start": "2026-05-20", "end": "2026-05-21"},
            "leave_type": "sick",
            "reason": "Medical appointment",
        }, headers=auth_headers).json()["data"]

        missing_reason = client.patch(f"/api/operations/leave-requests/{leave['id']}/decide", json={"status": "approved"}, headers=auth_headers)
        approved = client.patch(
            f"/api/operations/leave-requests/{leave['id']}/decide",
            json={"status": "approved", "reason": "Coverage arranged"},
            headers=auth_headers,
        )

        assert missing_reason.status_code == 400
        assert approved.status_code == 200
        assert fake_db.staff_availability.docs[0]["status"] == "on_leave"
        assert fake_db.notifications.docs[-1]["type"] == "leave_decision"

    def test_approval_request_routing_decision_and_notifications(self, client, auth_headers, fake_db):
        created = client.post("/api/operations/approval-requests", json={
            "title": "Schedule change",
            "description": "Adjust Friday assembly timing",
            "estimated_impact": "Medium",
            "note": "Academic calendar conflict",
            "routing": "owner_and_principal",
        }, headers=_headers("admin", "principal"))
        approval_id = created.json()["data"]["id"]
        listed = client.get("/api/operations/approval-requests?status=pending", headers=auth_headers)
        missing_reason = client.patch(f"/api/operations/approval-requests/{approval_id}/decide", json={"status": "approved"}, headers=auth_headers)
        decided = client.patch(
            f"/api/operations/approval-requests/{approval_id}/decide",
            json={"status": "approved", "reason": "Approved for this term"},
            headers=auth_headers,
        )

        assert created.status_code == 200
        assert listed.json()["meta"]["unread_count"] == 1
        assert missing_reason.status_code == 400
        assert decided.json()["data"]["status"] == "approved"
        assert fake_db.audit_logs.docs[-1]["action"] == "approval_decide"
        assert fake_db.notifications.docs[-1]["type"] == "approval_decision"
