from __future__ import annotations

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt
from services.actor_context import actor_ctx_from_user
from services.attendance_service import AttendanceValidationError, mark_attendance
from tests.backend.factories import make_student

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def attendance_seed(fake_db):
    original_students = list(fake_db.students.docs)
    original_attendance = list(fake_db.student_attendance.docs)
    original_audits = list(fake_db.audit_logs.docs)
    fake_db.students.docs.append(
        make_student(id="student-other-class", class_id="class-2", name="Other Class")
    )
    fake_db.student_attendance.docs[:] = []
    fake_db.audit_logs.docs[:] = []
    yield
    fake_db.students.docs[:] = original_students
    fake_db.student_attendance.docs[:] = original_attendance
    fake_db.audit_logs.docs[:] = original_audits


def _ctx():
    return actor_ctx_from_user(
        {"id": "owner-1", "role": "owner", "name": "Owner"},
        school_id="aaryans-joya",
    )


@pytest.mark.parametrize(
    "params,message",
    [
        (
            {"class_id": "class-1", "date": "08/05/2026", "records": [{"student_id": "student-1", "status": "present"}]},
            "YYYY-MM-DD",
        ),
        (
            {"class_id": "class-1", "date": "2026-08-05", "records": [{"student_id": "student-1", "status": "excused"}]},
            "invalid attendance status",
        ),
        (
            {"class_id": "missing-class", "date": "2026-08-05", "records": [{"student_id": "student-1", "status": "present"}]},
            "class not found",
        ),
        (
            {"class_id": "class-1", "date": "2026-08-05", "records": [{"student_id": "student-other-class", "status": "present"}]},
            "do not belong",
        ),
        (
            {"class_id": "class-1", "date": "2026-08-05", "records": [{"student_id": "student-1", "status": "present"}, {"student_id": "student-1", "status": "absent"}]},
            "only once",
        ),
    ],
)
async def test_invalid_attendance_batches_write_nothing(fake_db, params, message):
    with pytest.raises(AttendanceValidationError, match=message):
        await mark_attendance(fake_db, _ctx(), params)

    assert fake_db.student_attendance.docs == []
    assert fake_db.audit_logs.docs == []


async def test_rest_maps_attendance_validation_to_400(client, fake_db):
    token = create_jwt({"user_id": "owner-1", "role": "owner", "name": "Owner"})
    response = client.post(
        "/api/attendance/student/bulk",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "class_id": "class-1",
            "date": "2026-08-05",
            "records": [{"student_id": "student-other-class", "status": "present"}],
        },
    )

    assert response.status_code == 400
    assert "selected class" in response.json()["detail"]
    assert fake_db.student_attendance.docs == []


async def test_ai_returns_failed_envelope_for_invalid_attendance(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    result = await tool_functions_v2.tool_mark_attendance(
        {
            "class_id": "class-1",
            "date": "2026-08-05",
            "attendance": [{"student_id": "student-other-class", "status": "present"}],
        },
        {"id": "owner-1", "role": "owner", "name": "Owner"},
        None,
    )

    assert result["success"] is False
    assert "selected class" in result["message"]
    assert fake_db.student_attendance.docs == []
