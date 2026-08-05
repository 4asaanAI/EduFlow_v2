"""Enterprise applicant-to-student admissions API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db, get_txn_session
from middleware.auth import require_role
from services.actor_context import actor_ctx_from_user
from services.admissions_service import (
    AdmissionConflictError,
    AdmissionNotFoundError,
    AdmissionValidationError,
    add_application_document,
    create_application,
    enroll_application,
    issue_offer,
    record_assessment,
    transition_application,
)
from services.student_service import StudentConflictError, StudentValidationError
from services.txn_context import reset_current_session, set_current_session
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/admissions", tags=["admissions"])


def _actor(user: dict):
    return actor_ctx_from_user(user, school_id=get_school_id())


def _map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, AdmissionNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, (AdmissionConflictError, StudentConflictError)):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


def _can_enroll(user: dict) -> bool:
    return user.get("role") == "owner" or (
        user.get("role") == "admin" and user.get("sub_category") in {"principal", "admission"}
    )


@router.get("/applications")
async def list_applications(request: Request, status: str | None = None,
                            user: dict = Depends(require_role("owner", "admin"))):
    query = {"status": status} if status else {}
    rows = await get_db().admission_applications.find(
        scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.get("/applications/{application_id}")
async def get_application(application_id: str, request: Request,
                          user: dict = Depends(require_role("owner", "admin"))):
    row = await get_db().admission_applications.find_one(
        scoped_query({"id": application_id}, branch_id=user.get("branch_id")), {"_id": 0}
    )
    if not row:
        raise HTTPException(404, "Application not found")
    return {"success": True, "data": row}


@router.post("/applications")
async def post_application(request: Request,
                           user: dict = Depends(require_role("owner", "admin"))):
    try:
        result = await create_application(get_db(), _actor(user), await request.json())
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": result["application"], "meta": {"existing": result["existing"]}}


@router.patch("/applications/{application_id}/status")
async def patch_application_status(application_id: str, request: Request,
                                   user: dict = Depends(require_role("owner", "admin"))):
    try:
        result = await transition_application(
            get_db(), _actor(user), application_id, await request.json()
        )
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": result["application"]}


@router.post("/applications/{application_id}/documents")
async def post_application_document(application_id: str, request: Request,
                                    user: dict = Depends(require_role("owner", "admin"))):
    try:
        result = await add_application_document(
            get_db(), _actor(user), application_id, await request.json()
        )
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": result["document"]}


@router.post("/applications/{application_id}/assessment")
async def post_application_assessment(application_id: str, request: Request,
                                      user: dict = Depends(require_role("owner", "admin"))):
    try:
        result = await record_assessment(
            get_db(), _actor(user), application_id, await request.json()
        )
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": result["assessment"]}


@router.post("/applications/{application_id}/offer")
async def post_application_offer(application_id: str, request: Request,
                                 user: dict = Depends(require_role("owner", "admin"))):
    if not _can_enroll(user):
        raise HTTPException(403, "Only the school owner, principal, or admissions admin can issue an offer")
    try:
        result = await issue_offer(get_db(), _actor(user), application_id, await request.json())
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": result["offer"]}


@router.post("/applications/{application_id}/enroll")
async def post_application_enrollment(application_id: str, request: Request,
                                      user: dict = Depends(require_role("owner", "admin"))):
    if not _can_enroll(user):
        raise HTTPException(403, "Only the school owner, principal, or admissions admin can enroll a student")
    db = get_db()
    session = await get_txn_session()
    token = set_current_session(session)
    try:
        async with session:
            async with session.start_transaction():
                result = await enroll_application(
                    db, _actor(user), application_id, await request.json(), session=session
                )
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError,
            StudentValidationError, StudentConflictError) as exc:
        raise _map_error(exc)
    finally:
        reset_current_session(token)
    return {"success": True, "data": result}
