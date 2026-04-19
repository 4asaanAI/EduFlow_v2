from fastapi import APIRouter, Request, HTTPException
from database import get_db
from models.schemas import AttendanceBulkRequest, StudentAttendance, StaffAttendance
from middleware.auth import get_current_user
from datetime import date, datetime

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


def get_user(req: Request):
    return get_current_user(req)


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
                {"student_id": record.student_id, "date": body.date},
                {"$set": {**att.dict(), "_id": att.id}},
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

    students = await db.students.find({"class_id": class_id, "is_active": True}, {"_id": 0}).to_list(100)
    attendance = await db.student_attendance.find({"class_id": class_id, "date": target_date}, {"_id": 0}).to_list(100)
    att_by_student = {a["student_id"]: a for a in attendance}

    result = []
    for s in students:
        att = att_by_student.get(s["id"])
        result.append({
            "student_id": s["id"],
            "name": s["name"],
            "roll_number": s.get("roll_number", ""),
            "status": att["status"] if att else "not_marked",
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
