"""Story A.7 — dual-entrypoint parity for attendance correction.

Same seed + same actor (owner) through REST PATCH /api/attendance/{id}/correct and
the AI `correct_attendance` tool → attendance_corrections doc + student_attendance
update + 'correct' audit byte-identical except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "corrected_at"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask(docs):
    out = []
    for d in docs:
        m = {k: v for k, v in d.items() if k not in _VOLATILE}
        if isinstance(m.get("original_record"), dict):
            m = {**m, "original_record": {k: v for k, v in m["original_record"].items() if k not in _VOLATILE}}
        out.append(m)
    out.sort(key=lambda d: (d.get("attendance_id", ""), d.get("entity_id", ""), d.get("action", ""), d.get("id", "")))
    return out


def _snapshot(fake_db):
    return {
        "attendance_corrections": _mask(copy.deepcopy(fake_db.attendance_corrections.docs)),
        "student_attendance": _mask(copy.deepcopy(fake_db.student_attendance.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == "correct"]),
    }


def _clear(fake_db):
    for col in ("student_attendance", "attendance_corrections", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


def _seed(fake_db):
    fake_db.student_attendance.docs.append({
        "id": "att-1", "schoolId": "aaryans-joya", "student_id": "student-1",
        "class_id": "class-1", "date": "2026-05-12", "status": "present", "source": "manual",
    })


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_ai_and_rest_correction_identical(client, auth_headers, fake_db, monkeypatch):
    body = {"correction_type": "absent", "reason": "Teacher submitted signed correction note"}
    # --- REST ---
    _seed(fake_db)
    resp = client.patch("/api/attendance/att-1/correct", headers=auth_headers, json=body)
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI ---
    _clear(fake_db)
    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_correct_attendance(
        {"record_id": "att-1", "correction_type": "absent", "reason": "Teacher submitted signed correction note"},
        OWNER_USER, None,
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state["attendance_corrections"] == rest_state["attendance_corrections"]
    assert ai_state["student_attendance"] == rest_state["student_attendance"]
    assert ai_state["audit_logs"] == rest_state["audit_logs"]
    assert rest_state["student_attendance"][0]["status"] == "absent"
    assert len(rest_state["audit_logs"]) == 1
