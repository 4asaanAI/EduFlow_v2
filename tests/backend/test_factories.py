from __future__ import annotations
import pytest
from tests.backend.factories import (
    make_student, make_staff, make_fee_transaction,
    make_audit_record, make_notification, make_leave_request,
)

def test_make_student_defaults():
    s = make_student()
    assert s["schoolId"] == "aaryans-joya"
    assert s["branch_id"] == "branch-a"
    assert s["class_id"] == "cls-1"
    assert len(s["id"]) == 36  # UUID4

def test_make_student_overrides():
    s = make_student(class_id="cls-2", name="Alice", branch_id="branch-b")
    assert s["class_id"] == "cls-2"
    assert s["name"] == "Alice"
    assert s["branch_id"] == "branch-b"

def test_make_staff_with_sub_category():
    s = make_staff(role="admin", sub_category="principal")
    assert s["role"] == "admin"
    assert s["sub_category"] == "principal"

def test_make_fee_transaction():
    t = make_fee_transaction(student_id="stu-99", amount=10000)
    assert t["amount"] == 10000
    assert t["student_id"] == "stu-99"

def test_make_leave_request_pending():
    lr = make_leave_request()
    assert lr["status"] == "pending"

def test_make_notification_unread():
    n = make_notification(user_id="u-99")
    assert n["read"] is False
    assert n["user_id"] == "u-99"
