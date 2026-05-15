from __future__ import annotations
import uuid

SCHOOL_ID = "aaryans-joya"
BRANCH_ID = "branch-a"


def _id() -> str:
    return str(uuid.uuid4())


def make_student(*, class_id: str = "cls-1", branch_id: str = BRANCH_ID, **kwargs) -> dict:
    return {
        "id": _id(), "schoolId": SCHOOL_ID, "branch_id": branch_id,
        "name": "Test Student", "class_id": class_id,
        "admission_number": f"ADM-{_id()[:6]}",
        "is_active": True, "gender": "male",
        **kwargs,
    }


def make_staff(*, role: str = "teacher", sub_category: str | None = None,
               branch_id: str = BRANCH_ID, **kwargs) -> dict:
    d = {
        "id": _id(), "schoolId": SCHOOL_ID, "branch_id": branch_id,
        "name": "Test Staff", "role": role,
        "is_active": True,
        **kwargs,
    }
    if sub_category:
        d["sub_category"] = sub_category
    return d


def make_fee_transaction(*, student_id: str = "stu-1", amount: int = 5000,
                         branch_id: str = BRANCH_ID, **kwargs) -> dict:
    return {
        "id": _id(), "schoolId": SCHOOL_ID, "branch_id": branch_id,
        "student_id": student_id, "amount": amount,
        "status": "paid", "fee_type": "Tuition",
        **kwargs,
    }


def make_audit_record(*, actor_id: str = "u1", action: str = "student_created",
                      branch_id: str = BRANCH_ID, **kwargs) -> dict:
    return {
        "id": _id(), "schoolId": SCHOOL_ID, "branch_id": branch_id,
        "actor_id": actor_id, "action": action,
        "created_at": "2026-05-16T08:00:00Z",
        **kwargs,
    }


def make_notification(*, user_id: str = "u1", read: bool = False,
                      branch_id: str = BRANCH_ID, **kwargs) -> dict:
    return {
        "id": _id(), "schoolId": SCHOOL_ID, "branch_id": branch_id,
        "user_id": user_id, "title": "Test Notification",
        "body": "This is a test.", "read": read,
        "created_at": "2026-05-16T08:00:00Z",
        **kwargs,
    }


def make_leave_request(*, staff_id: str = "s1", status: str = "pending",
                       branch_id: str = BRANCH_ID, **kwargs) -> dict:
    return {
        "id": _id(), "schoolId": SCHOOL_ID, "branch_id": branch_id,
        "staff_id": staff_id, "leave_type": "casual",
        "start_date": "2026-06-01", "end_date": "2026-06-02",
        "reason": "Personal", "status": status,
        **kwargs,
    }
