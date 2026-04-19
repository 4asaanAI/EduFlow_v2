"""
Tool functions v2 — extends the original 14 tools with 15 new scope-aware tools.
Imports all originals from tool_functions and exposes a combined TOOL_REGISTRY (29 tools).
"""
from datetime import datetime, date, timedelta
from database import get_db
import time, re
import logging

# ----- Re-export all 14 original tools and their registry -----
from ai.tool_functions import (
    tool_get_school_pulse,
    tool_get_fee_summary,
    tool_get_staff_status,
    tool_get_attendance_overview,
    tool_get_smart_alerts,
    tool_search_students,
    tool_get_fee_transactions,
    tool_approve_leave,
    tool_get_enquiries,
    tool_get_my_attendance,
    tool_get_my_fees,
    tool_get_my_results,
    tool_get_financial_report,
    tool_get_daily_brief,
    TOOL_REGISTRY as _ORIGINAL_REGISTRY,
)

logger = logging.getLogger(__name__)


# =========================================================================
#  Helpers
# =========================================================================

def _apply_branch_filter(query: dict, scope: dict) -> dict:
    """If scope carries a branch_id, inject it into the Mongo query."""
    if scope and scope.get("branch_id"):
        query["branch_id"] = scope["branch_id"]
    return query


def _apply_class_filter(query: dict, scope: dict, field: str = "class_id") -> dict:
    """Restrict query to the classes the user is allowed to see."""
    if scope and scope.get("class_ids") is not None:
        query[field] = {"$in": scope["class_ids"]}
    return query


def _empty_result(message: str, query_time_ms: float = 0) -> dict:
    return {
        "success": True,
        "data": [],
        "meta": {"count": 0, "query_time_ms": round(query_time_ms, 2)},
        "message": message,
    }


def _ok(data: list, query_time_ms: float, message: str = "") -> dict:
    return {
        "success": True,
        "data": data,
        "meta": {"count": len(data), "query_time_ms": round(query_time_ms, 2)},
        "message": message,
    }


# =========================================================================
#  1. tool_get_student_database
# =========================================================================

async def tool_get_student_database(params: dict, user: dict, scope: dict = None) -> dict:
    """All students with filters (class, status, gender, search).
    Owner/admin see all. Teacher sees own classes."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    # Scope-based class restriction for teachers
    if scope and scope.get("class_ids") is not None:
        _apply_class_filter(query, scope)

    # Optional filters from params
    if params.get("status"):
        query["status"] = params["status"]
    else:
        query["is_active"] = True

    if params.get("gender"):
        query["gender"] = {"$regex": re.escape(params["gender"]), "$options": "i"}

    if params.get("search"):
        safe_search = re.escape(params["search"])
        query["$or"] = [
            {"name": {"$regex": safe_search, "$options": "i"}},
            {"admission_number": {"$regex": safe_search, "$options": "i"}},
        ]

    # If a specific class filter is supplied by the user (and scope allows it)
    if params.get("class_name"):
        cls = await db.classes.find_one({"name": {"$regex": re.escape(params["class_name"]), "$options": "i"}})
        if cls:
            # Only apply if scope allows this class
            if scope and scope.get("class_ids") is not None:
                if cls["id"] in scope["class_ids"]:
                    query["class_id"] = cls["id"]
                else:
                    return _empty_result(
                        "You do not have access to this class.",
                        (time.time() - t0) * 1000,
                    )
            else:
                query["class_id"] = cls["id"]

    students = await db.students.find(query).to_list(500)

    results = []
    for s in students:
        cls = await db.classes.find_one({"id": s.get("class_id")})
        results.append({
            "name": s.get("name", ""),
            "class": f"{cls['name']}-{cls['section']}" if cls else "N/A",
            "section": cls.get("section", "") if cls else "",
            "roll": s.get("roll_number", "N/A"),
            "admission_number": s.get("admission_number", "N/A"),
            "status": s.get("status", "active"),
        })

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No students found matching the given filters.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  2. tool_get_fee_structures
# =========================================================================

async def tool_get_fee_structures(params: dict, user: dict, scope: dict = None) -> dict:
    """Fee structures by class group with component breakdown."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    if params.get("class_group"):
        query["class_group"] = {"$regex": re.escape(params["class_group"]), "$options": "i"}

    structures = await db.fee_structures.find(query).to_list(100)

    results = []
    for fs in structures:
        components = fs.get("components", [])
        total_annual = sum(c.get("amount", 0) for c in components)
        results.append({
            "class_group": fs.get("class_group", fs.get("name", "N/A")),
            "components": [
                {"name": c.get("name", ""), "amount": c.get("amount", 0), "frequency": c.get("frequency", "annual")}
                for c in components
            ],
            "total_annual": total_annual,
            "total_annual_fmt": f"\u20b9{total_annual:,.0f}",
        })

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No fee structures configured yet.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  3. tool_get_class_wise_attendance
# =========================================================================

async def tool_get_class_wise_attendance(params: dict, user: dict, scope: dict = None) -> dict:
    """Per-class attendance for a date range.  Teacher sees own class only."""
    t0 = time.time()
    db = get_db()

    start = params.get("start_date", date.today().strftime("%Y-%m-%d"))
    end = params.get("end_date", date.today().strftime("%Y-%m-%d"))

    class_query: dict = {}
    _apply_branch_filter(class_query, scope)
    if scope and scope.get("class_ids") is not None:
        class_query["id"] = {"$in": scope["class_ids"]}

    classes = await db.classes.find(class_query).to_list(50)

    results = []
    for cls in classes:
        att_query = {"class_id": cls["id"], "date": {"$gte": start, "$lte": end}}
        records = await db.student_attendance.find(att_query).to_list(5000)
        total = len(records)
        present = sum(1 for r in records if r.get("status") == "present")
        absent = total - present
        rate = round(present / total * 100, 1) if total > 0 else 0

        total_students = await db.students.count_documents({"class_id": cls["id"], "is_active": True})
        results.append({
            "class_name": f"{cls.get('name', '')}-{cls.get('section', '')}",
            "total_students": total_students,
            "present": present,
            "absent": absent,
            "rate": f"{rate}%",
        })

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No attendance data found for the selected period.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  4. tool_get_leave_requests
# =========================================================================

async def tool_get_leave_requests(params: dict, user: dict, scope: dict = None) -> dict:
    """Leave requests filtered by status."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    if params.get("status"):
        query["status"] = params["status"]

    leaves = await db.leave_requests.find(query).sort("created_at", -1).to_list(100)

    results = []
    for lr in leaves:
        staff = await db.staff.find_one({"id": lr.get("staff_id")})
        results.append({
            "staff_name": staff["name"] if staff else "Unknown",
            "staff_type": staff.get("staff_type", "") if staff else "",
            "leave_type": lr.get("leave_type", ""),
            "start_date": lr.get("start_date", ""),
            "end_date": lr.get("end_date", ""),
            "status": lr.get("status", ""),
            "reason": lr.get("reason", ""),
        })

    elapsed = (time.time() - t0) * 1000
    if not results:
        status_label = params.get("status", "any")
        return _empty_result(f"No leave requests found with status '{status_label}'.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  5. tool_get_staff_list
# =========================================================================

async def tool_get_staff_list(params: dict, user: dict, scope: dict = None) -> dict:
    """All active staff.  Returns name, staff_type, department, designation, subject, attendance_rate.
    Excludes salary information."""
    t0 = time.time()
    db = get_db()

    query: dict = {"is_active": True}
    _apply_branch_filter(query, scope)

    if params.get("staff_type"):
        query["staff_type"] = {"$regex": re.escape(params["staff_type"]), "$options": "i"}
    if params.get("department"):
        query["department"] = {"$regex": re.escape(params["department"]), "$options": "i"}

    staff_list = await db.staff.find(query).to_list(200)

    today = date.today()
    month_start = today.replace(day=1).strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    results = []
    for s in staff_list:
        # Compute attendance rate for current month
        att_records = await db.staff_attendance.find({
            "staff_id": s["id"],
            "date": {"$gte": month_start, "$lte": today_str},
        }).to_list(31)
        total_att = len(att_records)
        present = sum(1 for r in att_records if r.get("status") in ("present", "late"))
        att_rate = round(present / total_att * 100, 1) if total_att > 0 else 0

        results.append({
            "name": s.get("name", ""),
            "staff_type": s.get("staff_type", ""),
            "department": s.get("department", ""),
            "designation": s.get("designation", ""),
            "subject": s.get("subject", ""),
            "attendance_rate": f"{att_rate}%",
        })

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No active staff found.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  6. tool_get_class_list
# =========================================================================

async def tool_get_class_list(params: dict, user: dict, scope: dict = None) -> dict:
    """All classes with section, class teacher name, and student count."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    classes = await db.classes.find(query).to_list(50)

    results = []
    for cls in classes:
        # Resolve class teacher name
        teacher_name = "N/A"
        if cls.get("class_teacher_id"):
            teacher = await db.staff.find_one({"id": cls["class_teacher_id"]})
            if not teacher:
                teacher = await db.staff.find_one({"user_id": cls["class_teacher_id"]})
            if teacher:
                teacher_name = teacher.get("name", "N/A")

        student_count = await db.students.count_documents({"class_id": cls["id"], "is_active": True})
        results.append({
            "class_name": cls.get("name", ""),
            "section": cls.get("section", ""),
            "class_teacher_name": teacher_name,
            "student_count": student_count,
        })

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No classes found.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  7. tool_get_fee_defaulters
# =========================================================================

async def tool_get_fee_defaulters(params: dict, user: dict, scope: dict = None) -> dict:
    """Students with overdue fees, sorted by amount."""
    t0 = time.time()
    db = get_db()

    overdue_query: dict = {"status": "overdue"}
    _apply_branch_filter(overdue_query, scope)

    overdue_txns = await db.fee_transactions.find(overdue_query).to_list(500)

    # Group by student
    student_dues: dict = {}
    for txn in overdue_txns:
        sid = txn.get("student_id")
        if not sid:
            continue
        if sid not in student_dues:
            student_dues[sid] = {"amount": 0, "oldest_due": txn.get("due_date", "")}
        student_dues[sid]["amount"] += txn.get("amount", 0)
        due = txn.get("due_date", "")
        if due and (not student_dues[sid]["oldest_due"] or due < student_dues[sid]["oldest_due"]):
            student_dues[sid]["oldest_due"] = due

    results = []
    for sid, dues in student_dues.items():
        student = await db.students.find_one({"id": sid})
        if not student:
            continue
        # Scope filter: if teacher, only show students in their classes
        if scope and scope.get("class_ids") is not None:
            if student.get("class_id") not in scope["class_ids"]:
                continue

        cls = await db.classes.find_one({"id": student.get("class_id")})
        class_name = f"{cls['name']}-{cls['section']}" if cls else "N/A"

        days_overdue = 0
        if dues["oldest_due"]:
            try:
                due_dt = datetime.strptime(dues["oldest_due"], "%Y-%m-%d").date()
                days_overdue = (date.today() - due_dt).days
            except (ValueError, TypeError):
                days_overdue = 0

        results.append({
            "name": student.get("name", ""),
            "class": class_name,
            "amount_due": dues["amount"],
            "amount_due_fmt": f"\u20b9{dues['amount']:,.0f}",
            "days_overdue": days_overdue,
        })

    results.sort(key=lambda x: x["amount_due"], reverse=True)

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No fee defaulters found. All dues are up to date.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  8. tool_get_student_profile
# =========================================================================

async def tool_get_student_profile(params: dict, user: dict, scope: dict = None) -> dict:
    """Full profile for a single student: info + attendance + fees + guardian."""
    t0 = time.time()
    db = get_db()

    student = None
    if params.get("student_id"):
        student = await db.students.find_one({"id": params["student_id"]})
    elif params.get("search_term"):
        safe_term = re.escape(params["search_term"])
        student = await db.students.find_one({
            "$or": [
                {"name": {"$regex": safe_term, "$options": "i"}},
                {"admission_number": {"$regex": safe_term, "$options": "i"}},
            ]
        })

    if not student:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("Student not found. Please check the name or ID and try again.", elapsed)

    # Scope check: self_only means student can only view their own profile
    if scope and scope.get("student_id") and scope["student_id"] != student["id"]:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("You do not have permission to view this student's profile.", elapsed)

    # Scope check: teacher can only see students in their classes
    if scope and scope.get("class_ids") is not None:
        if student.get("class_id") not in scope["class_ids"]:
            elapsed = (time.time() - t0) * 1000
            return _empty_result("This student is not in your assigned classes.", elapsed)

    # Class info
    cls = await db.classes.find_one({"id": student.get("class_id")})
    class_label = f"{cls['name']}-{cls['section']}" if cls else "N/A"

    # Attendance summary (last 30 days)
    end_str = date.today().strftime("%Y-%m-%d")
    start_str = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    att_records = await db.student_attendance.find({
        "student_id": student["id"],
        "date": {"$gte": start_str, "$lte": end_str},
    }).to_list(60)
    att_total = len(att_records)
    att_present = sum(1 for r in att_records if r.get("status") == "present")
    att_rate = round(att_present / att_total * 100, 1) if att_total > 0 else 0

    attendance_summary = {
        "period": "Last 30 days",
        "total_days": att_total,
        "present": att_present,
        "absent": att_total - att_present,
        "rate": f"{att_rate}%",
    }

    # Fee status
    fee_status = {}
    if scope is None or scope.get("can_see_fees", False):
        fee_txns = await db.fee_transactions.find({"student_id": student["id"]}).to_list(100)
        total_paid = sum(t.get("amount", 0) for t in fee_txns if t.get("status") == "paid")
        total_pending = sum(t.get("amount", 0) for t in fee_txns if t.get("status") in ("pending", "overdue"))
        fee_status = {
            "total_paid": f"\u20b9{total_paid:,.0f}",
            "total_pending": f"\u20b9{total_pending:,.0f}",
            "transactions_count": len(fee_txns),
        }

    # Guardian info
    guardian_info = {}
    if student.get("guardian_name"):
        guardian_info = {
            "name": student.get("guardian_name", ""),
            "relation": student.get("guardian_relation", ""),
            "phone": student.get("guardian_phone", ""),
            "email": student.get("guardian_email", ""),
        }
    elif student.get("parent_id"):
        parent = await db.parents.find_one({"id": student["parent_id"]})
        if parent:
            guardian_info = {
                "name": parent.get("name", ""),
                "relation": parent.get("relation", ""),
                "phone": parent.get("phone", ""),
                "email": parent.get("email", ""),
            }

    profile = {
        "id": student["id"],
        "name": student.get("name", ""),
        "class": class_label,
        "section": cls.get("section", "") if cls else "",
        "roll_number": student.get("roll_number", "N/A"),
        "admission_number": student.get("admission_number", "N/A"),
        "date_of_birth": student.get("date_of_birth", ""),
        "gender": student.get("gender", ""),
        "blood_group": student.get("blood_group", ""),
        "address": student.get("address", ""),
        "status": student.get("status", "active"),
        "attendance_summary": attendance_summary,
    }

    if fee_status:
        profile["fee_status"] = fee_status
    if guardian_info:
        profile["guardian"] = guardian_info

    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": [profile],
        "meta": {"count": 1, "query_time_ms": round(elapsed, 2)},
        "message": "",
    }


# =========================================================================
#  9. tool_get_my_class_students
# =========================================================================

async def tool_get_my_class_students(params: dict, user: dict, scope: dict = None) -> dict:
    """For teachers: students in their assigned classes.  Auto-scoped by scope resolver."""
    t0 = time.time()
    db = get_db()

    if not scope or not scope.get("class_ids"):
        elapsed = (time.time() - t0) * 1000
        return _empty_result("No classes assigned to your account.", elapsed)

    class_ids = scope["class_ids"]
    students = await db.students.find({
        "class_id": {"$in": class_ids},
        "is_active": True,
    }).to_list(500)

    # Build class-name lookup
    classes = await db.classes.find({"id": {"$in": class_ids}}).to_list(20)
    class_map = {c["id"]: f"{c.get('name', '')}-{c.get('section', '')}" for c in classes}

    results = []
    for s in students:
        results.append({
            "name": s.get("name", ""),
            "class": class_map.get(s.get("class_id"), "N/A"),
            "roll_number": s.get("roll_number", "N/A"),
            "admission_number": s.get("admission_number", "N/A"),
            "status": s.get("status", "active"),
        })

    results.sort(key=lambda x: (x["class"], x.get("roll_number", "")))

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No students found in your assigned classes.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  10. tool_get_today_class_attendance
# =========================================================================

async def tool_get_today_class_attendance(params: dict, user: dict, scope: dict = None) -> dict:
    """Today's attendance for a specific class, including unmarked students list."""
    t0 = time.time()
    db = get_db()

    today_str = date.today().strftime("%Y-%m-%d")

    # Determine class_id
    class_id = params.get("class_id")
    if not class_id and params.get("class_name"):
        cls = await db.classes.find_one({"name": {"$regex": re.escape(params["class_name"]), "$options": "i"}})
        if cls:
            class_id = cls["id"]

    # If teacher scope and no class_id provided, use first assigned class
    if not class_id and scope and scope.get("class_ids"):
        class_id = scope["class_ids"][0]

    if not class_id:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("Please specify a class name or ID.", elapsed)

    # Scope check
    if scope and scope.get("class_ids") is not None and class_id not in scope["class_ids"]:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("You do not have access to this class.", elapsed)

    cls = await db.classes.find_one({"id": class_id})
    class_label = f"{cls['name']}-{cls['section']}" if cls else "Unknown"

    # All active students in this class
    all_students = await db.students.find({"class_id": class_id, "is_active": True}).to_list(200)
    student_map = {s["id"]: s for s in all_students}

    # Today's attendance records
    att_records = await db.student_attendance.find({"class_id": class_id, "date": today_str}).to_list(200)
    marked_ids = {r["student_id"] for r in att_records}

    present = []
    absent = []
    for r in att_records:
        s = student_map.get(r["student_id"])
        name = s["name"] if s else "Unknown"
        if r.get("status") == "present":
            present.append(name)
        else:
            absent.append(name)

    unmarked = [s["name"] for s in all_students if s["id"] not in marked_ids]

    elapsed = (time.time() - t0) * 1000
    data = [{
        "class": class_label,
        "date": today_str,
        "total_students": len(all_students),
        "present_count": len(present),
        "absent_count": len(absent),
        "unmarked_count": len(unmarked),
        "rate": f"{round(len(present) / len(all_students) * 100, 1)}%" if all_students else "0%",
        "present": present,
        "absent": absent,
        "unmarked": unmarked,
    }]
    return _ok(data, elapsed)


# =========================================================================
#  11. tool_get_house_standings
# =========================================================================

async def tool_get_house_standings(params: dict, user: dict, scope: dict = None) -> dict:
    """House points leaderboard.  All roles can view."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    houses = await db.houses.find(query).to_list(20)

    if not houses:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("No houses configured in the system.", elapsed)

    results = []
    for h in houses:
        # Points breakdown by category
        points_pipeline = [
            {"$match": {"house_id": h["id"]}},
            {"$group": {"_id": "$category", "total": {"$sum": "$points"}}},
        ]
        breakdown_raw = await db.house_points.aggregate(points_pipeline).to_list(20)
        breakdown = {b["_id"]: b["total"] for b in breakdown_raw}
        points_total = sum(breakdown.values())

        results.append({
            "house_name": h.get("name", ""),
            "color": h.get("color", ""),
            "points_total": points_total,
            "breakdown": breakdown,
        })

    results.sort(key=lambda x: x["points_total"], reverse=True)

    elapsed = (time.time() - t0) * 1000
    return _ok(results, elapsed)


# =========================================================================
#  12. tool_get_house_details
# =========================================================================

async def tool_get_house_details(params: dict, user: dict, scope: dict = None) -> dict:
    """Single house details: members, captains, recent points."""
    t0 = time.time()
    db = get_db()

    house = None
    if params.get("house_id"):
        house = await db.houses.find_one({"id": params["house_id"]})
    elif params.get("house_name"):
        house = await db.houses.find_one({"name": {"$regex": re.escape(params["house_name"]), "$options": "i"}})

    if not house:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("House not found. Please check the name and try again.", elapsed)

    # Members
    members_raw = await db.students.find({"house_id": house["id"], "is_active": True}).to_list(500)
    members = [{"name": m.get("name", ""), "class": m.get("class_id", ""), "role": m.get("house_role", "member")} for m in members_raw]
    captains = [m for m in members if m["role"] in ("captain", "vice_captain")]

    # Recent points (last 20 entries)
    recent_points = await db.house_points.find({"house_id": house["id"]}).sort("created_at", -1).to_list(20)
    recent = []
    for rp in recent_points:
        student = await db.students.find_one({"id": rp.get("student_id")}) if rp.get("student_id") else None
        recent.append({
            "student_name": student["name"] if student else "N/A",
            "points": rp.get("points", 0),
            "category": rp.get("category", ""),
            "reason": rp.get("reason", ""),
            "date": rp.get("created_at", "")[:10] if rp.get("created_at") else "",
        })

    # Total points
    total_pipeline = [{"$match": {"house_id": house["id"]}}, {"$group": {"_id": None, "total": {"$sum": "$points"}}}]
    total_result = await db.house_points.aggregate(total_pipeline).to_list(1)
    total_points = total_result[0]["total"] if total_result else 0

    data = [{
        "house_name": house.get("name", ""),
        "color": house.get("color", ""),
        "total_points": total_points,
        "member_count": len(members),
        "captains": captains,
        "recent_points": recent,
    }]

    elapsed = (time.time() - t0) * 1000
    return _ok(data, elapsed)


# =========================================================================
#  13. tool_award_house_points
# =========================================================================

async def tool_award_house_points(params: dict, user: dict, scope: dict = None) -> dict:
    """Award house points to a student.  Returns confirm_action format (write tool)."""
    t0 = time.time()
    db = get_db()

    # Validate write permission
    if scope and not scope.get("can_write", False):
        elapsed = (time.time() - t0) * 1000
        return {
            "success": False,
            "data": [],
            "meta": {"count": 0, "query_time_ms": round(elapsed, 2)},
            "message": "You do not have permission to award house points.",
        }

    student_name = params.get("student_name", "")
    points = params.get("points", 0)
    category = params.get("category", "general")
    reason = params.get("reason", "")

    if not student_name or not points:
        elapsed = (time.time() - t0) * 1000
        return {
            "success": False,
            "data": [],
            "meta": {"count": 0, "query_time_ms": round(elapsed, 2)},
            "message": "student_name and points are required parameters.",
        }

    # Find the student
    student = await db.students.find_one({"name": {"$regex": re.escape(student_name), "$options": "i"}, "is_active": True})
    if not student:
        elapsed = (time.time() - t0) * 1000
        return _empty_result(f"Student '{student_name}' not found.", elapsed)

    house_id = student.get("house_id")
    if not house_id:
        elapsed = (time.time() - t0) * 1000
        return _empty_result(f"Student '{student['name']}' is not assigned to any house.", elapsed)

    house = await db.houses.find_one({"id": house_id})
    house_name = house["name"] if house else "Unknown"

    # Insert the points record
    import uuid
    point_record = {
        "id": f"hp-{uuid.uuid4()}",
        "house_id": house_id,
        "student_id": student["id"],
        "points": points,
        "category": category,
        "reason": reason,
        "awarded_by": user.get("id", ""),
        "created_at": datetime.now().isoformat(),
    }
    await db.house_points.insert_one({**point_record, "_id": point_record["id"]})

    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": [{
            "confirm_action": "award_house_points",
            "student_name": student["name"],
            "house_name": house_name,
            "points_awarded": points,
            "category": category,
            "reason": reason,
        }],
        "meta": {"count": 1, "query_time_ms": round(elapsed, 2)},
        "message": f"Awarded {points} points to {student['name']} ({house_name}) for {category}.",
    }


# =========================================================================
#  14. tool_get_student_council
# =========================================================================

async def tool_get_student_council(params: dict, user: dict, scope: dict = None) -> dict:
    """All student council positions: head boy/girl, captains, prefects."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    # Try dedicated council collection first
    council_members = await db.student_council.find(query).to_list(100)

    if council_members:
        results = []
        for cm in council_members:
            student = await db.students.find_one({"id": cm.get("student_id")})
            cls = None
            if student:
                cls = await db.classes.find_one({"id": student.get("class_id")})
            results.append({
                "name": student["name"] if student else cm.get("student_name", "Unknown"),
                "class": f"{cls['name']}-{cls['section']}" if cls else "N/A",
                "position": cm.get("position", ""),
                "house": cm.get("house_name", ""),
            })
    else:
        # Fallback: check for council roles on student records
        council_query = {"council_role": {"$exists": True, "$ne": None, "$ne": ""}}
        _apply_branch_filter(council_query, scope)
        council_students = await db.students.find(council_query).to_list(100)
        results = []
        for s in council_students:
            cls = await db.classes.find_one({"id": s.get("class_id")})
            house = await db.houses.find_one({"id": s.get("house_id")}) if s.get("house_id") else None
            results.append({
                "name": s.get("name", ""),
                "class": f"{cls['name']}-{cls['section']}" if cls else "N/A",
                "position": s.get("council_role", ""),
                "house": house.get("name", "") if house else "",
            })

    elapsed = (time.time() - t0) * 1000
    if not results:
        return _empty_result("No student council positions configured yet.", elapsed)
    return _ok(results, elapsed)


# =========================================================================
#  15. tool_get_library_status
# =========================================================================

async def tool_get_library_status(params: dict, user: dict, scope: dict = None) -> dict:
    """Library overview: total, issued, overdue.
    Students see own issued books.  Teachers see class overdue list."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    _apply_branch_filter(query, scope)

    # Overall book counts
    total_books = await db.library_books.count_documents(query)
    issued_query = {**query, "status": "issued"}
    total_issued = await db.library_books.count_documents(issued_query)
    today_str = date.today().strftime("%Y-%m-%d")
    overdue_query = {**query, "status": "issued", "due_date": {"$lt": today_str}}
    total_overdue = await db.library_books.count_documents(overdue_query)

    overview = {
        "total_books": total_books,
        "issued": total_issued,
        "available": total_books - total_issued,
        "overdue": total_overdue,
    }

    # Role-specific detail
    detail = []

    if scope and scope.get("student_id"):
        # Student: show own issued books
        my_issues = await db.library_issues.find({
            "student_id": scope["student_id"],
            "status": {"$in": ["issued", "overdue"]},
        }).to_list(50)
        for iss in my_issues:
            book = await db.library_books.find_one({"id": iss.get("book_id")})
            detail.append({
                "book_title": book.get("title", "Unknown") if book else "Unknown",
                "author": book.get("author", "") if book else "",
                "issue_date": iss.get("issue_date", ""),
                "due_date": iss.get("due_date", ""),
                "status": "overdue" if iss.get("due_date", "9999") < today_str else "issued",
            })

    elif scope and scope.get("class_ids") is not None:
        # Teacher: overdue books for students in their classes
        students_in_class = await db.students.find({
            "class_id": {"$in": scope["class_ids"]},
            "is_active": True,
        }).to_list(500)
        student_ids = [s["id"] for s in students_in_class]
        student_map = {s["id"]: s["name"] for s in students_in_class}

        overdue_issues = await db.library_issues.find({
            "student_id": {"$in": student_ids},
            "status": {"$in": ["issued", "overdue"]},
            "due_date": {"$lt": today_str},
        }).to_list(200)

        for iss in overdue_issues:
            book = await db.library_books.find_one({"id": iss.get("book_id")})
            detail.append({
                "student_name": student_map.get(iss.get("student_id"), "Unknown"),
                "book_title": book.get("title", "Unknown") if book else "Unknown",
                "due_date": iss.get("due_date", ""),
                "days_overdue": (date.today() - datetime.strptime(iss["due_date"], "%Y-%m-%d").date()).days
                    if iss.get("due_date") else 0,
            })
    else:
        # Admin / owner: top overdue list
        overdue_issues = await db.library_issues.find({
            "status": {"$in": ["issued", "overdue"]},
            "due_date": {"$lt": today_str},
        }).sort("due_date", 1).to_list(50)

        for iss in overdue_issues:
            student = await db.students.find_one({"id": iss.get("student_id")})
            book = await db.library_books.find_one({"id": iss.get("book_id")})
            days = 0
            if iss.get("due_date"):
                try:
                    days = (date.today() - datetime.strptime(iss["due_date"], "%Y-%m-%d").date()).days
                except (ValueError, TypeError):
                    pass
            detail.append({
                "student_name": student.get("name", "Unknown") if student else "Unknown",
                "book_title": book.get("title", "Unknown") if book else "Unknown",
                "due_date": iss.get("due_date", ""),
                "days_overdue": days,
            })

    elapsed = (time.time() - t0) * 1000
    data = [{
        "overview": overview,
        "detail": detail,
    }]
    return _ok(data, elapsed)


# =========================================================================
#  COMBINED TOOL_REGISTRY — all 29 tools
# =========================================================================

TOOL_REGISTRY = {
    # ---- 14 original tools (from tool_functions.py) ----
    "get_school_pulse": {
        "fn": tool_get_school_pulse,
        "roles": ["owner", "admin"],
        "description": "Full school dashboard: attendance, fees, staff, alerts.",
        "params_schema": {},
    },
    "get_daily_brief": {
        "fn": tool_get_daily_brief,
        "roles": ["owner", "admin"],
        "description": "Comprehensive morning brief combining pulse, alerts, and fees.",
        "params_schema": {},
    },
    "get_fee_summary": {
        "fn": tool_get_fee_summary,
        "roles": ["owner", "admin"],
        "description": "Fee collection stats and top defaulters list.",
        "params_schema": {},
    },
    "get_staff_status": {
        "fn": tool_get_staff_status,
        "roles": ["owner", "admin"],
        "description": "Staff attendance today, late patterns, pending leaves.",
        "params_schema": {},
    },
    "get_attendance_overview": {
        "fn": tool_get_attendance_overview,
        "roles": ["owner", "admin", "teacher"],
        "description": "Attendance trends over a time period with class-wise breakdown.",
        "params_schema": {
            "days": {"type": "integer", "description": "Number of days to look back (default 30)"},
            "class_id": {"type": "string", "description": "Optional class ID to filter"},
        },
    },
    "get_smart_alerts": {
        "fn": tool_get_smart_alerts,
        "roles": ["owner", "admin"],
        "description": "Proactive alerts: chronic absentees, overdue fees, pending leaves.",
        "params_schema": {},
    },
    "get_financial_report": {
        "fn": tool_get_financial_report,
        "roles": ["owner"],
        "description": "Detailed financial report with fee-type breakdown.",
        "params_schema": {},
    },
    "search_students": {
        "fn": tool_search_students,
        "roles": ["owner", "admin", "teacher"],
        "description": "Search students by name, admission number, or class.",
        "params_schema": {
            "query": {"type": "string", "description": "Name or admission number search"},
            "class_name": {"type": "string", "description": "Filter by class name"},
        },
    },
    "get_fee_transactions": {
        "fn": tool_get_fee_transactions,
        "roles": ["owner", "admin"],
        "description": "Fee transactions list, optionally filtered by student or status.",
        "params_schema": {
            "student_id": {"type": "string", "description": "Filter by student ID"},
            "status": {"type": "string", "description": "Filter by status: paid, pending, overdue"},
        },
    },
    "approve_leave": {
        "fn": tool_approve_leave,
        "roles": ["owner", "admin"],
        "description": "Approve or reject a staff leave request.",
        "params_schema": {
            "leave_id": {"type": "string", "description": "Leave request ID (required)"},
            "action": {"type": "string", "description": "approve or reject"},
            "reason": {"type": "string", "description": "Rejection reason (if rejecting)"},
        },
    },
    "get_enquiries": {
        "fn": tool_get_enquiries,
        "roles": ["owner", "admin"],
        "description": "Admission enquiries with funnel stats.",
        "params_schema": {
            "status": {"type": "string", "description": "Filter by status"},
        },
    },
    "get_my_attendance": {
        "fn": tool_get_my_attendance,
        "roles": ["student"],
        "description": "Student's own attendance for the last 30 days.",
        "params_schema": {},
    },
    "get_my_fees": {
        "fn": tool_get_my_fees,
        "roles": ["student"],
        "description": "Student's own fee transactions and balances.",
        "params_schema": {},
    },
    "get_my_results": {
        "fn": tool_get_my_results,
        "roles": ["student"],
        "description": "Student's own exam results and grades.",
        "params_schema": {},
    },

    # ---- 15 new scope-aware tools ----
    "get_student_database": {
        "fn": tool_get_student_database,
        "roles": ["owner", "admin", "teacher"],
        "description": "Full student database with filters (class, status, gender, search). Teachers see own classes only.",
        "params_schema": {
            "class_name": {"type": "string", "description": "Filter by class name"},
            "status": {"type": "string", "description": "Filter by student status (active, inactive, etc.)"},
            "gender": {"type": "string", "description": "Filter by gender"},
            "search": {"type": "string", "description": "Search by name or admission number"},
        },
    },
    "get_fee_structures": {
        "fn": tool_get_fee_structures,
        "roles": ["owner", "admin"],
        "description": "Fee structures by class group with component breakdown and annual totals.",
        "params_schema": {
            "class_group": {"type": "string", "description": "Filter by class group name"},
        },
    },
    "get_class_wise_attendance": {
        "fn": tool_get_class_wise_attendance,
        "roles": ["owner", "admin", "teacher"],
        "description": "Per-class attendance summary for a date range. Teachers see own class only.",
        "params_schema": {
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (default: today)"},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD (default: today)"},
        },
    },
    "get_leave_requests": {
        "fn": tool_get_leave_requests,
        "roles": ["owner", "admin"],
        "description": "Leave requests list filtered by status.",
        "params_schema": {
            "status": {"type": "string", "description": "Filter: pending, approved, rejected"},
        },
    },
    "get_staff_list": {
        "fn": tool_get_staff_list,
        "roles": ["owner", "admin"],
        "description": "All active staff with department, designation, subject, and attendance rate. Excludes salary.",
        "params_schema": {
            "staff_type": {"type": "string", "description": "Filter by staff type (teacher, admin, etc.)"},
            "department": {"type": "string", "description": "Filter by department"},
        },
    },
    "get_class_list": {
        "fn": tool_get_class_list,
        "roles": ["owner", "admin", "teacher"],
        "description": "All classes with section, class teacher name, and student count.",
        "params_schema": {},
    },
    "get_fee_defaulters": {
        "fn": tool_get_fee_defaulters,
        "roles": ["owner", "admin"],
        "description": "Students with overdue fees sorted by amount due.",
        "params_schema": {},
    },
    "get_student_profile": {
        "fn": tool_get_student_profile,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "Full profile for a single student: personal info, attendance, fees, guardian.",
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID"},
            "search_term": {"type": "string", "description": "Name or admission number to search"},
        },
    },
    "get_my_class_students": {
        "fn": tool_get_my_class_students,
        "roles": ["teacher"],
        "description": "Students in the teacher's assigned classes. Auto-scoped.",
        "params_schema": {},
    },
    "get_today_class_attendance": {
        "fn": tool_get_today_class_attendance,
        "roles": ["owner", "admin", "teacher"],
        "description": "Today's attendance for a class with present, absent, and unmarked lists.",
        "params_schema": {
            "class_id": {"type": "string", "description": "Class ID"},
            "class_name": {"type": "string", "description": "Class name (alternative to class_id)"},
        },
    },
    "get_house_standings": {
        "fn": tool_get_house_standings,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "House points leaderboard with category breakdown.",
        "params_schema": {},
    },
    "get_house_details": {
        "fn": tool_get_house_details,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "Single house details: members, captains, recent point awards.",
        "params_schema": {
            "house_id": {"type": "string", "description": "House ID"},
            "house_name": {"type": "string", "description": "House name (alternative to house_id)"},
        },
    },
    "award_house_points": {
        "fn": tool_award_house_points,
        "roles": ["owner", "admin", "teacher"],
        "description": "Award house points to a student. Write operation.",
        "params_schema": {
            "student_name": {"type": "string", "description": "Student name (required)"},
            "points": {"type": "integer", "description": "Points to award (required)"},
            "category": {"type": "string", "description": "Category: academics, sports, discipline, cultural, general"},
            "reason": {"type": "string", "description": "Reason for awarding points"},
        },
    },
    "get_student_council": {
        "fn": tool_get_student_council,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "Student council positions: head boy/girl, captains, prefects.",
        "params_schema": {},
    },
    "get_library_status": {
        "fn": tool_get_library_status,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "Library overview: total books, issued, overdue. Role-specific detail.",
        "params_schema": {},
    },
}
