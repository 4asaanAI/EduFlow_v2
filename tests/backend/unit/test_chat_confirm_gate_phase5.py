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


def test_parse_confirm_action_tool_call_from_model_json():
    parsed = chat._parse_tool_call(
        '```json\n{"confirm_action": true, "tool": "create_announcement", '
        '"params": {"title": "Holiday", "content": "School closed tomorrow"}, '
        '"display": "Publish announcement"}\n```'
    )

    assert parsed == {
        "action": "create_announcement",
        "params": {"title": "Holiday", "content": "School closed tomorrow"},
        "reason": "Publish announcement",
        "confirm_requested": True,
    }


def test_strip_tool_json_removes_confirm_action_blocks():
    text = (
        "I will do this.\n"
        '{"confirm_action": true, "tool": "approve_leave", '
        '"params": {"leave_id": "L1", "action": "approve"}}'
    )

    assert chat._strip_tool_json_from_text(text) == "I will do this."


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
