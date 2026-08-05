"""Student leave policy, request, and approval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_role
from services.actor_context import actor_ctx_from_user
from services.student_leave_service import (
    StudentLeaveAuthorizationError,
    StudentLeaveConflictError,
    StudentLeaveNotFoundError,
    StudentLeaveValidationError,
    create_request,
    decide_request,
    get_policy,
    replace_policy,
    resolve_request_student,
)
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/student-leave", tags=["student-leave"])
ALL_ROLES = require_role("owner", "admin", "teacher", "student", "parent")


def _actor(user: dict):
    return actor_ctx_from_user(user, school_id=get_school_id())


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, StudentLeaveNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, StudentLeaveAuthorizationError):
        return HTTPException(403, str(exc))
    if isinstance(exc, StudentLeaveConflictError):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


@router.get("/policy")
async def read_policy(request: Request, user: dict = Depends(ALL_ROLES)):
    return {"success": True, "data": await get_policy(get_db(), user.get("branch_id"))}


@router.put("/policy")
async def put_policy(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    if user.get("role") != "owner" and user.get("sub_category") != "principal":
        raise HTTPException(403, "Only the school owner or principal can change student leave policy")
    try:
        policy = await replace_policy(get_db(), _actor(user), await request.json())
    except StudentLeaveValidationError as exc:
        raise _error(exc)
    return {"success": True, "data": policy}


@router.post("/requests")
async def post_request(request: Request,
                       user: dict = Depends(require_role("student", "parent"))):
    body = await request.json()
    try:
        student = await resolve_request_student(get_db(), user, body.get("student_id"))
        leave = await create_request(get_db(), _actor(user), student, body)
    except (StudentLeaveValidationError, StudentLeaveNotFoundError,
            StudentLeaveAuthorizationError, StudentLeaveConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": leave}


@router.get("/requests")
async def list_requests(request: Request, status: str | None = None,
                        user: dict = Depends(ALL_ROLES)):
    db = get_db()
    branch_id = user.get("branch_id")
    query = {}
    if status:
        query["status"] = status
    if user.get("role") == "student":
        student = await db.students.find_one(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0, "id": 1}
        )
        query["student_id"] = student.get("id") if student else "__none__"
    elif user.get("role") == "parent":
        guardians = await db.guardians.find(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0, "student_id": 1}
        ).to_list(100)
        query["student_id"] = {"$in": [row["student_id"] for row in guardians if row.get("student_id")]}
    elif user.get("role") == "teacher":
        staff = await db.staff.find_one(
            scoped_query({"user_id": user["id"]}, branch_id=branch_id), {"_id": 0, "id": 1}
        )
        classes = await db.classes.find(
            scoped_query({"class_teacher_id": staff.get("id") if staff else "__none__"}, branch_id=branch_id),
            {"_id": 0, "id": 1},
        ).to_list(100)
        query["class_id"] = {"$in": [row["id"] for row in classes]}
    elif user.get("role") == "admin" and user.get("sub_category") != "principal":
        raise HTTPException(403, "Only the principal can view all student leave requests")
    rows = await db.student_leave_requests.find(
        scoped_query(query, branch_id=branch_id), {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.patch("/requests/{request_id}/decision")
async def patch_decision(request_id: str, request: Request,
                         user: dict = Depends(require_role("owner", "admin", "teacher"))):
    try:
        leave = await decide_request(get_db(), _actor(user), request_id, await request.json())
    except (StudentLeaveValidationError, StudentLeaveNotFoundError,
            StudentLeaveAuthorizationError, StudentLeaveConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": leave}
