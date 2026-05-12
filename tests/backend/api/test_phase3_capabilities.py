"""
API Tests: Phase 3 capabilities.
"""

from middleware.auth import create_jwt


def _headers(role="owner", sub_category=None, user_id="user-1"):
    payload = {"user_id": user_id, "role": role, "name": "Test User"}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


class TestIssueNamespaces:
    def test_maintenance_and_it_namespaces_are_isolated(self, client, fake_db):
        fake_db.facility_requests.docs.clear()
        fake_db.tech_requests.docs.clear()

        facility = client.post(
            "/api/issues/facility",
            json={"description": "Leaking tap", "location": "Block A", "category": "plumbing"},
            headers=_headers("admin", "maintenance", "maint-1"),
        )
        blocked_facility_read = client.get("/api/issues/facility", headers=_headers("admin", "it_tech", "it-1"))

        tech = client.post(
            "/api/issues/tech",
            json={"description": "Projector not working", "location": "Lab", "category": "hardware"},
            headers=_headers("admin", "it_tech", "it-1"),
        )
        blocked_tech_read = client.get("/api/issues/tech", headers=_headers("admin", "maintenance", "maint-1"))
        merged = client.get("/api/issues?type=all", headers=_headers("owner", user_id="owner-1"))

        assert facility.status_code == 200
        assert blocked_facility_read.status_code == 403
        assert tech.status_code == 200
        assert blocked_tech_read.status_code == 403
        assert merged.status_code == 200
        assert {item["issue_type"] for item in merged.json()["data"]} == {"facility", "tech"}

    def test_owner_confirmation_closes_facility_request_and_notifies_submitter(self, client, fake_db):
        fake_db.facility_requests.docs.clear()
        fake_db.notifications.docs.clear()

        request_doc = client.post(
            "/api/issues/facility",
            json={"description": "Gate light broken", "category": "electrical"},
            headers=_headers("admin", "maintenance", "maint-1"),
        ).json()["data"]
        client.patch(
            f"/api/issues/facility/{request_doc['id']}",
            json={"status": "pending_owner_confirmation", "note": "Fixed and waiting check"},
            headers=_headers("admin", "maintenance", "maint-1"),
        )
        closed = client.post(
            f"/api/issues/facility/{request_doc['id']}/confirm-resolution",
            headers=_headers("owner", user_id="owner-1"),
        )

        assert closed.status_code == 200
        assert fake_db.facility_requests.docs[0]["status"] == "closed"
        assert fake_db.notifications.docs[-1]["user_id"] == "maint-1"


class TestPhase3ExportsAndAudit:
    def test_attendance_export_returns_csv(self, client, fake_db):
        fake_db.student_attendance.docs[:] = [
            {"id": "att-1", "schoolId": "aaryans-joya", "student_id": "student-1", "class_id": "class-1", "date": "2026-05-01", "status": "present"},
            {"id": "att-2", "schoolId": "aaryans-joya", "student_id": "student-1", "class_id": "class-1", "date": "2026-05-02", "status": "late"},
        ]

        response = client.get("/api/attendance/export?class_id=class-1&month=2026-05&format=csv", headers=_headers("owner"))

        assert response.status_code == 200
        assert "student_name,admission_number,roll_number,present_days,absent_days,late_days,percentage" in response.text
        assert "Demo Student" in response.text

    def test_audit_record_history_supports_direct_record_route(self, client, fake_db):
        fake_db.audit_logs.docs[:] = [{
            "id": "audit-1",
            "schoolId": "aaryans-joya",
            "collection": "students",
            "entity_id": "student-1",
            "action": "update",
            "changed_by": "owner-1",
            "created_at": "2026-05-01T10:00:00",
        }]

        response = client.get("/api/audit-log/student-1", headers=_headers("owner"))

        assert response.status_code == 200
        assert response.json()["data"][0]["entity_id"] == "student-1"


class TestTransportAndSubstitutions:
    def test_transport_aliases_and_transport_head_student_assignment_scope(self, client, fake_db):
        fake_db.transport_routes.docs.clear()
        zone = client.post("/api/transport/zones", json={"name": "Zone A", "fare": 1200}, headers=_headers("admin", "transport_head"))
        update_transport = client.patch("/api/students/student-1", json={"route_zone_id": zone.json()["data"]["id"]}, headers=_headers("admin", "transport_head"))
        blocked_name_change = client.patch("/api/students/student-1", json={"name": "Blocked"}, headers=_headers("admin", "transport_head"))
        roster = client.get("/api/transport/roster", headers=_headers("owner"))

        assert zone.status_code == 200
        assert update_transport.status_code == 200
        assert blocked_name_change.status_code == 403
        assert roster.status_code == 200
        assert roster.json()["meta"]["total"] >= 1

    def test_principal_daily_substitution_plan_finds_absent_teacher_slots(self, client, fake_db):
        fake_db.staff.docs[:] = [
            {"id": "teacher-1", "schoolId": "aaryans-joya", "user_id": "teacher-user-1", "name": "Absent Teacher", "staff_type": "teacher", "is_active": True},
            {"id": "teacher-2", "schoolId": "aaryans-joya", "user_id": "teacher-user-2", "name": "Free Teacher", "staff_type": "teacher", "is_active": True},
        ]
        fake_db.staff_attendance.docs[:] = [{"id": "staff-att-1", "staff_id": "teacher-1", "date": "2026-05-12", "status": "absent"}]
        fake_db.subjects.docs[:] = [{"id": "subject-1", "name": "Math"}]
        fake_db.timetable_slots.docs[:] = [{
            "id": "slot-1",
            "teacher_id": "teacher-1",
            "class_id": "class-1",
            "subject_id": "subject-1",
            "day_of_week": 1,
            "period_number": 2,
            "room": "101",
        }]

        plan = client.get("/api/academics/substitutions?date=2026-05-12", headers=_headers("admin", "principal"))
        item = plan.json()["data"][0]
        assigned = client.post(
            "/api/academics/substitutions",
            json={
                "date": "2026-05-12",
                "absent_teacher_id": item["absent_teacher_id"],
                "substitute_teacher_id": item["candidate_substitutes"][0]["id"],
                "class_id": item["class_id"],
                "subject_id": item["subject_id"],
                "period_number": item["period_number"],
            },
            headers=_headers("admin", "principal"),
        )

        assert plan.status_code == 200
        assert plan.json()["meta"]["absent_teacher_count"] == 1
        assert item["candidate_substitutes"][0]["name"] == "Free Teacher"
        assert assigned.status_code == 200
        assert fake_db.substitutions.docs[-1]["substitute_teacher_id"] == "teacher-2"
