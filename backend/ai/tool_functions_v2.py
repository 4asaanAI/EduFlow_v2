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
from tenant import add_school_id, get_school_id, scoped_filter, scoped_query
from services.audit_service import write_audit_doc
from services.notification_service import create_notification
from services.actor_context import actor_ctx_from_user
from services.attendance_service import mark_attendance
from services.fees_service import record_payment, FeeValidationError
from services.discount_service import (
    apply_discount as svc_apply_discount,
    DiscountValidationError,
    DiscountNotFoundError,
)
from services.house_points_service import (
    award_points,
    HouseNotFoundError,
    HousePointsValidationError,
)
from services.approvals_service import (
    decide_approval_request,
    ApprovalValidationError,
    ApprovalNotFoundError,
    ApprovalAuthorizationError,
)
from services.announcement_service import (
    decide_announcement_status,
    AnnouncementValidationError,
)
from services.contact_log_service import log_contact_event, ContactLogValidationError
from services.student_service import (
    create_student as svc_create_student,
    update_student as svc_update_student,
    set_student_status as svc_set_student_status,
    upsert_guardians as svc_upsert_guardians,
    StudentValidationError,
    StudentNotFoundError,
    StudentConflictError,
    ClassNotFoundError,
    ClassValidationError,
)
from services.staff_service import (
    create_staff as svc_create_staff,
    update_staff as svc_update_staff,
    StaffValidationError,
    StaffNotFoundError,
    StaffAuthorizationError,
    LinkedUserNotFoundError,
)
from services.fee_config_service import (
    create_fee_structure as svc_create_fee_structure,
    update_fee_structure as svc_update_fee_structure,
    create_discount_type as svc_create_discount_type,
    update_discount_type as svc_update_discount_type,
    delete_discount_type as svc_delete_discount_type,
    FeeConfigValidationError,
    FeeConfigNotFoundError,
)
from services.academic_structure_service import (
    create_class as svc_create_class,
    update_class as svc_update_class,
    delete_class as svc_delete_class,
    create_house as svc_create_house,
    update_house as svc_update_house,
    delete_house as svc_delete_house,
    AcademicStructureValidationError,
    AcademicStructureNotFoundError,
    AcademicStructureConflictError,
)
from services.org_config_service import (
    create_branch as svc_create_branch,
    upsert_branch as svc_upsert_branch,
    delete_branch as svc_delete_branch,
    update_school_settings as svc_update_school_settings,
    year_end_transition as svc_year_end_transition,
    OrgConfigValidationError,
    OrgConfigNotFoundError,
    OrgConfigConflictError,
)
from services.incident_service import (
    resolve_record_type,
    assign_followup as svc_assign_followup,
    add_thread_entry as svc_add_thread_entry,
    update_incident_status as svc_update_incident_status,
    confirm_resolution as svc_confirm_resolution,
    IncidentValidationError,
    IncidentNotFoundError,
    IncidentAmbiguousError,
)
from services.substitution_service import initiate_substitution
from services.attendance_correction_service import (
    correct_attendance,
    AttendanceCorrectionValidationError,
    AttendanceCorrectionNotFoundError,
)

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


def _branch_id(user: dict | None, scope: dict | None = None) -> str | None:
    """Extract branch_id from the user JWT dict (preferred) or scope dict."""
    if user and isinstance(user, dict):
        bid = user.get("branch_id")
        if bid:
            return bid
    if scope and isinstance(scope, dict):
        bid = scope.get("branch_id")
        if bid:
            return bid
    return None


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
    if params.get("status"):
        query["status"] = params["status"]

    bid = _branch_id(user, scope)
    leaves = await db.leave_requests.find(scoped_query(query, branch_id=bid)).sort("created_at", -1).to_list(100)

    results = []
    for lr in leaves:
        staff = await db.staff.find_one(scoped_query({"id": lr.get("staff_id")}, branch_id=bid))
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
    if params.get("staff_type"):
        query["staff_type"] = {"$regex": re.escape(params["staff_type"]), "$options": "i"}
    if params.get("department"):
        query["department"] = {"$regex": re.escape(params["department"]), "$options": "i"}

    bid = _branch_id(user, scope)
    staff_list = await db.staff.find(scoped_query(query, branch_id=bid)).to_list(200)

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
        fee_txns = await db.fee_transactions.find(scoped_query({"student_id": student["id"]}, branch_id=_branch_id(user, scope))).to_list(100)
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

    # Story B.3: route through the shared house-points service so the AI award updates
    # the real standings (houses.points + house_points_log + audit) exactly like the
    # panel — replacing the old un-audited `house_points`-only write.
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {"house_id": house_id, "delta": points, "reason": reason}
    try:
        result = await award_points(db, actor_ctx, service_params)
    except HouseNotFoundError:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("House not found.", elapsed)
    except HousePointsValidationError as e:
        return {"success": False, "message": str(e)}

    house_name = result["house_name"] or "Unknown"
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
            "new_total": result["points"],
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


async def _write_audit(
    db,
    action: str,
    entity_type: str,
    entity_id: str,
    user: dict,
    changes: dict,
    reason: str | None = None,
    scope: dict | None = None,
):
    await write_audit_doc(
        db,
        _audit_doc(action, entity_type, entity_id, user, changes, reason),
        school_id=get_school_id(),
        branch_id=_branch_id(user, scope),
    )


async def _resolve_record_type_or_result(db, record_id: str, *, branch_id: str | None, not_found_msg: str):
    """AI-adapter helper: resolve the target collection EXPLICITLY up front (Story C.1)
    so the shared service writes to a known surface (no blind multi-collection scan at
    write). Returns ``(record_type, doc, None)`` on success, else ``(None, None, result)``
    where ``result`` is the tool envelope to return."""
    try:
        record_type, doc = await resolve_record_type(db, record_id, branch_id=branch_id)
        return record_type, doc, None
    except IncidentNotFoundError:
        return None, None, _empty_result(not_found_msg)
    except IncidentAmbiguousError as e:
        return None, None, {"success": False, "message": str(e)}


async def tool_assign_followup(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("record_id", "assignee_staff_id", "due_date", "note")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "record_id, assignee_staff_id, due_date, and note are required."}
    db = get_db()
    bid = _branch_id(user, scope)
    record_type, _doc, err = await _resolve_record_type_or_result(db, params["record_id"], branch_id=bid, not_found_msg="Record not found for follow-up assignment.")
    if err:
        return err
    actor_ctx = actor_ctx_from_user(user, branch_id=bid)
    try:
        result = await svc_assign_followup(db, actor_ctx, {
            "record_type": record_type,
            "record_id": params["record_id"],
            "assignee_staff_id": params["assignee_staff_id"],
            "due_date": params["due_date"],
            "note": params["note"],
        })
    except IncidentNotFoundError:
        return _empty_result("Record not found for follow-up assignment.")
    except IncidentValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": {"record_id": params["record_id"], **result["updates"]}, "message": "Follow-up assigned."}


async def tool_update_incident_status(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("record_id", "new_status", "note")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "record_id, new_status, and note are required."}
    db = get_db()
    bid = _branch_id(user, scope)
    record_type, _doc, err = await _resolve_record_type_or_result(db, params["record_id"], branch_id=bid, not_found_msg="Incident, complaint, or request not found.")
    if err:
        return err
    actor_ctx = actor_ctx_from_user(user, branch_id=bid)
    try:
        result = await svc_update_incident_status(db, actor_ctx, {
            "record_type": record_type,
            "record_id": params["record_id"],
            "new_status": params["new_status"],
            "note": params["note"],
        })
    except IncidentNotFoundError:
        return _empty_result("Incident, complaint, or request not found.")
    except IncidentValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": {"record_id": params["record_id"], **result["updates"]}, "message": "Status updated."}


async def tool_add_thread_entry(params: dict, user: dict, scope: dict = None) -> dict:
    if not params.get("record_id") or not params.get("content"):
        return {"success": False, "message": "record_id and content are required."}
    db = get_db()
    bid = _branch_id(user, scope)
    record_type, _doc, err = await _resolve_record_type_or_result(db, params["record_id"], branch_id=bid, not_found_msg="Record not found for thread entry.")
    if err:
        return err
    actor_ctx = actor_ctx_from_user(user, branch_id=bid)
    try:
        result = await svc_add_thread_entry(db, actor_ctx, {
            "record_type": record_type,
            "record_id": params["record_id"],
            "content": params["content"],
        })
    except IncidentNotFoundError:
        return _empty_result("Record not found for thread entry.")
    except IncidentValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["entry"], "message": "Thread entry added."}


async def tool_initiate_substitution(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("absent_staff_id", "substitute_staff_id", "class_id", "period_id")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "absent_staff_id, substitute_staff_id, class_id, and period_id are required."}
    db = get_db()
    # Resolve the timetable slot (AI-only convenience) to derive subject/period, then
    # delegate to the shared service — the SAME write path as the REST route (Story A.6).
    slot = await db.timetable_slots.find_one({"id": params["period_id"]}, {"_id": 0})
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {
        "date": params.get("date", date.today().isoformat()),
        "absent_teacher_id": params["absent_staff_id"],
        "substitute_teacher_id": params["substitute_staff_id"],
        "class_id": params["class_id"],
        "subject_id": (slot or {}).get("subject_id", params.get("subject_id")) or "",
        "period_number": (slot or {}).get("period_number"),
    }
    result = await initiate_substitution(db, actor_ctx, service_params)
    return {"success": True, "data": result["substitution"], "message": "Substitution initiated."}


async def tool_correct_attendance(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("record_id", "correction_type", "reason")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "record_id, correction_type, and reason are required."}
    # Thin adapter over services.attendance_correction_service — the SAME write path
    # as the REST correct route (Story A.7): snapshot + status update + canonical
    # 'correct' audit. School-wide scoping fixes the prior branch_id mismatch.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {
        "attendance_id": params["record_id"],
        "correction_type": params["correction_type"],
        "reason": params["reason"],
        "status": params.get("status"),
    }
    try:
        result = await correct_attendance(db, actor_ctx, service_params)
    except AttendanceCorrectionNotFoundError:
        return _empty_result("Attendance record not found.")
    except AttendanceCorrectionValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["correction"], "message": "Attendance correction applied."}


async def tool_log_contact_event(params: dict, user: dict, scope: dict = None) -> dict:
    required = ("student_id", "contact_type", "outcome", "note")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "student_id, contact_type, outcome, and note are required."}
    db = get_db()
    bid = _branch_id(user, scope)
    txn = None
    if params.get("fee_transaction_id"):
        txn = await db.fee_transactions.find_one(scoped_query({"id": params["fee_transaction_id"]}, branch_id=bid), {"_id": 0})
    if not txn:
        txns = await db.fee_transactions.find(scoped_query({"student_id": params["student_id"]}, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(1)
        txn = txns[0] if txns else None
    if not txn:
        return _empty_result("No fee transaction found for this student.")
    # Thin adapter over services.contact_log_service — the SAME write path as the REST
    # contact-log route (Story A.5). Txn resolution above is AI-only convenience; the
    # service writes an identical record + canonical 'contact_log' audit.
    actor_ctx = actor_ctx_from_user(user, branch_id=bid)
    service_params = {
        "student_id": params["student_id"],
        "fee_transaction_id": txn["id"],
        "date": params.get("date", date.today().isoformat()),
        "contact_type": params["contact_type"],
        "outcome": params["outcome"],
        "notes": params["note"],
    }
    result = await log_contact_event(db, actor_ctx, service_params)
    return {"success": True, "data": result["record"], "message": "Contact event logged."}


async def tool_apply_discount(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.discount_service.apply_discount — the SAME write path
    # as POST /api/fees/discounts/apply. Story B.2: the AI path now honours the owner
    # approval threshold (large discounts park in pending_discount_approvals instead of
    # applying directly — closing the bypass on children's fees).
    required = ("student_id", "discount_type_id", "effective_from")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "student_id, discount_type_id, and effective_from are required."}
    db = get_db()
    bid = _branch_id(user, scope)
    # AI convenience: derive original_amount from outstanding fees when the caller omits
    # it (the REST route requires it in the body; the assistant resolves it).
    original_amount = params.get("original_amount")
    if original_amount in (None, ""):
        txns = await db.fee_transactions.find(scoped_query({"student_id": params["student_id"]}, branch_id=bid), {"_id": 0}).to_list(200)
        original_amount = sum(float(txn.get("amount", 0)) for txn in txns if txn.get("status") in ("pending", "overdue", "unpaid"))
    actor_ctx = actor_ctx_from_user(user, branch_id=bid)
    service_params = {
        "student_id": params["student_id"],
        "discount_type_id": params["discount_type_id"],
        "original_amount": float(original_amount or 0),
        "effective_from": params["effective_from"],
        "note": params.get("note") or "",
    }
    try:
        result = await svc_apply_discount(db, actor_ctx, service_params)
    except DiscountNotFoundError:
        return _empty_result("Discount type not found.")
    except DiscountValidationError as e:
        return {"success": False, "message": str(e)}
    if result["status"] == "pending":
        return {"success": True, "pending_approval": True, "data": result["data"], "message": result["message"]}
    return {"success": True, "data": result["data"], "message": "Discount applied."}


async def tool_decide_approval_request(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.approvals_service.decide_approval_request — the SAME
    # write path as the REST decide route. Story A.3: the routing-dependent authority
    # check (owner decides any; principal only owner_and_principal) is now enforced in
    # the service for the AI path too (it was previously skipped — a real hole).
    required = ("request_id", "decision", "reason")
    if any(not params.get(field) for field in required):
        return {"success": False, "message": "request_id, decision, and reason are required."}
    decision_map = {"approve": "approved", "approved": "approved", "reject": "rejected", "rejected": "rejected"}
    status = decision_map.get(str(params["decision"]).lower())
    if not status:
        return {"success": False, "message": "decision must be approve or reject."}

    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {"approval_id": params["request_id"], "status": status, "reason": params["reason"]}
    try:
        result = await decide_approval_request(db, actor_ctx, service_params)
    except ApprovalNotFoundError:
        return _empty_result("Approval request not found.")
    except ApprovalAuthorizationError:
        return {"success": False, "message": "You are not authorized to decide this approval request."}
    except ApprovalValidationError as e:
        return {"success": False, "message": str(e)}

    update = {k: v for k, v in (result["approval"] or {}).items() if k in ("status", "decision_reason", "decided_by", "decided_at", "unread_for")}
    return {"success": True, "data": {"request_id": params["request_id"], **update}, "message": f"Approval request {status}."}


async def tool_confirm_resolution(params: dict, user: dict, scope: dict = None) -> dict:
    if not params.get("request_id") or not params.get("confirmation_note"):
        return {"success": False, "message": "request_id and confirmation_note are required."}
    # Thin adapter over services.incident_service.confirm_resolution — the SAME write
    # path as POST /api/issues/facility/{id}/confirm-resolution (Story C.3).
    db = get_db()
    bid = _branch_id(user, scope)
    actor_ctx = actor_ctx_from_user(user, branch_id=bid)
    try:
        result = await svc_confirm_resolution(db, actor_ctx, {
            "request_id": params["request_id"],
            "confirmation_note": params["confirmation_note"],
        })
    except IncidentNotFoundError:
        return _empty_result("Facility request not found.")
    except IncidentValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": {"request_id": params["request_id"], **result["update"]}, "message": "Resolution confirmed."}


async def tool_record_fee_payment(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.fees_service.record_payment — the SAME write path as
    # POST /api/fees/transactions. Story B.1: the AI path now supports partial payments,
    # is idempotent (no double-charge on confirm retry), and emits the SSE update.
    required = ("student_id", "amount", "fee_head", "mode")
    if any(params.get(field) in (None, "") for field in required):
        return {"success": False, "message": "student_id, amount, fee_head, and mode are required."}
    from routes.fees import _publish_fee_update

    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {
        "student_id": params["student_id"],
        "amount": params["amount"],
        "payment_mode": params["mode"],
        "fee_period": params.get("fee_period", date.today().strftime("%Y-%m")),
        "fee_head": params["fee_head"],
        "paid_amount": params.get("paid_amount"),
        "due_date": params.get("due_date"),
        "transaction_ref": params.get("transaction_ref"),
        "status": params.get("status"),
    }
    try:
        result = await record_payment(db, actor_ctx, service_params, publish_fn=_publish_fee_update)
    except FeeValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["data"], "message": "Fee payment recorded."}


async def tool_create_student(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.student_service.create_student — the SAME write path
    # as POST /api/students/ (Story J.1 / AD7). School-scoped (no branch); the
    # student result is DPDP-redacted by _safe_tool_result_for_chat before re-entering the LLM.
    if not (params.get("name") and params.get("class_id")):
        return {"success": False, "message": "name and class_id are required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_student(db, actor_ctx, params)
    except StudentConflictError as e:
        return {"success": False, "message": str(e)}
    except (StudentNotFoundError, ClassNotFoundError):
        return _empty_result("Class not found.")
    except (StudentValidationError, ClassValidationError) as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["student"], "message": "Student created."}


async def tool_update_student(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.student_service.update_student — the SAME write path
    # as PATCH /api/students/{id} (Story J.1 / AD7).
    if not params.get("student_id"):
        return {"success": False, "message": "student_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_student(db, actor_ctx, params)
    except StudentNotFoundError:
        return _empty_result("Student not found.")
    except ClassNotFoundError:
        return _empty_result("Class not found.")
    except StudentConflictError as e:
        return {"success": False, "message": str(e)}
    except (StudentValidationError, ClassValidationError) as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "Student updated."
    return {"success": True, "data": result["student"], "message": msg}


async def tool_set_student_status(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.student_service.set_student_status — a soft status
    # change (e.g. active → withdrawn) via the update path. NOT a delete/erase: those
    # stay UI-only (AD15) and have no AI tool.
    if not params.get("student_id") or not params.get("status"):
        return {"success": False, "message": "student_id and status are required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_set_student_status(db, actor_ctx, params)
    except StudentNotFoundError:
        return _empty_result("Student not found.")
    except StudentValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else f"Student status set to {params['status']}."
    return {"success": True, "data": result["student"], "message": msg}


async def tool_manage_student_guardians(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.student_service.upsert_guardians — the SAME write path
    # as PUT /api/students/{id}/guardians (Story J.1 / AD7). Replaces all guardians.
    if not params.get("student_id"):
        return {"success": False, "message": "student_id is required."}
    guardians = params.get("guardians")
    if not isinstance(guardians, list):
        return {"success": False, "message": "guardians must be a list of guardian objects."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_upsert_guardians(db, actor_ctx, params)
    except StudentNotFoundError:
        return _empty_result("Student not found.")
    except StudentValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["guardians"], "message": "Guardians updated."}


async def tool_create_staff(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.staff_service.create_staff — the SAME write path as
    # POST /api/staff/ (Story J.2 / AD7). The plaintext temporary password is NEVER
    # surfaced to the LLM/chat — it is delivered out-of-band via the panel.
    if not (params.get("name") and params.get("staff_type")):
        return {"success": False, "message": "name and staff_type are required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_staff(db, actor_ctx, params)
    except StaffAuthorizationError as e:
        return {"success": False, "message": str(e)}
    except LinkedUserNotFoundError:
        return _empty_result("Linked user account not found.")
    except StaffValidationError as e:
        return {"success": False, "message": str(e)}
    message = "Staff created."
    if result.get("temporary_password"):
        message += " A temporary password was issued; deliver it to the staff member via the staff panel."
    return {"success": True, "data": result["staff"], "message": message}


async def tool_update_staff(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.staff_service.update_staff — the SAME write path as
    # PATCH /api/staff/{id} (Story J.2 / AD7). OWNER_ONLY_FIELDS protections preserved.
    if not params.get("staff_id"):
        return {"success": False, "message": "staff_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_staff(db, actor_ctx, params)
    except StaffNotFoundError:
        return _empty_result("Staff not found.")
    except StaffAuthorizationError as e:
        return {"success": False, "message": str(e)}
    except StaffValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "Staff updated."
    return {"success": True, "data": result["staff"], "message": msg}


# ──────────────── Epic K.1: fee-config CRUD (Owner + Principal only) ─────────────


async def tool_create_fee_structure(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.fee_config_service.create_fee_structure — the SAME
    # write path as POST /api/fees/structures (Story K.1 / AD7). School-scoped.
    if not params.get("name"):
        return {"success": False, "message": "name is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_fee_structure(db, actor_ctx, params)
    except FeeConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["structure"], "message": "Fee structure created."}


async def tool_update_fee_structure(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.fee_config_service.update_fee_structure (Story K.1 / AD7).
    if not params.get("structure_id"):
        return {"success": False, "message": "structure_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_fee_structure(db, actor_ctx, params)
    except FeeConfigNotFoundError:
        return _empty_result("Fee structure not found.")
    except FeeConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Fee structure updated."}


async def tool_create_discount_type(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.fee_config_service.create_discount_type (Story K.1 / AD7).
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_discount_type(db, actor_ctx, params)
    except FeeConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["discount_type"], "message": "Discount type created."}


async def tool_update_discount_type(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.fee_config_service.update_discount_type (Story K.1 / AD7).
    if not params.get("discount_type_id"):
        return {"success": False, "message": "discount_type_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_discount_type(db, actor_ctx, params)
    except FeeConfigNotFoundError:
        return _empty_result("Discount type not found.")
    except FeeConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["discount_type"], "message": "Discount type updated."}


async def tool_delete_discount_type(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over services.fee_config_service.delete_discount_type (Story K.1 / AD7).
    # DESTRUCTIVE: routed through F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("discount_type_id"):
        return {"success": False, "message": "discount_type_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_delete_discount_type(db, actor_ctx, params)
    except FeeConfigNotFoundError:
        return _empty_result("Discount type not found.")
    except FeeConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Discount type deleted."}


# ──────────── Epic K.2: academic-structure CRUD (Owner + Principal only) ─────────


async def tool_create_class(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over academic_structure_service.create_class (Story K.2 / AD7).
    # Branch-scoped: owner = cross-branch, principal = own branch.
    if not params.get("name"):
        return {"success": False, "message": "name is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id(), branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_class(db, actor_ctx, params)
    except AcademicStructureValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["class"], "message": "Class created."}


async def tool_update_class(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over academic_structure_service.update_class (Story K.2 / AD7).
    if not params.get("class_id"):
        return {"success": False, "message": "class_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id(), branch_id=_branch_id(user, scope))
    try:
        result = await svc_update_class(db, actor_ctx, params)
    except AcademicStructureNotFoundError:
        return _empty_result("Class not found.")
    except AcademicStructureValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "Class updated."
    return {"success": True, "data": result["class"], "message": msg}


async def tool_delete_class(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over academic_structure_service.delete_class (Story K.2 / AD7).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("class_id"):
        return {"success": False, "message": "class_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id(), branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_class(db, actor_ctx, params)
    except AcademicStructureNotFoundError:
        return _empty_result("Class not found.")
    except AcademicStructureConflictError as e:
        return {"success": False, "message": str(e)}
    except AcademicStructureValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Class deleted."}


async def tool_create_house(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over academic_structure_service.create_house (Story K.2 / AD7).
    if not params.get("name"):
        return {"success": False, "message": "name is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_house(db, actor_ctx, params)
    except AcademicStructureValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["house"], "message": "House created."}


async def tool_update_house(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over academic_structure_service.update_house (Story K.2 / AD7).
    if not params.get("house_id"):
        return {"success": False, "message": "house_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_update_house(db, actor_ctx, params)
    except AcademicStructureNotFoundError:
        return _empty_result("House not found.")
    except AcademicStructureValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "House updated."
    return {"success": True, "data": result["house"], "message": msg}


async def tool_delete_house(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over academic_structure_service.delete_house (Story K.2 / AD7).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("house_id"):
        return {"success": False, "message": "house_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_delete_house(db, actor_ctx, params)
    except AcademicStructureNotFoundError:
        return _empty_result("House not found.")
    except AcademicStructureConflictError as e:
        return {"success": False, "message": str(e)}
    except AcademicStructureValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "House deleted."}


# ──────────── Epic K.3: org-config CRUD (Owner authority only) ───────────────────


async def tool_create_branch(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over org_config_service.create_branch (Story K.3 / AD7). Owner-only.
    if not params.get("name"):
        return {"success": False, "message": "name is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_create_branch(db, actor_ctx, params)
    except OrgConfigConflictError as e:
        return {"success": False, "message": str(e)}
    except OrgConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["branch"], "message": "Branch created."}


async def tool_update_branch(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over org_config_service.upsert_branch (Story K.3 / AD7). Owner-only.
    if not params.get("branch_id"):
        return {"success": False, "message": "branch_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_upsert_branch(db, actor_ctx, params)
    except OrgConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["branch"], "message": "Branch updated."}


async def tool_delete_branch(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over org_config_service.delete_branch (Story K.3 / AD7). Owner-only.
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("branch_id"):
        return {"success": False, "message": "branch_id is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        result = await svc_delete_branch(db, actor_ctx, params)
    except OrgConfigNotFoundError:
        return _empty_result("Branch not found.")
    except OrgConfigConflictError as e:
        return {"success": False, "message": str(e)}
    except OrgConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Branch deleted."}


async def tool_update_school_settings(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over org_config_service.update_school_settings (Story K.3 / AD7). Owner-only.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    result = await svc_update_school_settings(db, actor_ctx, params)
    return {"success": True, "data": result, "message": "School settings updated."}


async def tool_year_end_transition(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over org_config_service.year_end_transition (Story K.3 / AD7). Owner-only.
    # HIGH-IMPACT: F.10 two-step confirm at the chat layer.
    if not params.get("new_year_name"):
        return {"success": False, "message": "new_year_name is required."}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, school_id=get_school_id())
    try:
        data = await svc_year_end_transition(db, actor_ctx, params)
    except OrgConfigValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": data, "message": data["message"]}


async def tool_mark_attendance(params: dict, user: dict, scope: dict = None) -> dict:
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
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {
        "class_id": class_id,
        "date": target_date,
        "records": [{"student_id": item["student_id"], "status": item["status"]} for item in params["attendance"]],
    }
    result = await mark_attendance(db, actor_ctx, service_params)
    return {"success": True, "data": result["results"], "message": "Attendance marked."}


async def tool_query_dashboard_summary(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    today = date.today().isoformat()
    bid = _branch_id(user, scope)
    data = [{
        "open_incidents": await db.incidents.count_documents(scoped_query({"status": {"$ne": "closed"}}, branch_id=bid)),
        "pending_approvals": await db.approval_requests.count_documents(scoped_query({"status": "pending"}, branch_id=bid)),
        "staff_absent_today": await db.staff_attendance.count_documents(scoped_query({"date": today, "status": "absent"}, branch_id=bid)),
        "fee_outstanding_transactions": await db.fee_transactions.count_documents(scoped_query({"status": {"$in": ["pending", "overdue", "unpaid"]}}, branch_id=bid)),
    }]
    return _ok(data, 0, "Dashboard summary ready.")


async def tool_query_attendance_status(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    target_date = params.get("date", date.today().isoformat())
    bid = _branch_id(user, scope)
    records = await db.staff_attendance.find(scoped_query({"date": target_date}, branch_id=bid), {"_id": 0}).to_list(500)
    return _ok(records, 0, "Staff attendance status ready.")


async def tool_query_fee_status(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    bid = _branch_id(user, scope)
    base: dict = {}
    if params.get("student_id"):
        base["student_id"] = params["student_id"]
    if params.get("status"):
        base["status"] = params["status"]
    query = scoped_query(base, branch_id=bid)
    txns = await db.fee_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return _ok(txns, 0, "Fee status ready.")


async def tool_query_incidents(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    bid = _branch_id(user, scope)
    query: dict = {}
    if params.get("status"):
        query["status"] = params["status"]
    incidents = await db.incidents.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(100)
    complaints = await db.complaints.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(100)
    visitors = await db.visitor_log.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("time_in", -1).to_list(100)
    return _ok([{"incidents": incidents, "complaints": complaints, "visitors": visitors}], 0, "Incident data ready.")


async def tool_query_staff_availability(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    bid = _branch_id(user, scope)
    staff = await db.staff.find(scoped_query({"is_active": {"$ne": False}, "staff_type": "teacher"}, branch_id=bid), {"_id": 0}).to_list(500)
    return _ok(staff, 0, "Staff availability ready.")


async def tool_query_maintenance_requests(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    bid = _branch_id(user, scope)
    query: dict = {}
    if params.get("status"):
        query["status"] = params["status"]
    if _is_maintenance(user):
        query["logged_by"] = user.get("id")
    items = await db.facility_requests.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(100)
    return _ok(items, 0, "Maintenance requests ready.")


async def tool_query_student_record(params: dict, user: dict, scope: dict = None) -> dict:
    if not params.get("student_id"):
        return {"success": False, "message": "student_id is required."}
    db = get_db()
    bid = _branch_id(user, scope)
    student = await db.students.find_one(scoped_query({"id": params["student_id"]}, branch_id=bid), {"_id": 0})
    if not student:
        return _empty_result("Student not found.")
    data = {"student": student}
    if _is_accountant(user) or user.get("role") == "owner" or _is_principal(user):
        data["fees"] = await db.fee_transactions.find(scoped_query({"student_id": params["student_id"]}, branch_id=bid), {"_id": 0}).to_list(100)
    if user.get("role") == "owner" or _is_principal(user) or user.get("sub_category") == "transport_head":
        data["transport"] = {"route_zone_id": student.get("route_zone_id")}
    return _ok([data], 0, "Student record ready.")


async def tool_query_audit_log(params: dict, user: dict, scope: dict = None) -> dict:
    db = get_db()
    bid = _branch_id(user, scope)
    base: dict = {}
    if params.get("collection"):
        base["collection"] = params["collection"]
    if user.get("role") != "owner":
        base["changed_by"] = user.get("id")
    query = scoped_query(base, branch_id=bid)
    items = await db.audit_logs.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return _ok(items, 0, "Audit log ready.")


_AUDIENCE_ROLE_MAP = {
    "all": ["teacher", "student", "admin", "parent"],
    "staff": ["admin", "teacher"],
    "students": ["student"],
    "parents": ["parent"],
}

async def tool_get_timetable(params: dict, user: dict, scope: dict = None) -> dict:
    """Get class timetable for a specific day. Works for teachers (their classes) and admins (any class)."""
    t0 = time.time()
    db = get_db()
    bid = _branch_id(user, scope)

    # Determine which class to show
    class_name = params.get("class_name") or params.get("class")
    target_date = params.get("date", date.today().isoformat())
    day_name = params.get("day") or date.fromisoformat(target_date).strftime("%A")  # Monday, Tuesday, etc.

    # Find the class
    if class_name:
        cls = await db.classes.find_one(scoped_query(
            {"name": {"$regex": re.escape(class_name), "$options": "i"}}, branch_id=bid
        ))
    elif _scope_class_ids(scope):
        # Teacher: first assigned class
        class_ids = _scope_class_ids(scope)
        cls = await db.classes.find_one(scoped_query({"id": {"$in": class_ids}}, branch_id=bid))
    else:
        cls = None

    if not cls:
        return _empty_result("No class found. Please specify a class name.", (time.time() - t0) * 1000)

    class_id = cls["id"]

    # Fetch timetable slots for this class and day
    slots = await db.timetable_slots.find(
        scoped_query({"class_id": class_id, "day": {"$regex": f"^{day_name}", "$options": "i"}}, branch_id=bid),
        {"_id": 0}
    ).sort("period_number", 1).to_list(10)

    if not slots:
        return _empty_result(f"No timetable found for {cls.get('name')} {cls.get('section','')} on {day_name}.", (time.time() - t0) * 1000)

    # Enrich with teacher names
    results = []
    for s in slots:
        teacher_name = "TBD"
        if s.get("teacher_id"):
            staff = await db.staff.find_one({"id": s["teacher_id"]}, {"_id": 0, "name": 1})
            if staff:
                teacher_name = staff["name"]
        results.append({
            "period": s.get("period_number", "?"),
            "time": f"{s.get('start_time','?')}–{s.get('end_time','?')}",
            "subject": s.get("subject", "?"),
            "teacher": teacher_name,
            "room": s.get("room", ""),
        })

    elapsed = (time.time() - t0) * 1000
    return _ok(results, elapsed, f"Timetable for {cls.get('name')} {cls.get('section','')} — {day_name}")


async def tool_get_exam_results_summary(params: dict, user: dict, scope: dict = None) -> dict:
    """Get exam performance summary for a class or subject. For teachers and admins."""
    t0 = time.time()
    db = get_db()
    bid = _branch_id(user, scope)

    exam_name = params.get("exam_name") or params.get("exam")
    class_name = params.get("class_name") or params.get("class")
    subject = params.get("subject")

    # Find the exam
    exam_query = {}
    if exam_name:
        exam_query["name"] = {"$regex": re.escape(exam_name), "$options": "i"}

    # Apply class filter via scope
    class_ids = _scope_class_ids(scope) if _scope_class_ids(scope) else None
    if class_name:
        cls = await db.classes.find_one(scoped_query(
            {"name": {"$regex": re.escape(class_name), "$options": "i"}}, branch_id=bid
        ))
        if cls:
            exam_query["class_id"] = cls["id"]
    elif class_ids:
        exam_query["class_id"] = {"$in": class_ids}

    if subject:
        exam_query["subject"] = {"$regex": re.escape(subject), "$options": "i"}

    exams = await db.exams.find(
        scoped_query(exam_query, branch_id=bid), {"_id": 0}
    ).sort("exam_date", -1).to_list(5)

    if not exams:
        return _empty_result("No exams found matching the criteria.", (time.time() - t0) * 1000)

    results = []
    for exam in exams:
        # Get results for this exam
        exam_results = await db.exam_results.find(
            scoped_query({"exam_id": exam["id"]}, branch_id=bid),
            {"_id": 0, "student_id": 1, "marks_obtained": 1, "max_marks": 1, "grade": 1}
        ).to_list(200)

        if not exam_results:
            continue

        marks = [r["marks_obtained"] for r in exam_results if r.get("marks_obtained") is not None]
        max_marks = exam.get("max_marks", exam_results[0].get("max_marks", 100)) if exam_results else 100

        avg = round(sum(marks) / len(marks), 1) if marks else 0
        highest = max(marks) if marks else 0
        lowest = min(marks) if marks else 0
        passed = sum(1 for m in marks if m >= max_marks * 0.33)  # 33% passing

        results.append({
            "exam": exam.get("name", "Unnamed Exam"),
            "subject": exam.get("subject", ""),
            "date": exam.get("exam_date", ""),
            "students": len(marks),
            "average": f"{avg}/{max_marks}",
            "highest": highest,
            "lowest": lowest,
            "pass_rate": f"{round(passed/len(marks)*100, 1)}%" if marks else "N/A",
        })

    elapsed = (time.time() - t0) * 1000
    return _ok(results, elapsed, f"Exam results summary — {len(results)} exam(s)")


async def tool_get_upcoming_events(params: dict, user: dict, scope: dict = None) -> dict:
    """Get upcoming school events, exams, and announcements for the next N days."""
    t0 = time.time()
    db = get_db()
    bid = _branch_id(user, scope)

    days_ahead = min(int(params.get("days", 7)), 30)
    today = date.today().isoformat()
    until = (date.today() + timedelta(days=days_ahead)).isoformat()

    events = []

    # Upcoming exams
    class_ids = _scope_class_ids(scope) if _scope_class_ids(scope) else None
    exam_query = {"exam_date": {"$gte": today, "$lte": until}}
    if class_ids:
        exam_query["class_id"] = {"$in": class_ids}

    exams = await db.exams.find(
        scoped_query(exam_query, branch_id=bid), {"_id": 0, "name": 1, "subject": 1, "exam_date": 1, "class_id": 1}
    ).sort("exam_date", 1).to_list(20)

    for e in exams:
        events.append({"date": e.get("exam_date"), "type": "exam", "title": f"{e.get('name')} — {e.get('subject')}"})

    # Upcoming announcements / events (from announcements collection)
    announcements = await db.announcements.find(
        scoped_query(
            {"event_date": {"$gte": today, "$lte": until}, "status": "published"},
            branch_id=bid
        ),
        {"_id": 0, "title": 1, "event_date": 1, "audience": 1}
    ).sort("event_date", 1).to_list(10)

    for a in announcements:
        events.append({"date": a.get("event_date", today), "type": "event", "title": a.get("title", "Event")})

    # Sort all events by date
    events.sort(key=lambda x: x.get("date", ""))

    elapsed = (time.time() - t0) * 1000
    if not events:
        return _empty_result(f"No events scheduled in the next {days_ahead} days.", elapsed)
    return _ok(events, elapsed, f"Upcoming events — next {days_ahead} days")


async def tool_draft_parent_message(params: dict, user: dict, scope: dict = None) -> dict:
    """Draft a WhatsApp/SMS message to a student's parent for a given message type."""
    t0 = time.time()
    db = get_db()
    bid = _branch_id(user, scope)

    student_id = params.get("student_id") or params.get("student")
    message_type = params.get("message_type", "general")  # fee_reminder, absence_notification, general, exam_reminder
    custom_note = params.get("note", "")

    # Find student
    if student_id:
        student = await db.students.find_one(
            scoped_query({"$or": [{"id": student_id}, {"name": {"$regex": re.escape(str(student_id)), "$options": "i"}}]}, branch_id=bid),
            {"_id": 0, "name": 1, "id": 1, "class_id": 1, "admission_number": 1}
        )
    else:
        return _empty_result("Please specify a student name or ID.", (time.time() - t0) * 1000)

    if not student:
        return _empty_result(f"Student '{student_id}' not found.", (time.time() - t0) * 1000)

    # Get guardian contacts
    guardian = await db.students.find_one(
        {"id": student["id"]},
        {"_id": 0, "guardians": 1}
    )
    guardians = (guardian or {}).get("guardians", [])
    primary_guardian = next((g for g in guardians if g.get("is_primary")), guardians[0] if guardians else {})
    guardian_name = primary_guardian.get("name", "Parent/Guardian")
    guardian_phone = primary_guardian.get("whatsapp_phone") or primary_guardian.get("phone", "Not on file")

    # Resolve class name
    cls = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0, "name": 1, "section": 1})
    class_display = f"{cls.get('name','')} {cls.get('section','')}" if cls else "the class"

    # Draft message based on type
    student_name = student.get("name", "the student")
    school_name = "The Aaryans"

    templates = {
        "fee_reminder": f"Dear {guardian_name},\n\nThis is a reminder that fee payment for {student_name} ({class_display}) is due. Kindly visit the school office or contact the accounts department to clear the outstanding dues.\n\nRegards,\n{school_name}",
        "absence_notification": f"Dear {guardian_name},\n\n{student_name} ({class_display}) was absent from school today ({date.today().strftime('%d %b %Y')}). Please ensure regular attendance.\n\nIf there is a health concern, kindly inform the class teacher.\n\nRegards,\n{school_name}",
        "exam_reminder": f"Dear {guardian_name},\n\nThis is a reminder that exams for {student_name} ({class_display}) are scheduled soon. Please ensure {student_name} is well-prepared and present on time.\n\nRegards,\n{school_name}",
        "general": f"Dear {guardian_name},\n\nWe would like to speak with you regarding {student_name} ({class_display}). Please contact the school at your earliest convenience.\n\nRegards,\n{school_name}",
    }

    draft = templates.get(message_type, templates["general"])
    if custom_note:
        draft = draft.replace("Regards,", f"{custom_note}\n\nRegards,")

    result = {
        "student": student_name,
        "guardian": guardian_name,
        "phone": guardian_phone,
        "message_type": message_type,
        "draft_message": draft,
        "char_count": len(draft),
        "note": "This is a draft. Review before sending via the SMS panel.",
    }

    elapsed = (time.time() - t0) * 1000
    return _ok([result], elapsed, f"Parent message draft — {message_type} for {student_name}")


async def tool_create_announcement(params: dict, user: dict, scope: dict = None) -> dict:
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

    # Story A.4: moderation gate centralized in services.announcement_service — the SAME
    # decision the REST route makes (EC-9.1 owner/principal broadcast directly; others gated).
    # This replaces the previously-duplicated inline gate, which over-moderated owner/principal.
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        initial_status = decide_announcement_status(actor_ctx, audience_type, audience_roles)
    except AnnouncementValidationError as e:
        return {"success": False, "message": str(e)}
    requires_approval = initial_status == "pending_approval"

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
        "status": initial_status,
        # sent_at is intentionally omitted for pending_approval announcements;
        # it will be set when the principal approves via /announcements/{id}/approve.
        "sent_at": None if requires_approval else now,
        "created_by": created_by,
        "created_by_name": user.get("name", ""),
        "created_at": now,
    })
    await db.announcements.insert_one(announcement)
    await _write_audit(db, "create_announcement", "announcements", ann_id, user, {"title": title, "audience_type": audience_type, "status": initial_status}, scope=scope)
    if requires_approval:
        return {
            "success": True,
            "data": {k: v for k, v in announcement.items() if k != "_id"},
            "message": f"Announcement '{title}' submitted for principal approval (id: {ann_id}). It will be sent once approved.",
        }
    return {"success": True, "data": {k: v for k, v in announcement.items() if k != "_id"}, "message": f"Announcement '{title}' published successfully to {audience_type}."}


# =========================================================================
#  G.5 — On-demand recall & synthesis (the pre-meeting briefing)
# =========================================================================

async def tool_recall_history(params: dict, user: dict, scope: dict = None) -> dict:
    """Synthesize a briefing on a subject from the assistant's MEMORY + the
    role-scoped operational records the caller may already read (Story G.5, FR35).

    Authorization parity (hard AC): this tool performs NO direct DB reads of
    operational records. It delegates to the EXACT existing read tools
    (`tool_get_student_profile`, `tool_get_fee_transactions`, `tool_get_enquiries`),
    passing the SAME `(user, scope)` — so the assistant can never see anything here
    it couldn't see by calling those tools directly. Memory recall is additionally
    `(user_id, schoolId)`-isolated. Minor-record reads are audited by chat.py's
    `_audit_minor_read` because `recall_history` is in `MINOR_READ_TOOLS` and this
    result carries `student_id` refs.
    """
    t0 = time.time()
    from services.actor_context import actor_ctx_from_user
    from services.memory import is_memory_subject, store as memory_store

    subject = (params.get("subject") or params.get("query") or params.get("search_term") or "").strip()
    if not subject and not params.get("student_id"):
        return _empty_result("Tell me who or what to brief you on (a student, family, or topic).", (time.time() - t0) * 1000)

    sections: dict = {}
    student_ids: list = []

    # 1) Memory recall (owner-scoped; only for Owner/Principal per Phase-1 lockdown).
    if is_memory_subject(user):
        try:
            ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
            mems = await memory_store.recall(get_db(), ctx, subject or params.get("student_id", ""))
            if mems:
                sections["remembered"] = [
                    {"text": m.get("text"), "category": m.get("category"), "uses": m.get("uses", 0)}
                    for m in mems
                ]
        except Exception as e:  # never fail the briefing on memory issues
            logger.warning("recall_history memory recall failed: %s", e)

    # 2) Student profile (reuses tool_get_student_profile authz/scope path verbatim).
    prof_params = {}
    if params.get("student_id"):
        prof_params["student_id"] = params["student_id"]
    elif subject:
        prof_params["search_term"] = subject
    profile = await tool_get_student_profile(prof_params, user, scope)
    student_id = None
    if profile.get("success") and profile.get("data"):
        rec = profile["data"][0]
        student_id = rec.get("id")
        if student_id:
            student_ids.append(student_id)
        sections["student"] = rec

    # 3) Fee history for that student (reuses tool_get_fee_transactions verbatim).
    if student_id:
        fees = await tool_get_fee_transactions({"student_id": student_id}, user, scope)
        if fees.get("success") and fees.get("data"):
            sections["fees"] = fees["data"]

    # 4) Related admission enquiries (reuses tool_get_enquiries verbatim).
    enquiries = await tool_get_enquiries({}, user, scope)
    if enquiries.get("success") and enquiries.get("data"):
        subj_low = subject.lower()
        related = [
            e for e in enquiries["data"]
            if isinstance(e, dict) and subj_low and subj_low in json.dumps(e, default=str).lower()
        ]
        if related:
            sections["enquiries"] = related

    elapsed = (time.time() - t0) * 1000
    if not sections:
        return _empty_result(f"I found no related history for '{subject}'.", elapsed)
    return {
        "success": True,
        "data": {"subject": subject or student_id, "student_id": student_id, "sections": sections},
        "meta": {"count": len(sections), "student_refs": student_ids, "query_time_ms": round(elapsed, 2)},
        "message": "",
    }


# =========================================================================
#  Missing tool functions — transport, inventory, branch comparison
# =========================================================================

async def tool_get_transport_status(params: dict, user: dict, scope: dict = None) -> dict:
    """Transport overview: routes, vehicles, drivers (owner + admin)."""
    t0 = time.time()
    db = get_db()
    query: dict = {}
    _apply_branch_filter(query, scope)
    route_filter = params.get("route_id")

    routes = await db.transport_routes.find(query, {"_id": 0}).to_list(100)

    if route_filter:
        routes = [r for r in routes if r.get("id") == route_filter]

    def _fmt(r: dict) -> dict:
        phone = r.get("driver_phone", "")
        masked = (phone[:-3] + "XXX") if len(phone) >= 4 else phone
        return {
            "id": r.get("id"),
            "route_name": r.get("route_name"),
            "driver_name": r.get("driver_name"),
            "driver_phone": masked,
            "vehicle_number": r.get("vehicle_number"),
            "stops_count": len(r.get("stops", [])),
            "fare": r.get("fare"),
            "is_active": r.get("is_active", True),
        }

    active = [r for r in routes if r.get("is_active", True)]
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": {
            "total_routes": len(routes),
            "active_routes": len(active),
            "routes": [_fmt(r) for r in active[:25]],
        },
        "meta": {"count": len(active), "query_time_ms": round(elapsed, 2)},
        "message": "",
    }


async def tool_get_inventory_status(params: dict, user: dict, scope: dict = None) -> dict:
    """Inventory overview: total items, categories, low-stock alerts."""
    t0 = time.time()
    db = get_db()
    query: dict = {}
    _apply_branch_filter(query, scope)

    category_filter = params.get("category")
    if category_filter:
        query["category"] = category_filter

    items = await db.inventory_items.find(query, {"_id": 0}).to_list(500)

    if not items:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("No inventory items found.", elapsed)

    # Aggregate by category
    cats: dict = {}
    low_stock = []
    for item in items:
        cat = item.get("category", "other")
        cats[cat] = cats.get(cat, 0) + 1
        if item.get("quantity", 0) <= item.get("min_stock", 0):
            low_stock.append({
                "name": item.get("name"),
                "category": cat,
                "quantity": item.get("quantity"),
                "min_stock": item.get("min_stock"),
                "location": item.get("location"),
            })

    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": {
            "total_items": len(items),
            "categories": cats,
            "low_stock_count": len(low_stock),
            "low_stock_items": low_stock[:20],
        },
        "meta": {"count": len(items), "query_time_ms": round(elapsed, 2)},
        "message": "",
    }


async def tool_get_branch_comparison(params: dict, user: dict, scope: dict = None) -> dict:
    """Compare key metrics across school branches (owner only)."""
    t0 = time.time()
    db = get_db()
    metric = params.get("metric", "all")

    branches = await db.branches.find({}, {"_id": 0, "id": 1, "name": 1, "is_active": 1}).to_list(20)
    if not branches:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("No branches configured.", elapsed)

    today_str = date.today().strftime("%Y-%m-%d")
    comparison = []

    for br in branches:
        bid = br.get("id")
        entry: dict = {"branch_id": bid, "branch_name": br.get("name"), "is_active": br.get("is_active", True)}

        if metric in ("all", "strength"):
            entry["total_students"] = await db.students.count_documents(
                scoped_query({"status": "active"}, branch_id=bid)
            )

        if metric in ("all", "attendance"):
            today_records = await db.attendance.count_documents(
                scoped_query({"date": today_str, "status": "present"}, branch_id=bid)
            )
            total_today = await db.attendance.count_documents(
                scoped_query({"date": today_str}, branch_id=bid)
            )
            entry["attendance_rate_today"] = (
                round(today_records / total_today * 100, 1) if total_today else None
            )

        if metric in ("all", "fees"):
            from datetime import datetime as _dt
            month_start = _dt.now().strftime("%Y-%m-01")
            fee_cur = await db.fee_transactions.find(
                scoped_query({"payment_date": {"$gte": month_start}, "status": "paid"}, branch_id=bid),
                {"_id": 0, "amount": 1}
            ).to_list(5000)
            entry["fee_collected_month"] = sum(f.get("amount", 0) for f in fee_cur)

        comparison.append(entry)

    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": {"metric": metric, "branches": comparison},
        "meta": {"count": len(comparison), "query_time_ms": round(elapsed, 2)},
        "message": "",
    }


async def tool_get_expenses(params: dict, user: dict, scope: dict = None) -> dict:
    """List recent expenses with optional category filter."""
    import time
    t0 = time.time()
    db = get_db()
    bid = user.get("branch_id")
    query: dict = {}
    category = params.get("category")
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    month = params.get("month")
    if month:
        query["date"] = {"$gte": f"{month}-01", "$lte": f"{month}-31"}
    expenses = await db.expenses.find(
        scoped_query(query, branch_id=bid), {"_id": 0}
    ).sort("date", -1).to_list(100)
    total = sum(float(e.get("amount", 0)) for e in expenses)
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": {"expenses": expenses, "total_amount": round(total, 2), "count": len(expenses)},
        "meta": {"query_time_ms": round(elapsed, 2)},
        "message": f"{len(expenses)} expense(s) totalling ₹{total:,.2f}",
    }


async def tool_create_expense(params: dict, user: dict, scope: dict = None) -> dict:
    """Log a new expense record."""
    import time, uuid as _uuid
    from datetime import datetime as _dt
    t0 = time.time()
    db = get_db()
    bid = user.get("branch_id")
    amount = params.get("amount")
    category = params.get("category")
    if not amount:
        return {"success": False, "message": "amount is required"}
    if not category:
        return {"success": False, "message": "category is required"}
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return {"success": False, "message": "amount must be a number"}
    # Budget check
    budget = await db.expense_budgets.find_one(scoped_query({"category": category}, branch_id=bid), {"_id": 0})
    if budget:
        remaining = float(budget.get("remaining_amount", budget.get("monthly_limit", 0)) or 0)
        if amount > remaining:
            return {"success": False, "message": f"Expense of ₹{amount:,.2f} exceeds remaining budget of ₹{remaining:,.2f} for '{category}'"}
    exp_id = str(_uuid.uuid4())
    expense = {
        "id": exp_id,
        "schoolId": user.get("schoolId", ""),
        "category": category,
        "description": params.get("description", ""),
        "amount": amount,
        "date": params.get("date", _dt.now().strftime("%Y-%m-%d")),
        "vendor": params.get("vendor", ""),
        "approved_by": user["id"],
        "recorded_by": user["id"],
        "created_at": _dt.now().isoformat(),
    }
    if bid:
        expense["branch_id"] = bid
    await db.expenses.insert_one({**expense, "_id": exp_id})
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": expense,
        "meta": {"query_time_ms": round(elapsed, 2)},
        "message": f"Expense of ₹{amount:,.2f} logged under '{category}'",
    }


async def tool_create_enquiry(params: dict, user: dict, scope: dict = None) -> dict:
    """Log a new admission enquiry / lead."""
    import time, uuid as _uuid
    from datetime import datetime as _dt
    t0 = time.time()
    db = get_db()
    bid = user.get("branch_id")
    student_name = params.get("student_name")
    if not student_name:
        return {"success": False, "message": "student_name is required"}
    enq_id = str(_uuid.uuid4())
    enquiry = {
        "id": enq_id,
        "schoolId": user.get("schoolId", ""),
        "student_name": student_name,
        "parent_name": params.get("parent_name", ""),
        "phone": params.get("phone", ""),
        "class_applying": params.get("class_applying", ""),
        "status": "new",
        "source": params.get("source", "walk_in"),
        "notes": params.get("notes", ""),
        "assigned_to": params.get("assigned_to", ""),
        "created_by": user["id"],
        "created_at": _dt.now().isoformat(),
        "updated_at": _dt.now().isoformat(),
    }
    if bid:
        enquiry["branch_id"] = bid
    await db.enquiries.insert_one({**enquiry, "_id": enq_id})
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": enquiry,
        "meta": {"query_time_ms": round(elapsed, 2)},
        "message": f"Enquiry for '{student_name}' created (status: new)",
    }


async def tool_update_enquiry_status(params: dict, user: dict, scope: dict = None) -> dict:
    """Advance or update an admission enquiry through the pipeline."""
    import time
    from datetime import datetime as _dt
    t0 = time.time()
    db = get_db()
    bid = user.get("branch_id")
    enquiry_id = params.get("enquiry_id")
    new_status = params.get("status")
    if not enquiry_id:
        return {"success": False, "message": "enquiry_id is required"}
    if not new_status:
        return {"success": False, "message": "status is required"}
    VALID_STATUSES = ("new", "contacted", "visit_scheduled", "visited", "documents_submitted", "fee_paid", "enrolled", "lost")
    if new_status not in VALID_STATUSES:
        return {"success": False, "message": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}
    existing = await db.enquiries.find_one(scoped_query({"id": enquiry_id}, branch_id=bid), {"_id": 0})
    if not existing:
        return {"success": False, "message": f"Enquiry {enquiry_id} not found"}
    update: dict = {
        "status": new_status,
        "updated_at": _dt.now().isoformat(),
        "updated_by": user["id"],
    }
    if params.get("notes"):
        update["notes"] = params["notes"]
    if params.get("assigned_to"):
        update["assigned_to"] = params["assigned_to"]
    await db.enquiries.update_one(scoped_query({"id": enquiry_id}, branch_id=bid), {"$set": update})
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": {**existing, **update},
        "meta": {"query_time_ms": round(elapsed, 2)},
        "message": f"Enquiry for '{existing.get('student_name', enquiry_id)}' status → {new_status}",
    }


async def tool_create_incident(params: dict, user: dict, scope: dict = None) -> dict:
    """Log a new incident, visitor entry, or disciplinary event."""
    import time, uuid as _uuid
    from datetime import datetime as _dt
    t0 = time.time()
    db = get_db()
    bid = user.get("branch_id")
    description = params.get("description")
    if not description:
        return {"success": False, "message": "description is required"}
    severity = params.get("severity", "low")
    if severity not in ("low", "medium", "high"):
        return {"success": False, "message": "severity must be low, medium, or high"}
    assigned_to = "principal" if severity == "high" else params.get("assigned_to", None)
    inc_id = str(_uuid.uuid4())
    incident = {
        "id": inc_id,
        "schoolId": user.get("schoolId", ""),
        "title": params.get("title", ""),
        "description": description,
        "severity": severity,
        "involved_parties": params.get("involved_parties", ""),
        "category": params.get("category", "general"),
        "status": "open",
        "thread": [],
        "logged_by": user["id"],
        "logged_by_name": user.get("name", ""),
        "assigned_to": assigned_to,
        "due_date": None,
        "created_at": _dt.now().isoformat(),
        "updated_at": _dt.now().isoformat(),
    }
    if bid:
        incident["branch_id"] = bid
    await db.incidents.insert_one({**incident, "_id": inc_id})
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": incident,
        "meta": {"query_time_ms": round(elapsed, 2)},
        "message": f"Incident logged (severity: {severity}" + (", auto-assigned to principal" if assigned_to == "principal" else "") + ")",
    }


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
    "recall_history": {
        "fn": tool_recall_history,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": (
            "Synthesize a briefing on a student/family/topic from what you remember "
            "PLUS the records the user may already read (e.g. before a meeting). "
            "Read-only; reuses existing read-tool scoping."
        ),
        "params_schema": {
            "subject": {"type": "string", "description": "Who/what to brief on (name, family, or topic)"},
            "student_id": {"type": "string", "description": "Optional exact student ID"},
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
    "get_transport_status": {
        "fn": tool_get_transport_status,
        "roles": ["owner", "admin"],
        "description": "Transport overview: active routes, vehicles, driver assignments.",
        "params_schema": {
            "route_id": {"type": "string", "description": "Optional route ID to filter"},
        },
    },
    "get_inventory_status": {
        "fn": tool_get_inventory_status,
        "roles": ["owner", "admin"],
        "description": "Inventory overview: total items, categories, low-stock alerts.",
        "params_schema": {
            "category": {"type": "string", "description": "Optional category filter (furniture, it_equipment, sports, stationery, etc.)"},
        },
    },
    "get_branch_comparison": {
        "fn": tool_get_branch_comparison,
        "roles": ["owner"],
        "description": "Compare key metrics (strength, attendance, fees) across all school branches. Owner only.",
        "params_schema": {
            "metric": {"type": "string", "description": "attendance | fees | strength | all (default: all)"},
        },
    },

    # ---- Appendix A formal dispatch table ----
    "assign_followup": {
        "fn": tool_assign_followup,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
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
        "sub_categories": ["principal"],
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
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
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
        "sub_categories": ["principal"],
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
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
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
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
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
        "sub_categories": ["accountant"],
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
    # ---- Epic J: student CRUD (Owner + Principal only; Phase-1 lockdown applies) ----
    "create_student": {
        "fn": tool_create_student,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Create a new student record (with optional guardians) in the school database.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Student full name (required)"},
            "class_id": {"type": "string", "description": "Class ID the student joins (required)"},
            "admission_number": {"type": "string", "description": "Admission number (auto-generated if omitted)"},
            "roll_number": {"type": "string", "description": "Roll number"},
            "dob": {"type": "string", "description": "Date of birth YYYY-MM-DD"},
            "gender": {"type": "string", "description": "Gender"},
            "father_name": {"type": "string", "description": "Father name (with father_phone creates a guardian)"},
            "father_phone": {"type": "string", "description": "Father phone"},
            "mother_name": {"type": "string", "description": "Mother name (with mother_phone creates a guardian)"},
            "mother_phone": {"type": "string", "description": "Mother phone"},
        },
    },
    "update_student": {
        "fn": tool_update_student,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Update fields on an existing student record. Does NOT delete or erase students (UI-only).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID (required)"},
            "name": {"type": "string", "description": "Updated name"},
            "class_id": {"type": "string", "description": "Move to class ID"},
            "roll_number": {"type": "string", "description": "Roll number"},
            "house": {"type": "string", "description": "House assignment"},
            "photo_url": {"type": "string", "description": "Photo URL"},
        },
    },
    "set_student_status": {
        "fn": tool_set_student_status,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Set a student's status (e.g. active, withdrawn). Soft status change only — never a delete or DPDP-erase.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID (required)"},
            "status": {"type": "string", "description": "New status, e.g. active or withdrawn (required)"},
        },
    },
    "manage_student_guardians": {
        "fn": tool_manage_student_guardians,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Replace the guardian list for a student (each guardian needs name + phone).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID (required)"},
            "guardians": {"type": "array", "description": "List of {name, phone, relation, email, occupation, is_primary}"},
        },
    },
    # ---- Epic J: staff CRUD (Owner + Principal only; Phase-1 lockdown applies) ----
    "create_staff": {
        "fn": tool_create_staff,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Create a new staff member (auto-creates a login account). Only an owner may create privileged (owner/admin) accounts.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Staff full name (required)"},
            "staff_type": {"type": "string", "description": "e.g. teacher, accountant, receptionist (required)"},
            "role": {"type": "string", "description": "Login role (owner-only for owner/admin)"},
            "sub_category": {"type": "string", "description": "Admin sub-category (owner-only)"},
            "employee_id": {"type": "string", "description": "Employee ID"},
            "phone": {"type": "string", "description": "Phone"},
            "email": {"type": "string", "description": "Email"},
            "department": {"type": "string", "description": "Department"},
        },
    },
    "update_staff": {
        "fn": tool_update_staff,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Update an existing staff member's profile. role/sub_category/salary are owner-only and silently ignored otherwise.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "staff_id": {"type": "string", "description": "Staff ID (required)"},
            "name": {"type": "string", "description": "Updated name"},
            "phone": {"type": "string", "description": "Phone"},
            "email": {"type": "string", "description": "Email"},
            "department": {"type": "string", "description": "Department"},
            "qualification": {"type": "string", "description": "Qualification"},
        },
    },
    # ---- Epic K.1: fee-config CRUD (Owner + Principal only; Phase-1 lockdown) ----
    "create_fee_structure": {
        "fn": tool_create_fee_structure,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Create a fee structure (fee heads) for a class.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Structure name (required)"},
            "class_id": {"type": "string", "description": "Class ID this structure applies to"},
            "fee_heads": {"type": "array", "description": "List of {name, amount, frequency} fee heads"},
            "academic_year": {"type": "string", "description": "Academic year, e.g. 2026-27"},
        },
    },
    "update_fee_structure": {
        "fn": tool_update_fee_structure,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Update an existing fee structure's fields.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "structure_id": {"type": "string", "description": "Fee structure ID (required)"},
            "name": {"type": "string", "description": "Updated name"},
            "fee_heads": {"type": "array", "description": "Updated fee heads list"},
            "academic_year": {"type": "string", "description": "Academic year"},
        },
    },
    "create_discount_type": {
        "fn": tool_create_discount_type,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Create a fee discount type (e.g. sibling, staff-ward).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Discount name (required)"},
            "value": {"type": "number", "description": "Discount value (required)"},
            "value_type": {"type": "string", "description": "flat or percentage (required)"},
            "recurrence": {"type": "string", "description": "e.g. one-time or recurring (required)"},
            "reason_note": {"type": "string", "description": "Reason for the discount type (required)"},
        },
    },
    "update_discount_type": {
        "fn": tool_update_discount_type,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Update a discount type (name, active state, or reason note).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "discount_type_id": {"type": "string", "description": "Discount type ID (required)"},
            "name": {"type": "string", "description": "Updated name"},
            "is_active": {"type": "boolean", "description": "Activate/deactivate the discount type"},
            "reason_note": {"type": "string", "description": "Updated reason note"},
        },
    },
    "delete_discount_type": {
        "fn": tool_delete_discount_type,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Permanently delete a discount type. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "discount_type_id": {"type": "string", "description": "Discount type ID to delete (required)"},
        },
    },
    # ---- Epic K.2: academic-structure CRUD (Owner + Principal only; lockdown) ----
    "create_class": {
        "fn": tool_create_class,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Create a class (with an optional section).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Class name, e.g. 'Class 5' (required)"},
            "section": {"type": "string", "description": "Section, e.g. 'A'"},
            "academic_year_id": {"type": "string", "description": "Academic year ID"},
            "class_teacher_id": {"type": "string", "description": "Class teacher staff ID"},
            "room_number": {"type": "string", "description": "Room number"},
        },
    },
    "update_class": {
        "fn": tool_update_class,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Update a class's fields (name, section, teacher, room).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "class_id": {"type": "string", "description": "Class ID (required)"},
            "name": {"type": "string", "description": "Updated class name"},
            "section": {"type": "string", "description": "Updated section"},
            "class_teacher_id": {"type": "string", "description": "Class teacher staff ID"},
            "room_number": {"type": "string", "description": "Room number"},
        },
    },
    "delete_class": {
        "fn": tool_delete_class,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Permanently delete a class. Destructive — requires a second confirmation. Blocked if active students are assigned.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "class_id": {"type": "string", "description": "Class ID to delete (required)"},
        },
    },
    "create_house": {
        "fn": tool_create_house,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Create a house.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "House name (required)"},
            "colour": {"type": "string", "description": "House colour"},
        },
    },
    "update_house": {
        "fn": tool_update_house,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Update a house's name or colour (not its points).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "house_id": {"type": "string", "description": "House ID (required)"},
            "name": {"type": "string", "description": "Updated name"},
            "colour": {"type": "string", "description": "Updated colour"},
        },
    },
    "delete_house": {
        "fn": tool_delete_house,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Permanently delete a house. Destructive — requires a second confirmation. Blocked if active students are assigned.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "house_id": {"type": "string", "description": "House ID to delete (required)"},
        },
    },
    # ---- Epic K.3: org-config CRUD (Owner authority only — even in Phase 2) ----
    "create_branch": {
        "fn": tool_create_branch,
        "roles": ["owner"],
        "description": "Create a new school branch (owner only).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Branch name (required)"},
            "branch_code": {"type": "string", "description": "Unique branch code"},
            "location": {"type": "string", "description": "Branch location"},
        },
    },
    "update_branch": {
        "fn": tool_update_branch,
        "roles": ["owner"],
        "description": "Update (or create-by-id) a school branch (owner only).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "branch_id": {"type": "string", "description": "Branch ID (required)"},
            "name": {"type": "string", "description": "Branch name (required)"},
            "address": {"type": "string", "description": "Address"},
            "phone": {"type": "string", "description": "Phone"},
            "is_active": {"type": "boolean", "description": "Active state"},
        },
    },
    "delete_branch": {
        "fn": tool_delete_branch,
        "roles": ["owner"],
        "description": "Permanently delete a branch (owner only). Destructive — requires a second confirmation. Blocked if active students are assigned.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "branch_id": {"type": "string", "description": "Branch ID to delete (required)"},
        },
    },
    "update_school_settings": {
        "fn": tool_update_school_settings,
        "roles": ["owner"],
        "description": "Update school-level settings (name, board, city, attendance threshold, AI context) — owner only.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "school_name": {"type": "string", "description": "School name"},
            "board": {"type": "string", "description": "Board, e.g. CBSE"},
            "city": {"type": "string", "description": "City"},
            "attendance_threshold": {"type": "number", "description": "Attendance % threshold"},
            "ai_context": {"type": "string", "description": "AI assistant context note"},
        },
    },
    "year_end_transition": {
        "fn": tool_year_end_transition,
        "roles": ["owner"],
        "description": "Transition the school to a new academic year (owner only). High-impact — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "new_year_name": {"type": "string", "description": "New academic year, e.g. 2026-27 (required)"},
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
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
        "sub_categories": ["principal"],
        "description": "Current staff attendance status from biometric feed.",
        "params_schema": {
            "date": {"type": "string", "description": "Optional date YYYY-MM-DD"},
        },
    },
    "query_fee_status": {
        "fn": tool_query_fee_status,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant", "principal"],
        "description": "Fee status, defaulters, and overdue list for a student or cohort.",
        "params_schema": {
            "student_id": {"type": "string", "description": "Optional student ID"},
            "status": {"type": "string", "description": "Optional fee status"},
        },
    },
    "query_incidents": {
        "fn": tool_query_incidents,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Open complaints, incidents, or visitor logs by status/date/person.",
        "params_schema": {
            "status": {"type": "string", "description": "Optional status"},
        },
    },
    "query_staff_availability": {
        "fn": tool_query_staff_availability,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Available staff for a given period, filtered against timetable.",
        "params_schema": {
            "period_id": {"type": "string", "description": "Optional period ID"},
        },
    },
    "query_maintenance_requests": {
        "fn": tool_query_maintenance_requests,
        "roles": ["owner", "admin"],
        "sub_categories": ["maintenance"],
        "description": "Open facility requests by status, date, or location.",
        "params_schema": {
            "status": {"type": "string", "description": "Optional status"},
        },
    },
    "query_student_record": {
        "fn": tool_query_student_record,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal", "accountant", "transport_head"],
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
        "sub_categories": ["principal"],
        "description": "Publish a school announcement to all parents, students, and staff.",
        "params_schema": {
            "title": {"type": "string", "description": "Announcement title"},
            "content": {"type": "string", "description": "Full announcement message"},
            "audience_type": {"type": "string", "description": "all, parents, students, staff — default: all"},
        },
        "requires_confirmation": True,
        "dispatch_type": "write",
    },

    # ---- 4 new high-impact tools ----
    "get_timetable": {
        "fn": tool_get_timetable,
        "roles": ["owner", "admin", "teacher"],
        "description": "Get the class timetable for a specific day. Specify class name and optionally a day of week or date.",
        "params_schema": {
            "class_name": {"type": "string", "description": "class name (e.g. 'Class 9A')"},
            "day": {"type": "string", "description": "day of week (Monday/Tuesday/etc.) or leave blank for today"},
            "date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
        },
        "requires_confirmation": False,
    },
    "get_exam_results_summary": {
        "fn": tool_get_exam_results_summary,
        "roles": ["owner", "admin", "teacher"],
        "description": "Get exam performance analytics for a class or subject — averages, pass rate, highest/lowest marks.",
        "params_schema": {
            "exam_name": {"type": "string", "description": "exam name filter"},
            "class_name": {"type": "string", "description": "class name"},
            "subject": {"type": "string", "description": "subject filter"},
        },
        "requires_confirmation": False,
    },
    "get_upcoming_events": {
        "fn": tool_get_upcoming_events,
        "roles": ["owner", "admin", "teacher", "student"],
        "description": "Get upcoming school events, scheduled exams, and announcements for the next N days (default 7).",
        "params_schema": {
            "days": {"type": "integer", "description": "number of days to look ahead (default 7, max 30)"},
        },
        "requires_confirmation": False,
    },
    "draft_parent_message": {
        "fn": tool_draft_parent_message,
        "roles": ["owner", "admin", "teacher"],
        "description": "Draft a WhatsApp/SMS message to a student's parent. Types: fee_reminder, absence_notification, exam_reminder, general.",
        "params_schema": {
            "student_id": {"type": "string", "description": "student name or ID"},
            "message_type": {"type": "string", "description": "fee_reminder|absence_notification|exam_reminder|general"},
            "note": {"type": "string", "description": "additional note to include"},
        },
        "requires_confirmation": False,
    },

    # ---- Expense, Enquiry, Incident tools ----
    "get_expenses": {
        "fn": tool_get_expenses,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "List recent expenses with optional category or month filter.",
        "params_schema": {
            "category": {"type": "string", "description": "optional expense category filter"},
            "month": {"type": "string", "description": "optional YYYY-MM filter"},
        },
        "requires_confirmation": False,
    },
    "create_expense": {
        "fn": tool_create_expense,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "Log a new expense (category, amount, vendor, description).",
        "params_schema": {
            "category": {"type": "string", "description": "expense category e.g. maintenance, salary, stationery"},
            "amount": {"type": "number", "description": "expense amount in INR"},
            "description": {"type": "string", "description": "what the expense is for"},
            "vendor": {"type": "string", "description": "vendor or payee name"},
            "date": {"type": "string", "description": "optional YYYY-MM-DD (defaults to today)"},
        },
        "requires_confirmation": True,
        "dispatch_type": "write",
    },
    "create_enquiry": {
        "fn": tool_create_enquiry,
        "roles": ["owner", "admin"],
        "description": "Log a new admission enquiry / lead.",
        "params_schema": {
            "student_name": {"type": "string", "description": "prospective student name"},
            "parent_name": {"type": "string", "description": "parent or guardian name"},
            "phone": {"type": "string", "description": "contact phone number"},
            "class_applying": {"type": "string", "description": "class applying for e.g. 'Class 5'"},
            "source": {"type": "string", "description": "walk_in | referral | online | phone — default: walk_in"},
            "notes": {"type": "string", "description": "optional notes"},
        },
        "requires_confirmation": True,
        "dispatch_type": "write",
    },
    "update_enquiry_status": {
        "fn": tool_update_enquiry_status,
        "roles": ["owner", "admin"],
        "description": "Advance an admission enquiry through the pipeline stages.",
        "params_schema": {
            "enquiry_id": {"type": "string", "description": "enquiry ID (use get_enquiries to find it)"},
            "status": {"type": "string", "description": "new | contacted | visit_scheduled | visited | documents_submitted | fee_paid | enrolled | lost"},
            "notes": {"type": "string", "description": "optional notes about this stage"},
            "assigned_to": {"type": "string", "description": "optional staff name or ID to assign"},
        },
        "requires_confirmation": True,
        "dispatch_type": "write",
    },
    "create_incident": {
        "fn": tool_create_incident,
        "roles": ["owner", "admin", "teacher"],
        "description": "Log a new incident (disciplinary, visitor, safety, etc.).",
        "params_schema": {
            "title": {"type": "string", "description": "brief incident title"},
            "description": {"type": "string", "description": "full incident description — required"},
            "severity": {"type": "string", "description": "low | medium | high (high auto-assigns to principal)"},
            "category": {"type": "string", "description": "general | disciplinary | financial | safety | visitor — default: general"},
            "involved_parties": {"type": "string", "description": "names of people involved"},
            "assigned_to": {"type": "string", "description": "optional staff member to assign"},
        },
        "requires_confirmation": True,
        "dispatch_type": "write",
    },
}

WRITE_TOOL_NAMES = {
    name for name, tool in TOOL_REGISTRY.items()
    if tool.get("requires_confirmation") or tool.get("dispatch_type") == "write"
}
