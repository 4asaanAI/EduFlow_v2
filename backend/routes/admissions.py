"""Enterprise applicant-to-student admissions API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db, get_txn_session
from middleware.auth import require_role
from services.actor_context import actor_ctx_from_user
from services.admissions_journey import describe_position
from services.admission_test_service import (
    create_test as svc_create_test,
    get_test as svc_get_test,
    list_tests as svc_list_tests,
    mark_seat as svc_mark_seat,
    remove_seat as svc_remove_seat,
    seat_applicants as svc_seat_applicants,
    update_test as svc_update_test,
)
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


# ───────────────────────────── B1: entrance tests ─────────────────────────────
#
# All of these carry `require_role("owner", "admin")`, which is **exactly the gate the
# assessment route below has always had**. Running the test list and entering the marks
# from it are the same job, and this grants nobody anything they did not already have: a
# desk that could record a score one child at a time can now record the same scores from a
# list. Issuing an offer and enrolling stay narrower, on `_can_enroll`, untouched.
#
# `/tests` is declared before `/applications/{application_id}` in this module, but the two
# cannot collide: they sit under different path segments.


@router.get("/tests")
async def list_admission_tests(request: Request, status: str | None = None,
                               user: dict = Depends(require_role("owner", "admin"))):
    data = await svc_list_tests(get_db(), _actor(user), {"status": status})
    return {"success": True, "data": data["tests"], "meta": {"count": data["count"]}}


@router.post("/tests")
async def post_admission_test(request: Request,
                              user: dict = Depends(require_role("owner", "admin"))):
    try:
        row = await svc_create_test(get_db(), _actor(user), await request.json())
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": row}


@router.get("/tests/{test_id}")
async def get_admission_test(test_id: str, request: Request,
                             user: dict = Depends(require_role("owner", "admin"))):
    """The list for a given test: who is sitting it, who turned up, and who is marked."""
    try:
        data = await svc_get_test(get_db(), _actor(user), test_id)
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": data, "meta": data["counts"]}


@router.patch("/tests/{test_id}")
async def patch_admission_test(test_id: str, request: Request,
                               user: dict = Depends(require_role("owner", "admin"))):
    try:
        row = await svc_update_test(get_db(), _actor(user), test_id, await request.json())
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": row}


@router.post("/tests/{test_id}/seats")
async def post_admission_test_seats(test_id: str, request: Request,
                                    user: dict = Depends(require_role("owner", "admin"))):
    """Put applicants on a test. Returns who was seated AND who was refused, with reasons."""
    try:
        data = await svc_seat_applicants(get_db(), _actor(user), test_id, await request.json())
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": data, "meta": data["counts"]}


@router.patch("/tests/{test_id}/seats/{seat_id}")
async def patch_admission_test_seat(test_id: str, seat_id: str, request: Request,
                                    user: dict = Depends(require_role("owner", "admin"))):
    """Mark somebody present or absent, and record their score.

    A score is refused unless that applicant is marked present, and it is written to the
    application through the same `record_assessment` the application screen uses. If that
    refuses, nothing at all is stored.
    """
    try:
        data = await svc_mark_seat(get_db(), _actor(user), test_id, seat_id, await request.json())
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": data["seat"], "meta": {"changed": data["changed"]}}


@router.delete("/tests/{test_id}/seats/{seat_id}")
async def delete_admission_test_seat(test_id: str, seat_id: str, request: Request,
                                     user: dict = Depends(require_role("owner", "admin"))):
    try:
        data = await svc_remove_seat(get_db(), _actor(user), test_id, seat_id)
    except (AdmissionValidationError, AdmissionNotFoundError, AdmissionConflictError) as exc:
        raise _map_error(exc)
    return {"success": True, "data": data["removed"]}


@router.get("/applications")
async def list_applications(request: Request, status: str | None = None,
                            user: dict = Depends(require_role("owner", "admin"))):
    query = {"status": status} if status else {}
    rows = await get_db().admission_applications.find(
        scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    # A3. The same one vocabulary the enquiry list answers in, so the two halves stop
    # describing the same journey in different words.
    for row in rows:
        row["journey"] = describe_position(application=row)
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
