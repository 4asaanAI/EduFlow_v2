from __future__ import annotations

from datetime import datetime
import hashlib
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from database import get_db
from middleware.auth import get_current_user, require_owner, require_role
from models.schemas import StudentCreate
from services.actor_context import actor_ctx_from_user
from services.audit_service import write_audit_doc
from services.student_service import (
    create_student as create_student_service,
    update_student as update_student_service,
    upsert_guardians as upsert_guardians_service,
    ClassNotFoundError,
    ClassValidationError,
    StudentConflictError,
    StudentNotFoundError,
    StudentValidationError,
)
from services.s3_storage import (
    build_upload_key,
    create_presigned_get_url,
    delete_object,
    infer_content_type,
    upload_bytes,
)
from services.teacher_scope_service import compute_teacher_scope
from tenant import get_school_id, scoped_filter
from utils.class_order import ordered_class_ids


router = APIRouter(prefix="/api/students", tags=["students"])

ADMIN_ROLES = {"owner", "admin"}
READ_ROLES = {"owner", "admin", "teacher"}

# The server-side sort whitelist (Epic 3, Story 3.3).
#
# This is the enforcement boundary, not a convenience: an unrecognised `sort`
# falls back to the default rather than reaching a query, so the parameter can
# never select a field the caller was not offered.
#
# Every key here must correspond to a column the shared DataTable presents as
# sortable, and vice versa — a heading that offers to sort and then does
# nothing is worse than one that does not offer.
SORT_FIELDS = {
    "created_at": ("created_at", -1),
    "name": ("name", 1),
    "admission_number": ("admission_number", 1),
    "dob": ("dob", 1),
    "gender": ("gender", 1),
    # "class" is handled separately — see _class_ordered_page(). It cannot be a
    # plain field sort because class_id is a random UUID.
    "class": ("class_id", 1),
}
# NOTE: the student updatable-field whitelist now lives ONLY in
# services/student_service.py (UPDATABLE_FIELDS) — the single shared write path.
# Do not reintroduce a route-local copy (it would silently drift from the service).

GUARDIAN_UPDATABLE_FIELDS = {
    "name", "phone", "alt_phone", "whatsapp_phone",
    "email", "occupation", "annual_income", "is_primary",
}
SELF_UPDATABLE_FIELDS = {
    "phone", "email", "preferred_name", "emergency_contact",
    "address", "dob", "gender",
    "blood_group", "height_cm", "weight_kg", "medical_notes",
}
GUARDIAN_SELF_UPDATABLE_FIELDS = {"name", "phone", "whatsapp_phone", "email", "occupation"}
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


GENDER_MALE_VALUES = ("male", "boy", "m")
GENDER_FEMALE_VALUES = ("female", "girl", "f")


def classify_gender(value) -> str:
    """Which strength bucket a stored `gender` belongs in.

    The single definition of the rule the Mongo aggregation below implements. It is
    a plain function so the rule can be tested exhaustively — the in-memory test
    double cannot evaluate `$cond`/`$toLower`/`$trim`, so a test asserting the
    aggregation's numbers through the fake would be measuring the fake, not this.

    "not_recorded" is deliberately NOT "other": all 1,802 students have an empty
    gender, so folding them together made the Other column equal the Total column on
    every row (reported by the owner, 2026-07-22).
    """
    text = str(value or "").strip().lower()
    if text == "":
        return "not_recorded"
    if text in GENDER_MALE_VALUES:
        return "boys"
    if text in GENDER_FEMALE_VALUES:
        return "girls"
    return "other"


@router.get("/strength")
async def class_strength_stats(request: Request):
    """Aggregated gender-count stats per class — used by the Class Strength tab."""
    db = get_db()
    user = get_user(request)
    if user["role"] not in READ_ROLES:
        raise HTTPException(403, "Forbidden")
    school_id = get_school_id()
    pipeline = [
        {"$match": scoped_filter({"is_active": True}, school_id)},
        {"$lookup": {"from": "classes", "localField": "class_id", "foreignField": "id", "as": "_cls"}},
        {"$unwind": {"path": "$_cls", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$class_id",
            "class_name": {"$first": "$_cls.name"},
            "class_section": {"$first": "$_cls.section"},
            "boys": {"$sum": {"$cond": [{"$in": [{"$toLower": {"$ifNull": ["$gender", ""]}}, ["male", "boy", "m"]]}, 1, 0]}},
            "girls": {"$sum": {"$cond": [{"$in": [{"$toLower": {"$ifNull": ["$gender", ""]}}, ["female", "girl", "f"]]}, 1, 0]}},
            # UI Sweep Epic 4 / Story 4.2. "Other" used to be everything that was not
            # male or female — which lumped a student recorded as another gender in
            # with a student whose gender was NEVER CAPTURED. Gender is empty for all
            # 1,802 students, so the screen showed "Boys 0, Girls 0, Other = everyone"
            # and the owner rightly asked why two columns held the same number.
            # They are separate facts and are now counted separately.
            "not_recorded": {"$sum": {"$cond": [
                {"$eq": [{"$trim": {"input": {"$ifNull": ["$gender", ""]}}}, ""]}, 1, 0
            ]}},
            "total": {"$sum": 1},
        }},
        {"$addFields": {"other": {"$subtract": [
            "$total", {"$add": ["$boys", "$girls", "$not_recorded"]}
        ]}}},
        {"$sort": {"class_name": 1, "class_section": 1}},
    ]
    results = await db.students.aggregate(pipeline).to_list(500)
    data = []
    for r in results:
        cls_label = "Unassigned"
        if r.get("class_name"):
            cls_label = f"{r['class_name']}-{r['class_section']}" if r.get("class_section") else r["class_name"]
        data.append({
            "class_id": r["_id"],
            "class_label": cls_label,
            "boys": r["boys"],
            "girls": r["girls"],
            "other": r.get("other", 0),
            "not_recorded": r.get("not_recorded", 0),
            "total": r["total"],
        })
    return {"success": True, "data": data}


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
    per_page = max(1, min(limit, 500))
    query = {} if include_inactive else {"is_active": True}
    if class_id:
        query["class_id"] = class_id
    if search:
        safe_search = re.escape(search)
        query["$or"] = [
            {"name": {"$regex": safe_search, "$options": "i"}},
            {"admission_number": {"$regex": safe_search, "$options": "i"}},
        ]

    # Part 14 + 15: Teacher should only see students in their assigned classes.
    # Assignments come from the Academic Structure (classes.class_teacher_id +
    # subjects.teacher_id) — the single source of truth that the admin edits.
    if user.get("role") == "teacher":
        scope = await compute_teacher_scope(db, user, get_school_id())
        teacher_class_ids = scope["all_class_ids"]
        if not teacher_class_ids:
            # No assignment → expose nothing rather than the whole school.
            return {"success": True, "data": [], "meta": {"page": page, "total": 0, "per_page": per_page, "sort": sort}}
        if class_id:
            # An explicit class filter must stay inside the teacher's scope.
            if class_id not in set(teacher_class_ids):
                return {"success": True, "data": [], "meta": {"page": page, "total": 0, "per_page": per_page, "sort": sort}}
            query["class_id"] = class_id
        else:
            query["class_id"] = {"$in": teacher_class_ids}

    scoped_query = _student_query(query)
    skip = (page - 1) * per_page
    total = await db.students.count_documents(scoped_query)

    if sort == "class":
        # Sorting on class_id would order by a random UUID. Rank the 48 class
        # records in the school's own order (NUR -> LKG -> UKG -> 1st ... 12th,
        # then sections A-E) and sort students by their class's position in
        # that list. Owner item 5, applied to the student listing rather than
        # only to dropdowns.
        all_classes = await db.classes.find(
            scoped_filter({}, get_school_id()),  # branch-scope: intentional — class order is school-wide
            {"_id": 0, "id": 1, "name": 1, "section": 1},
        ).to_list(500)
        ranked_ids = ordered_class_ids(all_classes)
        students = await db.students.aggregate([
            {"$match": scoped_query},
            # A class not in the list yields -1, which would sort first; push
            # those to the end so an unassigned student never leads the list.
            {"$addFields": {"_class_rank": {"$indexOfArray": [ranked_ids, "$class_id"]}}},
            {"$addFields": {"_class_rank": {"$cond": [{"$lt": ["$_class_rank", 0]}, len(ranked_ids), "$_class_rank"]}}},
            {"$sort": {"_class_rank": 1, "name": 1}},
            {"$skip": skip},
            {"$limit": per_page},
            {"$project": {"_id": 0, "coordinates": 0, "_class_rank": 0}},
        ]).to_list(per_page)
    else:
        sort_field, sort_dir = SORT_FIELDS.get(sort, SORT_FIELDS["created_at"])
        students = await db.students.find(scoped_query, {"_id": 0, "coordinates": 0}).sort(sort_field, sort_dir).skip(skip).limit(per_page).to_list(per_page)

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
    # Thin adapter over services.student_service.create_student — the SAME write
    # path as the AI `create_student` tool (Story J.1 / AD7).
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await create_student_service(db, actor_ctx, _serialize(body))
    except (ClassNotFoundError, StudentNotFoundError) as e:
        raise HTTPException(404, str(e))
    except StudentConflictError as e:
        raise HTTPException(409, str(e))
    except (ClassValidationError, StudentValidationError) as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["student"]}


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


@router.patch("/me/guardians/{guardian_id}")
async def update_my_guardian(guardian_id: str, request: Request, user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await db.students.find_one(_student_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student record not found")
    guardian = await db.guardians.find_one(
        scoped_filter({"id": guardian_id, "student_id": student["id"]}, get_school_id()), {"_id": 0}
    )
    if not guardian:
        raise HTTPException(404, "Guardian not found")
    body = await request.json()
    update = {k: v for k, v in body.items() if k in GUARDIAN_SELF_UPDATABLE_FIELDS}
    if not update:
        raise HTTPException(400, "No updatable guardian fields provided")
    update["updated_at"] = datetime.now().isoformat()
    await db.guardians.update_one(
        scoped_filter({"id": guardian_id}, get_school_id()), {"$set": update}
    )
    await _audit(
        db,
        action="student_guardian_self_update",
        student_id=student["id"],
        user=user,
        changes={k: {"previous": guardian.get(k), "new": v} for k, v in update.items() if k != "updated_at"},
    )
    updated = await db.guardians.find_one(
        scoped_filter({"id": guardian_id}, get_school_id()), {"_id": 0}
    )
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

    # Thin adapter over services.student_service.update_student — the SAME write
    # path as the AI `update_student` tool. Transport-head field restriction maps
    # to 403 (preserved); other validation errors map to 400 (Story J.1 / AD7).
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await update_student_service(db, actor_ctx, {**body, "student_id": student_id})
    except StudentNotFoundError as e:
        raise HTTPException(404, str(e))
    except ClassNotFoundError as e:
        raise HTTPException(404, str(e))
    except StudentConflictError as e:
        raise HTTPException(409, str(e))
    except StudentValidationError as e:
        msg = str(e)
        if msg == "Transport Head can only update transport assignment fields":
            raise HTTPException(403, msg)
        raise HTTPException(400, msg)
    except ClassValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "data": result["student"]}


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
    # Thin adapter over services.student_service.upsert_guardians — the SAME write
    # path as the AI `manage_student_guardians` tool (Story J.1 / AD7).
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await upsert_guardians_service(
            db, actor_ctx, {"student_id": student_id, "guardians": body}
        )
    except StudentNotFoundError as e:
        raise HTTPException(404, str(e))
    except StudentValidationError as e:
        msg = str(e)
        # Preserve the REST contract: bad body shape → 400 "Body must be a list..."
        if msg == "guardians must be a list of guardian objects":
            raise HTTPException(400, "Body must be a list of guardian objects")
        raise HTTPException(400, msg)
    return {"success": True, "data": result["guardians"]}


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
    # Epic G (G.7 / DPDP §12): purge any AI memory that references this student so
    # the right-to-erasure also covers what the assistant "learned" about them.
    try:
        from services.memory.store import purge_student_references

        await purge_student_references(
            db, school_id=get_school_id(), student_id=student_id, changed_by=user.get("id", "system")
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning("ai_memory purge on student erase failed", exc_info=True)
    return {"success": True, "data": {"erasure_token": token}}
