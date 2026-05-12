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
        "record_fee_payment",
        "mark_attendance",
        "approve_leave",
        "award_house_points",
    }.issubset(chat.WRITE_ACTION_TOOLS)


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
