"""Story A.1 — characterization + actor_ctx contract for the attendance service.

Pins the REST `POST /api/attendance/student/bulk` blast radius (records + the
single bulk audit row + idempotency) so the service extraction is provably
behavior-preserving, and pins the `actor_ctx` contract (AD14).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from services.actor_context import ActorContext, actor_ctx_from_user
from services.attendance_service import mark_attendance

pytestmark = pytest.mark.asyncio

OWNER_HEADERS = None  # set via auth_headers fixture in REST tests


_TOUCHED = ("student_attendance", "audit_logs", "attendance_bulk_keys", "idempotency_keys")


@pytest.fixture(autouse=True)
def _clean(fake_db):
    for col in _TOUCHED:
        getattr(fake_db, col).docs[:] = []
    yield
    for col in _TOUCHED:
        getattr(fake_db, col).docs[:] = []


# ─── REST characterization (red baseline → must stay green after extraction) ──

def test_rest_bulk_marks_records_and_writes_one_audit(client, auth_headers, fake_db):
    resp = client.post(
        "/api/attendance/student/bulk",
        headers=auth_headers,
        json={
            "class_id": "class-1",
            "date": "2026-06-08",
            "records": [
                {"student_id": "student-1", "status": "present"},
                {"student_id": "student-9", "status": "absent"},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data == [
        {"student_id": "student-1", "status": "saved"},
        {"student_id": "student-9", "status": "saved"},
    ]

    att = fake_db.student_attendance.docs
    assert len(att) == 2
    for doc in att:
        assert doc["source"] == "bulk"
        assert doc["date"] == "2026-06-08"
        assert doc["class_id"] == "class-1"
        assert doc["marked_by"] == "admin-1"
        assert doc["schoolId"] == "aaryans-joya"
        assert "created_at" not in doc  # canonical bulk record carries no created_at

    audits = [d for d in fake_db.audit_logs.docs if d.get("action") == "attendance_bulk"]
    assert len(audits) == 1
    assert audits[0]["entity_id"] == "class-1"
    assert audits[0]["changes"] == {"count_marked": 2, "date": "2026-06-08", "class_id": "class-1"}


def test_rest_bulk_idempotency_key_replays_without_second_write(client, auth_headers, fake_db):
    # The global Idempotency-Key middleware (server.py) fronts header-based keys:
    # the replay returns the first response verbatim and the route never re-runs,
    # so exactly one bulk audit row exists. (The route/service-level
    # attendance_bulk_keys layer is exercised directly in the service test below.)
    payload = {
        "class_id": "class-1",
        "date": "2026-06-08",
        "records": [{"student_id": "student-1", "status": "present"}],
    }
    headers = {**auth_headers, "Idempotency-Key": "abc-123"}

    first = client.post("/api/attendance/student/bulk", headers=headers, json=payload)
    second = client.post("/api/attendance/student/bulk", headers=headers, json=payload)

    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    audits = [d for d in fake_db.audit_logs.docs if d.get("action") == "attendance_bulk"]
    assert len(audits) == 1


# ─── actor_ctx contract (AD14) ────────────────────────────────────────────────

def test_actor_context_pinned_fields():
    fields = {f.name for f in dataclasses.fields(ActorContext)}
    assert fields == {
        "user_id", "role", "sub_category", "school_id", "branch_id", "actor_name", "now_fn",
    }


def test_actor_context_is_frozen():
    ctx = actor_ctx_from_user({"id": "u1", "role": "owner", "name": "Owner"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.user_id = "u2"  # type: ignore[misc]


def test_actor_ctx_from_user_synthesizes_consistently():
    user = {"id": "u1", "role": "admin", "sub_category": "principal", "name": "P", "branch_id": "branch-a"}
    rest_ctx = actor_ctx_from_user(user, school_id="aaryans-joya")
    ai_ctx = actor_ctx_from_user(user, school_id="aaryans-joya", branch_id="branch-a")
    assert rest_ctx == ai_ctx
    assert rest_ctx.sub_category == "principal"
    assert rest_ctx.branch_id == "branch-a"
    assert rest_ctx.actor_name == "P"


def test_actor_ctx_now_fn_is_injectable():
    fixed = datetime(2020, 1, 2, 3, 4, 5)
    ctx = actor_ctx_from_user({"id": "u1"}, now_fn=lambda: fixed)
    assert ctx.now_iso() == fixed.isoformat()


# ─── service-level behavior (entrypoint-independent) ──────────────────────────

async def test_service_marks_and_audits(fake_db):
    ctx = actor_ctx_from_user(
        {"id": "admin-1", "role": "owner", "name": "Admin User"}, school_id="aaryans-joya"
    )
    result = await mark_attendance(
        fake_db,
        ctx,
        {"class_id": "class-1", "date": "2026-06-08", "records": [{"student_id": "student-1", "status": "present"}]},
    )
    assert result == {"results": [{"student_id": "student-1", "status": "saved"}], "idempotent": False}
    assert len(fake_db.student_attendance.docs) == 1
    assert fake_db.student_attendance.docs[0]["source"] == "bulk"
    assert len([d for d in fake_db.audit_logs.docs if d.get("action") == "attendance_bulk"]) == 1


async def test_service_idempotency_key_replays_cached(fake_db):
    ctx = actor_ctx_from_user({"id": "admin-1", "role": "owner"}, school_id="aaryans-joya")
    params = {"class_id": "class-1", "date": "2026-06-08", "records": [{"student_id": "student-1", "status": "present"}]}

    first = await mark_attendance(fake_db, ctx, params, idempotency_key="k-1")
    second = await mark_attendance(fake_db, ctx, params, idempotency_key="k-1")

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert second["results"] == first["results"]
    # Replay short-circuits before writing a second audit row.
    assert len([d for d in fake_db.audit_logs.docs if d.get("action") == "attendance_bulk"]) == 1


async def test_service_does_not_raise_httpexception_on_empty(fake_db):
    ctx = actor_ctx_from_user({"id": "admin-1", "role": "owner"}, school_id="aaryans-joya")
    result = await mark_attendance(fake_db, ctx, {"class_id": "class-1", "date": "2026-06-08", "records": []})
    assert result["results"] == []
    # Empty bulk still writes exactly one audit row (count_marked=0), matching REST.
    assert len([d for d in fake_db.audit_logs.docs if d.get("action") == "attendance_bulk"]) == 1
