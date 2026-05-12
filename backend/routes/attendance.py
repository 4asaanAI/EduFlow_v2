from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from database import get_db
from models.schemas import AttendanceBulkRequest, StudentAttendance, StaffAttendance
from middleware.auth import get_current_user
from datetime import date, datetime
from tenant import get_school_id, scoped_filter
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


async def _audit(db, *, action: str, attendance_id: str, user: dict, changes: dict, reason: str | None = None):
    await db.audit_logs.insert_one({
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
    })


@router.post("")
async def manual_student_attendance(request: Request):
    db = get_db()
    user = get_user(request)
    if not _can_admin_attendance(user):
        raise HTTPException(403, "Only Owner or Principal can manually enter attendance")
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
async def correct_attendance(attendance_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    correction_type = body.get("correction_type")
    reason = body.get("reason")
    if not correction_type or not reason:
        raise HTTPException(400, "correction_type and reason are required")

    original = await db.student_attendance.find_one(_attendance_query({"id": attendance_id}), {"_id": 0})
    if not original:
        raise HTTPException(404, "Attendance record not found")

    new_status = body.get("status") or correction_type
    correction = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "attendance_id": attendance_id,
        "original_record": original,
        "previous_status": original.get("status"),
        "new_status": new_status,
        "correction_type": correction_type,
        "reason": reason,
        "corrected_by": user["id"],
        "corrected_at": datetime.now().isoformat(),
    }
    await db.attendance_corrections.insert_one(correction)
    await db.student_attendance.update_one(
        _attendance_query({"id": attendance_id}),
        {"$set": {"status": new_status, "corrected": True, "updated_at": correction["corrected_at"]}},
    )
    await _audit(
        db,
        action="correct",
        attendance_id=attendance_id,
        user=user,
        changes={"status": {"previous": original.get("status"), "new": new_status}},
        reason=reason,
    )
    return {"success": True, "data": {k: v for k, v in correction.items() if k != "_id"}}


@router.get("/{attendance_id}/history")
async def get_attendance_history(attendance_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher"]:
        raise HTTPException(403, "Forbidden")
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
async def mark_student_attendance(body: AttendanceBulkRequest, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher"]:
        raise HTTPException(403, "Forbidden")

    results = []
    for record in body.records:
        att = StudentAttendance(
            student_id=record.student_id,
            class_id=body.class_id,
            date=body.date,
            status=record.status,
            marked_by=user["id"],
        )
        try:
            await db.student_attendance.update_one(
                _attendance_query({"student_id": record.student_id, "date": body.date}),
                {"$set": {**_serialize(att), "_id": att.id, "schoolId": get_school_id(), "source": "bulk"}},
                upsert=True,
            )
            results.append({"student_id": record.student_id, "status": "saved"})
        except Exception as e:
            results.append({"student_id": record.student_id, "status": "error", "error": str(e)})

    return {"success": True, "data": results}


@router.get("/student")
async def get_student_attendance(request: Request, class_id: str = None, student_id: str = None, start_date: str = None, end_date: str = None):
    db = get_db()
    user = get_user(request)

    query = {}
    if class_id:
        query["class_id"] = class_id
    if student_id:
        # Students can only see own attendance
        if user["role"] == "student":
            own_student = await db.students.find_one({"user_id": user["id"]})
            if not own_student or own_student["id"] != student_id:
                raise HTTPException(403, "Forbidden")
        query["student_id"] = student_id
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing_date = query.get("date", {})
        existing_date["$lte"] = end_date
        query["date"] = existing_date

    records = await db.student_attendance.find(query, {"_id": 0}).sort("date", -1).to_list(200)
    return {"success": True, "data": records}


@router.get("/student/today/{class_id}")
async def get_today_attendance(class_id: str, request: Request, date: str = None):
    db = get_db()
    user = get_user(request)
    from datetime import date as dt
    target_date = date if date else dt.today().strftime("%Y-%m-%d")

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
async def mark_staff_attendance(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    body = await request.json()
    today = body.get("date", date.today().strftime("%Y-%m-%d"))
    records = body.get("records", [])

    for rec in records:
        att = StaffAttendance(
            staff_id=rec["staff_id"],
            date=today,
            status=rec["status"],
            check_in=rec.get("check_in"),
            check_out=rec.get("check_out"),
        )
        await db.staff_attendance.update_one(
            {"staff_id": rec["staff_id"], "date": today},
            {"$set": {**att.dict(), "_id": att.id}},
            upsert=True,
        )

    return {"success": True}


@router.get("/low-attendance")
async def get_low_attendance_students(request: Request, threshold: float = 75.0, days: int = 30):
    """Return students whose attendance rate over the last `days` days is below `threshold` percent."""
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

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
            # Resolve parent phone: try guardian first, then student record
            guardian = await db.guardians.find_one({"student_id": a["_id"]}, {"_id": 0})
            phone = (guardian or {}).get("phone") or student.get("guardian_phone") or student.get("phone") or ""
            class_obj = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0})
            results.append({
                "student_id": a["_id"],
                "student_name": student.get("name", ""),
                "class": class_obj.get("name", "") + (" " + class_obj.get("section", "") if class_obj else "") if class_obj else student.get("class_id", ""),
                "attendance_rate": rate,
                "present_days": a["present"],
                "total_days": a["total"],
                "phone": phone,
                "guardian_name": (guardian or {}).get("name") or student.get("guardian_name", ""),
            })

    results.sort(key=lambda x: x["attendance_rate"])
    return {"success": True, "data": results, "meta": {"threshold": threshold, "days": days, "count": len(results)}}


@router.get("/staff")
async def get_staff_attendance(request: Request, start_date: str = None, end_date: str = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    query = {}
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing = query.get("date", {})
        existing["$lte"] = end_date
        query["date"] = existing

    records = await db.staff_attendance.find(query, {"_id": 0}).sort("date", -1).to_list(200)
    return {"success": True, "data": records}
