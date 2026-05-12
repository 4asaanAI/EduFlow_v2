from __future__ import annotations

from datetime import datetime
import hashlib
import re
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from database import get_db
from middleware.auth import get_current_user
from models.schemas import Guardian, Student, StudentCreate
from services.s3_storage import (
    build_upload_key,
    create_presigned_get_url,
    delete_object,
    infer_content_type,
    upload_bytes,
)
from tenant import get_school_id, scoped_filter


router = APIRouter(prefix="/api/students", tags=["students"])

ADMIN_ROLES = {"owner", "admin"}
READ_ROLES = {"owner", "admin", "teacher"}
SORT_FIELDS = {
    "created_at": ("created_at", -1),
    "name": ("name", 1),
    "class": ("class_id", 1),
}
UPDATABLE_FIELDS = {
    "name",
    "class_id",
    "admission_number",
    "roll_number",
    "dob",
    "gender",
    "blood_group",
    "photo_url",
    "uses_transport",
    "bus_route",
    "route_zone_id",
    "status",
}
PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic"}
MAX_PHOTO_BYTES = 5 * 1024 * 1024


def get_user(req: Request):
    return get_current_user(req)


def _public_doc(doc: dict | None) -> dict | None:
    if not doc:
        return None
    return {k: v for k, v in doc.items() if k != "_id"}


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _student_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


def _role_can_manage(user: dict) -> bool:
    return user.get("role") in ADMIN_ROLES


def _is_transport_head(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "transport_head"


async def _get_current_academic_year(db) -> dict | None:
    return await db.academic_years.find_one(scoped_filter({"is_current": True}, get_school_id()), {"_id": 0})


async def _validate_class(db, class_id: str) -> dict:
    cls = await db.classes.find_one(scoped_filter({"id": class_id}, get_school_id()), {"_id": 0})
    if not cls:
        raise HTTPException(404, "Class not found")

    current_year = await _get_current_academic_year(db)
    class_year = cls.get("academic_year_id")
    if current_year and class_year and class_year != current_year.get("id"):
        raise HTTPException(400, "Class does not belong to the current academic year")
    return cls


async def _add_class_and_guardians(db, student: dict, include_guardians: bool = False) -> dict:
    cls = await db.classes.find_one(scoped_filter({"id": student.get("class_id")}, get_school_id()), {"_id": 0})
    student["class_info"] = cls
    if include_guardians:
        guardians = await db.guardians.find(
            scoped_filter({"student_id": student["id"]}, get_school_id()),
            {"_id": 0},
        ).to_list(10)
        student["guardians"] = guardians
    return student


async def _audit(db, *, action: str, student_id: str, user: dict, changes: dict | None = None, reason: str | None = None):
    record = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "entity_type": "student",
        "entity_id": student_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_role": user.get("role"),
        "changes": changes or {},
        "reason": reason,
        "created_at": datetime.now().isoformat(),
    }
    await db.audit_logs.insert_one(record)


@router.get("/")
async def list_students(
    request: Request,
    class_id: str = None,
    search: str = None,
    page: int = 1,
    limit: int = 20,
    sort: str = "created_at",
    include_inactive: bool = False,
):
    db = get_db()
    user = get_user(request)
    if user["role"] not in READ_ROLES:
        raise HTTPException(403, "Forbidden")
    if include_inactive and user["role"] != "owner":
        raise HTTPException(403, "Only owners can include inactive students")

    page = max(page, 1)
    per_page = max(1, min(limit, 20))
    query = {} if include_inactive else {"is_active": True}
    if class_id:
        query["class_id"] = class_id
    if search:
        safe_search = re.escape(search)
        query["$or"] = [
            {"name": {"$regex": safe_search, "$options": "i"}},
            {"admission_number": {"$regex": safe_search, "$options": "i"}},
        ]

    sort_field, sort_dir = SORT_FIELDS.get(sort, SORT_FIELDS["created_at"])
    scoped_query = _student_query(query)
    skip = (page - 1) * per_page
    students = await db.students.find(scoped_query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(per_page).to_list(per_page)
    total = await db.students.count_documents(scoped_query)

    class_ids = list({s.get("class_id") for s in students if s.get("class_id")})
    classes = await db.classes.find(scoped_filter({"id": {"$in": class_ids}}, get_school_id()), {"_id": 0}).to_list(len(class_ids)) if class_ids else []
    class_map = {c["id"]: {"name": c.get("name"), "section": c.get("section")} for c in classes}
    for student in students:
        student["class_info"] = class_map.get(student.get("class_id"))
        if student.get("photo_url") and student["photo_url"].startswith("s3://"):
            student["photo_url"] = None

    return {"success": True, "data": students, "meta": {"page": page, "total": total, "per_page": per_page, "sort": sort}}


@router.post("/")
async def create_student(body: StudentCreate, request: Request):
    db = get_db()
    user = get_user(request)
    if not _role_can_manage(user):
        raise HTTPException(403, "Forbidden")

    await _validate_class(db, body.class_id)

    admission_number = body.admission_number or f"ADM{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:4].upper()}"
    existing = await db.students.find_one(_student_query({"admission_number": admission_number}), {"_id": 0})
    if existing:
        raise HTTPException(409, "Admission number already exists")

    student = Student(
        class_id=body.class_id,
        name=body.name,
        admission_number=admission_number,
        roll_number=body.roll_number,
        dob=body.dob,
        gender=body.gender,
    )
    student_doc = _serialize(student)
    await db.students.insert_one({**student_doc, "_id": student.id})

    if body.guardian_name and body.guardian_phone:
        guardian = Guardian(
            student_id=student.id,
            name=body.guardian_name,
            relation="Parent",
            phone=body.guardian_phone,
            whatsapp_phone=body.guardian_phone,
            is_primary=True,
        )
        guardian_doc = _serialize(guardian)
        await db.guardians.insert_one({**guardian_doc, "_id": guardian.id})

    await _audit(db, action="create", student_id=student.id, user=user, changes={"created": student_doc})
    return {"success": True, "data": student_doc}


@router.get("/me")
async def get_my_profile(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] != "student":
        raise HTTPException(403, "Only students can access this endpoint")
    student = await db.students.find_one(_student_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        return {"success": True, "data": None}
    return {"success": True, "data": await _add_class_and_guardians(db, student, include_guardians=True)}


@router.get("/classes/all")
async def get_all_classes(request: Request):
    db = get_db()
    classes = await db.classes.find(scoped_filter({}, get_school_id()), {"_id": 0}).to_list(50)
    return {"success": True, "data": classes}


@router.get("/{student_id}")
async def get_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)

    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    if user["role"] == "student" and student.get("user_id") != user["id"]:
        raise HTTPException(403, "Forbidden")
    if user["role"] not in READ_ROLES and user["role"] != "student":
        raise HTTPException(403, "Forbidden")

    return {"success": True, "data": await _add_class_and_guardians(db, student, include_guardians=True)}


@router.patch("/{student_id}")
async def update_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if not _role_can_manage(user):
        raise HTTPException(403, "Forbidden")

    existing = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Student not found")

    body = await request.json()
    update = {k: v for k, v in body.items() if k in UPDATABLE_FIELDS}
    if not update:
        raise HTTPException(400, "No updatable fields provided")
    if _is_transport_head(user):
        allowed_transport_fields = {"route_zone_id", "uses_transport", "bus_route"}
        blocked = set(update) - allowed_transport_fields
        if blocked:
            raise HTTPException(403, "Transport Head can only update transport assignment fields")
    if "class_id" in update:
        await _validate_class(db, update["class_id"])
    if "admission_number" in update and update["admission_number"] != existing.get("admission_number"):
        duplicate = await db.students.find_one(_student_query({"admission_number": update["admission_number"]}), {"_id": 0})
        if duplicate and duplicate.get("id") != student_id:
            raise HTTPException(409, "Admission number already exists")

    changes = {
        key: {"previous": existing.get(key), "new": value}
        for key, value in update.items()
        if existing.get(key) != value
    }
    if not changes:
        return {"success": True, "data": existing}

    update["updated_at"] = datetime.now().isoformat()
    await db.students.update_one(_student_query({"id": student_id}), {"$set": update})
    await _audit(db, action="update", student_id=student_id, user=user, changes=changes)
    updated = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    return {"success": True, "data": updated}


@router.delete("/{student_id}")
async def delete_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if not _role_can_manage(user):
        raise HTTPException(403, "Forbidden")
    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    withdrawal_date = datetime.now().strftime("%Y-%m-%d")
    await db.students.update_one(
        _student_query({"id": student_id}),
        {"$set": {"is_active": False, "status": "withdrawn", "withdrawal_date": withdrawal_date, "updated_at": datetime.now().isoformat()}},
    )
    await _audit(
        db,
        action="deactivate",
        student_id=student_id,
        user=user,
        changes={"is_active": {"previous": student.get("is_active"), "new": False}, "status": {"previous": student.get("status"), "new": "withdrawn"}},
    )
    return {"success": True}


@router.post("/{student_id}/photo")
async def upload_student_photo(student_id: str, request: Request, file: UploadFile = File(...)):
    db = get_db()
    user = get_user(request)
    if not _role_can_manage(user):
        raise HTTPException(403, "Forbidden")

    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in PHOTO_EXTENSIONS:
        raise HTTPException(400, "Student photo must be jpg, jpeg, png, webp, or heic")
    content = await file.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "Student photo exceeds 5MB limit")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    content_type = infer_content_type(file.filename, file.content_type)
    stored = upload_bytes(
        content=content,
        key=build_upload_key(file_id, file.filename),
        content_type=content_type,
        original_filename=file.filename,
    )
    record = {
        "_id": file_id,
        "id": file_id,
        "schoolId": get_school_id(),
        "uploaded_by": user["id"],
        "file_url": f"/api/uploads/serve/{safe_filename}",
        "file_name": file.filename,
        "safe_filename": safe_filename,
        "file_type": content_type,
        "file_size_bytes": len(content),
        "linked_table": "students",
        "linked_id": student_id,
        "created_at": datetime.now().isoformat(),
        "storage": "s3",
        "s3_bucket": stored.bucket,
        "s3_key": stored.key,
        "s3_etag": stored.etag,
        "sha256": stored.sha256,
    }
    try:
        await db.file_uploads.insert_one(record)
        await db.students.update_one(_student_query({"id": student_id}), {"$set": {"photo_url": record["file_url"], "updated_at": datetime.now().isoformat()}})
        await _audit(db, action="photo_update", student_id=student_id, user=user, changes={"photo_url": {"previous": student.get("photo_url"), "new": record["file_url"]}})
    except Exception:
        delete_object(stored.key)
        raise

    return {"success": True, "data": {"photo_url": record["file_url"], "upload_id": file_id, "preview_url": create_presigned_get_url(stored.key)}}


@router.post("/{student_id}/erase")
async def erase_student(student_id: str, request: Request, reason: str = Form(default=None)):
    db = get_db()
    user = get_user(request)
    if user.get("role") != "owner":
        raise HTTPException(403, "Owner only")
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(400, "A detailed erasure reason is required")

    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    token = hashlib.sha256(f"{student_id}:{datetime.now().isoformat()}".encode("utf-8")).hexdigest()
    await _audit(
        db,
        action="dpdp_erase",
        student_id=student_id,
        user=user,
        changes={"erasure_token": token, "student_snapshot": student},
        reason=reason.strip(),
    )
    await db.student_attendance.update_many(
        _student_query({"student_id": student_id}),
        {"$set": {"student_id": token, "student_name": None, "guardian_phone": None, "erased_student_ref": token}},
    )
    uploads = await db.file_uploads.find(scoped_filter({"linked_table": "students", "linked_id": student_id}, get_school_id()), {"_id": 0}).to_list(100)
    for upload in uploads:
        if upload.get("s3_key"):
            delete_object(upload["s3_key"])
    await db.guardians.delete_many(scoped_filter({"student_id": student_id}, get_school_id()))
    await db.file_uploads.delete_many(scoped_filter({"linked_table": "students", "linked_id": student_id}, get_school_id()))
    await db.students.delete_one(_student_query({"id": student_id}))
    return {"success": True, "data": {"erasure_token": token}}
