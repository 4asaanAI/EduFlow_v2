from __future__ import annotations

import uuid
from datetime import datetime

DEFAULT_SCHOOL_ID = "aaryans-joya"
DEFAULT_BRANCH_ID = "branch-a"

# Legacy aliases for tests that import SCHOOL_ID / BRANCH_ID directly
SCHOOL_ID = DEFAULT_SCHOOL_ID
BRANCH_ID = DEFAULT_BRANCH_ID


def _with_defaults(base: dict, **kwargs) -> dict:
    doc = {
        "id": str(uuid.uuid4()),
        "schoolId": DEFAULT_SCHOOL_ID,
        "branch_id": DEFAULT_BRANCH_ID,
        **base,
    }
    doc.update(kwargs)
    if not doc.get("id"):
        doc["id"] = str(uuid.uuid4())
    return doc


def make_student(class_id: str = "cls-1", branch_id: str = DEFAULT_BRANCH_ID, **kwargs) -> dict:
    return _with_defaults(
        {
            "name": "Test Student",
            "class_id": class_id,
            "admission_number": f"ADM-{uuid.uuid4().hex[:8]}",
            "is_active": True,
            "status": "active",
            "gender": "male",
            "created_at": datetime.now().isoformat(),
        },
        branch_id=branch_id,
        **kwargs,
    )


def make_staff(role: str = "teacher", sub_category: str | None = None, branch_id: str = DEFAULT_BRANCH_ID, **kwargs) -> dict:
    return _with_defaults(
        {
            "name": "Test Staff",
            "role": role,
            "sub_category": sub_category,
            "staff_type": "teacher" if role == "teacher" else "admin",
            "is_active": True,
            "created_at": datetime.now().isoformat(),
        },
        branch_id=branch_id,
        **kwargs,
    )


def make_fee_transaction(student_id: str = "stu-1", amount: float = 5000, **kwargs) -> dict:
    return _with_defaults(
        {
            "student_id": student_id,
            "fee_type": "tuition",
            "fee_head": "tuition",
            "fee_period": "2026-05",
            "amount": amount,
            "status": "paid",
            "payment_mode": "cash",
            "created_at": datetime.now().isoformat(),
        },
        **kwargs,
    )


def make_audit_record(actor_id: str = "u1", action: str = "student_created", **kwargs) -> dict:
    return _with_defaults(
        {
            "actor_id": actor_id,
            "changed_by": actor_id,
            "action": action,
            "entity_type": "student",
            "entity_id": "stu-1",
            "collection": "students",
            "created_at": datetime.now().isoformat(),
        },
        **kwargs,
    )


def make_notification(user_id: str = "u1", read: bool = False, **kwargs) -> dict:
    return _with_defaults(
        {
            "user_id": user_id,
            "type": "info",
            "title": "Notification",
            "message": "Test notification",
            "read": read,
            "created_at": datetime.now().isoformat(),
        },
        **kwargs,
    )


def make_leave_request(staff_id: str = "s1", status: str = "pending", **kwargs) -> dict:
    return _with_defaults(
        {
            "staff_id": staff_id,
            "user_id": "u1",
            "leave_type": "casual",
            "reason": "Personal work",
            "status": status,
            "applied_at": datetime.now().isoformat(),
        },
        **kwargs,
    )
