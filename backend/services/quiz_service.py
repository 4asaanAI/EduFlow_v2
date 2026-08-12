"""Server-graded quiz definitions and attempts."""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone

from services import audit_changes
from services.actor_context import ActorContext
from services.audit_service import write_audit
from tenant import scoped_query


class QuizValidationError(Exception):
    pass


class QuizNotFoundError(Exception):
    pass


class QuizConflictError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _questions(raw) -> list[dict]:
    if not isinstance(raw, list) or not raw:
        raise QuizValidationError("questions must contain at least one question")
    result = []
    for index, question in enumerate(raw):
        if not isinstance(question, dict):
            raise QuizValidationError(f"questions[{index}] must be an object")
        prompt = str(question.get("prompt") or "").strip()
        options = question.get("options")
        if not prompt or not isinstance(options, list) or len(options) < 2:
            raise QuizValidationError(f"questions[{index}] requires a prompt and at least two options")
        cleaned_options = [str(value).strip() for value in options]
        if any(not value for value in cleaned_options):
            raise QuizValidationError(f"questions[{index}] options cannot be blank")
        try:
            correct = int(question.get("correct_option"))
            points = float(question.get("points", 1))
        except (TypeError, ValueError):
            raise QuizValidationError(f"questions[{index}] correct_option and points must be numeric")
        if correct < 0 or correct >= len(cleaned_options):
            raise QuizValidationError(f"questions[{index}] correct_option is out of range")
        if points <= 0:
            raise QuizValidationError(f"questions[{index}] points must be positive")
        result.append({
            "id": str(uuid.uuid4()), "prompt": prompt, "options": cleaned_options,
            "correct_option": correct, "points": points,
            "explanation": question.get("explanation"),
        })
    return result


async def create_quiz(db, actor_ctx: ActorContext, params: dict) -> dict:
    title = str(params.get("title") or "").strip()
    class_id = str(params.get("class_id") or "").strip()
    if not title or not class_id:
        raise QuizValidationError("title and class_id are required")
    questions = _questions(params.get("questions"))
    try:
        max_attempts = int(params.get("max_attempts") or 1)
        duration_minutes = int(params.get("duration_minutes") or 30)
    except (TypeError, ValueError):
        raise QuizValidationError("max_attempts and duration_minutes must be integers")
    if max_attempts < 1 or max_attempts > 10 or duration_minutes < 1 or duration_minutes > 300:
        raise QuizValidationError("Quiz attempt or duration limit is invalid")
    quiz_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": quiz_id, "id": quiz_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "title": title, "description": params.get("description"),
        "class_id": class_id, "subject_id": params.get("subject_id"),
        "questions": questions, "total_points": sum(row["points"] for row in questions),
        "duration_minutes": duration_minutes, "max_attempts": max_attempts,
        "randomize_questions": bool(params.get("randomize_questions", True)),
        "status": "draft", "created_by": actor_ctx.user_id,
        "created_at": now, "updated_at": now,
    }
    await db.quizzes.insert_one(doc)
    clean = {key: value for key, value in doc.items() if key != "_id"}
    # R4-2: a quiz carries marks, so who set it and who changed it is a school record.
    # Attempts are deliberately NOT audited: an attempt row already carries the student,
    # the answers, the score and the time, so it IS the record, and copying every
    # attempt into the audit trail would multiply storage by the size of the school for
    # no new information (decision 13).
    await write_audit(
        db,
        action="quiz_create",
        entity_id=doc["id"],
        collection="quizzes",
        changed_by=actor_ctx.user_id or "",
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes=audit_changes.created(clean),
        reason=f"Quiz: {doc.get('title') or doc['id']}",
    )
    return clean


async def publish_quiz(db, actor_ctx: ActorContext, quiz_id: str) -> dict:
    quiz = await db.quizzes.find_one(
        scoped_query({"id": quiz_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not quiz:
        raise QuizNotFoundError("Quiz not found")
    if quiz.get("created_by") != actor_ctx.user_id and actor_ctx.role == "teacher":
        raise QuizConflictError("Teachers can publish only quizzes they created")
    if quiz.get("status") == "published":
        return quiz
    now = _now()
    await db.quizzes.update_one(
        scoped_query({"id": quiz_id, "status": "draft"}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "published", "published_at": now, "updated_at": now}},
    )
    # R4-2. Publishing is the moment a quiz becomes real to students, and it is the
    # change most likely to be queried later ("this went out before we were ready").
    await write_audit(
        db,
        action="quiz_publish",
        entity_id=quiz_id,
        collection="quizzes",
        changed_by=actor_ctx.user_id or "",
        changed_by_role=actor_ctx.role or "",
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id or "",
        changes=audit_changes.edit(quiz, {"status": "published", "published_at": now}),
        reason=f"Published {quiz.get('title') or quiz_id}",
    )
    return {**quiz, "status": "published", "published_at": now}


async def start_attempt(db, actor_ctx: ActorContext, quiz: dict, student: dict) -> dict:
    attempts = await db.quiz_attempts.count_documents(scoped_query({
        "quiz_id": quiz["id"], "student_id": student["id"],
        "status": {"$in": ["in_progress", "submitted"]},
    }, branch_id=actor_ctx.branch_id))
    active = await db.quiz_attempts.find_one(scoped_query({
        "quiz_id": quiz["id"], "student_id": student["id"], "status": "in_progress",
    }, branch_id=actor_ctx.branch_id), {"_id": 0})
    if active:
        return public_attempt(active, quiz=quiz)
    if attempts >= int(quiz.get("max_attempts") or 1):
        raise QuizConflictError("Maximum quiz attempts reached")
    question_ids = [row["id"] for row in quiz["questions"]]
    if quiz.get("randomize_questions"):
        random.SystemRandom().shuffle(question_ids)
    attempt_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": attempt_id, "id": attempt_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "quiz_id": quiz["id"],
        "student_id": student["id"], "student_user_id": actor_ctx.user_id,
        "question_ids": question_ids,
        "attempt_number": attempts + 1, "status": "in_progress",
        "started_at": now, "answers": {},
    }
    await db.quiz_attempts.insert_one(doc)
    return public_attempt(doc, quiz=quiz)


def public_attempt(attempt: dict, quiz: dict | None = None) -> dict:
    data = {key: value for key, value in attempt.items() if key not in {"_id", "answers"}}
    if quiz and attempt.get("status") == "in_progress":
        by_id = {row["id"]: row for row in quiz["questions"]}
        data["quiz"] = {
            "id": quiz["id"], "title": quiz["title"],
            "duration_minutes": quiz.get("duration_minutes"),
            "questions": [{
                "id": by_id[qid]["id"], "prompt": by_id[qid]["prompt"],
                "options": by_id[qid]["options"], "points": by_id[qid]["points"],
            } for qid in attempt["question_ids"] if qid in by_id],
        }
    return data


async def submit_attempt(db, actor_ctx: ActorContext, attempt_id: str, answers: dict) -> dict:
    attempt = await db.quiz_attempts.find_one(
        scoped_query({"id": attempt_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not attempt:
        raise QuizNotFoundError("Quiz attempt not found")
    if attempt.get("student_user_id") not in (None, actor_ctx.user_id):
        raise QuizConflictError("Cannot submit another student's quiz attempt")
    if attempt.get("status") == "submitted":
        return public_attempt(attempt)
    if not isinstance(answers, dict):
        raise QuizValidationError("answers must be an object keyed by question id")
    quiz = await db.quizzes.find_one(
        scoped_query({"id": attempt["quiz_id"]}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not quiz:
        raise QuizNotFoundError("Quiz not found")
    detail = []
    score = 0.0
    for question in quiz["questions"]:
        raw = answers.get(question["id"])
        try:
            selected = int(raw) if raw is not None else None
        except (TypeError, ValueError):
            raise QuizValidationError(f"Invalid answer for question {question['id']}")
        if selected is not None and (selected < 0 or selected >= len(question["options"])):
            raise QuizValidationError(f"Answer is out of range for question {question['id']}")
        correct = selected == question["correct_option"]
        if correct:
            score += question["points"]
        detail.append({
            "question_id": question["id"], "selected_option": selected,
            "correct_option": question["correct_option"], "correct": correct,
            "points_awarded": question["points"] if correct else 0,
            "explanation": question.get("explanation"),
        })
    total = float(quiz.get("total_points") or 0)
    now = _now()
    update = {
        "status": "submitted", "answers": answers, "result_detail": detail,
        "score": score, "total_points": total,
        "percentage": round(score / total * 100, 2) if total else 0,
        "submitted_at": now,
    }
    result = await db.quiz_attempts.update_one(
        scoped_query({"id": attempt_id, "status": "in_progress"}, branch_id=actor_ctx.branch_id),
        {"$set": update},
    )
    if result.matched_count == 0:
        raise QuizConflictError("Quiz attempt changed; refresh and retry")
    return public_attempt({**attempt, **update})
