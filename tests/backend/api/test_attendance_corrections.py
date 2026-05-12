"""
API Tests: Attendance corrections - EduFlow Backend.
"""

def _manual_payload():
    return {
        "student_id": "student-1",
        "class_id": "class-1",
        "date": "2026-05-12",
        "status": "present",
        "reason": "Biometric terminal was offline during morning attendance",
    }


class TestAttendanceCorrections:
    def test_manual_attendance_requires_biometric_disabled(self, client, auth_headers, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "true")

        response = client.post("/api/attendance", json=_manual_payload(), headers=auth_headers)

        assert response.status_code == 409

    def test_manual_attendance_creates_audited_manual_record(self, client, auth_headers, fake_db, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "false")

        response = client.post("/api/attendance", json=_manual_payload(), headers=auth_headers)

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "manual"
        assert data["manual_reason"] == _manual_payload()["reason"]
        assert any(a["action"] == "manual_entry" and a["entity_id"] == data["id"] for a in fake_db.audit_logs.docs)

    def test_correction_preserves_original_and_returns_history(self, client, auth_headers, fake_db, monkeypatch):
        monkeypatch.setenv("BIOMETRIC_ATTENDANCE_ENABLED", "false")
        created = client.post("/api/attendance", json=_manual_payload(), headers=auth_headers).json()["data"]

        response = client.patch(
            f"/api/attendance/{created['id']}/correct",
            json={"correction_type": "absent", "reason": "Teacher submitted signed correction note"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        correction = response.json()["data"]
        assert correction["previous_status"] == "present"
        assert correction["new_status"] == "absent"
        assert correction["original_record"]["status"] == "present"
        updated = next(r for r in fake_db.student_attendance.docs if r["id"] == created["id"])
        assert updated["status"] == "absent"

        history = client.get(f"/api/attendance/{created['id']}/history", headers=auth_headers)
        assert history.status_code == 200
        assert len(history.json()["data"]["corrections"]) >= 1

    def test_hard_delete_is_rejected(self, client, auth_headers):
        response = client.delete("/api/attendance/attendance-1", headers=auth_headers)

        assert response.status_code == 405
