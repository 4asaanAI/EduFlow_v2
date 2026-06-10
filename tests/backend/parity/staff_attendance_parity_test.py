"""Dual-entrypoint parity — bulk staff attendance marking.

Same seed through REST `POST /api/attendance/staff/bulk` and the AI
`mark_staff_attendance` tool → identical staff_attendance docs + ONE audit row
per bulk call (EC-14.1), via services/staff_attendance_service.py (AD7).
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}
SCHOOL = "aaryans-joya"


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _scrub(value):
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _mask(docs):
    out = [_scrub(d) for d in copy.deepcopy(docs)]
    return sorted(out, key=lambda d: str(sorted(d.items())))


def _state(fake_db):
    return {
        "staff_attendance": _mask(fake_db.staff_attendance.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("entity_type") == "staff_attendance"]),
    }


def _clear(fake_db):
    for col in ("staff_attendance", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _ai_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db)
    yield
    _clear(fake_db)


_BODY = {
    "date": "2026-06-10",
    "records": [
        {"staff_id": "staff-1", "status": "present"},
        {"staff_id": "staff-2", "status": "late", "check_in": "09:30"},
    ],
}


async def test_staff_bulk_attendance_parity(client, fake_db):
    resp = client.post("/api/attendance/staff/bulk", json=_BODY, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_mark_staff_attendance(copy.deepcopy(_BODY), OWNER_USER, None)
    assert out["success"] is True
    assert _state(fake_db) == rest_state
    assert len(rest_state["staff_attendance"]) == 2
    assert len(rest_state["audit"]) == 1  # EC-14.1: one audit row per bulk call


async def test_ai_mark_all_staff_expands_active_staff(fake_db):
    fake_db.staff.docs[:] = [
        {"_id": "staff-1", "id": "staff-1", "schoolId": SCHOOL, "name": "A", "is_active": True},
        {"_id": "staff-2", "id": "staff-2", "schoolId": SCHOOL, "name": "B", "is_active": True},
        {"_id": "staff-3", "id": "staff-3", "schoolId": SCHOOL, "name": "C", "is_active": False},
    ]
    out = await tool_functions_v2.tool_mark_staff_attendance(
        {"date": "2026-06-10", "status": "present"}, OWNER_USER, None)
    assert out["success"] is True
    assert out["data"]["marked"] == 2  # inactive staff excluded
    marked_ids = {d["staff_id"] for d in fake_db.staff_attendance.docs}
    assert marked_ids == {"staff-1", "staff-2"}
    fake_db.staff.docs[:] = []


async def test_invalid_status_rejected_on_both_entrypoints(client, fake_db):
    bad = {"date": "2026-06-10", "records": [{"staff_id": "staff-1", "status": "vacationing"}]}
    resp = client.post("/api/attendance/staff/bulk", json=bad, headers=_owner_headers())
    assert resp.status_code == 400
    out = await tool_functions_v2.tool_mark_staff_attendance(bad, OWNER_USER, None)
    assert out["success"] is False
    assert fake_db.staff_attendance.docs == []
