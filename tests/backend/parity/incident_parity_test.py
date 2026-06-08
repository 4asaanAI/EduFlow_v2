"""Stories C.2 / C.3 — dual-entrypoint parity for the incident/complaint tools.

Same seed + same actor (owner) through the REST route and the AI tool → the resolved
collection doc + audit row + notification fan-out are byte-identical except a volatile
allowlist (ids / timestamps).

Covered:
  C.2  assign  — PATCH /api/ops/incidents/{id}/assign       vs  tool_assign_followup
  C.2  thread  — POST  /api/ops/incidents/{id}/thread       vs  tool_add_thread_entry
  C.3  status  — PATCH /api/ops/incidents/{id}              vs  tool_update_incident_status
  C.3  confirm — POST  /api/issues/facility/{id}/confirm-resolution vs tool_confirm_resolution
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "timestamp", "updated_at", "resolved_at"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _scrub(value):
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _audits(fake_db, action):
    rows = [a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == action]
    return [_scrub(r) for r in rows]


def _notifs(fake_db):
    return [_scrub(n) for n in copy.deepcopy(fake_db.notifications.docs)]


def _clear(fake_db):
    for col in ("incidents", "complaints", "facility_requests", "tech_requests", "audit_logs", "notifications", "staff"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db, monkeypatch):
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    yield
    _clear(fake_db)


def _seed_incident(fake_db):
    fake_db.incidents.docs.append({
        "_id": "inc-1", "id": "inc-1", "schoolId": "aaryans-joya",
        "status": "open", "thread": [], "created_at": "2026-05-01T00:00:00",
    })


def _seed_staff(fake_db):
    fake_db.staff.docs.append({
        "_id": "staff-1", "id": "staff-1", "schoolId": "aaryans-joya", "user_id": "staff-user-1",
    })


async def test_assign_parity(client, auth_headers, fake_db):
    payload = {"assigned_to": "staff-1", "due_date": "2026-06-15", "note": "Please follow up."}
    # --- REST ---
    _seed_incident(fake_db)
    _seed_staff(fake_db)
    resp = client.patch("/api/ops/incidents/inc-1/assign", headers=auth_headers, json=payload)
    assert resp.status_code == 200
    rest = (_scrub(copy.deepcopy(fake_db.incidents.docs[0])), _audits(fake_db, "assign_followup"), _notifs(fake_db))

    # --- AI ---
    _clear(fake_db)
    _seed_incident(fake_db)
    _seed_staff(fake_db)
    out = await tool_functions_v2.tool_assign_followup(
        {"record_id": "inc-1", "assignee_staff_id": "staff-1", "due_date": "2026-06-15", "note": "Please follow up."},
        OWNER_USER, None,
    )
    assert out["success"] is True
    ai = (_scrub(copy.deepcopy(fake_db.incidents.docs[0])), _audits(fake_db, "assign_followup"), _notifs(fake_db))

    assert ai == rest
    assert len(rest[1]) == 1  # one audit row
    assert len(rest[2]) == 1  # one notification to the assignee


async def test_thread_parity(client, auth_headers, fake_db):
    # --- REST ---
    _seed_incident(fake_db)
    resp = client.post("/api/ops/incidents/inc-1/thread", headers=auth_headers, json={"content": "Looking into it."})
    assert resp.status_code == 200
    rest = (_scrub(copy.deepcopy(fake_db.incidents.docs[0])), _audits(fake_db, "add_thread_entry"))

    # --- AI ---
    _clear(fake_db)
    _seed_incident(fake_db)
    out = await tool_functions_v2.tool_add_thread_entry(
        {"record_id": "inc-1", "content": "Looking into it."}, OWNER_USER, None,
    )
    assert out["success"] is True
    ai = (_scrub(copy.deepcopy(fake_db.incidents.docs[0])), _audits(fake_db, "add_thread_entry"))

    assert ai == rest
    assert len(rest[1]) == 1


async def test_status_parity(client, auth_headers, fake_db):
    # --- REST (status only, to match the AI tool's surface) ---
    _seed_incident(fake_db)
    resp = client.patch("/api/ops/incidents/inc-1", headers=auth_headers, json={"status": "in_progress"})
    assert resp.status_code == 200
    rest = (_scrub(copy.deepcopy(fake_db.incidents.docs[0])), _audits(fake_db, "update_incident_status"))

    # --- AI ---
    _clear(fake_db)
    _seed_incident(fake_db)
    out = await tool_functions_v2.tool_update_incident_status(
        {"record_id": "inc-1", "new_status": "in_progress", "note": "Started work."}, OWNER_USER, None,
    )
    assert out["success"] is True
    ai_doc = _scrub(copy.deepcopy(fake_db.incidents.docs[0]))
    ai_audit = _audits(fake_db, "update_incident_status")

    # The AI tool also threads a note; the REST status-only update does not. Compare the
    # status transition + audit (the parity surface), allowing the AI thread note.
    assert ai_doc["status"] == rest[0]["status"] == "in_progress"
    assert ai_audit[0]["changes"]["previous_status"] == rest[1][0]["changes"]["previous_status"] == "open"
    assert ai_audit[0]["changes"]["status"] == rest[1][0]["changes"]["status"] == "in_progress"


def _seed_facility(fake_db):
    fake_db.facility_requests.docs.append({
        "_id": "fr-1", "id": "fr-1", "schoolId": "aaryans-joya",
        "status": "pending_owner_confirmation", "logged_by": "maint-1", "notes": [],
        "created_at": "2026-05-01T00:00:00",
    })


async def test_confirm_resolution_parity(client, auth_headers, fake_db):
    # --- REST ---
    _seed_facility(fake_db)
    resp = client.post("/api/issues/facility/fr-1/confirm-resolution", headers=auth_headers, json={"confirmation_note": "Verified."})
    assert resp.status_code == 200
    rest = (_scrub(copy.deepcopy(fake_db.facility_requests.docs[0])), _audits(fake_db, "confirm_resolution"), _notifs(fake_db))

    # --- AI ---
    _clear(fake_db)
    _seed_facility(fake_db)
    out = await tool_functions_v2.tool_confirm_resolution(
        {"request_id": "fr-1", "confirmation_note": "Verified."}, OWNER_USER, None,
    )
    assert out["success"] is True
    ai = (_scrub(copy.deepcopy(fake_db.facility_requests.docs[0])), _audits(fake_db, "confirm_resolution"), _notifs(fake_db))

    assert ai == rest
    assert rest[0]["status"] == "closed"
    assert len(rest[1]) == 1
    assert len(rest[2]) == 1
