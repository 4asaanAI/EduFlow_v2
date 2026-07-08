from __future__ import annotations
import pytest
from datetime import date, timedelta
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# tool_draft_parent_message
# ---------------------------------------------------------------------------

async def test_draft_parent_message_returns_draft(monkeypatch):
    """tool_draft_parent_message returns a formatted fee_reminder draft."""
    from ai.tool_functions_v2 import tool_draft_parent_message
    from tests.backend.factories import make_student

    student = make_student(name="Alice Kumar", class_id="cls-1")
    student["guardians"] = [
        {
            "name": "Mr Kumar",
            "phone": "9876543210",
            "whatsapp_phone": "9876543210",
            "is_primary": True,
        }
    ]

    db = type("FakeDb", (), {
        "students": FakeCollection([student]),
        "classes": FakeCollection([
            {
                "id": "cls-1",
                "name": "Class 9",
                "section": "A",
                "schoolId": "aaryans-joya",
                "branch_id": "branch-a",
            }
        ]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_draft_parent_message(
        params={"student_id": student["id"], "message_type": "fee_reminder"},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    data_list = result.get("data", [])
    assert len(data_list) == 1
    data = data_list[0]
    assert "draft_message" in data
    assert len(data["draft_message"]) > 20
    assert data["message_type"] == "fee_reminder"


async def test_draft_parent_message_absence_notification(monkeypatch):
    """tool_draft_parent_message produces an absence_notification draft."""
    from ai.tool_functions_v2 import tool_draft_parent_message
    from tests.backend.factories import make_student

    student = make_student(name="Bob Singh", class_id="cls-2")
    student["guardians"] = [
        {"name": "Mrs Singh", "phone": "9000000001", "is_primary": True}
    ]

    db = type("FakeDb", (), {
        "students": FakeCollection([student]),
        "classes": FakeCollection([
            {"id": "cls-2", "name": "Class 10", "section": "B",
             "schoolId": "aaryans-joya", "branch_id": "branch-a"}
        ]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_draft_parent_message(
        params={"student_id": student["id"], "message_type": "absence_notification"},
        user={"id": "u1", "role": "teacher", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    draft = result["data"][0]["draft_message"]
    assert "absent" in draft.lower()


async def test_draft_parent_message_unknown_student_returns_empty(monkeypatch):
    """tool_draft_parent_message returns empty result when student not found."""
    from ai.tool_functions_v2 import tool_draft_parent_message

    db = type("FakeDb", (), {
        "students": FakeCollection([]),
        "classes": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_draft_parent_message(
        params={"student_id": "nonexistent-id", "message_type": "general"},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    assert result.get("data") == []


async def test_draft_parent_message_no_student_id_returns_empty(monkeypatch):
    """tool_draft_parent_message returns empty result when no student_id given."""
    from ai.tool_functions_v2 import tool_draft_parent_message

    db = type("FakeDb", (), {
        "students": FakeCollection([]),
        "classes": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_draft_parent_message(
        params={"message_type": "fee_reminder"},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    assert result.get("data") == []


async def test_draft_parent_message_includes_custom_note(monkeypatch):
    """tool_draft_parent_message inserts a custom note into the draft."""
    from ai.tool_functions_v2 import tool_draft_parent_message
    from tests.backend.factories import make_student

    student = make_student(name="Priya Nair", class_id="cls-3")
    student["guardians"] = [
        {"name": "Mr Nair", "phone": "9111111111", "is_primary": True}
    ]

    db = type("FakeDb", (), {
        "students": FakeCollection([student]),
        "classes": FakeCollection([
            {"id": "cls-3", "name": "Class 8", "section": "C",
             "schoolId": "aaryans-joya", "branch_id": "branch-a"}
        ]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_draft_parent_message(
        params={
            "student_id": student["id"],
            "message_type": "general",
            "note": "Please call before 4 PM.",
        },
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    draft = result["data"][0]["draft_message"]
    assert "Please call before 4 PM." in draft


async def test_draft_parent_message_guardian_phone_in_result(monkeypatch):
    """tool_draft_parent_message exposes guardian phone number in response."""
    from ai.tool_functions_v2 import tool_draft_parent_message
    from tests.backend.factories import make_student

    student = make_student(name="Ravi Mehta", class_id="cls-4")
    student["guardians"] = [
        {
            "name": "Mrs Mehta",
            "phone": "9988776655",
            "whatsapp_phone": "9988776655",
            "is_primary": True,
        }
    ]

    db = type("FakeDb", (), {
        "students": FakeCollection([student]),
        "classes": FakeCollection([
            {"id": "cls-4", "name": "Class 7", "section": "A",
             "schoolId": "aaryans-joya", "branch_id": "branch-a"}
        ]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_draft_parent_message(
        params={"student_id": student["id"], "message_type": "exam_reminder"},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    data = result["data"][0]
    assert data["phone"] == "9988776655"
    assert data["guardian"] == "Mrs Mehta"


# ---------------------------------------------------------------------------
# tool_get_upcoming_events
# ---------------------------------------------------------------------------

async def test_get_upcoming_events_returns_exam_events(monkeypatch):
    """tool_get_upcoming_events returns exam entries within the window."""
    from ai.tool_functions_v2 import tool_get_upcoming_events

    next_week = (date.today() + timedelta(days=7)).isoformat()

    db = type("FakeDb", (), {
        "exams": FakeCollection([
            {
                "id": "e1",
                "name": "Mid Term",
                "subject": "Maths",
                "exam_date": next_week,
                "class_id": "cls-1",
                "schoolId": "aaryans-joya",
                "branch_id": "branch-a",
            }
        ]),
        "announcements": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_upcoming_events(
        params={"days": 14},
        user={"id": "u1", "role": "teacher", "branch_id": "branch-a"},
        scope={"class_ids": ["cls-1"]},
    )

    assert result.get("success") is True
    events = result.get("data", [])
    assert len(events) >= 1
    assert any("Mid Term" in e.get("title", "") for e in events)


async def test_get_upcoming_events_returns_announcement_events(monkeypatch):
    """tool_get_upcoming_events returns published announcements with event_date."""
    from ai.tool_functions_v2 import tool_get_upcoming_events

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    db = type("FakeDb", (), {
        "exams": FakeCollection([]),
        "announcements": FakeCollection([
            {
                "id": "ann-1",
                "title": "Sports Day",
                "event_date": tomorrow,
                # M6: real announcements are stored active + sent_at (never "published").
                "status": "active",
                "sent_at": "2026-07-08T09:00:00+00:00",
                "audience": "all",
                "schoolId": "aaryans-joya",
                "branch_id": "branch-a",
            }
        ]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_upcoming_events(
        params={"days": 7},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    events = result.get("data", [])
    assert any(e.get("title") == "Sports Day" for e in events)


async def test_get_upcoming_events_no_events_returns_empty(monkeypatch):
    """tool_get_upcoming_events returns empty result when nothing is scheduled."""
    from ai.tool_functions_v2 import tool_get_upcoming_events

    db = type("FakeDb", (), {
        "exams": FakeCollection([]),
        "announcements": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_upcoming_events(
        params={"days": 7},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )

    assert result.get("success") is True
    assert result.get("data") == []


async def test_get_upcoming_events_days_capped_at_30(monkeypatch):
    """tool_get_upcoming_events caps days at 30 regardless of input."""
    from ai.tool_functions_v2 import tool_get_upcoming_events

    db = type("FakeDb", (), {
        "exams": FakeCollection([]),
        "announcements": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    # Even with days=999, should not raise and should succeed
    result = await tool_get_upcoming_events(
        params={"days": 999},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope=None,
    )
    assert result.get("success") is True


async def test_get_upcoming_events_events_sorted_by_date(monkeypatch):
    """tool_get_upcoming_events returns events sorted ascending by date."""
    from ai.tool_functions_v2 import tool_get_upcoming_events

    day3 = (date.today() + timedelta(days=3)).isoformat()
    day10 = (date.today() + timedelta(days=10)).isoformat()

    db = type("FakeDb", (), {
        "exams": FakeCollection([
            {
                "id": "e-late",
                "name": "Final Exam",
                "subject": "English",
                "exam_date": day10,
                "class_id": "cls-1",
                "schoolId": "aaryans-joya",
                "branch_id": "branch-a",
            },
            {
                "id": "e-early",
                "name": "Quiz",
                "subject": "Science",
                "exam_date": day3,
                "class_id": "cls-1",
                "schoolId": "aaryans-joya",
                "branch_id": "branch-a",
            },
        ]),
        "announcements": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_upcoming_events(
        params={"days": 14},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope={"class_ids": ["cls-1"]},
    )

    assert result.get("success") is True
    events = result.get("data", [])
    assert len(events) == 2
    assert events[0]["date"] <= events[1]["date"]


async def test_get_upcoming_events_excludes_past_exams(monkeypatch):
    """tool_get_upcoming_events does not return exams with past exam_date."""
    from ai.tool_functions_v2 import tool_get_upcoming_events

    yesterday = (date.today() - timedelta(days=1)).isoformat()

    db = type("FakeDb", (), {
        "exams": FakeCollection([
            {
                "id": "e-past",
                "name": "Past Exam",
                "subject": "History",
                "exam_date": yesterday,
                "class_id": "cls-1",
                "schoolId": "aaryans-joya",
                "branch_id": "branch-a",
            }
        ]),
        "announcements": FakeCollection([]),
    })()

    import ai.tool_functions_v2 as _mod
    monkeypatch.setattr(_mod, "get_db", lambda: db)

    result = await tool_get_upcoming_events(
        params={"days": 7},
        user={"id": "u1", "role": "admin", "branch_id": "branch-a"},
        scope={"class_ids": ["cls-1"]},
    )

    assert result.get("success") is True
    events = result.get("data", [])
    assert not any("Past Exam" in e.get("title", "") for e in events)
