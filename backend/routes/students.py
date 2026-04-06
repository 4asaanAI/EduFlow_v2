from fastapi import APIRouter, Request, HTTPException
from database import get_db
from models.schemas import Student, Guardian, StudentCreate
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/students", tags=["students"])


def get_user(req: Request):
    return {
        "id": req.headers.get("X-User-Id", "user-owner-001"),
        "role": req.headers.get("X-User-Role", "owner"),
        "name": req.headers.get("X-User-Name", "Aman"),
    }


@router.get("/")
async def list_students(request: Request, class_id: str = None, search: str = None, page: int = 1):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher"]:
        raise HTTPException(403, "Forbidden")

    query = {"is_active": True}
    if class_id:
        query["class_id"] = class_id
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"admission_number": {"$regex": search, "$options": "i"}},
        ]

    per_page = 20
    skip = (page - 1) * per_page
    students = await db.students.find(query, {"_id": 0}).skip(skip).limit(per_page).to_list(per_page)
    total = await db.students.count_documents(query)

    # Batch class lookups (fix N+1)
    class_ids = list(set(s.get("class_id") for s in students if s.get("class_id")))
    classes = await db.classes.find({"id": {"$in": class_ids}}, {"_id": 0}).to_list(len(class_ids)) if class_ids else []
    class_map = {c["id"]: {"name": c["name"], "section": c["section"]} for c in classes}
    for s in students:
        s["class_info"] = class_map.get(s.get("class_id"))

    return {"success": True, "data": students, "meta": {"page": page, "total": total, "per_page": per_page}}


@router.post("/")
async def create_student(body: StudentCreate, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    # Verify class exists
    cls = await db.classes.find_one({"id": body.class_id})
    if not cls:
        raise HTTPException(404, "Class not found")

    student = Student(
        class_id=body.class_id,
        name=body.name,
        admission_number=body.admission_number or f"ADM{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:4].upper()}",
        roll_number=body.roll_number,
        dob=body.dob,
        gender=body.gender,
    )
    await db.students.insert_one({**student.dict(), "_id": student.id})

    # Create guardian if provided
    if body.guardian_name and body.guardian_phone:
        guardian = Guardian(
            student_id=student.id,
            name=body.guardian_name,
            relation="Parent",
            phone=body.guardian_phone,
            whatsapp_phone=body.guardian_phone,
            is_primary=True,
        )
        await db.guardians.insert_one({**guardian.dict(), "_id": guardian.id})

    return {"success": True, "data": student.dict()}


@router.get("/{student_id}")
async def get_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)

    student = await db.students.find_one({"id": student_id}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    # Role check: student can only see own data
    if user["role"] == "student" and student.get("user_id") != user["id"]:
        raise HTTPException(403, "Forbidden")

    cls = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0})
    student["class_info"] = cls
    guardians = await db.guardians.find({"student_id": student_id}, {"_id": 0}).to_list(5)
    student["guardians"] = guardians

    return {"success": True, "data": student}


@router.patch("/{student_id}")
async def update_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    body["updated_at"] = datetime.now().isoformat()
    body.pop("id", None)
    await db.students.update_one({"id": student_id}, {"$set": body})
    return {"success": True}


@router.delete("/{student_id}")
async def delete_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    # Soft delete
    await db.students.update_one({"id": student_id}, {"$set": {"is_active": False, "status": "withdrawn", "withdrawal_date": datetime.now().strftime("%Y-%m-%d")}})
    return {"success": True}


@router.get("/classes/all")
async def get_all_classes(request: Request):
    db = get_db()
    classes = await db.classes.find({}, {"_id": 0}).to_list(50)
    return {"success": True, "data": classes}
