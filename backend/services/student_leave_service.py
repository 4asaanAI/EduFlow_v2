"""Policy-driven student leave requests and approvals."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from tenant import scoped_query


DEFAULT_POLICY = {
    "teacher_approval_required": True,
    "principal_approval_after_days": 3,
    "maximum_consecutive_days": 30,
    "allow_past_requests": False,
    "require_reason": True,
}


class StudentLeaveValidationError(Exception):
    pass


class StudentLeaveNotFoundError(Exception):
    pass


class StudentLeaveAuthorizationError(Exception):
    pass


class StudentLeaveConflictError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_range(start_value: str, end_value: str) -> tuple[date, date, int]:
    try:
        start = date.fromisoformat(str(start_value))
        end = date.fromisoformat(str(end_value))
    except (TypeError, ValueError):
        raise StudentLeaveValidationError("start_date and end_date must be YYYY-MM-DD")
    if end < start:
        raise StudentLeaveValidationError("end_date cannot be before start_date")
    return start, end, (end - start).days + 1


async def get_policy(db, branch_id: str | None) -> dict:
    stored = await db.student_leave_policies.find_one(
        scoped_query({"scope": "school"}, branch_id=branch_id), {"_id": 0}
    )
    return {**DEFAULT_POLICY, **(stored or {})}


async def replace_policy(db, actor_ctx: ActorContext, params: dict) -> dict:
    policy = {**DEFAULT_POLICY}
    for boolean_field in ("teacher_approval_required", "allow_past_requests", "require_reason"):
        if boolean_field in params:
            policy[boolean_field] = bool(params[boolean_field])
    for number_field in ("principal_approval_after_days", "maximum_consecutive_days"):
        try:
            value = int(params.get(number_field, policy[number_field]))
        except (TypeError, ValueError):
            raise StudentLeaveValidationError(f"{number_field} must be an integer")
        if value < 1 or value > 365:
            raise StudentLeaveValidationError(f"{number_field} must be between 1 and 365")
        policy[number_field] = value
    if policy["principal_approval_after_days"] > policy["maximum_consecutive_days"]:
        raise StudentLeaveValidationError("Principal threshold cannot exceed maximum consecutive days")
    now = _now()
    doc = {
        **policy, "scope": "school", "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "updated_by": actor_ctx.user_id, "updated_at": now,
    }
    await db.student_leave_policies.update_one(
        scoped_query({"scope": "school"}, branch_id=actor_ctx.branch_id),
        {"$set": doc, "$setOnInsert": {"id": str(uuid.uuid4()), "created_at": now}},
        upsert=True,
    )
    await write_audit_doc(db, {
        "id": str(uuid.uuid4()), "entity_type": "student_leave_policy", "entity_id": "school",
        "action": "policy_updated", "changed_by": actor_ctx.user_id,
        "changed_by_role": actor_ctx.role, "changes": policy, "created_at": now,
    }, school_id=actor_ctx.school_id, branch_id=actor_ctx.branch_id or "")
    return doc


async def resolve_request_student(db, user: dict, requested_student_id: str | None) -> dict:
    branch_id = user.get("branch_id")
    if user.get("role") == "student":
        student = await db.students.find_one(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0}
        )
        if not student:
            raise StudentLeaveAuthorizationError("Student profile not found")
        if requested_student_id and requested_student_id != student.get("id"):
            raise StudentLeaveAuthorizationError("Cannot request leave for another student")
        return student
    if user.get("role") == "parent":
        if not requested_student_id:
            raise StudentLeaveValidationError("student_id is required for a guardian request")
        link = await db.guardians.find_one(
            scoped_query({"user_id": user["id"], "student_id": requested_student_id}, branch_id=branch_id),
            {"_id": 0, "student_id": 1},
        )
        if not link:
            raise StudentLeaveAuthorizationError("Guardian is not linked to this student")
        student = await db.students.find_one(
            scoped_query({"id": requested_student_id}, branch_id=branch_id), {"_id": 0}
        )
        if not student:
            raise StudentLeaveNotFoundError("Student not found")
        return student
    raise StudentLeaveAuthorizationError("Only students and linked guardians can submit student leave")


async def create_request(db, actor_ctx: ActorContext, student: dict, params: dict) -> dict:
    policy = await get_policy(db, actor_ctx.branch_id)
    start, end, days = _parse_range(params.get("start_date"), params.get("end_date"))
    reason = str(params.get("reason") or "").strip()
    if policy["require_reason"] and not reason:
        raise StudentLeaveValidationError("reason is required")
    if not policy["allow_past_requests"] and start < date.today():
        raise StudentLeaveValidationError("Past leave requests are not allowed")
    if days > policy["maximum_consecutive_days"]:
        raise StudentLeaveValidationError(
            f"Leave cannot exceed {policy['maximum_consecutive_days']} consecutive days"
        )
    overlap = await db.student_leave_requests.find_one(scoped_query({
        "student_id": student["id"], "status": {"$in": ["pending_teacher", "pending_principal", "approved"]},
        "start_date": {"$lte": end.isoformat()}, "end_date": {"$gte": start.isoformat()},
    }, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1})
    if overlap:
        raise StudentLeaveConflictError("An active leave request already overlaps these dates")
    status = "pending_teacher" if policy["teacher_approval_required"] else "pending_principal"
    request_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": request_id, "id": request_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "student_id": student["id"],
        "student_name": student.get("name"), "class_id": student.get("class_id"),
        "start_date": start.isoformat(), "end_date": end.isoformat(), "days": days,
        "leave_type": params.get("leave_type") or "other", "reason": reason,
        "status": status, "submitted_by": actor_ctx.user_id,
        "submitted_by_role": actor_ctx.role, "decisions": [],
        "created_at": now, "updated_at": now,
    }
    await db.student_leave_requests.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def _is_class_teacher(db, actor_ctx: ActorContext, leave: dict) -> bool:
    staff = await db.staff.find_one(
        scoped_query({"user_id": actor_ctx.user_id}, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1}
    )
    if not staff:
        return False
    class_doc = await db.classes.find_one(
        scoped_query({"id": leave.get("class_id")}, branch_id=actor_ctx.branch_id),
        {"_id": 0, "class_teacher_id": 1},
    )
    return bool(class_doc and class_doc.get("class_teacher_id") == staff.get("id"))


async def decide_request(db, actor_ctx: ActorContext, request_id: str, params: dict) -> dict:
    decision = str(params.get("decision") or "").lower()
    if decision not in {"approve", "reject"}:
        raise StudentLeaveValidationError("decision must be approve or reject")
    note = str(params.get("note") or "").strip()
    if decision == "reject" and not note:
        raise StudentLeaveValidationError("note is required when rejecting leave")
    leave = await db.student_leave_requests.find_one(
        scoped_query({"id": request_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not leave:
        raise StudentLeaveNotFoundError("Student leave request not found")
    if leave.get("status") not in {"pending_teacher", "pending_principal"}:
        raise StudentLeaveConflictError("Student leave request has already been decided")
    privileged = actor_ctx.role == "owner" or (
        actor_ctx.role == "admin" and actor_ctx.sub_category == "principal"
    )
    teacher = actor_ctx.role == "teacher" and await _is_class_teacher(db, actor_ctx, leave)
    if not privileged and not teacher:
        raise StudentLeaveAuthorizationError("Only the class teacher, principal, or school owner can decide this request")
    if teacher and leave["status"] != "pending_teacher":
        raise StudentLeaveAuthorizationError("This request is awaiting principal approval")

    policy = await get_policy(db, actor_ctx.branch_id)
    if decision == "reject":
        new_status = "rejected"
    elif privileged:
        new_status = "approved"
    elif leave.get("days", 1) > policy["principal_approval_after_days"]:
        new_status = "pending_principal"
    else:
        new_status = "approved"
    record = {
        "decision": decision, "from": leave["status"], "to": new_status,
        "by": actor_ctx.user_id, "role": actor_ctx.role,
        "note": note or None, "at": _now(),
    }
    result = await db.student_leave_requests.update_one(
        scoped_query({"id": request_id, "status": leave["status"]}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": new_status, "updated_at": _now()}, "$push": {"decisions": record}},
    )
    if result.matched_count == 0:
        raise StudentLeaveConflictError("Student leave request changed; refresh and try again")
    if new_status == "approved":
        leave_days = []
        current = date.fromisoformat(leave["start_date"])
        end = date.fromisoformat(leave["end_date"])
        while current <= end:
            leave_days.append({
                "id": str(uuid.uuid4()), "schoolId": actor_ctx.school_id,
                "branch_id": actor_ctx.branch_id, "student_id": leave["student_id"],
                "leave_request_id": request_id, "date": current.isoformat(),
                "status": "approved_leave", "created_at": _now(),
            })
            current += timedelta(days=1)
        if leave_days:
            await db.student_leave_days.insert_many(leave_days)
    student = await db.students.find_one({"id": leave["student_id"]}, {"_id": 0, "user_id": 1})
    if student and student.get("user_id"):
        await create_notification(
            db=db, user_id=student["user_id"], title="Student leave updated",
            notification_type="student_leave_decision",
            message=f"Your leave request is now {new_status.replace('_', ' ')}.",
            source_id=request_id, source_type="student_leave_request",
        )
    return {**leave, "status": new_status, "decisions": [*(leave.get("decisions") or []), record]}
