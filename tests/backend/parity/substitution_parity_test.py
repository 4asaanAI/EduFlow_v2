"""Story A.6 — dual-entrypoint parity for substitutions.

Same actor (owner) + equivalent inputs (REST passes period_number/subject_id directly;
the AI resolves them from a timetable slot) → substitution doc + audit + notification
byte-identical except a volatile allowlist.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

# The substitution id is freshly generated each run; everything referencing it
# (entity_id/record_id/source_id) is volatile, alongside ids/timestamps.
_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp",
             "source_id", "source_record_id", "entity_id", "record_id"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask(docs):
    out = []
    for d in docs:
        m = {k: v for k, v in d.items() if k not in _VOLATILE}
        ch = m.get("changes")
        if isinstance(ch, dict) and isinstance(ch.get("created"), dict):
            m = {**m, "changes": {"created": {k: v for k, v in ch["created"].items() if k not in _VOLATILE}}}
        out.append(m)
    out.sort(key=lambda d: (d.get("entity_id", ""), d.get("action", ""), d.get("period_number", 0),
                            d.get("notification_type", ""), d.get("type", "")))
    return out


def _snapshot(fake_db):
    return {
        "substitutions": _mask(copy.deepcopy(fake_db.substitutions.docs)),
        "audit_logs": _mask([a for a in copy.deepcopy(fake_db.audit_logs.docs) if a.get("action") == "assign"]),
        "notifications": _mask(copy.deepcopy(fake_db.notifications.docs)),
    }


def _clear(fake_db):
    for col in ("substitutions", "audit_logs", "notifications", "staff", "timetable_slots"):
        getattr(fake_db, col).docs[:] = []


def _seed(fake_db):
    fake_db.staff.docs.append({"id": "teacher-2", "schoolId": "aaryans-joya", "user_id": "tu-2", "name": "Sub"})
    fake_db.timetable_slots.docs.append({"id": "slot-1", "subject_id": "subject-1", "period_number": 2})


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


async def test_ai_and_rest_substitution_identical(client, auth_headers, fake_db, monkeypatch):
    # --- REST (explicit subject_id + period_number) ---
    _seed(fake_db)
    resp = client.post("/api/academics/substitutions", headers=auth_headers, json={
        "date": "2026-05-12", "absent_teacher_id": "teacher-1", "substitute_teacher_id": "teacher-2",
        "class_id": "class-1", "subject_id": "subject-1", "period_number": 2,
    })
    assert resp.status_code == 200
    rest_state = _snapshot(fake_db)

    # --- AI (resolves slot-1 → subject-1, period 2) ---
    _clear(fake_db)
    _seed(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_initiate_substitution(
        {"absent_staff_id": "teacher-1", "substitute_staff_id": "teacher-2",
         "class_id": "class-1", "period_id": "slot-1", "date": "2026-05-12"},
        OWNER_USER, None,
    )
    assert out["success"] is True
    ai_state = _snapshot(fake_db)

    assert ai_state["substitutions"] == rest_state["substitutions"]
    assert ai_state["audit_logs"] == rest_state["audit_logs"]
    assert ai_state["notifications"] == rest_state["notifications"]
    assert rest_state["substitutions"][0]["status"] == "assigned"
    assert len(rest_state["notifications"]) == 1
