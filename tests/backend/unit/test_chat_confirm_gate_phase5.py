"""
Unit Tests: Phase 5 AI confirm-action gate contract.
"""

import pytest

try:
    from routes import chat
except (ImportError, TypeError) as exc:
    pytest.skip(f"chat route unavailable in this interpreter: {exc}", allow_module_level=True)


def test_write_action_tools_require_confirmation_before_dispatch():
    assert {
        "add_thread_entry",
        "apply_discount",
        "assign_followup",
        "confirm_resolution",
        "correct_attendance",
        "decide_approval_request",
        "initiate_substitution",
        "log_contact_event",
        "update_incident_status",
        "record_fee_payment",
        "mark_attendance",
        "approve_leave",
        "award_house_points",
    }.issubset(chat.WRITE_ACTION_TOOLS)


def test_query_action_tools_do_not_require_confirmation():
    assert {
        "query_dashboard_summary",
        "query_attendance_status",
        "query_fee_status",
        "query_incidents",
        "query_staff_availability",
        "query_maintenance_requests",
        "query_student_record",
        "query_audit_log",
    }.isdisjoint(chat.WRITE_ACTION_TOOLS)


def test_confirm_display_summarizes_fee_payment_without_raw_json():
    display = chat._build_confirm_display(
        "record_fee_payment",
        {
            "amount": 2500,
            "student_id": "student-1",
            "_resolved_student": "Demo Student",
            "mode": "upi",
        },
    )

    assert display == "Record fee payment of 2500 for student Demo Student via upi"


def test_confirm_display_falls_back_for_unknown_tool():
    display = chat._build_confirm_display("custom_write_tool", {"x": 1})

    assert display == 'Execute custom_write_tool with parameters: {"x": 1}'


def test_native_tool_call_maps_write_tool_to_confirm_candidate():
    """R11.2: a native tool_call for a write tool maps to an internal candidate
    with confirm_requested=True (the confirm card is issued server-side; the
    model no longer emits a confirm_action JSON block)."""
    from ai.llm_client import ToolCall

    candidates = chat._tool_calls_to_candidates([
        ToolCall(id="call_1", name="create_announcement",
                 arguments={"title": "Holiday", "content": "School closed tomorrow"}),
    ])

    assert candidates == [{
        "action": "create_announcement",
        "params": {"title": "Holiday", "content": "School closed tomorrow"},
        "reason": "",
        "confirm_requested": True,
        "id": "call_1",
    }]


def test_native_tool_call_maps_read_tool_without_confirm():
    """R11.2: a read tool_call maps to a candidate with confirm_requested=False."""
    from ai.llm_client import ToolCall

    candidates = chat._tool_calls_to_candidates([
        ToolCall(id="c2", name="search_students", arguments={"query": "Rahul"}),
    ])
    assert candidates[0]["action"] == "search_students"
    assert candidates[0]["confirm_requested"] is False


def test_tool_calls_to_candidates_tolerates_empty_and_bad_input():
    """Non-list / empty / nameless tool calls degrade to [] without raising."""
    assert chat._tool_calls_to_candidates(None) == []
    assert chat._tool_calls_to_candidates([]) == []


def test_missing_required_params_for_write_actions():
    missing = chat._missing_required_params("record_fee_payment", {"amount": 2500, "mode": "upi"})

    assert missing == ["student_id", "fee_head"]


def test_missing_required_params_cover_all_confirmed_write_actions():
    assert chat.WRITE_ACTION_TOOLS.issubset(set(chat.WRITE_TOOL_REQUIRED_PARAMS))


def test_award_house_points_requires_student_not_house():
    missing = chat._missing_required_params(
        "award_house_points",
        {"student_name": "Demo Student", "points": 5},
    )

    assert missing == []


def test_appendix_write_tools_do_not_confirm_empty_params():
    missing = chat._missing_required_params("assign_followup", {})

    assert missing == ["record_id", "assignee_staff_id", "due_date", "note"]


def test_safe_tool_result_redacts_sensitive_chat_fields():
    result = chat._safe_tool_result_for_chat(
        {
            "data": [
                {
                    "name": "Demo Student",
                    "guardian_phone": "9876543210",
                    "address": "123 Main Road",
                    "date_of_birth": "2012-01-01",
                }
            ]
        }
    )

    assert result["data"][0]["guardian_phone"] == "98XX-XXX-210"
    assert result["data"][0]["address"] == "[restricted in chat]"
    assert result["data"][0]["date_of_birth"] == "[restricted in chat]"
