"""Routes: assignments, exams, results, subjects, timetable"""
from fastapi import APIRouter, Request, HTTPException
from database import get_db
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/academics", tags=["academics"])


def get_user(req: Request):
    return {"id": req.headers.get("X-User-Id", "user-owner-001"), "role": req.headers.get("X-User-Role", "owner")}


# --- Assignments ---
@router.get("/assignments")
async def list_assignments(request: Request, class_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if class_id:
        query["class_id"] = class_id
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    elif user["role"] == "student":
        student = await db.students.find_one({"user_id": user["id"]})
        if student:
            query["class_id"] = student["class_id"]
    assignments = await db.assignments.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    for a in assignments:
        subj = await db.subjects.find_one({"id": a.get("subject_id")}, {"_id": 0})
        a["subject_name"] = subj["name"] if subj else "N/A"
        cls = await db.classes.find_one({"id": a.get("class_id")}, {"_id": 0})
        a["class_name"] = f"{cls['name']}-{cls['section']}" if cls else "N/A"
    return {"success": True, "data": assignments}


@router.post("/assignments")
async def create_assignment(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    assignment = {
        "id": str(uuid.uuid4()),
        "class_id": body.get("class_id"),
        "subject_id": body.get("subject_id"),
        "teacher_id": user["id"],
        "title": body.get("title"),
        "description": body.get("description", ""),
        "due_date": body.get("due_date"),
        "is_ai_blocked": body.get("is_ai_blocked", True),
        "created_at": datetime.now().isoformat(),
    }
    await db.assignments.insert_one({**assignment, "_id": assignment["id"]})
    return {"success": True, "data": assignment}


@router.patch("/assignments/{assignment_id}")
async def update_assignment(assignment_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["title", "description", "due_date", "subject_id", "class_id"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.assignments.update_one({"id": assignment_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Assignment not found")
    return {"success": True}


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(assignment_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    result = await db.assignments.delete_one({"id": assignment_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Assignment not found")
    return {"success": True}


# --- Exams ---
@router.get("/exams")
async def list_exams(request: Request):
    db = get_db()
    exams = await db.exams.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return {"success": True, "data": exams}


@router.post("/exams")
async def create_exam(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    ay = await db.academic_years.find_one({"is_current": True})
    exam = {
        "id": str(uuid.uuid4()),
        "academic_year_id": ay["id"] if ay else None,
        "name": body.get("name"),
        "exam_type": body.get("exam_type", "unit_test"),
        "start_date": body.get("start_date"),
        "end_date": body.get("end_date"),
        "created_at": datetime.now().isoformat(),
    }
    await db.exams.insert_one({**exam, "_id": exam["id"]})
    return {"success": True, "data": exam}


# --- Exam Results ---
@router.get("/results")
async def get_results(request: Request, exam_id: str = None, student_id: str = None, class_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if exam_id:
        query["exam_id"] = exam_id
    if class_id:
        class_students = await db.students.find({"class_id": class_id}, {"_id": 0, "id": 1}).to_list(200)
        query["student_id"] = {"$in": [s["id"] for s in class_students]}
    if student_id:
        if user["role"] == "student":
            own = await db.students.find_one({"user_id": user["id"]})
            if not own or own["id"] != student_id:
                raise HTTPException(403, "Forbidden")
        query["student_id"] = student_id
    elif user["role"] == "student" and not class_id:
        own = await db.students.find_one({"user_id": user["id"]})
        if own:
            query["student_id"] = own["id"]
    results = await db.exam_results.find(query, {"_id": 0}).to_list(500)
    enriched = []
    for r in results:
        subj = await db.subjects.find_one({"id": r.get("subject_id")}, {"_id": 0})
        student = await db.students.find_one({"id": r.get("student_id")}, {"_id": 0})
        enriched.append({**r, "subject_name": subj["name"] if subj else "N/A", "student_name": student["name"] if student else "N/A"})
    return {"success": True, "data": enriched}


@router.post("/results/bulk")
async def bulk_enter_results(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    results = body.get("results", [])
    saved = 0
    for r in results:
        doc = {
            "id": str(uuid.uuid4()),
            "exam_id": r.get("exam_id"),
            "student_id": r.get("student_id"),
            "subject_id": r.get("subject_id"),
            "marks_obtained": r.get("marks_obtained"),
            "max_marks": r.get("max_marks", 100),
            "grade": r.get("grade"),
            "remarks": r.get("remarks", ""),
            "entered_by": user["id"],
            "created_at": datetime.now().isoformat(),
        }
        await db.exam_results.update_one(
            {"exam_id": r.get("exam_id"), "student_id": r.get("student_id"), "subject_id": r.get("subject_id")},
            {"$set": {**doc, "_id": doc["id"]}}, upsert=True
        )
        saved += 1
    return {"success": True, "saved": saved}


@router.post("/lesson-plans")
async def create_lesson_plan(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    plan = {
        "id": str(uuid.uuid4()),
        "teacher_id": user["id"],
        "subject_id": body.get("subject_id"),
        "class_id": body.get("class_id"),
        "chapter": body.get("chapter"),
        "content": body.get("content", {}),
        "created_at": datetime.now().isoformat(),
    }
    await db.lesson_plans.insert_one({**plan, "_id": plan["id"]})
    return {"success": True, "data": plan}


@router.get("/lesson-plans")
async def list_lesson_plans(request: Request):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    plans = await db.lesson_plans.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": plans}


@router.patch("/lesson-plans/{plan_id}")
async def update_lesson_plan(plan_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["chapter", "subject_id", "class_id", "content"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.lesson_plans.update_one({"id": plan_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/lesson-plans/{plan_id}")
async def delete_lesson_plan(plan_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    result = await db.lesson_plans.delete_one({"id": plan_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.post("/question-papers/generate")
async def generate_question_paper(request: Request):
    """Use LLM to generate a question paper."""
    from ai.llm_client import llm_client
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    subject = body.get("subject", "Mathematics")
    chapters = body.get("chapters", "all chapters")
    total_marks = body.get("total_marks", 100)
    easy_pct = body.get("easy", 30)
    medium_pct = body.get("medium", 50)
    hard_pct = body.get("hard", 20)
    exam_type = body.get("exam_type", "Unit Test")
    board = "CBSE"

    prompt = f"""Generate a complete {board} {exam_type} question paper for {subject}.
Topics/Chapters: {chapters}
Total Marks: {total_marks}
Difficulty: Easy {easy_pct}%, Medium {medium_pct}%, Hard {hard_pct}%

Format the paper with:
- Section A: Multiple Choice Questions (1 mark each)
- Section B: Short Answer Questions (2-3 marks each)  
- Section C: Long Answer Questions (5-6 marks each)

Include time duration, general instructions, and clear question numbering.
Make questions appropriate for Classes 9-12 CBSE standard."""

    import uuid
    session_id = f"qp-{uuid.uuid4()}"
    try:
        paper_text = await llm_client.chat(
            "You are an expert CBSE question paper setter. Generate well-structured, academically accurate question papers.",
            [{"role": "user", "content": prompt}],
            session_id
        )
        # Save to DB
        db = get_db()
        subj = await db.subjects.find_one({"name": {"$regex": subject, "$options": "i"}}, {"_id": 0})
        qp = {
            "id": str(uuid.uuid4()),
            "teacher_id": user["id"],
            "subject_id": subj["id"] if subj else None,
            "title": f"{subject} - {exam_type}",
            "chapters": [chapters] if isinstance(chapters, str) else chapters,
            "difficulty_mix": {"easy": easy_pct, "medium": medium_pct, "hard": hard_pct},
            "generated_content": paper_text,
            "total_marks": total_marks,
            "created_at": datetime.now().isoformat(),
        }
        await db.question_papers.insert_one({**qp, "_id": qp["id"]})
        return {"success": True, "data": {"content": paper_text, "id": qp["id"]}}
    except Exception as e:
        raise HTTPException(500, f"Generation failed: {str(e)}")


@router.get("/question-papers")
async def list_question_papers(request: Request):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    papers = await db.question_papers.find(query, {"_id": 0, "generated_content": 0}).sort("created_at", -1).to_list(20)
    return {"success": True, "data": papers}


@router.get("/question-papers/{paper_id}")
async def get_question_paper(paper_id: str, request: Request):
    db = get_db()
    paper = await db.question_papers.find_one({"id": paper_id}, {"_id": 0})
    if not paper:
        raise HTTPException(404, "Not found")
    return {"success": True, "data": paper}


@router.patch("/question-papers/{paper_id}")
async def update_question_paper(paper_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["title", "generated_content"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.question_papers.update_one({"id": paper_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/question-papers/{paper_id}")
async def delete_question_paper(paper_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    result = await db.question_papers.delete_one({"id": paper_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


# --- Subjects ---
@router.get("/subjects")
async def list_subjects(request: Request, class_id: str = None):
    db = get_db()
    query = {}
    if class_id:
        query["class_id"] = class_id
    subjects = await db.subjects.find(query, {"_id": 0}).to_list(100)
    return {"success": True, "data": subjects}


# --- Timetable ---
@router.get("/timetable/{class_id}")
async def get_timetable(class_id: str, request: Request):
    db = get_db()
    slots = await db.timetable_slots.find({"class_id": class_id}, {"_id": 0}).sort("day_of_week", 1).to_list(100)
    enriched = []
    for s in slots:
        subj = await db.subjects.find_one({"id": s.get("subject_id")}, {"_id": 0})
        s["subject_name"] = subj["name"] if subj else "N/A"
        enriched.append(s)
    return {"success": True, "data": enriched}


@router.post("/timetable")
async def add_timetable_slot(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    slot = {
        "id": str(uuid.uuid4()),
        "class_id": body.get("class_id"),
        "subject_id": body.get("subject_id"),
        "teacher_id": body.get("teacher_id"),
        "day_of_week": body.get("day_of_week"),
        "period_number": body.get("period_number"),
        "start_time": body.get("start_time"),
        "end_time": body.get("end_time"),
        "room": body.get("room", ""),
    }
    await db.timetable_slots.update_one(
        {"class_id": slot["class_id"], "day_of_week": slot["day_of_week"], "period_number": slot["period_number"]},
        {"$set": {**slot, "_id": slot["id"]}}, upsert=True
    )
    return {"success": True, "data": slot}


@router.patch("/timetable/{slot_id}")
async def update_timetable_slot(slot_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    await db.timetable_slots.update_one({"id": slot_id}, {"$set": body})
    slot = await db.timetable_slots.find_one({"id": slot_id}, {"_id": 0})
    return {"success": True, "data": slot}


@router.delete("/timetable/{slot_id}")
async def delete_timetable_slot(slot_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    await db.timetable_slots.delete_one({"id": slot_id})
    return {"success": True}


# --- PTM Notes ---
@router.get("/ptm-notes")
async def list_ptm_notes(request: Request, student_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if student_id:
        query["student_id"] = student_id
    elif user["role"] == "student":
        own = await db.students.find_one({"user_id": user["id"]})
        if own:
            query["student_id"] = own["id"]
    elif user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    notes = await db.ptm_notes.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    for n in notes:
        student = await db.students.find_one({"id": n.get("student_id")}, {"_id": 0})
        n["student_name"] = student["name"] if student else "N/A"
    return {"success": True, "data": notes}


@router.post("/ptm-notes")
async def create_ptm_note(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    note = {
        "id": str(uuid.uuid4()),
        "student_id": body.get("student_id"),
        "teacher_id": user["id"],
        "notes": body.get("notes"),
        "summary_sent": False,
        "created_at": datetime.now().isoformat(),
    }
    await db.ptm_notes.insert_one({**note, "_id": note["id"]})
    return {"success": True, "data": note}


@router.patch("/ptm-notes/{note_id}")
async def update_ptm_note(note_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["notes", "student_id"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.ptm_notes.update_one({"id": note_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/ptm-notes/{note_id}")
async def delete_ptm_note(note_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin", "owner"]:
        raise HTTPException(403, "Forbidden")
    result = await db.ptm_notes.delete_one({"id": note_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.get("/worksheets")
async def list_worksheets(request: Request):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["teacher_id"] = user["id"]
    elif user["role"] == "student":
        own = await db.students.find_one({"user_id": user["id"]})
        if own:
            query["class_id"] = own["class_id"]
    worksheets = await db.worksheets.find(query, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"success": True, "data": worksheets}


@router.post("/worksheets")
async def create_worksheet(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    ws = {
        "id": str(uuid.uuid4()),
        "teacher_id": user["id"],
        "subject_id": body.get("subject_id"),
        "topic": body.get("topic"),
        "type": body.get("type", "practice"),
        "content": body.get("content", ""),
        "is_ai_blocked": False,
        "created_at": datetime.now().isoformat(),
    }
    await db.worksheets.insert_one({**ws, "_id": ws["id"]})
    return {"success": True, "data": ws}


@router.patch("/worksheets/{ws_id}")
async def update_worksheet(ws_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["topic", "subject_id", "type", "content"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.worksheets.update_one({"id": ws_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/worksheets/{ws_id}")
async def delete_worksheet(ws_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    result = await db.worksheets.delete_one({"id": ws_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.get("/substitutions")
async def list_substitutions(request: Request):
    db = get_db()
    # Return empty for now — substitutions are managed manually
    return {"success": True, "data": []}


# --- Curriculum Progress ---
@router.get("/curriculum")
async def list_curriculum(request: Request, class_id: str = None, subject_id: str = None):
    db = get_db()
    user = get_user(request)
    query = {}
    if user["role"] == "teacher":
        query["updated_by"] = user["id"]
    if class_id:
        query["class_id"] = class_id
    if subject_id:
        query["subject_id"] = subject_id
    progress = await db.curriculum_progress.find(query, {"_id": 0}).to_list(100)
    return {"success": True, "data": progress}


@router.post("/curriculum")
async def update_curriculum(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    doc = {
        "id": str(uuid.uuid4()),
        "class_id": body.get("class_id"),
        "subject_id": body.get("subject_id"),
        "topic": body.get("topic"),
        "status": body.get("status", "not_started"),
        "updated_by": user["id"],
        "updated_at": datetime.now().isoformat(),
    }
    await db.curriculum_progress.update_one(
        {"class_id": doc["class_id"], "subject_id": doc["subject_id"], "topic": doc["topic"]},
        {"$set": {**doc, "_id": doc["id"]}}, upsert=True
    )
    return {"success": True, "data": doc}


@router.patch("/curriculum/{item_id}")
async def patch_curriculum(item_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in ["topic", "status", "class_id", "subject_id"]}
    update["updated_at"] = datetime.now().isoformat()
    result = await db.curriculum_progress.update_one({"id": item_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}


@router.delete("/curriculum/{item_id}")
async def delete_curriculum(item_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Forbidden")
    result = await db.curriculum_progress.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "Not found")
    return {"success": True}
