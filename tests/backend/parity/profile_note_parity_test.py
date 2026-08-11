"""Owner request 4 - dual-entrypoint parity for private profile notes.

Same seed and the same actor through `POST /api/profile-notes` and the AI
`add_profile_note` tool must land the same note and the same audit row, apart from
the volatile fields. If they ever drift, Flo becomes a second, differently-behaved
way to write on a child's record - and this one is about privacy, so a difference
here is not cosmetic.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

# `entity_id` and `record_id` on the audit row are the note's own generated id, so
# they are volatile for the same reason `id` is.
_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id"}
OWNER_USER = {"id": "admin-1", "role": "owner", "name": "Admin User"}


def _mask(docs):
    out = []
    for doc in docs:
        out.append({k: v for k, v in doc.items() if k not in _VOLATILE})
    out.sort(key=lambda d: (d.get("subject_id", ""), d.get("body", ""), d.get("action", "")))
    return out


def _snapshot(fake_db):
    return {
        "profile_notes": _mask(copy.deepcopy(fake_db.profile_notes.docs)),
        "audit_logs": _mask([
            a for a in copy.deepcopy(fake_db.audit_logs.docs)
            if a.get("action") == "profile_note_added"
        ]),
    }


def _clear(fake_db):
    for col in ("profile_notes", "audit_logs"):
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    # Seeded here rather than relying on the shared fixture's demo student: other
    # parity modules empty `students`, and a missing subject turns this into a
    # "could not find that person" pass-through instead of a parity check.
    original = list(fake_db.students.docs)
    fake_db.students.docs[:] = [{
        "id": "student-1", "schoolId": "aaryans-joya", "name": "Demo Student",
        "class_id": "class-1", "is_active": True, "status": "active",
        "created_at": "2026-01-01T00:00:00",
    }]
    yield
    fake_db.students.docs[:] = original
    _clear(fake_db)


async def test_ai_and_rest_profile_note_identical(client, auth_headers, fake_db, monkeypatch):
    body = "Spoke to the family about attendance after the winter break."

    # --- REST ---
    resp = client.post(
        "/api/profile-notes",
        headers=auth_headers,
        json={"subject_type": "student", "subject_id": "student-1", "body": body},
    )
    assert resp.status_code == 200, resp.text
    rest_state = _snapshot(fake_db)

    # --- AI (subject named rather than pinned by id, which is how a person asks) ---
    _clear(fake_db)
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    out = await tool_functions_v2.tool_add_profile_note(
        {"subject_type": "student", "name": "Demo Student", "note": body},
        OWNER_USER, None,
    )
    assert out["success"] is True, out
    ai_state = _snapshot(fake_db)

    assert ai_state == rest_state


async def test_the_ai_tool_cannot_read_somebody_elses_note(fake_db, monkeypatch):
    """The privacy rule is the point of the feature, so it is proved on the AI side
    too - Flo must not become the way around it."""
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    fake_db.profile_notes.docs.append({
        "id": "note-principal", "schoolId": "aaryans-joya", "branch_id": None,
        "subject_type": "student", "subject_id": "student-1",
        "author_id": "principal-1", "author_name": "P", "author_role": "admin",
        "body": "The principal's own note", "attachments": [],
        "created_at": "2026-08-01T09:00:00", "updated_at": "2026-08-01T09:00:00",
    })

    out = await tool_functions_v2.tool_get_profile_notes(
        {"subject_type": "student", "subject_id": "student-1"}, OWNER_USER, None,
    )

    assert out["data"] == []
    assert "no notes" in out["message"].lower()
