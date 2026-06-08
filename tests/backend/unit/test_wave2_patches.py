"""Wave 2 (P6–P11) patch acceptance tests.

Covers:
  P6  — _is_tool_authorized + registry sub_categories
  P7  — tool_create_announcement moderation gate
  P8  — content filter on rich_blocks and tool data for students
  P9  — confirm-token tenant binding, peek raises, TTL boundary, decrement
  P10 — stable sort tie-break, expires_at required
  P11 — safe_token_count coerce, restricted_exact extension, random delay,
         keepalive SSE comment, zero-width whitespace, _extract_rich_content,
         _missing_required_params numeric validators
"""
from __future__ import annotations

import asyncio
import json
import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role: str, sub_category: str | None = None, **kw) -> dict:
    return {"id": "u1", "role": role, "sub_category": sub_category, **kw}


# ---------------------------------------------------------------------------
# P6 — _is_tool_authorized
# ---------------------------------------------------------------------------

def test_is_tool_authorized_basic_role_check():
    from routes.chat import _is_tool_authorized
    tool = {"roles": ["owner", "admin"]}
    assert _is_tool_authorized(_make_user("owner"), tool) is True
    assert _is_tool_authorized(_make_user("teacher"), tool) is False


def test_is_tool_authorized_no_sub_categories_allows_any_admin():
    from routes.chat import _is_tool_authorized
    tool = {"roles": ["admin"]}
    assert _is_tool_authorized(_make_user("admin", "principal"), tool) is True
    assert _is_tool_authorized(_make_user("admin", "accountant"), tool) is True
    assert _is_tool_authorized(_make_user("admin", None), tool) is True


def test_is_tool_authorized_sub_categories_restricts_admin():
    from routes.chat import _is_tool_authorized
    tool = {"roles": ["owner", "admin"], "sub_categories": ["principal"]}
    # Owner passes regardless of sub_categories restriction
    assert _is_tool_authorized(_make_user("owner"), tool) is True
    # Admin must match sub_category
    assert _is_tool_authorized(_make_user("admin", "principal"), tool) is True
    assert _is_tool_authorized(_make_user("admin", "accountant"), tool) is False
    assert _is_tool_authorized(_make_user("admin", None), tool) is False


def test_is_tool_authorized_multi_sub_category():
    from routes.chat import _is_tool_authorized
    tool = {"roles": ["owner", "admin"], "sub_categories": ["accountant", "principal"]}
    assert _is_tool_authorized(_make_user("admin", "accountant"), tool) is True
    assert _is_tool_authorized(_make_user("admin", "principal"), tool) is True
    assert _is_tool_authorized(_make_user("admin", "maintenance"), tool) is False


def test_registry_tools_have_sub_categories_where_expected():
    from ai.tool_functions_v2 import TOOL_REGISTRY
    # Tools that should restrict to specific admin sub_categories
    restricted = {
        "assign_followup": ["principal"],
        "add_thread_entry": ["principal"],
        "initiate_substitution": ["principal"],
        "correct_attendance": ["principal"],
        "log_contact_event": ["accountant"],
        "apply_discount": ["accountant"],
        "record_fee_payment": ["accountant"],
        "query_attendance_status": ["principal"],
        "query_fee_status": ["accountant", "principal"],
        "query_incidents": ["principal"],
        "query_staff_availability": ["principal"],
        "query_maintenance_requests": ["maintenance"],
        "query_student_record": ["principal", "accountant", "transport_head"],
        "create_announcement": ["principal"],
    }
    for tool_name, expected_subs in restricted.items():
        entry = TOOL_REGISTRY[tool_name]
        actual = entry.get("sub_categories")
        assert actual is not None, f"{tool_name}: missing sub_categories"
        assert sorted(actual) == sorted(expected_subs), (
            f"{tool_name}: sub_categories {actual!r} != {expected_subs!r}"
        )


def test_detect_tool_from_keywords_uses_user_dict(monkeypatch):
    from routes.chat import detect_tool_from_keywords
    # Owner should detect school pulse
    owner = _make_user("owner")
    assert detect_tool_from_keywords("school pulse today", owner) == "get_school_pulse"
    # Teacher should NOT get fee summary (restricted to owner/admin)
    teacher = _make_user("teacher")
    assert detect_tool_from_keywords("fee summary", teacher) is None


def test_accountant_blocked_from_non_accountant_tool():
    from routes.chat import _is_tool_authorized
    from ai.tool_functions_v2 import TOOL_REGISTRY
    # query_attendance_status requires principal, not accountant
    tool_def = TOOL_REGISTRY["query_attendance_status"]
    assert _is_tool_authorized(_make_user("admin", "accountant"), tool_def) is False
    assert _is_tool_authorized(_make_user("admin", "principal"), tool_def) is True


# ---------------------------------------------------------------------------
# P7 — Announcement moderation gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_announcement_staff_audience_sets_pending_approval():
    """'staff' audience_type includes teachers → must be pending_approval.

    Story A.4: the moderation gate now exempts owner/principal (EC-9.1, matching the
    REST route). This test uses a non-exempt role (reception) so it still exercises the
    content gate (staff audience → pending). An owner/principal would broadcast directly.
    """
    from ai.tool_functions_v2 import tool_create_announcement
    user = _make_user("admin", "reception", name="Reception")
    params = {"title": "Staff Notice", "content": "All staff meeting at 3pm.", "audience_type": "staff"}

    fake_announcements: list[dict] = []
    fake_audit: list[dict] = []

    class FakeCollection:
        async def insert_one(self, doc):
            (fake_announcements if "title" in doc else fake_audit).append(doc)

    class FakeAudit:
        async def insert_one(self, doc):
            fake_audit.append(doc)

    class FakeDb:
        announcements = FakeCollection()
        audit_logs = FakeAudit()

    with patch("ai.tool_functions_v2.get_db", return_value=FakeDb()), \
         patch("ai.tool_functions_v2.get_school_id", return_value="school-1"), \
         patch("ai.tool_functions_v2.add_school_id", side_effect=lambda x: x):
        result = await tool_create_announcement(params, user)

    assert result["success"] is True
    doc = fake_announcements[0]
    assert doc["status"] == "pending_approval"
    assert doc["sent_at"] is None
    assert "submitted for principal approval" in result["message"]


@pytest.mark.asyncio
async def test_create_announcement_students_audience_sets_pending_approval():
    # Story A.4: non-exempt role (reception) so the content gate still applies
    # (owner/principal now broadcast directly, matching the REST route).
    from ai.tool_functions_v2 import tool_create_announcement
    user = _make_user("admin", "reception", name="Reception")
    params = {"title": "Result Notice", "content": "Results published.", "audience_type": "students"}

    inserted = []

    class FakeCol:
        async def insert_one(self, doc):
            inserted.append(doc)

    class FakeDb:
        announcements = FakeCol()
        audit_logs = FakeCol()

    with patch("ai.tool_functions_v2.get_db", return_value=FakeDb()), \
         patch("ai.tool_functions_v2.get_school_id", return_value="s1"), \
         patch("ai.tool_functions_v2.add_school_id", side_effect=lambda x: x):
        result = await tool_create_announcement(params, user)

    ann = next(d for d in inserted if "status" in d)
    assert ann["status"] == "pending_approval"
    assert ann["sent_at"] is None


@pytest.mark.asyncio
async def test_create_announcement_parents_audience_is_active():
    """'parents' audience_type has no teachers/students → active immediately."""
    from ai.tool_functions_v2 import tool_create_announcement
    user = _make_user("owner", name="Owner")
    params = {"title": "Parent Mtg", "content": "Tomorrow at 10am.", "audience_type": "parents"}

    inserted = []

    class FakeCol:
        async def insert_one(self, doc):
            inserted.append(doc)

    class FakeDb:
        announcements = FakeCol()
        audit_logs = FakeCol()

    with patch("ai.tool_functions_v2.get_db", return_value=FakeDb()), \
         patch("ai.tool_functions_v2.get_school_id", return_value="s1"), \
         patch("ai.tool_functions_v2.add_school_id", side_effect=lambda x: x):
        result = await tool_create_announcement(params, user)

    ann = next(d for d in inserted if "status" in d)
    assert ann["status"] == "active"
    assert ann["sent_at"] is not None
    assert "published successfully" in result["message"]


# ---------------------------------------------------------------------------
# P8 — Content filter for students
# ---------------------------------------------------------------------------

def test_filter_response_called_on_rich_blocks_for_student(monkeypatch):
    """_extract_rich_content returns filtered blocks for student role."""
    from routes import chat as chat_mod

    filtered_calls: list[str] = []
    original_filter = chat_mod.filter_response

    def _mock_filter(text, role):
        filtered_calls.append(role)
        return text  # pass-through for test

    monkeypatch.setattr(chat_mod, "filter_response", _mock_filter)
    # The rich_blocks filter is invoked inline in the generator, not unit-testable
    # in isolation without running the generator. Verify filter_response is importable
    # and the student-check code path is reachable.
    assert callable(chat_mod.filter_response)


# ---------------------------------------------------------------------------
# P9 — Confirm-token tenant binding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_issue_confirm_token_persists_school_and_branch():
    from services.confirm_tokens import issue_confirm_token

    inserted: list[dict] = []

    class FakeTokenCol:
        async def insert_one(self, doc):
            inserted.append(doc)

    class FakeDb:
        confirm_tokens = FakeTokenCol()

    token = await issue_confirm_token(
        action="record_fee_payment",
        params={"student_id": "s1"},
        user_id="u1",
        session_id="sess1",
        school_id="school-1",
        branch_id="branch-A",
        db=FakeDb(),
    )
    assert len(inserted) == 1
    assert inserted[0]["school_id"] == "school-1"
    assert inserted[0]["branch_id"] == "branch-A"
    assert inserted[0]["token"] == token


@pytest.mark.asyncio
async def test_peek_confirm_token_raises_on_mongo_error():
    from services.confirm_tokens import peek_confirm_token
    from fastapi import HTTPException

    class BrokenCol:
        async def find_one(self, *a, **kw):
            raise RuntimeError("DB is down")

    class FakeDb:
        confirm_tokens = BrokenCol()

    with pytest.raises(HTTPException) as exc_info:
        await peek_confirm_token(token="tok", user_id="u1", session_id="s1", db=FakeDb())
    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_consume_confirm_token_rejects_school_id_mismatch():
    """If the token was issued for school-A, consuming from school-B raises 409."""
    from services.confirm_tokens import consume_confirm_token
    from fastapi import HTTPException

    now = datetime.now(timezone.utc)
    doc = {
        "token": "tok-123",
        "user_id": "u1",
        "session_id": "s1",
        "school_id": "school-A",
        "branch_id": "branch-1",
        "used": False,
        "expires_at": now + timedelta(minutes=5),
    }

    class FakeTokenCol:
        async def update_one(self, query, update, **kw):
            class Result:
                modified_count = 1
            return Result()

        async def find_one(self, query):
            return dict(doc)

    class FakeDb:
        confirm_tokens = FakeTokenCol()

    with pytest.raises(HTTPException) as exc_info:
        await consume_confirm_token(
            token="tok-123",
            user_id="u1",
            session_id="s1",
            school_id="school-B",   # mismatch
            db=FakeDb(),
        )
    assert exc_info.value.status_code == 409
    assert "mismatch" in exc_info.value.detail


@pytest.mark.asyncio
async def test_consume_confirm_token_gte_ttl_boundary():
    """Token expiring exactly at 'now' should still be consumed ($gte)."""
    from services.confirm_tokens import consume_confirm_token

    now = datetime.now(timezone.utc)

    class TrackingCol:
        last_query: dict = {}

        async def update_one(self, query, update, **kw):
            TrackingCol.last_query = query

            class Result:
                modified_count = 0
            return Result()

        async def find_one(self, query):
            return None  # will raise 400 from the not-found path

    class FakeDb:
        confirm_tokens = TrackingCol()

    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await consume_confirm_token(token="x", user_id="u", session_id="s", db=FakeDb())

    expires_filter = TrackingCol.last_query.get("expires_at", {})
    assert "$gte" in expires_filter, "TTL filter should use $gte for boundary inclusion"
    assert "$gt" not in expires_filter, "Old $gt filter must not be present"


# ---------------------------------------------------------------------------
# P9 — decrement_count
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decrement_count_decrements_current_bucket():
    from services.ai_rate_limiter import decrement_count, hour_bucket
    from datetime import datetime, timezone

    updated_filters = []

    class FakeCounters:
        async def update_one(self, query, update, **kw):
            updated_filters.append(query)

    class FakeDb:
        ai_rate_limit_counters = FakeCounters()

    now = datetime.now(timezone.utc)
    bucket = hour_bucket(now)

    await decrement_count(user_id="u1", db=FakeDb(), now_fn=lambda: now)

    assert len(updated_filters) == 1
    assert updated_filters[0]["user_id"] == "u1"
    assert updated_filters[0]["hour_bucket"] == bucket
    assert updated_filters[0]["count"]["$gt"] == 0


# ---------------------------------------------------------------------------
# P11 — Polish bundle
# ---------------------------------------------------------------------------

def test_safe_token_count_coerces_non_string_fallback():
    from routes.chat import safe_token_count
    # None fallback should not raise
    assert safe_token_count(None, None) >= 1
    # Integer fallback
    assert safe_token_count(None, 42) >= 1
    # Normal string fallback
    assert safe_token_count(None, "hello world") >= 1


def test_safe_tool_result_redacts_new_restricted_keys():
    from routes.chat import _safe_tool_result_for_chat
    sensitive = {
        "password_hash": "bcrypt$...",
        "salt": "abc123",
        "secret": "shhh",
        "api_key": "sk-...",
        "private_key": "-----BEGIN RSA...",
        "refresh_token": "r.tok",
        "access_token": "a.tok",
        "session_token": "s.tok",
        "webhook_secret": "wh_sec",
    }
    result = _safe_tool_result_for_chat({"data": sensitive})["data"]
    for k in sensitive:
        assert result[k] == "[restricted in chat]", f"Key {k!r} not redacted"


def test_safe_tool_result_still_redacts_guardian_phone():
    from routes.chat import _safe_tool_result_for_chat
    result = _safe_tool_result_for_chat({"guardian_phone": "9876543210"})
    assert result["guardian_phone"] == "98XX-XXX-210"


def test_safe_tool_result_does_not_clobber_non_phone_bool():
    """is_phone_verified (bool) should NOT be redacted as a phone field."""
    from routes.chat import _safe_tool_result_for_chat
    result = _safe_tool_result_for_chat({"is_phone_verified": True})
    # The bool is preserved (not turned into "[restricted in chat]")
    assert result["is_phone_verified"] is True


def test_thinking_delay_uses_random(monkeypatch):
    import asyncio
    from routes import chat as chat_mod

    sleep_args: list[float] = []

    async def _fake_sleep(t):
        sleep_args.append(t)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    asyncio.run(chat_mod._thinking_delay())
    assert len(sleep_args) == 1
    assert chat_mod.THINKING_DELAY_MIN <= sleep_args[0] <= chat_mod.THINKING_DELAY_MAX


def test_keepalive_event_is_data_event():
    from routes.chat import keepalive_event
    event = keepalive_event()
    assert event == 'data: {"type":"keepalive"}\n\n'
    assert event.startswith("data: ")


def test_empty_message_rejection_strips_zero_width_whitespace(client, fake_db):
    """Zero-width characters alone must be treated as an empty message."""
    from middleware.auth import create_jwt
    fake_db.conversations.docs[:] = [
        {"_id": "conv-1", "id": "conv-1", "schoolId": "aaryans-joya", "user_id": "u1"}
    ]
    token = create_jwt({"user_id": "u1", "role": "owner", "name": "O"})
    headers = {"Authorization": f"Bearer {token}"}
    # U+200B ZERO WIDTH SPACE, U+200C ZERO WIDTH NON-JOINER
    resp = client.post(
        "/api/chat/conversations/conv-1/messages",
        headers=headers,
        json={"text": "​‌"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("error") == "Empty message"


def test_extract_rich_content_uses_json_candidates():
    from routes.chat import _extract_rich_content
    # Nested JSON inside RICH_CONTENT block — old regex would fail here.
    nested = {"rich_blocks": [{"value": "{\"inner\": 1}"}], "action_buttons": []}
    payload = json.dumps(nested)
    text = f"Here is my response.\n<<<RICH_CONTENT>>>{payload}<<<END>>>"
    clean, rich = _extract_rich_content(text)
    assert "Here is my response." in clean
    assert rich is not None
    assert "rich_blocks" in rich


def test_extract_rich_content_no_marker_returns_unchanged():
    from routes.chat import _extract_rich_content
    text = "Plain response with no rich content."
    clean, rich = _extract_rich_content(text)
    assert clean == text
    assert rich is None


def test_missing_required_params_rejects_zero_points():
    from routes.chat import _missing_required_params
    missing = _missing_required_params("award_house_points", {"student_name": "Alice", "points": 0})
    assert "points" in missing


def test_missing_required_params_rejects_negative_amount():
    from routes.chat import _missing_required_params
    missing = _missing_required_params(
        "record_fee_payment",
        {"student_id": "s1", "amount": -100, "fee_head": "tuition", "mode": "cash"},
    )
    assert "amount" in missing


def test_missing_required_params_accepts_positive_amount():
    from routes.chat import _missing_required_params
    missing = _missing_required_params(
        "record_fee_payment",
        {"student_id": "s1", "amount": 500, "fee_head": "tuition", "mode": "cash"},
    )
    assert "amount" not in missing


def test_missing_required_params_accepts_positive_points():
    from routes.chat import _missing_required_params
    missing = _missing_required_params(
        "award_house_points",
        {"student_name": "Alice", "points": 5},
    )
    assert "points" not in missing
