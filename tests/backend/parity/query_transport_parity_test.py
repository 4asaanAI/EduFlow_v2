"""Wave-2 dual-entrypoint parity — query tickets, transport, announcement moderation.

Covers:
  create/resolve/reopen/assign/delete_query_ticket → services/query_ticket_service.py
  create/update/delete_transport_route, add_transport_vehicle → services/transport_service.py
  decide_announcement / delete_announcement → services/announcement_service.py
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id",
             "resolved_at", "approved_at", "rejected_at", "source_id"}

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


_COLS = ("queries", "transport_routes", "vehicles", "announcements", "audit_logs",
         "notifications", "students")


def _clear(fake_db, cols=_COLS):
    for col in cols:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _ai_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    saved_students = list(fake_db.students.docs)
    _clear(fake_db)
    yield
    _clear(fake_db)
    fake_db.students.docs[:] = saved_students


# ─── Query tickets ───────────────────────────────────────────────────────────

_TICKET = {"title": "Projector broken", "description": "Lab 1 projector will not start",
           "priority": "high"}


def _ticket_state(fake_db):
    return {"queries": _mask(fake_db.queries.docs)}


def _seed_ticket(fake_db, status="open"):
    fake_db.queries.docs[:] = [{
        "_id": "tk-1", "id": "tk-1", "schoolId": SCHOOL, "title": "Projector broken",
        "description": "Lab 1 projector will not start", "priority": "high",
        "status": status, "category": "general", "assigned_to": None,
        "created_by": "own-1", "created_by_name": "Owner", "created_by_role": "owner",
        "attachment_url": None, "attachment_type": None,
        "created_at": "2026-06-10T08:00:00", "resolved_at": None,
        "resolved_by": None, "resolved_by_name": None,
    }]


async def test_create_query_ticket_parity(client, fake_db):
    resp = client.post("/api/queries", data=_TICKET, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _ticket_state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_create_query_ticket(dict(_TICKET), OWNER_USER, None)
    assert out["success"] is True
    assert _ticket_state(fake_db) == rest_state
    assert rest_state["queries"][0]["status"] == "open"


async def test_resolve_and_reopen_ticket_parity(client, fake_db):
    _seed_ticket(fake_db)
    resp = client.patch("/api/queries/tk-1/resolve", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _ticket_state(fake_db)

    _seed_ticket(fake_db)
    out = await tool_functions_v2.tool_resolve_query_ticket({"ticket_id": "tk-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert _ticket_state(fake_db) == rest_state
    assert fake_db.queries.docs[0]["status"] == "resolved"

    out = await tool_functions_v2.tool_reopen_query_ticket({"ticket_id": "tk-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert fake_db.queries.docs[0]["status"] == "open"
    assert fake_db.queries.docs[0]["resolved_by"] is None


async def test_assign_and_delete_ticket_parity(client, fake_db):
    _seed_ticket(fake_db)
    resp = client.patch("/api/queries/tk-1/assign", json={"assigned_to": "staff-9"},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _ticket_state(fake_db)

    _seed_ticket(fake_db)
    out = await tool_functions_v2.tool_assign_query_ticket(
        {"ticket_id": "tk-1", "assigned_to": "staff-9"}, OWNER_USER, None)
    assert out["success"] is True
    assert _ticket_state(fake_db) == rest_state
    assert fake_db.queries.docs[0]["status"] == "in_progress"

    out = await tool_functions_v2.tool_delete_query_ticket({"ticket_id": "tk-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert fake_db.queries.docs == []
    assert any(a.get("entity_type") == "query_ticket" and a.get("action") == "delete"
               for a in fake_db.audit_logs.docs)  # F.10 deletion audit


# ─── Transport ───────────────────────────────────────────────────────────────

_ROUTE = {"route_name": "Zone A — Joya Market", "start_point": "School",
          "end_point": "Joya Market", "driver_name": "Ramesh", "fare": 800}


def _transport_state(fake_db):
    return {
        "transport_routes": _mask(fake_db.transport_routes.docs),
        "vehicles": _mask(fake_db.vehicles.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs
                        if a.get("entity_type") in ("transport_route", "vehicle")]),
    }


def _seed_route(fake_db):
    fake_db.transport_routes.docs[:] = [{
        "_id": "rt-1", "id": "rt-1", "schoolId": SCHOOL, "route_name": "Zone A",
        "start_point": "School", "end_point": "Market", "stops": [], "driver_name": "Ramesh",
        "driver_phone": "", "vehicle_no": "", "capacity": "", "fare": 800,
        "is_active": True, "created_at": "2026-06-01T00:00:00",
    }]


async def test_create_transport_route_parity(client, fake_db):
    resp = client.post("/api/transport", json=_ROUTE, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _transport_state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_create_transport_route(dict(_ROUTE), OWNER_USER, None)
    assert out["success"] is True
    assert _transport_state(fake_db) == rest_state


async def test_update_route_and_vehicle_parity(client, fake_db):
    _seed_route(fake_db)
    resp = client.patch("/api/transport/rt-1", json={"driver_name": "Suresh", "fare": 900},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _transport_state(fake_db)

    _clear(fake_db)
    _seed_route(fake_db)
    out = await tool_functions_v2.tool_update_transport_route(
        {"route_id": "rt-1", "driver_name": "Suresh", "fare": 900}, OWNER_USER, None)
    assert out["success"] is True
    assert _transport_state(fake_db) == rest_state

    body = {"vehicle_number": "UP14 AB 1234", "capacity": 40, "driver_name": "Suresh"}
    resp = client.post("/api/transport/vehicles", json=body, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _transport_state(fake_db)

    fake_db.vehicles.docs[:] = []
    fake_db.audit_logs.docs[:] = [a for a in fake_db.audit_logs.docs if a.get("entity_type") != "vehicle"]
    out = await tool_functions_v2.tool_add_transport_vehicle(dict(body), OWNER_USER, None)
    assert out["success"] is True
    assert _transport_state(fake_db)["vehicles"] == rest_state["vehicles"]


async def test_delete_route_blocked_with_assigned_students_both_entrypoints(client, fake_db):
    _seed_route(fake_db)
    fake_db.students.docs.append({
        "_id": "stu-rt", "id": "stu-rt", "schoolId": SCHOOL, "name": "R",
        "route_zone_id": "rt-1", "is_active": True,
    })
    resp = client.delete("/api/transport/rt-1", headers=_owner_headers())
    assert resp.status_code == 409
    out = await tool_functions_v2.tool_delete_transport_route({"route_id": "rt-1"}, OWNER_USER, None)
    assert out["success"] is False
    assert len(fake_db.transport_routes.docs) == 1

    fake_db.students.docs[:] = [s for s in fake_db.students.docs if s.get("id") != "stu-rt"]
    out = await tool_functions_v2.tool_delete_transport_route({"route_id": "rt-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert fake_db.transport_routes.docs == []


# ─── Announcement moderation ─────────────────────────────────────────────────

def _seed_pending_announcement(fake_db):
    fake_db.announcements.docs[:] = [{
        "_id": "ann-1", "id": "ann-1", "schoolId": SCHOOL, "title": "Sports Day",
        "content": "Sports day on Friday", "status": "pending_approval",
        "created_by": "teacher-1", "target_roles": ["teacher", "student"],
        "created_at": "2026-06-10T08:00:00",
    }]


def _ann_state(fake_db):
    return {
        "announcements": _mask(fake_db.announcements.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("entity_type") == "announcement"]),
        "notifications": _mask(fake_db.notifications.docs),
    }


async def test_decide_announcement_approve_parity(client, fake_db):
    _seed_pending_announcement(fake_db)
    resp = client.patch("/api/ops/announcements/ann-1/approve", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _ann_state(fake_db)

    _clear(fake_db)
    _seed_pending_announcement(fake_db)
    out = await tool_functions_v2.tool_decide_announcement(
        {"announcement_id": "ann-1", "decision": "approve"}, OWNER_USER, None)
    assert out["success"] is True
    assert _ann_state(fake_db) == rest_state
    assert fake_db.announcements.docs[0]["status"] == "active"


async def test_decide_announcement_reject_parity_notifies_author(client, fake_db):
    _seed_pending_announcement(fake_db)
    resp = client.patch("/api/ops/announcements/ann-1/reject", json={"reason": "duplicate"},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _ann_state(fake_db)

    _clear(fake_db)
    _seed_pending_announcement(fake_db)
    out = await tool_functions_v2.tool_decide_announcement(
        {"announcement_id": "ann-1", "decision": "reject", "reason": "duplicate"}, OWNER_USER, None)
    assert out["success"] is True
    assert _ann_state(fake_db) == rest_state
    assert len(rest_state["notifications"]) == 1


async def test_delete_announcement_parity(client, fake_db):
    _seed_pending_announcement(fake_db)
    resp = client.delete("/api/ops/announcements/ann-1", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _ann_state(fake_db)

    _clear(fake_db)
    _seed_pending_announcement(fake_db)
    out = await tool_functions_v2.tool_delete_announcement({"announcement_id": "ann-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert _ann_state(fake_db) == rest_state
    assert fake_db.announcements.docs == []
    assert len(rest_state["audit"]) == 1  # F.10 deletion audit
