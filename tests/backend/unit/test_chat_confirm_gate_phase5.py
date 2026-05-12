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
            "payment_mode": "upi",
        },
    )

    assert display == "Record fee payment of 2500 for student Demo Student via upi"


def test_confirm_display_falls_back_for_unknown_tool():
    display = chat._build_confirm_display("custom_write_tool", {"x": 1})

    assert display == 'Execute custom_write_tool with parameters: {"x": 1}'
