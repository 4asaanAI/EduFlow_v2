"""Quiz authoring, publication, attempts, and server-side grading."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_role
from services.actor_context import actor_ctx_from_user
from services.quiz_service import (
    QuizConflictError,
    QuizNotFoundError,
    QuizValidationError,
    create_quiz,
    publish_quiz,
    start_attempt,
    submit_attempt,
)
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/quizzes", tags=["quizzes"])


def _actor(user):
    return actor_ctx_from_user(user, school_id=get_school_id())


def _error(exc):
    if isinstance(exc, QuizNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, QuizConflictError):
        return HTTPException(409, str(exc))
    return HTTPException(400, str(exc))


async def _student(db, user):
    row = await db.students.find_one(
        scoped_query({"user_id": user["id"]}, branch_id=user.get("branch_id")), {"_id": 0}
    )
    if not row:
        raise HTTPException(403, "Student profile not found")
    return row


async def _teacher_can_author(db, user, class_id: str, subject_id: str | None) -> bool:
    if user.get("role") != "teacher":
        return True
    bid = user.get("branch_id")
    staff = await db.staff.find_one(
        scoped_query({"user_id": user["id"]}, branch_id=bid), {"_id": 0, "id": 1}
    )
    if not staff:
        return False
    class_doc = await db.classes.find_one(
        scoped_query({"id": class_id, "class_teacher_id": staff["id"]}, branch_id=bid), {"_id": 0, "id": 1}
    )
    if class_doc:
        return True
    if subject_id:
        subject = await db.subjects.find_one(
            scoped_query({"id": subject_id, "class_id": class_id, "teacher_id": staff["id"]}, branch_id=bid),
            {"_id": 0, "id": 1},
        )
        return bool(subject)
    return False


@router.get("")
async def list_quizzes(request: Request,
                       user: dict = Depends(require_role("owner", "admin", "teacher", "student"))):
    db = get_db()
    bid = user.get("branch_id")
    query = {}
    if user.get("role") == "student":
        student = await _student(db, user)
        query = {"class_id": student.get("class_id"), "status": "published"}
    elif user.get("role") == "teacher":
        query = {"created_by": user["id"]}
    elif user.get("role") == "admin" and user.get("sub_category") != "principal":
        raise HTTPException(403, "Only the principal can view every quiz")
    rows = await db.quizzes.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(500)
    data = [{key: value for key, value in row.items() if key != "questions"} | {"question_count": len(row.get("questions") or [])} for row in rows]
    return {"success": True, "data": data, "meta": {"count": len(data)}}


@router.post("")
async def post_quiz(request: Request,
                    user: dict = Depends(require_role("owner", "admin", "teacher"))):
    body = await request.json()
    if user.get("role") == "admin" and user.get("sub_category") != "principal":
        raise HTTPException(403, "Only the principal can author quizzes")
    if not await _teacher_can_author(get_db(), user, body.get("class_id"), body.get("subject_id")):
        raise HTTPException(403, "Teacher is not assigned to this class or subject")
    try:
        row = await create_quiz(get_db(), _actor(user), body)
    except (QuizValidationError, QuizNotFoundError, QuizConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/{quiz_id}/publish")
async def patch_quiz_publish(quiz_id: str, request: Request,
                             user: dict = Depends(require_role("owner", "admin", "teacher"))):
    if user.get("role") == "admin" and user.get("sub_category") != "principal":
        raise HTTPException(403, "Only the principal can publish quizzes")
    try:
        row = await publish_quiz(get_db(), _actor(user), quiz_id)
    except (QuizValidationError, QuizNotFoundError, QuizConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": {key: value for key, value in row.items() if key != "questions"}}


@router.post("/{quiz_id}/attempts")
async def post_attempt(quiz_id: str, request: Request,
                       user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await _student(db, user)
    quiz = await db.quizzes.find_one(scoped_query({
        "id": quiz_id, "class_id": student.get("class_id"), "status": "published",
    }, branch_id=user.get("branch_id")), {"_id": 0})
    if not quiz:
        raise HTTPException(404, "Published quiz not found for this class")
    try:
        row = await start_attempt(db, _actor(user), quiz, student)
    except (QuizValidationError, QuizNotFoundError, QuizConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.post("/attempts/{attempt_id}/submit")
async def post_attempt_submission(attempt_id: str, request: Request,
                                  user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await _student(db, user)
    attempt = await db.quiz_attempts.find_one(scoped_query({
        "id": attempt_id, "student_id": student["id"],
    }, branch_id=user.get("branch_id")), {"_id": 0, "id": 1})
    if not attempt:
        raise HTTPException(404, "Quiz attempt not found")
    body = await request.json()
    try:
        row = await submit_attempt(db, _actor(user), attempt_id, body.get("answers"))
    except (QuizValidationError, QuizNotFoundError, QuizConflictError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/attempts/results")
async def list_attempt_results(request: Request, quiz_id: str | None = None,
                               user: dict = Depends(require_role("owner", "admin", "teacher", "student"))):
    db = get_db()
    bid = user.get("branch_id")
    query = {"status": "submitted"}
    if quiz_id:
        query["quiz_id"] = quiz_id
    if user.get("role") == "student":
        query["student_id"] = (await _student(db, user))["id"]
    elif user.get("role") == "teacher":
        quizzes = await db.quizzes.find(
            scoped_query({"created_by": user["id"]}, branch_id=bid), {"_id": 0, "id": 1}
        ).to_list(500)
        query["quiz_id"] = {"$in": [row["id"] for row in quizzes]}
    elif user.get("role") == "admin" and user.get("sub_category") != "principal":
        raise HTTPException(403, "Only the principal can view every quiz result")
    rows = await db.quiz_attempts.find(scoped_query(query, branch_id=bid), {"_id": 0, "answers": 0}).sort("submitted_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}
