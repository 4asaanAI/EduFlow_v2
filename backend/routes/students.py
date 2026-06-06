from __future__ import annotations

from datetime import datetime
import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from database import get_db
from middleware.auth import get_current_user, require_owner, require_role
from models.schemas import Guardian, Student, StudentCreate
from services.audit_service import write_audit_doc
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
    "height_cm",
    "weight_kg",
    "medical_notes",
    "emergency_contact",
    "house",
    "photo_url",
    "uses_transport",
    "bus_route",
    "route_zone_id",
    "status",
}

GUARDIAN_UPDATABLE_FIELDS = {
    "name", "phone", "alt_phone", "whatsapp_phone",
    "email", "occupation", "annual_income", "is_primary",
}
SELF_UPDATABLE_FIELDS = {"phone", "email", "preferred_name", "emergency_contact"}
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
    await write_audit_doc(db, record, school_id=get_school_id(), branch_id=user.get("branch_id"))


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
    # auth: read-only roles gate (owner/admin/teacher); extra owner-only check
    # below for `include_inactive`. Single Depends() can't express both.
    if user["role"] not in READ_ROLES:
        raise HTTPException(403, "Forbidden")
    if include_inactive and user["role"] != "owner":
        raise HTTPException(403, "Forbidden")

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

    # Part 14 + 15: Teacher should only see students in their assigned classes
    bid = user.get("branch_id")
    if user.get("role") == "teacher":
        staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
        if staff:
            teacher_class_ids = staff.get("class_teacher_of") or ([staff.get("class_id")] if staff.get("class_id") else [])
            if teacher_class_ids:
                query["class_id"] = {"$in": teacher_class_ids}
            # If teacher has no class assignment, return empty (don't expose all students)
        else:
            return {"success": True, "data": [], "meta": {"page": page, "total": 0, "per_page": per_page, "sort": sort}}

    sort_field, sort_dir = SORT_FIELDS.get(sort, SORT_FIELDS["created_at"])
    scoped_query = _student_query(query)
    skip = (page - 1) * per_page
    students = await db.students.find(scoped_query, {"_id": 0, "coordinates": 0}).sort(sort_field, sort_dir).skip(skip).limit(per_page).to_list(per_page)
    total = await db.students.count_documents(scoped_query)

    class_ids = list({s.get("class_id") for s in students if s.get("class_id")})
    classes = await db.classes.find(scoped_filter({"id": {"$in": class_ids}}, get_school_id()), {"_id": 0}).to_list(len(class_ids)) if class_ids else []
    class_map = {c["id"]: {"name": c.get("name"), "section": c.get("section")} for c in classes}

    student_ids = [s["id"] for s in students if s.get("id")]
    primary_guardians = await db.guardians.find(
        scoped_filter({"student_id": {"$in": student_ids}, "is_primary": True}, get_school_id()),
        {"_id": 0, "student_id": 1, "phone": 1},
    ).to_list(len(student_ids)) if student_ids else []
    guardian_phone_map = {g["student_id"]: g.get("phone") for g in primary_guardians}

    for student in students:
        student["class_info"] = class_map.get(student.get("class_id"))
        student["primary_phone"] = guardian_phone_map.get(student.get("id"))
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
        blood_group=body.blood_group,
        height_cm=body.height_cm,
        weight_kg=body.weight_kg,
        medical_notes=body.medical_notes,
    )
    student_doc = _serialize(student)
    await db.students.insert_one({**student_doc, "_id": student.id})

    guardians_to_create = []
    if body.father_name and body.father_phone:
        guardians_to_create.append(Guardian(
            student_id=student.id,
            name=body.father_name,
            relation="Father",
            phone=body.father_phone,
            whatsapp_phone=body.father_phone,
            occupation=body.father_occupation,
            annual_income=body.annual_income,
            is_primary=True,
        ))
    if body.mother_name and body.mother_phone:
        guardians_to_create.append(Guardian(
            student_id=student.id,
            name=body.mother_name,
            relation="Mother",
            phone=body.mother_phone,
            whatsapp_phone=body.mother_phone,
            occupation=body.mother_occupation,
            is_primary=not body.father_name,
        ))
    if not guardians_to_create and body.guardian_name and body.guardian_phone:
        guardians_to_create.append(Guardian(
            student_id=student.id,
            name=body.guardian_name,
            relation="Parent",
            phone=body.guardian_phone,
            whatsapp_phone=body.guardian_phone,
            is_primary=True,
        ))
    for g in guardians_to_create:
        g_doc = _serialize(g)
        await db.guardians.insert_one({**g_doc, "_id": g.id})

    await _audit(db, action="create", student_id=student.id, user=user, changes={"created": student_doc})
    return {"success": True, "data": student_doc}


@router.get("/me")
async def get_my_profile(request: Request, user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await db.students.find_one(_student_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        return {"success": True, "data": None}
    student = await _add_class_and_guardians(db, student, include_guardians=True)
    # EC-15.6: Remove sensitive guardian fields from student self-view
    GUARDIAN_SENSITIVE_FIELDS = {"annual_income", "occupation", "employer"}
    if student.get("guardians"):
        for guardian in student["guardians"]:
            for field in GUARDIAN_SENSITIVE_FIELDS:
                guardian.pop(field, None)
    return {"success": True, "data": student}


@router.patch("/me")
async def update_my_profile(request: Request, user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await db.students.find_one(_student_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student record not found")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in SELF_UPDATABLE_FIELDS}
    if not update:
        raise HTTPException(400, "No self-service fields provided")
    update["updated_at"] = datetime.now().isoformat()
    await db.students.update_one(_student_query({"id": student["id"]}), {"$set": update})
    await _audit(
        db,
        action="student_self_update",
        student_id=student["id"],
        user=user,
        changes={k: {"previous": student.get(k), "new": v} for k, v in update.items() if k != "updated_at"},
    )
    updated = await db.students.find_one(_student_query({"id": student["id"]}), {"_id": 0})
    return {"success": True, "data": updated}


@router.post("/me/consent")
async def record_my_consent(request: Request, user: dict = Depends(require_role("student"))):
    db = get_db()
    body = await request.json()
    purpose = (body.get("purpose") or "").strip()
    granted = body.get("granted")
    if not purpose or granted is None:
        raise HTTPException(400, "purpose and granted are required")
    student = await db.students.find_one(_student_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student record not found")
    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "student_id": student["id"],
        "user_id": user["id"],
        "purpose": purpose,
        "granted": bool(granted),
        "recorded_at": datetime.now().isoformat(),
        "source": "student_self_service",
    }
    await db.dpdp_consents.insert_one(doc)
    await _audit(db, action="dpdp_consent_recorded", student_id=student["id"], user=user, changes={"purpose": purpose, "granted": bool(granted)})
    return {"success": True, "data": {k: v for k, v in doc.items() if k != "_id"}}


@router.get("/me/consent")
async def list_my_consents(request: Request, user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await db.students.find_one(_student_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        return {"success": True, "data": []}
    consents = await db.dpdp_consents.find(scoped_filter({"student_id": student["id"]}, get_school_id()), {"_id": 0}).sort("recorded_at", -1).to_list(50)
    return {"success": True, "data": consents}


@router.get("/classes/all")
async def get_all_classes(request: Request, user: dict = Depends(require_role("admin", "owner", "teacher", "staff"))):
    db = get_db()
    classes = await db.classes.find(scoped_filter({}, get_school_id()), {"_id": 0}).to_list(50)
    return {"success": True, "data": classes}


@router.get("/{student_id}")
async def get_student(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)

    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0, "coordinates": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    # auth: composite — students may view only their own record; staff
    # with read roles may view any. Combined gate not expressible as one Depends.
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
    if "class_id" in update and update["class_id"] != existing.get("class_id"):
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


@router.get("/{student_id}/guardians")
async def list_guardians(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    # auth: students may view their own guardians; staff with read roles may
    # view any. Combined gate not expressible as one Depends.
    if user["role"] not in READ_ROLES and user["role"] != "student":
        raise HTTPException(403, "Forbidden")
    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")
    guardians = await db.guardians.find(
        scoped_filter({"student_id": student_id}, get_school_id()), {"_id": 0}
    ).to_list(10)
    return {"success": True, "data": guardians}


@router.put("/{student_id}/guardians")
async def upsert_guardians(student_id: str, request: Request):
    """Replace all guardians for a student. Body: list of guardian objects."""
    db = get_db()
    user = get_user(request)
    if not _role_can_manage(user):
        raise HTTPException(403, "Forbidden")
    student = await db.students.find_one(_student_query({"id": student_id}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student not found")

    body = await request.json()
    if not isinstance(body, list):
        raise HTTPException(400, "Body must be a list of guardian objects")

    existing = await db.guardians.find(
        scoped_filter({"student_id": student_id}, get_school_id()), {"_id": 0}
    ).to_list(10)
    existing_by_relation = {g["relation"].lower(): g for g in existing}

    saved = []
    for item in body:
        relation = (item.get("relation") or "Parent").strip()
        name = (item.get("name") or "").strip()
        phone = (item.get("phone") or "").strip()
        if not name or not phone:
            continue
        existing_g = existing_by_relation.get(relation.lower())
        update_doc = {
            "name": name,
            "phone": phone,
            "whatsapp_phone": item.get("whatsapp_phone") or phone,
            "alt_phone": item.get("alt_phone"),
            "email": item.get("email"),
            "occupation": item.get("occupation"),
            "annual_income": item.get("annual_income"),
            "is_primary": item.get("is_primary", False),
            "updated_at": datetime.now().isoformat(),
        }
        if existing_g:
            await db.guardians.update_one(
                scoped_filter({"id": existing_g["id"]}, get_school_id()),
                {"$set": update_doc},
            )
            saved.append({**existing_g, **update_doc})
        else:
            new_g = Guardian(
                student_id=student_id,
                name=name,
                relation=relation,
                phone=phone,
                whatsapp_phone=item.get("whatsapp_phone") or phone,
                alt_phone=item.get("alt_phone"),
                email=item.get("email"),
                occupation=item.get("occupation"),
                annual_income=item.get("annual_income"),
                is_primary=item.get("is_primary", False),
            )
            g_doc = _serialize(new_g)
            await db.guardians.insert_one({**g_doc, "_id": new_g.id})
            saved.append(g_doc)

    await _audit(db, action="guardians_update", student_id=student_id, user=user, changes={"count": len(saved)})
    return {"success": True, "data": saved}


@router.post("/{student_id}/guardians/{guardian_id}/photo")
async def upload_guardian_photo(student_id: str, guardian_id: str, request: Request, file: UploadFile = File(...)):
    db = get_db()
    user = get_user(request)
    if not _role_can_manage(user):
        raise HTTPException(403, "Forbidden")

    guardian = await db.guardians.find_one(
        scoped_filter({"id": guardian_id, "student_id": student_id}, get_school_id()), {"_id": 0}
    )
    if not guardian:
        raise HTTPException(404, "Guardian not found")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in PHOTO_EXTENSIONS:
        raise HTTPException(400, "Photo must be jpg, jpeg, png, webp, or heic")
    content = await file.read()
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(400, "Photo exceeds 5MB limit")

    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    content_type = infer_content_type(file.filename, file.content_type)
    stored = upload_bytes(
        content=content,
        key=build_upload_key(file_id, file.filename),
        content_type=content_type,
        original_filename=file.filename,
    )
    photo_url = f"/api/uploads/serve/{safe_filename}"
    record = {
        "_id": file_id,
        "id": file_id,
        "schoolId": get_school_id(),
        "uploaded_by": user["id"],
        "file_url": photo_url,
        "file_name": file.filename,
        "safe_filename": safe_filename,
        "file_type": content_type,
        "file_size_bytes": len(content),
        "linked_table": "guardians",
        "linked_id": guardian_id,
        "created_at": datetime.now().isoformat(),
        "storage": "s3",
        "s3_bucket": stored.bucket,
        "s3_key": stored.key,
    }
    await db.file_uploads.insert_one(record)
    await db.guardians.update_one(
        scoped_filter({"id": guardian_id}, get_school_id()),
        {"$set": {"photo_url": photo_url}},
    )
    return {"success": True, "data": {"photo_url": photo_url}}


@router.post("/{student_id}/erase")
async def erase_student(student_id: str, request: Request, reason: str = Form(default=None), user: dict = Depends(require_owner)):
    db = get_db()
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
