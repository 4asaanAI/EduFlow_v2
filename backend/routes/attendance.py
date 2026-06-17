from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from database import get_db
from models.schemas import AttendanceBulkRequest, StudentAttendance, StaffAttendance
from middleware.auth import get_current_user, require_role, require_owner_or_principal
from datetime import date, datetime
from tenant import get_school_id, scoped_filter, scoped_query
from services.audit_service import write_audit_doc
from services.actor_context import actor_ctx_from_user
from services.attendance_service import mark_attendance
from services.attendance_correction_service import (
    correct_attendance as correct_attendance_service,
    AttendanceCorrectionValidationError,
    AttendanceCorrectionNotFoundError,
)
from services.staff_attendance_service import (
    mark_staff_attendance as staff_attendance_service,
    StaffAttendanceValidationError,
)
from services.sse import KEEPALIVE_SECONDS, connect as sse_connect, disconnect as sse_disconnect, encode_sse, normalize_session_id, publish
from services.teacher_scope_service import compute_teacher_scope
import asyncio
import csv
import io
import os
import uuid

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def get_user(req: Request):
    return get_current_user(req)


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _attendance_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


def _can_admin_attendance(user: dict) -> bool:
    return user.get("role") == "owner" or (user.get("role") == "admin" and user.get("sub_category", "principal") == "principal")


async def _teacher_can_access_class(db, user: dict, class_id: str | None) -> bool:
    """Attendance is class-teacher-only: a teacher may view/mark attendance solely
    for the class(es) the Academic Structure names them class teacher of. Teaching
    a subject in a class does NOT grant attendance access."""
    if user.get("role") != "teacher" or not class_id:
        return True
    scope = await compute_teacher_scope(db, user, get_school_id())
    return class_id in set(scope["class_teacher_class_ids"])


async def _require_teacher_class_access(db, user: dict, class_id: str | None):
    if not await _teacher_can_access_class(db, user, class_id):
        raise HTTPException(403, "Teacher can access only assigned classes")


async def _audit(db, *, action: str, attendance_id: str, user: dict, changes: dict, reason: str | None = None):
    await write_audit_doc(db, {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "entity_type": "student_attendance",
        "entity_id": attendance_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_role": user.get("role"),
        "changes": changes,
        "reason": reason,
        "created_at": datetime.now().isoformat(),
    }, school_id=get_school_id(), branch_id=user.get("branch_id"))


@router.post("")
async def manual_student_attendance(request: Request):
    db = get_db()
    user = get_user(request)
    # auth: owner OR admin (sub_category=principal or absent). Slightly broader
    # than require_owner_or_principal which rejects admins without sub_category.
    if not _can_admin_attendance(user):
        raise HTTPException(403, "Forbidden")
    if os.environ.get("BIOMETRIC_ATTENDANCE_ENABLED", "false").lower() == "true":
        raise HTTPException(409, "Manual attendance is disabled while biometric attendance is enabled")

    body = await request.json()
    required = {"student_id", "class_id", "date", "status", "reason"}
    if any(not body.get(field) for field in required):
        raise HTTPException(400, "student_id, class_id, date, status, and reason are required")

    att = StudentAttendance(
        student_id=body["student_id"],
        class_id=body["class_id"],
        date=body["date"],
        status=body["status"],
        marked_by=user["id"],
    )
    doc = {**_serialize(att), "_id": att.id, "source": "manual", "manual_reason": body["reason"], "schoolId": get_school_id()}
    await db.student_attendance.insert_one(doc)
    await _audit(db, action="manual_entry", attendance_id=att.id, user=user, changes={"created": doc}, reason=body["reason"])
    return {"success": True, "data": {k: v for k, v in doc.items() if k != "_id"}}


@router.patch("/{attendance_id}/correct")
async def correct_attendance(attendance_id: str, request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    params = {
        "attendance_id": attendance_id,
        "correction_type": body.get("correction_type"),
        "reason": body.get("reason"),
        "status": body.get("status"),
    }
    try:
        result = await correct_attendance_service(db, actor_ctx, params)
    except AttendanceCorrectionValidationError as e:
        raise HTTPException(400, str(e))
    except AttendanceCorrectionNotFoundError as e:
        raise HTTPException(404, str(e))
    return {"success": True, "data": result["correction"]}


@router.get("/{attendance_id}/history")
async def get_attendance_history(attendance_id: str, request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    original = await db.student_attendance.find_one(_attendance_query({"id": attendance_id}), {"_id": 0})
    if not original:
        raise HTTPException(404, "Attendance record not found")
    corrections = await db.attendance_corrections.find(
        scoped_filter({"attendance_id": attendance_id}, get_school_id()),
        {"_id": 0},
    ).sort("corrected_at", 1).to_list(50)
    audits = await db.audit_logs.find(
        scoped_filter({"entity_type": "student_attendance", "entity_id": attendance_id}, get_school_id()),
        {"_id": 0},
    ).sort("created_at", 1).to_list(50)
    return {"success": True, "data": {"original": original, "corrections": corrections, "audit": audits}}


@router.delete("/{attendance_id}")
async def delete_attendance(attendance_id: str, request: Request):
    raise HTTPException(405, "Attendance records cannot be hard deleted")


@router.post("/student/bulk")
async def mark_student_attendance(body: AttendanceBulkRequest, request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    await _require_teacher_class_access(db, user, body.class_id)
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    params = {
        "class_id": body.class_id,
        "date": body.date,
        "records": [{"student_id": r.student_id, "status": r.status} for r in body.records],
    }
    result = await mark_attendance(db, actor_ctx, params, idempotency_key=request.headers.get("Idempotency-Key"))
    if result.get("idempotent"):
        return {"success": True, "data": result["results"], "idempotent": True}
    return {"success": True, "data": result["results"]}


@router.get("/student")
async def get_student_attendance(request: Request, class_id: str = None, student_id: str = None, start_date: str = None, end_date: str = None):
    db = get_db()
    user = get_user(request)

    query = {}
    if class_id:
        await _require_teacher_class_access(db, user, class_id)
        query["class_id"] = class_id
    if student_id:
        # Students can only see own attendance
        if user["role"] == "student":
            own_student = await db.students.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
            if not own_student or own_student["id"] != student_id:
                raise HTTPException(403, "Forbidden")
        elif user["role"] == "teacher":
            student = await db.students.find_one(scoped_filter({"id": student_id}, get_school_id()), {"_id": 0})
            await _require_teacher_class_access(db, user, (student or {}).get("class_id"))
        query["student_id"] = student_id
    elif user["role"] == "student":
        own_student = await db.students.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
        if not own_student:
            return {"success": True, "data": []}
        query["student_id"] = own_student["id"]
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing_date = query.get("date", {})
        existing_date["$lte"] = end_date
        query["date"] = existing_date

    records = await db.student_attendance.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("date", -1).to_list(200)
    return {"success": True, "data": records}


@router.get("/student/today/{class_id}")
async def get_today_attendance(class_id: str, request: Request, date: str = None):
    db = get_db()
    user = get_user(request)
    from datetime import date as dt
    target_date = date if date else dt.today().strftime("%Y-%m-%d")

    await _require_teacher_class_access(db, user, class_id)
    students = await db.students.find(scoped_filter({"class_id": class_id, "is_active": True}, get_school_id()), {"_id": 0}).to_list(100)
    attendance = await db.student_attendance.find(scoped_filter({"class_id": class_id, "date": target_date}, get_school_id()), {"_id": 0}).to_list(100)
    att_by_student = {a["student_id"]: a for a in attendance}

    result = []
    for s in students:
        att = att_by_student.get(s["id"])
        result.append({
            "student_id": s["id"],
            "attendance_id": att.get("id") if att else None,
            "name": s["name"],
            "roll_number": s.get("roll_number", ""),
            "status": att["status"] if att else "not_marked",
            "corrected": bool(att.get("corrected")) if att else False,
        })

    return {"success": True, "data": result, "date": target_date, "class_id": class_id}


@router.post("/staff/bulk")
async def mark_staff_attendance(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    # AD7 shared write path — same service as the AI `mark_staff_attendance` tool.
    db = get_db()
    body = await request.json()
    actor_ctx = actor_ctx_from_user(user)
    try:
        await staff_attendance_service(db, actor_ctx, body, publish_fn=publish)
    except StaffAttendanceValidationError as e:
        raise HTTPException(400, str(e))
    return {"success": True}


@router.get("/stream")
async def attendance_stream(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    session_id = normalize_session_id(
        request.headers.get("X-SSE-Session-ID") or request.query_params.get("session_id")
    )
    keepalive = int(request.query_params.get("keepalive", KEEPALIVE_SECONDS))
    once = request.query_params.get("once", "").lower() == "true"
    queue = await sse_connect("attendance", session_id)

    async def event_generator():
        try:
            latest = await db.staff_attendance.find(_attendance_query(), {"_id": 0}).sort("date", -1).to_list(200)
            yield encode_sse({
                "type": "snapshot",
                "channel": "attendance",
                "data": latest,
                "last_updated": datetime.now().isoformat(),
            })
            if once:
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=keepalive)
                except asyncio.TimeoutError:
                    yield encode_sse({"type": "keepalive", "channel": "attendance"})
                    continue
                if isinstance(event, str):
                    yield event
                    continue
                if event.get("type") == "close":
                    yield encode_sse(event)
                    break
                yield encode_sse(event)
        finally:
            await sse_disconnect("attendance", session_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/low-attendance")
async def get_low_attendance_students(request: Request, threshold: float = 75.0, days: int = 30, user: dict = Depends(require_role("owner", "admin"))):
    """Return students whose attendance rate over the last `days` days is below `threshold` percent."""
    db = get_db()
    from datetime import timedelta
    end = date.today()
    start = (end - timedelta(days=days)).strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # Aggregate attendance per student for the period
    pipeline = [
        {"$match": {"date": {"$gte": start, "$lte": end_str}}},
        {"$group": {
            "_id": "$student_id",
            "total": {"$sum": 1},
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
        }},
    ]
    agg = await db.student_attendance.aggregate(pipeline).to_list(2000)

    results = []
    for a in agg:
        if a["total"] == 0:
            continue
        rate = round(a["present"] / a["total"] * 100, 1)
        if rate < threshold:
            student = await db.students.find_one({"id": a["_id"], "is_active": True}, {"_id": 0})
            if not student:
                continue
            # Resolve parent phone: prefer primary guardian, fall back to any guardian, then student fields
            primary_guardian = await db.guardians.find_one({"student_id": a["_id"], "is_primary": True}, {"_id": 0})
            guardian = primary_guardian or await db.guardians.find_one({"student_id": a["_id"]}, {"_id": 0})
            phone = (guardian or {}).get("phone") or (guardian or {}).get("whatsapp_phone") or student.get("guardian_phone") or student.get("phone") or ""
            class_obj = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0})
            results.append({
                "student_id": a["_id"],
                "student_name": student.get("name", ""),
                "class": (class_obj.get("name", "") + (" " + class_obj.get("section", "") if class_obj.get("section") else "")) if class_obj else student.get("class_id", ""),
                "attendance_rate": rate,
                "present_days": a["present"],
                "total_days": a["total"],
                "phone": phone,
                "guardian_name": (guardian or {}).get("name") or student.get("guardian_name", ""),
            })

    results.sort(key=lambda x: x["attendance_rate"])
    return {"success": True, "data": results, "meta": {"threshold": threshold, "days": days, "count": len(results)}}


@router.get("/export")
async def export_attendance_summary(request: Request, class_id: str, month: str, format: str = "csv", user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    if format != "csv":
        raise HTTPException(400, "Only csv export is supported")
    if not class_id or not month:
        raise HTTPException(400, "class_id and month=YYYY-MM are required")

    students = await db.students.find(
        scoped_filter({"class_id": class_id, "is_active": {"$ne": False}}, get_school_id()),
        {"_id": 0, "id": 1, "name": 1, "admission_number": 1, "roll_number": 1},
    ).sort("roll_number", 1).to_list(500)
    student_ids = [s["id"] for s in students]
    records = await db.student_attendance.find(
        scoped_filter({"class_id": class_id, "student_id": {"$in": student_ids}, "date": {"$regex": f"^{month}"}}, get_school_id()),
        {"_id": 0},
    ).to_list(5000)
    by_student = {}
    for rec in records:
        by_student.setdefault(rec.get("student_id"), []).append(rec)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_name", "admission_number", "roll_number", "present_days", "absent_days", "late_days", "percentage"])
    for student in students:
        rows = by_student.get(student["id"], [])
        present = sum(1 for r in rows if r.get("status") == "present")
        absent = sum(1 for r in rows if r.get("status") == "absent")
        late = sum(1 for r in rows if r.get("status") == "late")
        total = present + absent + late
        percentage = round((present + (late * 0.5)) / total * 100, 1) if total else 0
        writer.writerow([
            student.get("name", ""),
            student.get("admission_number", ""),
            student.get("roll_number", ""),
            present,
            absent,
            late,
            percentage,
        ])
    output.seek(0)
    filename = f"attendance_{class_id}_{month}.csv"
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/class-summary")
async def get_class_summary(
    request: Request,
    date: str = None,
    user: dict = Depends(require_owner_or_principal),
):
    """Class-level attendance summary for principal — uses aggregation pipeline (EC-9.2: ≤5 queries total)."""
    db = get_db()
    bid = user.get("branch_id")
    today = date or datetime.now().strftime("%Y-%m-%d")

    # EC-9.2: Single aggregation pipeline — NOT N×3 individual count queries
    pipeline = [
        {"$match": scoped_query({"date": today}, branch_id=bid)},
        {"$group": {
            "_id": "$class_id",
            "present": {"$sum": {"$cond": [{"$eq": ["$status", "present"]}, 1, 0]}},
            "absent":  {"$sum": {"$cond": [{"$eq": ["$status", "absent"]},  1, 0]}},
            "late":    {"$sum": {"$cond": [{"$eq": ["$status", "late"]},    1, 0]}},
            "total":   {"$sum": 1},
        }},
    ]
    results = await db.student_attendance.aggregate(pipeline).to_list(None)

    # Enrich with class names
    enriched = []
    for r in results:
        cls = await db.classes.find_one(scoped_query({"id": r["_id"]}, branch_id=bid))
        class_name = f"{cls.get('name','')} {cls.get('section','')}".strip() if cls else r["_id"]
        total = r["total"]
        enriched.append({
            "class_id": r["_id"],
            "class_name": class_name,
            "present": r["present"],
            "absent": r["absent"],
            "late": r.get("late", 0),
            "not_marked": 0,  # calculated separately if needed
            "total_marked": total,
            "attendance_pct": round(r["present"] / total * 100, 1) if total else 0,
        })

    enriched.sort(key=lambda x: x["class_name"])
    return {"success": True, "data": enriched, "meta": {"count": len(enriched), "date": today}}


@router.get("/staff/today")
async def get_staff_attendance_today(
    request: Request,
    date: str = None,
    user: dict = Depends(require_owner_or_principal),
):
    """Staff attendance for today — shows which teachers are present/absent."""
    db = get_db()
    bid = user.get("branch_id")
    today = date or datetime.now().strftime("%Y-%m-%d")

    attendance_records = await db.staff_attendance.find(
        scoped_query({"date": today}, branch_id=bid)
    ).to_list(200)

    # Enrich with staff names
    result = []
    for rec in attendance_records:
        staff = await db.staff.find_one(scoped_query({"id": rec.get("staff_id")}, branch_id=bid))
        result.append({
            "staff_id": rec.get("staff_id"),
            "staff_name": staff.get("name") if staff else rec.get("staff_id"),
            "role": staff.get("role") if staff else None,
            "sub_category": staff.get("sub_category") if staff else None,
            "status": rec.get("status"),
            "marked_at": rec.get("marked_at") or rec.get("created_at"),
        })

    return {"success": True, "data": result, "meta": {"count": len(result), "date": today}}


# NOTE: /staff/me must be declared before /staff/{date} to avoid path parameter shadowing
@router.get("/staff/me")
async def get_my_staff_attendance(request: Request, start_date: str = None, end_date: str = None, user: dict = Depends(require_role("teacher", "admin", "owner"))):
    db = get_db()
    staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()), {"_id": 0})
    if not staff:
        return {"success": True, "data": []}
    query = {"staff_id": staff["id"]}
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing = query.get("date", {})
        existing["$lte"] = end_date
        query["date"] = existing
    records = await db.staff_attendance.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("date", -1).to_list(120)
    return {"success": True, "data": records}


@router.get("/staff")
async def get_staff_attendance(request: Request, start_date: str = None, end_date: str = None, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    query = {}
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing = query.get("date", {})
        existing["$lte"] = end_date
        query["date"] = existing

    records = await db.staff_attendance.find(query, {"_id": 0}).sort("date", -1).to_list(200)
    return {"success": True, "data": records}
