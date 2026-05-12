"""
Tool functions v2 — extends the original 14 tools with 15 new scope-aware tools.
Imports all originals from tool_functions and exposes a combined TOOL_REGISTRY (29 tools).
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
from database import get_db
import time, re
import uuid
import logging
from tenant import add_school_id, get_school_id, scoped_filter

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
    branch_id = None
    if scope:
        branch_id = scope.get("branch_id") if isinstance(scope, dict) else getattr(scope, "branch_id", None)
    if branch_id:
        query["branch_id"] = branch_id
    return query


def _apply_class_filter(query: dict, scope: dict, field: str = "class_id") -> dict:
    """Restrict query to the classes the user is allowed to see."""
    class_ids = _scope_class_ids(scope)
    if class_ids is not None:
        query[field] = {"$in": class_ids}
    return query


def _scope_class_ids(scope) -> list | None:
    if not scope:
        return None
    return scope.get("class_ids") if isinstance(scope, dict) else getattr(scope, "class_ids", None)


def _scope_student_id(scope) -> str | None:
    if not scope:
        return None
    return scope.get("student_id") if isinstance(scope, dict) else getattr(scope, "student_id", None)


def _scope_bool(scope, key: str, default: bool = False) -> bool:
    if not scope:
        return default
    return bool(scope.get(key, default)) if isinstance(scope, dict) else bool(getattr(scope, key, default))


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
    if _scope_class_ids(scope) is not None:
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
            if _scope_class_ids(scope) is not None:
                if cls["id"] in _scope_class_ids(scope):
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
    if _scope_class_ids(scope) is not None:
        class_query["id"] = {"$in": _scope_class_ids(scope)}

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
        if _scope_class_ids(scope) is not None:
            if student.get("class_id") not in _scope_class_ids(scope):
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
    if _scope_student_id(scope) and _scope_student_id(scope) != student["id"]:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("You do not have permission to view this student's profile.", elapsed)

    # Scope check: teacher can only see students in their classes
    if _scope_class_ids(scope) is not None:
        if student.get("class_id") not in _scope_class_ids(scope):
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
    if scope is None or _scope_bool(scope, "can_see_fees", False):
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

    if not _scope_class_ids(scope):
        elapsed = (time.time() - t0) * 1000
        return _empty_result("No classes assigned to your account.", elapsed)

    class_ids = _scope_class_ids(scope)
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
    if not class_id and _scope_class_ids(scope):
        class_id = _scope_class_ids(scope)[0]

    if not class_id:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("Please specify a class name or ID.", elapsed)

    # Scope check
    if _scope_class_ids(scope) is not None and class_id not in _scope_class_ids(scope):
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
    if scope and not _scope_bool(scope, "can_write", True):
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

    if _scope_student_id(scope):
        # Student: show own issued books
        my_issues = await db.library_issues.find({
            "student_id": _scope_student_id(scope),
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

    elif _scope_class_ids(scope) is not None:
        # Teacher: overdue books for students in their classes
        students_in_class = await db.students.find({
            "class_id": {"$in": _scope_class_ids(scope)},
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
#  Appendix A dispatch tools
# =========================================================================

def _is_principal(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "principal"


def _is_accountant(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "accountant"


def _is_maintenance(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "maintenance"


def _can_owner_or_principal(user: dict) -> bool:
    return user.get("role") == "owner" or _is_principal(user)


def _audit_doc(action: str, entity_type: str, entity_id: str, user: dict, changes: dict, reason: str | None = None):
    return add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "collection": entity_type,
        "entity_id": entity_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_name": user.get("name", ""),
        "changed_by_role": user.get("role"),
        "changes": changes,
        "reason": reason,
        "created_at": datetime.now().isoformat(),
    })


async def _notify(db, *, user_id: str, notification_type: str, message: str, source_id: str, source_type: str):
    if not user_id:
        return
    await db.notifications.insert_one(add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": notification_type,
        "message": message,
        "source_record_id": source_id,
        "source_record_type": source_type,
        "read": False,
        "created_at": datetime.now().isoformat(),
    }))


async def _find_mutable_record(db, record_id: str, *, include_tech: bool = True):
    candidates = [
        ("incidents", db.incidents, {"id": record_id}),
        ("complaints", db.complaints, {"id": record_id}),
        ("facility_requests", db.facility_requests, {"id": record_id}),
    ]
    if include_tech:
        candidates.append(("tech_requests", db.tech_requests, {"id": record_id}))
    for collection, handle, query in candidates:
        doc = await handle.find_one(scoped_filter(query, get_school_id()), {"_id": 0})
        if doc:
            return collection, handle, doc
    return None, None, None


async def _append_record_note(handle, record_id: str, existing: dict, user: dict, content: str, field: str):
    entry = {
        "id": str(uuid.uuid4()),
        "author_id": user.get("id"),
        "author_name": user.get("name", ""),
        "author_role": user.get("role", ""),
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    current = list(existing.get(field) or [])
    current.append(entry)
    await handle.update_one(
        scoped_filter({"id": record_id}, get_school_id()),
        {"$set": {field: current, "updated_at": datetime.now().isoformat()}},
    )
    return entry


async def tool_assign_followup(params: dict, user: dict, scope: dict = None) -> dict:
    if not _can_owner_or_principal(user):
        return {"success": False, "message": "Only Owner or Principal can assign follow-up actions."}
    required = ("record_id", "assignee_staff_id", "due_date", "note")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "record_id, assignee_staff_id, due_date, and note are required."}
    db = get_db()
    collection, handle, existing = await _find_mutable_record(db, params["record_id"])
    if not existing:
        return _empty_result("Record not found for follow-up assignment.")
    staff = await db.staff.find_one(scoped_filter({"id": params["assignee_staff_id"]}, get_school_id()), {"_id": 0})
    updates = {"assigned_to": params["assignee_staff_id"], "due_date": params["due_date"], "updated_at": datetime.now().isoformat()}
    await handle.update_one(scoped_filter({"id": params["record_id"]}, get_school_id()), {"$set": updates})
    field = "thread" if collection in ("incidents", "complaints") else "notes"
    await _append_record_note(handle, params["record_id"], existing, user, params["note"], field)
    await db.audit_logs.insert_one(_audit_doc("assign_followup", collection, params["record_id"], user, updates, params["note"]))
    await _notify(db, user_id=(staff or {}).get("user_id"), notification_type="followup_assigned", message=params["note"], source_id=params["record_id"], source_type=collection)
    return {"success": True, "data": {"record_id": params["record_id"], **updates}, "message": "Follow-up assigned."}


async def tool_update_incident_status(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("record_id", "new_status", "note")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "record_id, new_status, and note are required."}
    db = get_db()
    collection, handle, existing = await _find_mutable_record(db, params["record_id"])
    if not existing:
        return _empty_result("Incident, complaint, or request not found.")
    if not _can_owner_or_principal(user) and not (_is_maintenance(user) and collection == "facility_requests"):
        return {"success": False, "message": "Only Owner, Principal, or Maintenance Admin for facility requests can update status."}
    if _is_maintenance(user) and params["new_status"] == "closed":
        return {"success": False, "message": "Maintenance Admin cannot close a facility request directly."}
    updates = {"status": params["new_status"], "updated_at": datetime.now().isoformat()}
    await handle.update_one(scoped_filter({"id": params["record_id"]}, get_school_id()), {"$set": updates})
    field = "thread" if collection in ("incidents", "complaints") else "notes"
    await _append_record_note(handle, params["record_id"], existing, user, params["note"], field)
    await db.audit_logs.insert_one(_audit_doc("update_incident_status", collection, params["record_id"], user, {"previous_status": existing.get("status"), **updates}, params["note"]))
    return {"success": True, "data": {"record_id": params["record_id"], **updates}, "message": "Status updated."}


async def tool_add_thread_entry(params: dict, user: dict, scope: dict = None) -> dict:
    if not _can_owner_or_principal(user):
        return {"success": False, "message": "Only Owner or Principal can add thread entries."}
    if not params.get("record_id") or not params.get("content"):
        return {"success": False, "message": "record_id and content are required."}
    db = get_db()
    collection, handle, existing = await _find_mutable_record(db, params["record_id"])
    if not existing:
        return _empty_result("Record not found for thread entry.")
    field = "thread" if collection in ("incidents", "complaints") else "notes"
    entry = await _append_record_note(handle, params["record_id"], existing, user, params["content"], field)
    await db.audit_logs.insert_one(_audit_doc("add_thread_entry", collection, params["record_id"], user, {"entry": entry}))
    return {"success": True, "data": entry, "message": "Thread entry added."}


async def tool_initiate_substitution(params: dict, user: dict, scope: dict = None) -> dict:
    if not _is_principal(user):
        return {"success": False, "message": "Only Principal can initiate substitutions."}
    required = ("absent_staff_id", "substitute_staff_id", "class_id", "period_id")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "absent_staff_id, substitute_staff_id, class_id, and period_id are required."}
    db = get_db()
    slot = await db.timetable_slots.find_one({"id": params["period_id"]}, {"_id": 0})
    record = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "date": params.get("date", date.today().isoformat()),
        "absent_teacher_id": params["absent_staff_id"],
        "substitute_teacher_id": params["substitute_staff_id"],
        "class_id": params["class_id"],
        "subject_id": (slot or {}).get("subject_id", params.get("subject_id")),
        "period_id": params["period_id"],
        "period_number": (slot or {}).get("period_number"),
        "created_by": user.get("id"),
        "created_at": datetime.now().isoformat(),
    })
    await db.substitutions.insert_one(record)
    await db.audit_logs.insert_one(_audit_doc("initiate_substitution", "substitutions", record["id"], user, {"created": {k: v for k, v in record.items() if k != "_id"}}))
    substitute = await db.staff.find_one(scoped_filter({"id": params["substitute_staff_id"]}, get_school_id()), {"_id": 0})
    await _notify(db, user_id=(substitute or {}).get("user_id"), notification_type="substitution_assigned", message="You have been assigned as a substitute teacher.", source_id=record["id"], source_type="substitution")
    return {"success": True, "data": {k: v for k, v in record.items() if k != "_id"}, "message": "Substitution initiated."}


async def tool_correct_attendance(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") != "owner" and not _is_principal(user):
        return {"success": False, "message": "Only Owner or Principal can correct attendance through AI dispatch."}
    required = ("record_id", "correction_type", "reason")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "record_id, correction_type, and reason are required."}
    db = get_db()
    original = await db.student_attendance.find_one(scoped_filter({"id": params["record_id"]}, get_school_id()), {"_id": 0})
    if not original:
        return _empty_result("Attendance record not found.")
    new_status = params.get("status") or params["correction_type"]
    correction = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "attendance_id": params["record_id"],
        "original_record": original,
        "previous_status": original.get("status"),
        "new_status": new_status,
        "correction_type": params["correction_type"],
        "reason": params["reason"],
        "corrected_by": user.get("id"),
        "corrected_at": datetime.now().isoformat(),
    })
    await db.attendance_corrections.insert_one(correction)
    await db.student_attendance.update_one(scoped_filter({"id": params["record_id"]}, get_school_id()), {"$set": {"status": new_status, "corrected": True, "updated_at": correction["corrected_at"]}})
    await db.audit_logs.insert_one(_audit_doc("correct_attendance", "student_attendance", params["record_id"], user, {"status": {"previous": original.get("status"), "new": new_status}}, params["reason"]))
    return {"success": True, "data": {k: v for k, v in correction.items() if k != "_id"}, "message": "Attendance correction applied."}


async def tool_log_contact_event(params: dict, user: dict, scope: dict = None) -> dict:
    if not _is_accountant(user):
        return {"success": False, "message": "Only Accountant can log fee contact events through AI dispatch."}
    required = ("student_id", "contact_type", "outcome", "note")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "student_id, contact_type, outcome, and note are required."}
    db = get_db()
    txn = None
    if params.get("fee_transaction_id"):
        txn = await db.fee_transactions.find_one(scoped_filter({"id": params["fee_transaction_id"]}, get_school_id()), {"_id": 0})
    if not txn:
        txns = await db.fee_transactions.find(scoped_filter({"student_id": params["student_id"]}, get_school_id()), {"_id": 0}).sort("created_at", -1).to_list(1)
        txn = txns[0] if txns else None
    if not txn:
        return _empty_result("No fee transaction found for this student.")
    record = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "student_id": params["student_id"],
        "fee_transaction_id": txn["id"],
        "date": params.get("date", date.today().isoformat()),
        "contact_type": params["contact_type"],
        "outcome": params["outcome"],
        "notes": params["note"],
        "created_by": user.get("id"),
        "created_at": datetime.now().isoformat(),
    })
    await db.fee_contact_logs.insert_one(record)
    await db.audit_logs.insert_one(_audit_doc("log_contact_event", "fee_transactions", txn["id"], user, {"contact": {k: v for k, v in record.items() if k != "_id"}}))
    return {"success": True, "data": {k: v for k, v in record.items() if k != "_id"}, "message": "Contact event logged."}


async def tool_apply_discount(params: dict, user: dict, scope: dict = None) -> dict:
    if not _is_accountant(user):
        return {"success": False, "message": "Only Accountant can apply discounts through AI dispatch."}
    required = ("student_id", "discount_type_id", "effective_from")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "student_id, discount_type_id, and effective_from are required."}
    db = get_db()
    dtype = await db.fee_discount_types.find_one(scoped_filter({"id": params["discount_type_id"], "is_active": True}, get_school_id()), {"_id": 0})
    if not dtype:
        return _empty_result("Active discount type not found.")
    original_amount = params.get("original_amount")
    if original_amount in (None, ""):
        txns = await db.fee_transactions.find(scoped_filter({"student_id": params["student_id"]}, get_school_id()), {"_id": 0}).to_list(200)
        original_amount = sum(float(txn.get("amount", 0)) for txn in txns if txn.get("status") in ("pending", "overdue", "unpaid"))
    application = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "student_id": params["student_id"],
        "discount_type_id": dtype["id"],
        "original_amount": float(original_amount or 0),
        "effective_from": params["effective_from"],
        "applied_by": user.get("id"),
        "applied_at": datetime.now().isoformat(),
        "note": params.get("note"),
    })
    await db.fee_discounts.insert_one(application)
    await db.audit_logs.insert_one(_audit_doc("apply_discount", "fee_discounts", application["id"], user, {"applied": {k: v for k, v in application.items() if k != "_id"}}, params.get("note")))
    return {"success": True, "data": {k: v for k, v in application.items() if k != "_id"}, "message": "Discount applied."}


async def tool_decide_approval_request(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("request_id", "decision", "reason")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "request_id, decision, and reason are required."}
    decision_map = {"approve": "approved", "approved": "approved", "reject": "rejected", "rejected": "rejected"}
    status = decision_map.get(str(params["decision"]).lower())
    if not status:
        return {"success": False, "message": "decision must be approve or reject."}
    db = get_db()
    approval = await db.approval_requests.find_one(scoped_filter({"id": params["request_id"]}, get_school_id()), {"_id": 0})
    if not approval:
        return _empty_result("Approval request not found.")
    if user.get("role") != "owner" and not (_is_principal(user) and approval.get("routing") in ("owner_and_principal", "academic")):
        return {"success": False, "message": "Not authorized to decide this approval request."}
    update = {"status": status, "decision_reason": params["reason"], "decided_by": user.get("id"), "decided_at": datetime.now().isoformat(), "unread_for": []}
    await db.approval_requests.update_one(scoped_filter({"id": params["request_id"]}, get_school_id()), {"$set": update})
    await db.audit_logs.insert_one(_audit_doc("decide_approval_request", "approval_requests", params["request_id"], user, update, params["reason"]))
    await _notify(db, user_id=approval.get("submitted_by"), notification_type="approval_decision", message=f"{approval.get('title', 'Approval request')} {status}", source_id=params["request_id"], source_type="approval_request")
    return {"success": True, "data": {"request_id": params["request_id"], **update}, "message": f"Approval request {status}."}


async def tool_confirm_resolution(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") != "owner":
        return {"success": False, "message": "Only Owner can confirm facility resolution."}
    if not params.get("request_id") or not params.get("confirmation_note"):
        return {"success": False, "message": "request_id and confirmation_note are required."}
    db = get_db()
    existing = await db.facility_requests.find_one(scoped_filter({"id": params["request_id"]}, get_school_id()), {"_id": 0})
    if not existing:
        return _empty_result("Facility request not found.")
    if existing.get("status") != "pending_owner_confirmation":
        return {"success": False, "message": "Request must be pending Owner confirmation before it can be closed."}
    update = {"status": "closed", "resolved_by": user.get("id"), "resolved_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}
    await db.facility_requests.update_one(scoped_filter({"id": params["request_id"]}, get_school_id()), {"$set": update})
    await _append_record_note(db.facility_requests, params["request_id"], existing, user, params["confirmation_note"], "notes")
    await db.audit_logs.insert_one(_audit_doc("confirm_resolution", "facility_requests", params["request_id"], user, update, params["confirmation_note"]))
    await _notify(db, user_id=existing.get("logged_by"), notification_type="facility_resolved", message="Facility request resolved and closed by Owner.", source_id=params["request_id"], source_type="facility_request")
    return {"success": True, "data": {"request_id": params["request_id"], **update}, "message": "Resolution confirmed."}


async def tool_record_fee_payment(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") != "owner" and not _is_accountant(user):
        return {"success": False, "message": "Only Owner or Accountant can record fee payments through AI dispatch."}
    required = ("student_id", "amount", "fee_head", "mode")
    if any(params.get(field) in (None, "") for field in required):
        return {"success": False, "message": "student_id, amount, fee_head, and mode are required."}
    db = get_db()
    txn_id = str(uuid.uuid4())
    receipt_number = f"RCP{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    txn = add_school_id({
        "_id": txn_id,
        "id": txn_id,
        "student_id": params["student_id"],
        "fee_period": params.get("fee_period", date.today().strftime("%Y-%m")),
        "fee_head": params["fee_head"],
        "fee_type": params.get("fee_type", params["fee_head"]),
        "amount": float(params["amount"]),
        "payment_mode": params["mode"],
        "receipt_number": receipt_number,
        "status": "paid",
        "paid_date": params.get("paid_date", date.today().isoformat()),
        "recorded_by": user.get("id"),
        "note": params.get("receipt_note"),
        "created_at": datetime.now().isoformat(),
    })
    await db.fee_transactions.insert_one(txn)
    await db.audit_logs.insert_one(_audit_doc("record_fee_payment", "fee_transactions", txn_id, user, {"created": {k: v for k, v in txn.items() if k != "_id"}}))
    return {"success": True, "data": {k: v for k, v in txn.items() if k != "_id"}, "message": "Fee payment recorded."}


async def tool_mark_attendance(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") not in ("owner", "admin", "teacher"):
        return {"success": False, "message": "Only Owner, Admin, or Teacher can mark attendance."}
    if not params.get("class_id") and not params.get("class_name"):
        return {"success": False, "message": "class_id or class_name is required."}
    if not params.get("attendance"):
        return {"success": False, "message": "attendance list is required."}
    db = get_db()
    class_id = params.get("class_id")
    if not class_id and params.get("class_name"):
        cls = await db.classes.find_one({"name": {"$regex": re.escape(params["class_name"]), "$options": "i"}}, {"_id": 0})
        class_id = (cls or {}).get("id")
    if not class_id:
        return _empty_result("Class not found.")
    target_date = params.get("date", date.today().isoformat())
    saved = []
    for item in params["attendance"]:
        att_id = str(uuid.uuid4())
        doc = add_school_id({
            "_id": att_id,
            "id": att_id,
            "student_id": item["student_id"],
            "class_id": class_id,
            "date": target_date,
            "status": item["status"],
            "marked_by": user.get("id"),
            "source": "ai_dispatch",
            "created_at": datetime.now().isoformat(),
        })
        await db.student_attendance.update_one(
            scoped_filter({"student_id": item["student_id"], "class_id": class_id, "date": target_date}, get_school_id()),
            {"$set": doc},
            upsert=True,
        )
        saved.append({"student_id": item["student_id"], "status": item["status"]})
    await db.audit_logs.insert_one(_audit_doc("mark_attendance", "student_attendance", class_id, user, {"date": target_date, "records": saved}))
    return {"success": True, "data": saved, "message": "Attendance marked."}


async def tool_query_dashboard_summary(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") != "owner":
        return {"success": False, "message": "Only Owner can query dashboard summary."}
    db = get_db()
    today = date.today().isoformat()
    data = [{
        "open_incidents": await db.incidents.count_documents(scoped_filter({"status": {"$ne": "closed"}}, get_school_id())),
        "pending_approvals": await db.approval_requests.count_documents(scoped_filter({"status": "pending"}, get_school_id())),
        "staff_absent_today": await db.staff_attendance.count_documents({"date": today, "status": "absent"}),
        "fee_outstanding_transactions": await db.fee_transactions.count_documents(scoped_filter({"status": {"$in": ["pending", "overdue", "unpaid"]}}, get_school_id())),
    }]
    return _ok(data, 0, "Dashboard summary ready.")


async def tool_query_attendance_status(params: dict, user: dict, scope: dict = None) -> dict:
    if not _can_owner_or_principal(user):
        return {"success": False, "message": "Only Owner or Principal can query staff attendance status."}
    db = get_db()
    target_date = params.get("date", date.today().isoformat())
    records = await db.staff_attendance.find({"date": target_date}, {"_id": 0}).to_list(500)
    return _ok(records, 0, "Staff attendance status ready.")


async def tool_query_fee_status(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") != "owner" and not _is_accountant(user) and not _is_principal(user):
        return {"success": False, "message": "Only Owner, Accountant, or Principal can query fee status."}
    db = get_db()
    query = scoped_filter({}, get_school_id())
    if params.get("student_id"):
        query["student_id"] = params["student_id"]
    if params.get("status"):
        query["status"] = params["status"]
    txns = await db.fee_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return _ok(txns, 0, "Fee status ready.")


async def tool_query_incidents(params: dict, user: dict, scope: dict = None) -> dict:
    if not _can_owner_or_principal(user):
        return {"success": False, "message": "Only Owner or Principal can query incidents."}
    db = get_db()
    query = {}
    if params.get("status"):
        query["status"] = params["status"]
    incidents = await db.incidents.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("created_at", -1).to_list(100)
    complaints = await db.complaints.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    visitors = await db.visitor_log.find({}, {"_id": 0}).sort("time_in", -1).to_list(100)
    return _ok([{"incidents": incidents, "complaints": complaints, "visitors": visitors}], 0, "Incident data ready.")


async def tool_query_staff_availability(params: dict, user: dict, scope: dict = None) -> dict:
    if not _is_principal(user):
        return {"success": False, "message": "Only Principal can query staff availability."}
    db = get_db()
    staff = await db.staff.find(scoped_filter({"is_active": {"$ne": False}, "staff_type": "teacher"}, get_school_id()), {"_id": 0}).to_list(500)
    return _ok(staff, 0, "Staff availability ready.")


async def tool_query_maintenance_requests(params: dict, user: dict, scope: dict = None) -> dict:
    if user.get("role") != "owner" and not _is_maintenance(user):
        return {"success": False, "message": "Only Owner or Maintenance Admin can query maintenance requests."}
    db = get_db()
    query = {}
    if params.get("status"):
        query["status"] = params["status"]
    if _is_maintenance(user):
        query["logged_by"] = user.get("id")
    items = await db.facility_requests.find(scoped_filter(query, get_school_id()), {"_id": 0}).sort("created_at", -1).to_list(100)
    return _ok(items, 0, "Maintenance requests ready.")


async def tool_query_student_record(params: dict, user: dict, scope: dict = None) -> dict:
    if not params.get("student_id"):
        return {"success": False, "message": "student_id is required."}
    allowed = user.get("role") == "owner" or _is_principal(user) or _is_accountant(user) or (user.get("role") == "admin" and user.get("sub_category") == "transport_head")
    if not allowed:
        return {"success": False, "message": "Not authorized to query student records."}
    db = get_db()
    student = await db.students.find_one(scoped_filter({"id": params["student_id"]}, get_school_id()), {"_id": 0})
    if not student:
        return _empty_result("Student not found.")
    data = {"student": student}
    if _is_accountant(user) or user.get("role") == "owner" or _is_principal(user):
        data["fees"] = await db.fee_transactions.find(scoped_filter({"student_id": params["student_id"]}, get_school_id()), {"_id": 0}).to_list(100)
    if user.get("role") == "owner" or _is_principal(user) or user.get("sub_category") == "transport_head":
        data["transport"] = {"route_zone_id": student.get("route_zone_id")}
    return _ok([data], 0, "Student record ready.")


async def tool_query_audit_log(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    query = scoped_filter({}, get_school_id())
    if params.get("collection"):
        query["collection"] = params["collection"]
    if user.get("role") != "owner":
        query["changed_by"] = user.get("id")
    items = await db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return _ok(items, 0, "Audit log ready.")


_AUDIENCE_ROLE_MAP = {
    "all": [],
    "staff": ["admin", "teacher"],
    "students": ["student"],
    "parents": ["parent"],
}

async def tool_create_announcement(params: dict, user: dict, scope: dict = None) -> dict:
    if not _can_owner_or_principal(user):
        return {"success": False, "message": "Only Owner or Principal can publish announcements via AI."}
    title = (params.get("title") or "").strip()
    content = (params.get("content") or "").strip()
    if not title or not content:
        return {"success": False, "message": "title and content are required for an announcement."}
    if len(title) > 200:
        return {"success": False, "message": "title must be 200 characters or fewer."}
    if len(content) > 5000:
        return {"success": False, "message": "content must be 5000 characters or fewer."}
    audience_type = params.get("audience_type", "all")
    if audience_type not in _AUDIENCE_ROLE_MAP:
        audience_type = "all"
    audience_roles = _AUDIENCE_ROLE_MAP[audience_type]
    db = get_db()
    ann_id = str(uuid.uuid4())
    created_by = user.get("id") or "unknown"
    now = datetime.now().isoformat()
    announcement = add_school_id({
        "_id": ann_id,
        "id": ann_id,
        "title": title,
        "content": content,
        "audience_type": audience_type,
        "audience_classes": [],
        "audience_roles": audience_roles,
        "target_roles": audience_roles,
        "channels": ["push"],
        "is_draft": False,
        "sent_at": now,
        "created_by": created_by,
        "created_by_name": user.get("name", ""),
        "created_at": now,
    })
    await db.announcements.insert_one(announcement)
    await db.audit_logs.insert_one(_audit_doc("create_announcement", "announcements", ann_id, user, {"title": title, "audience_type": audience_type}))
    return {"success": True, "data": {k: v for k, v in announcement.items() if k != "_id"}, "message": f"Announcement '{title}' published successfully to {audience_type}."}


# =========================================================================
#  COMBINED TOOL_REGISTRY
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
        "dispatch_type": "write",
        "requires_confirmation": True,
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
        "dispatch_type": "write",
        "requires_confirmation": True,
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

    # ---- Appendix A formal dispatch table ----
    "assign_followup": {
        "fn": tool_assign_followup,
        "roles": ["owner", "admin"],
        "description": "Assign a follow-up action on a complaint or incident to a named staff member.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "record_id": {"type": "string", "description": "Complaint, incident, or request ID"},
            "assignee_staff_id": {"type": "string", "description": "Staff ID to assign"},
            "due_date": {"type": "string", "description": "Due date YYYY-MM-DD"},
            "note": {"type": "string", "description": "Follow-up note"},
        },
    },
    "update_incident_status": {
        "fn": tool_update_incident_status,
        "roles": ["owner", "admin"],
        "description": "Update status of a complaint, incident, or maintenance request.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "record_id": {"type": "string", "description": "Complaint, incident, or request ID"},
            "new_status": {"type": "string", "description": "New status"},
            "note": {"type": "string", "description": "Status-change note"},
        },
    },
    "add_thread_entry": {
        "fn": tool_add_thread_entry,
        "roles": ["owner", "admin"],
        "description": "Add a follow-up entry to an existing complaint or incident thread.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "record_id": {"type": "string", "description": "Complaint, incident, or request ID"},
            "content": {"type": "string", "description": "Thread entry content"},
        },
    },
    "initiate_substitution": {
        "fn": tool_initiate_substitution,
        "roles": ["admin"],
        "description": "Approve a substitution assignment for an absent teacher.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "absent_staff_id": {"type": "string", "description": "Absent teacher staff ID"},
            "substitute_staff_id": {"type": "string", "description": "Substitute teacher staff ID"},
            "class_id": {"type": "string", "description": "Class ID"},
            "period_id": {"type": "string", "description": "Timetable period/slot ID"},
        },
    },
    "correct_attendance": {
        "fn": tool_correct_attendance,
        "roles": ["owner", "admin"],
        "description": "Apply a correction to an existing attendance record with a mandatory reason.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "record_id": {"type": "string", "description": "Attendance record ID"},
            "correction_type": {"type": "string", "description": "Correction or new attendance status"},
            "reason": {"type": "string", "description": "Mandatory correction reason"},
        },
    },
    "log_contact_event": {
        "fn": tool_log_contact_event,
        "roles": ["admin"],
        "description": "Log a contact event against a student's fee record.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID"},
            "contact_type": {"type": "string", "description": "call, message, visit, or other"},
            "outcome": {"type": "string", "description": "Contact outcome"},
            "note": {"type": "string", "description": "Contact note"},
        },
    },
    "apply_discount": {
        "fn": tool_apply_discount,
        "roles": ["admin"],
        "description": "Apply a configured discount type to a student's fee profile.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID"},
            "discount_type_id": {"type": "string", "description": "Configured discount type ID"},
            "effective_from": {"type": "string", "description": "Effective date YYYY-MM-DD"},
        },
    },
    "decide_approval_request": {
        "fn": tool_decide_approval_request,
        "roles": ["owner", "admin"],
        "description": "Approve or reject a pending approval request with a mandatory reason.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "request_id": {"type": "string", "description": "Approval request ID"},
            "decision": {"type": "string", "description": "approve or reject"},
            "reason": {"type": "string", "description": "Mandatory decision reason"},
        },
    },
    "confirm_resolution": {
        "fn": tool_confirm_resolution,
        "roles": ["owner"],
        "description": "Owner confirms a facility request marked complete by Maintenance Admin.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "request_id": {"type": "string", "description": "Facility request ID"},
            "confirmation_note": {"type": "string", "description": "Owner confirmation note"},
        },
    },
    "record_fee_payment": {
        "fn": tool_record_fee_payment,
        "roles": ["owner", "admin"],
        "description": "Record a fee payment for a student.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID"},
            "amount": {"type": "number", "description": "Payment amount"},
            "fee_head": {"type": "string", "description": "Fee head"},
            "mode": {"type": "string", "description": "cash, upi, cheque, or bank_transfer"},
        },
    },
    "mark_attendance": {
        "fn": tool_mark_attendance,
        "roles": ["owner", "admin", "teacher"],
        "description": "Mark attendance for a class or student list.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "class_id": {"type": "string", "description": "Class ID"},
            "date": {"type": "string", "description": "Attendance date YYYY-MM-DD"},
            "attendance": {"type": "array", "description": "List of {student_id, status}"},
        },
    },
    "query_dashboard_summary": {
        "fn": tool_query_dashboard_summary,
        "roles": ["owner"],
        "description": "Composite summary of open incidents, pending approvals, attendance, and fee status.",
        "params_schema": {},
    },
    "query_attendance_status": {
        "fn": tool_query_attendance_status,
        "roles": ["owner", "admin"],
        "description": "Current staff attendance status from biometric feed.",
        "params_schema": {
            "date": {"type": "string", "description": "Optional date YYYY-MM-DD"},
        },
    },
    "query_fee_status": {
        "fn": tool_query_fee_status,
        "roles": ["owner", "admin"],
        "description": "Fee status, defaulters, and overdue list for a student or cohort.",
        "params_schema": {
            "student_id": {"type": "string", "description": "Optional student ID"},
            "status": {"type": "string", "description": "Optional fee status"},
        },
    },
    "query_incidents": {
        "fn": tool_query_incidents,
        "roles": ["owner", "admin"],
        "description": "Open complaints, incidents, or visitor logs by status/date/person.",
        "params_schema": {
            "status": {"type": "string", "description": "Optional status"},
        },
    },
    "query_staff_availability": {
        "fn": tool_query_staff_availability,
        "roles": ["admin"],
        "description": "Available staff for a given period, filtered against timetable.",
        "params_schema": {
            "period_id": {"type": "string", "description": "Optional period ID"},
        },
    },
    "query_maintenance_requests": {
        "fn": tool_query_maintenance_requests,
        "roles": ["owner", "admin"],
        "description": "Open facility requests by status, date, or location.",
        "params_schema": {
            "status": {"type": "string", "description": "Optional status"},
        },
    },
    "query_student_record": {
        "fn": tool_query_student_record,
        "roles": ["owner", "admin"],
        "description": "Student profile, fee profile, and transport assignment.",
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID"},
        },
    },
    "query_audit_log": {
        "fn": tool_query_audit_log,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "Scoped audit log entries per role.",
        "params_schema": {
            "collection": {"type": "string", "description": "Optional collection filter"},
        },
    },
    "create_announcement": {
        "fn": tool_create_announcement,
        "roles": ["owner", "admin"],
        "description": "Publish a school announcement to all parents, students, and staff.",
        "params_schema": {
            "title": {"type": "string", "description": "Announcement title"},
            "content": {"type": "string", "description": "Full announcement message"},
            "audience_type": {"type": "string", "description": "all, parents, students, staff — default: all"},
        },
        "requires_confirmation": True,
        "dispatch_type": "write",
    },
}

WRITE_TOOL_NAMES = {
    name for name, tool in TOOL_REGISTRY.items()
    if tool.get("requires_confirmation") or tool.get("dispatch_type") == "write"
}
