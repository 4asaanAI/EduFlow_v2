from __future__ import annotations

from datetime import datetime, date
from database import get_db
from tenant import get_school_id, scoped_filter


def _tenant_query(query: dict | None = None) -> dict:
    return scoped_filter(query or {}, get_school_id())


def _tenant_match(query: dict | None = None) -> dict:
    return {"$match": _tenant_query(query)}


async def _get_house_standings(db) -> list:
    """Return the 4 houses sorted by points (descending)."""
    pipeline = [
        _tenant_match({}),
        {"$group": {"_id": "$house", "points": {"$sum": "$points"}}},
        {"$sort": {"points": -1}},
        {"$limit": 4},
    ]
    results = await db.house_points.aggregate(pipeline).to_list(4)
    return [{"house": r["_id"], "points": r["points"]} for r in results if r["_id"]]


async def _get_attendance_rate(db, today: str) -> str:
    """Return today's school-wide attendance rate as a formatted string."""
    total_marked = await db.student_attendance.count_documents(_tenant_query({"date": today}))
    present = await db.student_attendance.count_documents(_tenant_query({"date": today, "status": "present"}))
    if total_marked > 0:
        rate = round(present / total_marked * 100, 1)
        return f"{rate}% ({present}/{total_marked} present)"
    return "Not yet marked today"


def _format_currency(amount: int | float) -> str:
    """Format an amount as INR, using lakhs for large values."""
    if amount >= 100000:
        return f"\u20b9{amount / 100000:.1f}L"
    return f"\u20b9{amount:,.0f}"


async def _get_fee_outstanding(db) -> str:
    """Return total outstanding (pending + overdue) fees as formatted string."""
    pipeline = [
        _tenant_match({"status": {"$in": ["pending", "overdue"]}}),
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    result = await db.fee_transactions.aggregate(pipeline).to_list(1)
    outstanding = result[0]["total"] if result else 0
    return _format_currency(outstanding)


async def _get_todays_collections(db, today: str) -> str:
    """Return total fee collections made today as formatted string."""
    pipeline = [
        _tenant_match({"status": "paid", "paid_date": today}),
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    result = await db.fee_transactions.aggregate(pipeline).to_list(1)
    collected = result[0]["total"] if result else 0
    return _format_currency(collected)


async def _get_active_alerts(db, today: str) -> int:
    """Count active alerts (absent staff, overdue fees)."""
    alerts = 0
    absent_staff = await db.staff_attendance.count_documents(_tenant_query({"date": today, "status": "absent"}))
    if absent_staff > 0:
        alerts += 1
    overdue_fees = await db.fee_transactions.count_documents(_tenant_query({"status": "overdue"}))
    if overdue_fees > 0:
        alerts += 1
    return alerts


async def _get_library_stats(db) -> dict:
    """Return library statistics: total books, books issued, overdue returns."""
    total_books = await db.library_books.count_documents(_tenant_query())
    books_issued = await db.library_transactions.count_documents(_tenant_query({"status": "issued"}))
    overdue_returns = await db.library_transactions.count_documents(_tenant_query({"status": "overdue"}))
    return {
        "total_books": total_books,
        "books_issued": books_issued,
        "overdue_returns": overdue_returns,
    }


async def _get_transport_stats(db, today: str) -> dict:
    """Return transport statistics."""
    total_vehicles = await db.vehicles.count_documents(_tenant_query({"is_active": True}))
    active_routes = await db.transport_routes.count_documents(_tenant_query({"is_active": True}))
    students_using_transport = await db.students.count_documents(_tenant_query({"transport_opted": True, "is_active": True}))
    driver_present = await db.staff_attendance.count_documents(_tenant_query({
        "date": today,
        "status": "present",
        "role": "driver",
    }))
    driver_total = await db.staff.count_documents(_tenant_query({"role": "driver", "is_active": True}))
    return {
        "total_vehicles": total_vehicles,
        "active_routes": active_routes,
        "students_using_transport": students_using_transport,
        "driver_attendance_today": f"{driver_present}/{driver_total} present",
    }


async def _get_inventory_alerts(db) -> int:
    """Return count of inventory items below reorder level."""
    return await db.inventory.count_documents(_tenant_query({
        "$expr": {"$lte": ["$quantity", "$reorder_level"]}
    }))


# ---------------------------------------------------------------------------
# Owner context: everything
# ---------------------------------------------------------------------------
async def _build_owner_context(db, today: str) -> dict:
    ctx = {}

    ctx["total_students"] = await db.students.count_documents(_tenant_query({"is_active": True}))
    ctx["total_staff"] = await db.staff.count_documents(_tenant_query({"is_active": True}))
    ctx["attendance_rate"] = await _get_attendance_rate(db, today)
    ctx["fee_outstanding"] = await _get_fee_outstanding(db)
    ctx["todays_collections"] = await _get_todays_collections(db, today)
    ctx["fee_defaulters"] = await db.fee_transactions.count_documents(_tenant_query({"status": "overdue"}))
    ctx["pending_invoices"] = await db.fee_transactions.count_documents(_tenant_query({"status": "pending"}))
    ctx["pending_leaves"] = await db.leave_requests.count_documents(_tenant_query({"status": "pending"}))
    ctx["active_alerts"] = await _get_active_alerts(db, today)

    # House standings
    ctx["house_standings"] = await _get_house_standings(db)

    # Library
    ctx["library"] = await _get_library_stats(db)

    # Transport
    ctx["transport"] = await _get_transport_stats(db, today)

    # Inventory alerts
    ctx["inventory_low_stock_count"] = await _get_inventory_alerts(db)

    return ctx


# ---------------------------------------------------------------------------
# Principal: same as owner minus financials
# ---------------------------------------------------------------------------
async def _build_principal_context(db, today: str) -> dict:
    ctx = {}

    ctx["total_students"] = await db.students.count_documents(_tenant_query({"is_active": True}))
    ctx["total_staff"] = await db.staff.count_documents(_tenant_query({"is_active": True}))
    ctx["attendance_rate"] = await _get_attendance_rate(db, today)
    ctx["pending_leaves"] = await db.leave_requests.count_documents(_tenant_query({"status": "pending"}))
    ctx["active_alerts"] = await _get_active_alerts(db, today)

    # House standings
    ctx["house_standings"] = await _get_house_standings(db)

    # Library
    ctx["library"] = await _get_library_stats(db)

    # Transport
    ctx["transport"] = await _get_transport_stats(db, today)

    # Inventory alerts
    ctx["inventory_low_stock_count"] = await _get_inventory_alerts(db)

    return ctx


# ---------------------------------------------------------------------------
# Accounts admin: financial context only
# ---------------------------------------------------------------------------
async def _build_accounts_context(db, today: str) -> dict:
    ctx = {}
    ctx["fee_outstanding"] = await _get_fee_outstanding(db)
    ctx["todays_collections"] = await _get_todays_collections(db, today)
    ctx["fee_defaulters"] = await db.fee_transactions.count_documents(_tenant_query({"status": "overdue"}))
    ctx["pending_invoices"] = await db.fee_transactions.count_documents(_tenant_query({"status": "pending"}))
    return ctx


# ---------------------------------------------------------------------------
# Transport head: transport context only
# ---------------------------------------------------------------------------
async def _build_transport_head_context(db, today: str) -> dict:
    return await _get_transport_stats(db, today)


# ---------------------------------------------------------------------------
# Receptionist: enquiries and visitors
# ---------------------------------------------------------------------------
async def _build_receptionist_context(db, today: str) -> dict:
    ctx = {}
    ctx["new_enquiries_today"] = await db.enquiries.count_documents(_tenant_query({"created_at": {"$gte": today}}))
    ctx["pending_enquiries"] = await db.enquiries.count_documents(_tenant_query({"status": "pending"}))
    ctx["todays_visitor_count"] = await db.visitor_log.count_documents(_tenant_query({"time_in": {"$gte": today}}))
    return ctx


# ---------------------------------------------------------------------------
# Class teacher: own class info
# ---------------------------------------------------------------------------
async def _build_class_teacher_context(db, today: str, user_id: str) -> dict:
    ctx = {}

    assigned_class = await db.classes.find_one(_tenant_query({"class_teacher_id": user_id}))
    if not assigned_class:
        ctx["note"] = "No class assigned"
        return ctx

    class_id = assigned_class["id"]
    ctx["assigned_class"] = assigned_class.get("name", class_id)

    # Student count in class
    student_count = await db.students.count_documents(_tenant_query({"class_id": class_id, "is_active": True}))
    ctx["student_count"] = student_count

    # Today's attendance for class
    student_ids = [
        s["id"]
        async for s in db.students.find(_tenant_query({"class_id": class_id, "is_active": True}), {"id": 1})
    ]
    if student_ids:
        marked = await db.student_attendance.count_documents(_tenant_query({
            "student_id": {"$in": student_ids},
            "date": today,
        }))
        present = await db.student_attendance.count_documents(_tenant_query({
            "student_id": {"$in": student_ids},
            "date": today,
            "status": "present",
        }))
        if marked > 0:
            rate = round(present / marked * 100, 1)
            ctx["class_attendance_today"] = f"{rate}% ({present}/{marked})"
        else:
            ctx["class_attendance_today"] = "Not yet marked"
    else:
        ctx["class_attendance_today"] = "No students in class"

    # Pending assignments for this class
    ctx["pending_assignments"] = await db.assignments.count_documents(_tenant_query({
        "class_id": class_id,
        "status": "pending",
    }))

    # Own leave balance
    staff = await db.staff.find_one(_tenant_query({"user_id": user_id}))
    if staff:
        ctx["own_leave_balance"] = staff.get("leave_balance", 0)

    return ctx


# ---------------------------------------------------------------------------
# HOD: subject-level view
# ---------------------------------------------------------------------------
async def _build_hod_context(db, today: str, user_id: str) -> dict:
    ctx = {}

    staff = await db.staff.find_one(_tenant_query({"user_id": user_id}))
    subject = staff.get("subject", "Unknown") if staff else "Unknown"
    ctx["subject"] = subject

    # Classes teaching this subject
    classes = await db.classes.find(_tenant_query({"subjects": subject})).to_list(100)
    ctx["classes_teaching_subject"] = len(classes)
    class_names = [c.get("name", c.get("id", "")) for c in classes]
    ctx["class_names"] = class_names

    # Cross-class attendance for subject today
    class_ids = [c["id"] for c in classes if "id" in c]
    if class_ids:
        student_ids = [
            s["id"]
            async for s in db.students.find(_tenant_query({"class_id": {"$in": class_ids}, "is_active": True}), {"id": 1})
        ]
        if student_ids:
            marked = await db.student_attendance.count_documents(_tenant_query({
                "student_id": {"$in": student_ids},
                "date": today,
            }))
            present = await db.student_attendance.count_documents(_tenant_query({
                "student_id": {"$in": student_ids},
                "date": today,
                "status": "present",
            }))
            if marked > 0:
                rate = round(present / marked * 100, 1)
                ctx["cross_class_attendance"] = f"{rate}% ({present}/{marked})"
            else:
                ctx["cross_class_attendance"] = "Not yet marked"
        else:
            ctx["cross_class_attendance"] = "No students found"
    else:
        ctx["cross_class_attendance"] = "No classes found"

    return ctx


# ---------------------------------------------------------------------------
# Coordinator: class-range view
# ---------------------------------------------------------------------------
async def _build_coordinator_context(db, today: str, user_id: str) -> dict:
    ctx = {}

    staff = await db.staff.find_one(_tenant_query({"user_id": user_id}))
    coordinator_range = staff.get("coordinator_range", "") if staff else ""
    ctx["class_range"] = coordinator_range

    # Get classes in the coordinator's range (e.g., "1-5" → match class names containing 1,2,3,4,5)
    classes = []
    if coordinator_range and "-" in coordinator_range:
        try:
            start, end = coordinator_range.split("-")
            class_numbers = list(range(int(start), int(end) + 1))
            class_name_patterns = [str(n) for n in class_numbers]
            classes = await db.classes.find(_tenant_query({"name": {"$regex": "|".join(class_name_patterns), "$options": "i"}})).to_list(100)
        except (ValueError, TypeError):
            classes = []
    elif coordinator_range:
        classes = await db.classes.find(_tenant_query({"name": {"$regex": coordinator_range, "$options": "i"}})).to_list(100)
    else:
        classes = []

    ctx["classes_in_range"] = len(classes)

    # Attendance summary for range
    class_ids = [c["id"] for c in classes if "id" in c]
    if class_ids:
        student_ids = [
            s["id"]
            async for s in db.students.find(_tenant_query({"class_id": {"$in": class_ids}, "is_active": True}), {"id": 1})
        ]
        if student_ids:
            marked = await db.student_attendance.count_documents(_tenant_query({
                "student_id": {"$in": student_ids},
                "date": today,
            }))
            present = await db.student_attendance.count_documents(_tenant_query({
                "student_id": {"$in": student_ids},
                "date": today,
                "status": "present",
            }))
            if marked > 0:
                rate = round(present / marked * 100, 1)
                ctx["attendance_summary"] = f"{rate}% ({present}/{marked})"
            else:
                ctx["attendance_summary"] = "Not yet marked"
        else:
            ctx["attendance_summary"] = "No students found"
    else:
        ctx["attendance_summary"] = "No classes in range"

    return ctx


# ---------------------------------------------------------------------------
# Student: own context
# ---------------------------------------------------------------------------
async def _build_student_context(db, today: str, user_id: str) -> dict:
    ctx = {}

    student = await db.students.find_one(_tenant_query({"user_id": user_id}))
    if not student:
        ctx["note"] = "Student record not found"
        return ctx

    student_id = student["id"]
    ctx["student_id"] = student_id
    ctx["class_id"] = student.get("class_id")

    # Today's own attendance
    att = await db.student_attendance.find_one(_tenant_query({"student_id": student_id, "date": today}))
    ctx["my_attendance_today"] = att["status"] if att else "Not marked"

    # Overall attendance percentage
    total_days = await db.student_attendance.count_documents(_tenant_query({"student_id": student_id}))
    present_days = await db.student_attendance.count_documents(_tenant_query({"student_id": student_id, "status": "present"}))
    if total_days > 0:
        ctx["my_attendance_pct"] = f"{round(present_days / total_days * 100, 1)}%"
    else:
        ctx["my_attendance_pct"] = "No records"

    # Pending assignments
    class_id = student.get("class_id")
    if class_id:
        ctx["pending_assignments"] = await db.assignments.count_documents(_tenant_query({
            "class_id": class_id,
            "status": "pending",
        }))
    else:
        ctx["pending_assignments"] = 0

    # Fee status (paid/unpaid, no amounts)
    unpaid = await db.fee_transactions.count_documents(_tenant_query({
        "student_id": student_id,
        "status": {"$in": ["pending", "overdue"]},
    }))
    ctx["fee_status"] = "unpaid" if unpaid > 0 else "paid"

    # House points
    house = student.get("house")
    if house:
        pipeline = [
            _tenant_match({"house": house}),
            {"$group": {"_id": None, "points": {"$sum": "$points"}}},
        ]
        result = await db.house_points.aggregate(pipeline).to_list(1)
        ctx["house"] = house
        ctx["house_points"] = result[0]["points"] if result else 0
    else:
        ctx["house"] = None
        ctx["house_points"] = 0

    return ctx


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def build_school_context(role: str, user_id: str) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")

    # Determine sub_category for scoped context
    if role == "student":
        return await _build_student_context(db, today, user_id)

    # For all staff roles, look up sub_category
    staff = await db.staff.find_one(_tenant_query({"user_id": user_id}))
    sub_category = staff.get("sub_category", role) if staff else role

    # Owner: everything
    if role == "owner":
        return await _build_owner_context(db, today)

    # Admin sub-categories
    if role == "admin":
        if sub_category == "principal":
            return await _build_principal_context(db, today)
        if sub_category == "accounts":
            return await _build_accounts_context(db, today)
        if sub_category == "transport_head":
            return await _build_transport_head_context(db, today)
        if sub_category == "receptionist":
            return await _build_receptionist_context(db, today)
        # Default admin (e.g. sub_category == "admin") gets principal-level view
        return await _build_principal_context(db, today)

    # Teacher sub-categories
    if role == "teacher":
        if sub_category == "class_teacher":
            return await _build_class_teacher_context(db, today, user_id)
        if str(sub_category).lower() == "hod":
            return await _build_hod_context(db, today, user_id)
        if sub_category == "coordinator":
            return await _build_coordinator_context(db, today, user_id)
        # Default teacher gets class_teacher view
        return await _build_class_teacher_context(db, today, user_id)

    # Fallback: return minimal context
    return {"role": role, "note": "No scoped context available for this role"}


def detect_language(text: str) -> str:
    """Detect if text is Hindi (Devanagari) or English."""
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return "hi"
    return "en"
