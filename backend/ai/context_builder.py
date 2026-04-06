from datetime import datetime, date
from database import get_db


async def build_school_context(role: str, user_id: str) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")

    ctx = {}

    if role in ["owner", "admin"]:
        ctx["total_students"] = await db.students.count_documents({"is_active": True})
        ctx["total_staff"] = await db.staff.count_documents({"is_active": True})

        # Today's attendance
        total_marked = await db.student_attendance.count_documents({"date": today})
        present = await db.student_attendance.count_documents({"date": today, "status": "present"})
        if total_marked > 0:
            rate = round(present / total_marked * 100, 1)
            ctx["attendance_rate"] = f"{rate}% ({present}/{total_marked} present)"
        else:
            ctx["attendance_rate"] = "Not yet marked today"

        # Fee outstanding
        pipeline = [
            {"$match": {"status": {"$in": ["pending", "overdue"]}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
        result = await db.fee_transactions.aggregate(pipeline).to_list(1)
        outstanding = result[0]["total"] if result else 0
        if outstanding >= 100000:
            ctx["fee_outstanding"] = f"₹{outstanding/100000:.1f}L"
        else:
            ctx["fee_outstanding"] = f"₹{outstanding:,.0f}"

        # Pending leaves
        ctx["pending_leaves"] = await db.leave_requests.count_documents({"status": "pending"})

        # Active alerts count
        alerts = 0
        absent_staff = await db.staff_attendance.count_documents({"date": today, "status": "absent"})
        if absent_staff > 0:
            alerts += 1
        overdue_fees = await db.fee_transactions.count_documents({"status": "overdue"})
        if overdue_fees > 0:
            alerts += 1
        ctx["active_alerts"] = alerts

    elif role == "teacher":
        # Teacher sees their class info
        staff = await db.staff.find_one({"user_id": user_id})
        if staff:
            classes = await db.classes.find({"class_teacher_id": user_id}).to_list(10)
            ctx["my_classes"] = len(classes)
            ctx["total_students"] = await db.students.count_documents(
                {"class_id": {"$in": [c["id"] for c in classes]}}
            ) if classes else 0

    elif role == "student":
        student = await db.students.find_one({"user_id": user_id})
        if student:
            # Today's own attendance
            att = await db.student_attendance.find_one(
                {"student_id": student["id"], "date": today}
            )
            ctx["my_attendance_today"] = att["status"] if att else "Not marked"
            ctx["student_id"] = student["id"]
            ctx["class_id"] = student.get("class_id")

    return ctx


def detect_language(text: str) -> str:
    """Detect if text is Hindi (Devanagari) or English."""
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return "hi"
    return "en"
