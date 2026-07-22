"""
Tool functions v2 — extends the original 14 tools with 15 new scope-aware tools.
Imports all originals from tool_functions and exposes a combined TOOL_REGISTRY (29 tools).
"""
from __future__ import annotations

from datetime import datetime, date, timedelta, timezone
from database import get_db
import json
import time, re
import uuid
import logging
from ai.redaction import _mask_phone  # canonical phone mask (first-2 + last-3)
from tenant import add_school_id, get_school_id, scoped_filter, scoped_query
from ai.fee_metrics import DEFAULTER_STATUSES, student_outstanding_from_txns
from services.audit_service import write_audit_doc
from services.notification_service import create_notification, fan_out_notifications
from services.actor_context import actor_ctx_from_user
from services.attendance_service import mark_attendance
from services.fees_service import (
    record_payment,
    correct_transaction as svc_correct_fee_transaction,
    delete_transaction as svc_delete_fee_transaction,
    FeeValidationError,
    FeeTransactionNotFoundError,
    FeeAuthorizationError,
)
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
    decide_announcement as svc_decide_announcement,
    delete_announcement as svc_delete_announcement,
    AnnouncementNotFoundError,
    AnnouncementStateError,
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
    create_incident as svc_create_incident,
    update_incident_status as svc_update_incident_status,
    confirm_resolution as svc_confirm_resolution,
    IncidentValidationError,
    IncidentNotFoundError,
    IncidentAmbiguousError,
)
from services.expense_service import (
    create_expense as svc_create_expense,
    update_expense as svc_update_expense,
    delete_expense as svc_delete_expense,
    ExpenseValidationError,
    ExpenseNotFoundError,
)
from services.enquiry_service import (
    create_enquiry as svc_create_enquiry,
    update_enquiry as svc_update_enquiry,
    EnquiryValidationError,
    EnquiryNotFoundError,
    EnquiryConflictError,
)
from services.staff_attendance_service import (
    mark_staff_attendance as svc_mark_staff_attendance,
    StaffAttendanceValidationError,
)
from services.fee_sync_service import trigger_sync as svc_trigger_fee_sync, FeeSyncUpstreamError
from services.asset_service import (
    create_asset as svc_create_asset,
    update_asset as svc_update_asset,
    delete_asset as svc_delete_asset,
    AssetValidationError,
    AssetNotFoundError,
)
from services.visitor_service import (
    log_visitor as svc_log_visitor,
    checkout_visitor as svc_checkout_visitor,
    delete_visitor as svc_delete_visitor,
    VisitorValidationError,
    VisitorNotFoundError,
    VisitorDuplicateError,
    VisitorRateLimitError,
)
from services.certificate_service import (
    create_certificate as svc_create_certificate,
    approve_certificate as svc_approve_certificate,
    reject_certificate as svc_reject_certificate,
    CertificateValidationError,
    CertificateNotFoundError,
    CertificateStateError,
)
from services.query_ticket_service import (
    create_ticket as svc_create_query_ticket,
    resolve_ticket as svc_resolve_query_ticket,
    reopen_ticket as svc_reopen_query_ticket,
    assign_ticket as svc_assign_query_ticket,
    delete_ticket as svc_delete_query_ticket,
    TicketValidationError,
    TicketNotFoundError,
)
from services.transport_service import (
    create_route as svc_create_transport_route,
    update_route as svc_update_transport_route,
    delete_route as svc_delete_transport_route,
    create_vehicle as svc_create_vehicle,
    TransportValidationError,
    TransportNotFoundError,
    TransportConflictError,
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

# R5.1 (H4): `_apply_branch_filter` was removed. It consulted ONLY the resolved
# `scope`, never the JWT, so a branch-bound admin whose scope lacked a branch_id
# read every branch's data. All read tools now use
# `scoped_query(query, branch_id=_branch_id(user, scope))`, which prefers the
# JWT branch and fails closed (owner/principal without a branch stay school-wide).


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


def _normalize_iso_date(value) -> str | None:
    """Coerce a user/LLM-supplied date to ISO ``YYYY-MM-DD`` or return None.

    Calendar comparisons in the AI layer are lexicographic string compares that
    only behave correctly on zero-padded ISO dates. A non-ISO or unparseable
    value becomes ``None`` (dateless) rather than a corrupt sort key.
    """
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Already ISO (accept a full ISO datetime by taking the date part).
    head = s[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            src = head if fmt == "%Y-%m-%d" else s
            return datetime.strptime(src, fmt).date().isoformat()
        except (ValueError, TypeError):
            continue
    return None


def _empty_result(message: str, query_time_ms: float = 0) -> dict:
    return {
        "success": True,
        "data": [],
        "meta": {"count": 0, "query_time_ms": round(query_time_ms, 2)},
        "message": message,
        "denied": False,
    }


def _ok(data: list, query_time_ms: float, message: str = "") -> dict:
    return {
        "success": True,
        "data": data,
        "meta": {"count": len(data), "query_time_ms": round(query_time_ms, 2)},
        "message": message,
        "denied": False,
    }


def _denied(message: str, query_time_ms: float = 0) -> dict:
    """R4.3/M2: an authorization/permission failure — NOT an empty result.

    `denied: True` + `success: False` so the LLM relays "you don't have access"
    honestly instead of answering "there are none"."""
    return {
        "success": False,
        "data": [],
        "meta": {"count": 0, "query_time_ms": round(query_time_ms, 2)},
        "message": message,
        "denied": True,
    }


def _failed(message: str, query_time_ms: float = 0) -> dict:
    """R4.3/L1: an operation that could not complete (bad input, not-found on a
    write, downstream error) — `success: False` but NOT a denial. Distinct from an
    empty read so a failed write is never reported as a benign empty success."""
    return {
        "success": False,
        "data": [],
        "meta": {"count": 0, "query_time_ms": round(query_time_ms, 2)},
        "message": message,
        "denied": False,
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
    query = scoped_query(query, branch_id=_branch_id(user, scope))

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
                    return _denied(
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
    query = scoped_query(query, branch_id=_branch_id(user, scope))

    if params.get("class_group"):
        query["$or"] = [
            {"class_group": {"$regex": re.escape(params["class_group"]), "$options": "i"}},
            {"name": {"$regex": re.escape(params["class_group"]), "$options": "i"}},
        ]

    structures = await db.fee_structures.find(query).to_list(100)

    results = []
    for fs in structures:
        components = fs.get("components", fs.get("fee_heads", []))
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
    class_query = scoped_query(class_query, branch_id=_branch_id(user, scope))
    if _scope_class_ids(scope) is not None:
        class_query["id"] = {"$in": _scope_class_ids(scope)}

    classes = await db.classes.find(class_query).to_list(50)
    class_ids = [c["id"] for c in classes if c.get("id")]

    # M4: batch attendance + student counts with $in, then aggregate in-memory
    # (was one find + one count_documents per class).
    att_records = await db.student_attendance.find(
        {"class_id": {"$in": class_ids}, "date": {"$gte": start, "$lte": end}}
    ).to_list(50000)
    att_by_class: dict = {}
    for r in att_records:
        cid = r.get("class_id")
        bucket = att_by_class.setdefault(cid, {"present": 0, "total": 0})
        bucket["total"] += 1
        if r.get("status") == "present":
            bucket["present"] += 1

    strength_agg = await db.students.aggregate([
        {"$match": {"class_id": {"$in": class_ids}, "is_active": True}},
        {"$group": {"_id": "$class_id", "count": {"$sum": 1}}},
    ]).to_list(len(class_ids) or 1)
    strength_by_class = {row["_id"]: row["count"] for row in strength_agg}

    results = []
    for cls in classes:
        bucket = att_by_class.get(cls["id"], {"present": 0, "total": 0})
        total = bucket["total"]
        present = bucket["present"]
        absent = total - present
        rate = round(present / total * 100, 1) if total > 0 else 0
        results.append({
            "class_name": f"{cls.get('name', '')}-{cls.get('section', '')}",
            "total_students": strength_by_class.get(cls["id"], 0),
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

    # M4: batch staff lookups (was find_one per leave request).
    lr_staff_ids = [lr["staff_id"] for lr in leaves if lr.get("staff_id")]
    lr_staff = await db.staff.find(
        scoped_query({"id": {"$in": lr_staff_ids}}, branch_id=bid)
    ).to_list(len(lr_staff_ids) or 1) if lr_staff_ids else []
    lr_staff_map = {s["id"]: s for s in lr_staff}

    results = []
    for lr in leaves:
        staff = lr_staff_map.get(lr.get("staff_id"))
        results.append({
            # L3/R4.4: include the leave id — approve_leave needs it to act.
            "id": lr.get("id"),
            "leave_id": lr.get("id"),
            "staff_name": staff.get("name", "Unknown") if staff else "Unknown",
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

    # M4: batch this month's attendance for all staff (was one find per staff).
    staff_ids = [s["id"] for s in staff_list if s.get("id")]
    month_att = await db.staff_attendance.find({
        "staff_id": {"$in": staff_ids},
        "date": {"$gte": month_start, "$lte": today_str},
    }).to_list(50000)
    att_by_staff: dict = {}
    for r in month_att:
        sid = r.get("staff_id")
        bucket = att_by_staff.setdefault(sid, {"total": 0, "present": 0})
        bucket["total"] += 1
        if r.get("status") in ("present", "late"):
            bucket["present"] += 1

    results = []
    for s in staff_list:
        bucket = att_by_staff.get(s["id"], {"total": 0, "present": 0})
        total_att = bucket["total"]
        present = bucket["present"]
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
    query = scoped_query(query, branch_id=_branch_id(user, scope))

    classes = await db.classes.find(query).to_list(50)
    class_ids = [c["id"] for c in classes if c.get("id")]

    # M4: batch teacher lookups (by id OR user_id) and per-class strength counts.
    teacher_ids = [c["class_teacher_id"] for c in classes if c.get("class_teacher_id")]
    teacher_docs = await db.staff.find(
        {"$or": [{"id": {"$in": teacher_ids}}, {"user_id": {"$in": teacher_ids}}]}
    ).to_list(len(teacher_ids) or 1) if teacher_ids else []
    teacher_by_id = {t["id"]: t for t in teacher_docs if t.get("id")}
    teacher_by_user = {t["user_id"]: t for t in teacher_docs if t.get("user_id")}

    strength_agg = await db.students.aggregate([
        {"$match": {"class_id": {"$in": class_ids}, "is_active": True}},
        {"$group": {"_id": "$class_id", "count": {"$sum": 1}}},
    ]).to_list(len(class_ids) or 1)
    strength_by_class = {row["_id"]: row["count"] for row in strength_agg}

    results = []
    for cls in classes:
        teacher_name = "N/A"
        tid = cls.get("class_teacher_id")
        if tid:
            teacher = teacher_by_id.get(tid) or teacher_by_user.get(tid)
            if teacher:
                teacher_name = teacher.get("name", "N/A")
        results.append({
            "class_name": cls.get("name", ""),
            "section": cls.get("section", ""),
            "class_teacher_name": teacher_name,
            "student_count": strength_by_class.get(cls["id"], 0),
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

    # M5/AC3: a defaulter is any student with an outstanding balance
    # (overdue/pending/unpaid/partial), NOT only status='overdue' \u2014 consistent
    # with fee_summary. Uses the shared canonical helper.
    outstanding_query = scoped_query(
        {"status": {"$in": list(DEFAULTER_STATUSES)}},
        branch_id=_branch_id(user, scope),
    )
    outstanding_txns = await db.fee_transactions.find(outstanding_query).to_list(1000)
    student_dues = student_outstanding_from_txns(outstanding_txns)

    # Batch-fetch students + classes (no N+1) \u2014 M4.
    sid_list = list(student_dues.keys())
    students_docs = await db.students.find({"id": {"$in": sid_list}}).to_list(len(sid_list) or 1)
    student_map = {s["id"]: s for s in students_docs}
    class_ids = list({s.get("class_id") for s in students_docs if s.get("class_id")})
    classes_docs = await db.classes.find({"id": {"$in": class_ids}}).to_list(len(class_ids) or 1)
    class_map = {c["id"]: c for c in classes_docs}

    results = []
    for sid, dues in student_dues.items():
        student = student_map.get(sid)
        if not student:
            continue
        # Scope filter: if teacher, only show students in their classes
        if _scope_class_ids(scope) is not None:
            if student.get("class_id") not in _scope_class_ids(scope):
                continue

        cls = class_map.get(student.get("class_id"))
        class_name = f"{cls['name']}-{cls['section']}" if cls else "N/A"

        days_overdue = 0
        if dues["oldest_due"]:
            try:
                due_dt = datetime.strptime(dues["oldest_due"], "%Y-%m-%d").date()
                # AC3 widened "defaulter" to include PENDING invoices, which may
                # carry a future due_date; clamp at 0 so we never report a
                # nonsensical "overdue -20 days".
                days_overdue = max(0, (date.today() - due_dt).days)
            except (ValueError, TypeError):
                days_overdue = 0

        results.append({
            "name": student.get("name", ""),
            "class": class_name,
            "amount_due": dues["owed"],
            "amount_due_fmt": f"\u20b9{dues['owed']:,.0f}",
            "days_overdue": days_overdue,
            "student_id": sid,
            # R4.4/AC3/DPDP: mask guardian phones AT SOURCE (like get_transport_status).
            "father_phone": _mask_phone(student.get("father_phone", "")),
            "mother_phone": _mask_phone(student.get("mother_phone", "")),
            "guardian_phone": _mask_phone(student.get("guardian_phone", "")),
            "phone": _mask_phone(student.get("phone", "")),
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

    # R5.2 (H4): branch-scope the lookup so a branch-bound admin cannot read a
    # student in another branch. Owner/principal (no JWT branch) stay school-wide.
    bid = _branch_id(user, scope)
    student = None
    if params.get("student_id"):
        student = await db.students.find_one(scoped_query({"id": params["student_id"]}, branch_id=bid))
    elif params.get("search_term"):
        safe_term = re.escape(params["search_term"])
        student = await db.students.find_one(scoped_query({
            "$or": [
                {"name": {"$regex": safe_term, "$options": "i"}},
                {"admission_number": {"$regex": safe_term, "$options": "i"}},
            ]
        }, branch_id=bid))

    if not student:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("Student not found. Please check the name or ID and try again.", elapsed)

    # Scope check: self_only means student can only view their own profile
    if _scope_student_id(scope) and _scope_student_id(scope) != student["id"]:
        elapsed = (time.time() - t0) * 1000
        return _denied("You do not have permission to view this student's profile.", elapsed)

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
        return _denied("You do not have access to this class.", elapsed)

    cls = await db.classes.find_one({"id": class_id})
    class_label = f"{cls['name']}-{cls['section']}" if cls else "Unknown"

    # All active students in this class
    all_students = await db.students.find({"class_id": class_id, "is_active": True}).to_list(200)
    student_map = {s["id"]: s for s in all_students}

    # Today's attendance records
    att_records = await db.student_attendance.find({"class_id": class_id, "date": today_str}).to_list(200)
    marked_ids = {r["student_id"] for r in att_records}

    # M7/AC2: only count attendance for students who are active in THIS class, so
    # stray records (transferred/inactive students) can't push the rate above 100%.
    present = []
    absent = []
    for r in att_records:
        s = student_map.get(r["student_id"])
        if not s:
            continue
        name = s["name"]
        if r.get("status") == "present":
            present.append(name)
        else:
            absent.append(name)

    unmarked = [s["name"] for s in all_students if s["id"] not in marked_ids]

    # Defensive clamp: rate is present/total, never above 100.
    rate_val = min(100.0, round(len(present) / len(all_students) * 100, 1)) if all_students else 0.0

    elapsed = (time.time() - t0) * 1000
    data = [{
        "class": class_label,
        "date": today_str,
        "total_students": len(all_students),
        "present_count": len(present),
        "absent_count": len(absent),
        "unmarked_count": len(unmarked),
        "rate": f"{rate_val}%",
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
    query = scoped_query(query, branch_id=_branch_id(user, scope))

    houses = await db.houses.find(query).to_list(20)

    if not houses:
        elapsed = (time.time() - t0) * 1000
        return _empty_result("No houses configured in the system.", elapsed)

    # M4: one query for ALL houses' points (was one aggregate per house), grouped
    # by house + category in memory.
    house_ids = [h["id"] for h in houses if h.get("id")]
    point_rows = await db.house_points.find(
        {"house_id": {"$in": house_ids}}, {"_id": 0, "house_id": 1, "category": 1, "points": 1}
    ).to_list(50000)
    breakdown_by_house: dict = {}
    for row in point_rows:
        hid = row.get("house_id")
        cat = row.get("category")
        cat_map = breakdown_by_house.setdefault(hid, {})
        cat_map[cat] = cat_map.get(cat, 0) + (row.get("points") or 0)

    results = []
    for h in houses:
        breakdown = breakdown_by_house.get(h["id"], {})
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
    # M4: batch student name lookups (was find_one per point).
    rp_sids = [rp["student_id"] for rp in recent_points if rp.get("student_id")]
    rp_students = await db.students.find({"id": {"$in": rp_sids}}).to_list(len(rp_sids) or 1) if rp_sids else []
    rp_student_map = {s["id"]: s for s in rp_students}
    recent = []
    for rp in recent_points:
        student = rp_student_map.get(rp.get("student_id"))
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
        return _denied("You do not have permission to award house points.", elapsed)

    student_name = params.get("student_name", "")
    points = params.get("points", 0)
    reason = params.get("reason", "")

    if not student_name or not points:
        elapsed = (time.time() - t0) * 1000
        return _failed("student_name and points are required parameters.", elapsed)

    # Find the student — R5.2 (H4): branch-scope so a branch-bound user cannot
    # award points to (or misfire a write against) another branch's student.
    student = await db.students.find_one(scoped_query(
        {"name": {"$regex": re.escape(student_name), "$options": "i"}, "is_active": True},
        branch_id=_branch_id(user, scope),
    ))
    if not student:
        # R4.3/L1: a not-found on a WRITE is a failure, not a benign empty read.
        elapsed = (time.time() - t0) * 1000
        return _failed(f"Student '{student_name}' not found.", elapsed)

    house_id = student.get("house_id")
    if not house_id:
        elapsed = (time.time() - t0) * 1000
        return _failed(f"Student '{student['name']}' is not assigned to any house.", elapsed)

    # Story B.3: route through the shared house-points service so the AI award updates
    # the real standings (houses.points + house_points_log + audit) exactly like the
    # panel — replacing the old un-audited `house_points`-only write.
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    service_params = {"house_id": house_id, "delta": points, "reason": reason}
    try:
        result = await award_points(db, actor_ctx, service_params)
    except HouseNotFoundError:
        elapsed = (time.time() - t0) * 1000
        return _failed("House not found.", elapsed)
    except HousePointsValidationError as e:
        return _failed(str(e))

    house_name = result["house_name"] or "Unknown"
    elapsed = (time.time() - t0) * 1000
    return {
        "success": True,
        "data": [{
            "confirm_action": "award_house_points",
            "student_name": student["name"],
            "house_name": house_name,
            "points_awarded": points,
            "reason": reason,
            "new_total": result["points"],
        }],
        "meta": {"count": 1, "query_time_ms": round(elapsed, 2)},
        "message": f"Awarded {points} points to {student['name']} ({house_name}).",
    }


# =========================================================================
#  14. tool_get_student_council
# =========================================================================

async def tool_get_student_council(params: dict, user: dict, scope: dict = None) -> dict:
    """All student council positions: head boy/girl, captains, prefects."""
    t0 = time.time()
    db = get_db()

    query: dict = {}
    query = scoped_query(query, branch_id=_branch_id(user, scope))

    # Try dedicated council collection first
    council_members = await db.student_council.find(query).to_list(100)

    if council_members:
        # M4: batch student + class lookups (was two find_one per member).
        cm_sids = [cm["student_id"] for cm in council_members if cm.get("student_id")]
        cm_students = await db.students.find({"id": {"$in": cm_sids}}).to_list(len(cm_sids) or 1) if cm_sids else []
        cm_student_map = {s["id"]: s for s in cm_students}
        cm_class_ids = list({s.get("class_id") for s in cm_students if s.get("class_id")})
        cm_classes = await db.classes.find({"id": {"$in": cm_class_ids}}).to_list(len(cm_class_ids) or 1) if cm_class_ids else []
        cm_class_map = {c["id"]: c for c in cm_classes}
        results = []
        for cm in council_members:
            student = cm_student_map.get(cm.get("student_id"))
            cls = cm_class_map.get(student.get("class_id")) if student else None
            results.append({
                "name": student["name"] if student else cm.get("student_name", "Unknown"),
                "class": f"{cls['name']}-{cls['section']}" if cls else "N/A",
                "position": cm.get("position", ""),
                "house": cm.get("house_name", ""),
            })
    else:
        # Fallback: check for council roles on student records
        council_query = {"council_role": {"$exists": True, "$ne": None, "$ne": ""}}
        council_query = scoped_query(council_query, branch_id=_branch_id(user, scope))
        council_students = await db.students.find(council_query).to_list(100)
        # M4: batch class + house lookups.
        cs_class_ids = list({s.get("class_id") for s in council_students if s.get("class_id")})
        cs_classes = await db.classes.find({"id": {"$in": cs_class_ids}}).to_list(len(cs_class_ids) or 1) if cs_class_ids else []
        cs_class_map = {c["id"]: c for c in cs_classes}
        cs_house_ids = list({s.get("house_id") for s in council_students if s.get("house_id")})
        cs_houses = await db.houses.find({"id": {"$in": cs_house_ids}}).to_list(len(cs_house_ids) or 1) if cs_house_ids else []
        cs_house_map = {h["id"]: h for h in cs_houses}
        results = []
        for s in council_students:
            cls = cs_class_map.get(s.get("class_id"))
            house = cs_house_map.get(s.get("house_id")) if s.get("house_id") else None
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
    query = scoped_query(query, branch_id=_branch_id(user, scope))

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
        # L2: UTC-aware, consistent with the rest of the audit pipeline.
        "created_at": datetime.now(timezone.utc).isoformat(),
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
        return _denied("You are not authorized to decide this approval request.")
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
        return _failed("student_id is required.")
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
        return _failed("student_id is required.")
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
    bid = _branch_id(user, scope)
    class_id = params.get("class_id")
    if not class_id and params.get("class_name"):
        # R5.2 (H4): branch-scope the class name lookup so a branch-bound user
        # cannot resolve (and then mark attendance against) another branch's class.
        cls = await db.classes.find_one(scoped_query(
            {"name": {"$regex": re.escape(params["class_name"]), "$options": "i"}},
            branch_id=bid,
        ), {"_id": 0})
        class_id = (cls or {}).get("id")
    if not class_id:
        return _empty_result("Class not found.")
    # R5.2 defense-in-depth: whether class_id was supplied directly or resolved
    # by name, confirm it exists in the caller's branch before writing —
    # student_attendance carries no branch_id, so the service cannot re-check.
    class_in_branch = await db.classes.find_one(
        scoped_query({"id": class_id}, branch_id=bid), {"_id": 0, "id": 1}
    )
    if not class_in_branch:
        return _failed("Class not found in your branch.")
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
        return _failed("student_id is required.")
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
        # M7/AC2: use the ACTUAL max_marks — exam's, else each result's own — and
        # never silently assume /100. Pass rate is only reported when max is known.
        exam_max = exam.get("max_marks")

        def _row_max(r: dict):
            return exam_max if exam_max is not None else r.get("max_marks")

        avg = round(sum(marks) / len(marks), 1) if marks else 0
        highest = max(marks) if marks else 0
        lowest = min(marks) if marks else 0

        # Only count students whose max_marks is known (33% passing threshold).
        scorable = [r for r in exam_results
                    if r.get("marks_obtained") is not None and _row_max(r) not in (None, 0)]
        passed = sum(1 for r in scorable if r["marks_obtained"] >= _row_max(r) * 0.33)
        # Report a pass-rate ONLY when every graded student is scorable — otherwise
        # a rate computed over a subset would read as if it covered all `students`
        # (shown alongside), which is misleading. Partial coverage → "N/A".
        pass_rate = (
            f"{round(passed / len(scorable) * 100, 1)}%"
            if scorable and len(scorable) == len(marks) else "N/A"
        )

        avg_display = f"{avg}/{exam_max}" if exam_max is not None else f"{avg}"

        results.append({
            "exam": exam.get("name", "Unnamed Exam"),
            "subject": exam.get("subject", ""),
            "date": exam.get("exam_date", ""),
            "students": len(marks),
            "average": avg_display,
            "highest": highest,
            "lowest": lowest,
            "pass_rate": pass_rate,
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

    # Upcoming announcements / events (from announcements collection).
    # M6: match the SAME visibility rule as tool_get_announcements — announcements
    # are stored with status "active" and sent_at set (never "published"), so the
    # old status="published" filter matched nothing AI-created. Use event_date when
    # present, else fall back to the send date, and window-filter in Python.
    announcements = await db.announcements.find(
        scoped_query(
            {"status": "active", "sent_at": {"$ne": None}},
            branch_id=bid
        ),
        {"_id": 0, "title": 1, "event_date": 1, "sent_at": 1}
    ).to_list(50)

    for a in announcements:
        eff_date = a.get("event_date") or (a.get("sent_at") or "")[:10]
        if not eff_date or eff_date < today or eff_date > until:
            continue
        events.append({"date": eff_date, "type": "event", "title": a.get("title", "Event")})

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
        # M6: persist an optional event_date so calendar-style announcements surface
        # in get_upcoming_events. Normalize to ISO (YYYY-MM-DD) — the events window
        # does a lexicographic compare, so a non-ISO date (e.g. "15/07/2026") would
        # be silently dropped/mis-ordered. Unparseable → dateless (falls back to
        # sent_at), never a corrupt sort key.
        "event_date": _normalize_iso_date(params.get("event_date")),
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


async def tool_get_announcements(params: dict, user: dict, scope: dict = None) -> dict:
    """Read published school announcements visible to the caller (R3.3/H2).

    Previously advertised to students but ABSENT from the registry — a guaranteed
    dead tool call. Now implemented student-safe: only announcements that have
    actually been sent (never drafts or pending-approval) whose audience includes
    the caller's role. School-scoped automatically via the scoped db; the
    announcement data model is school-wide (no per-branch targeting)."""
    t0 = time.time()
    db = get_db()
    try:
        days = int(params.get("days", 7) or 7)
    except (TypeError, ValueError):
        days = 7
    role = user.get("role", "")
    # A published announcement is one that is not a draft and has been sent
    # (sent_at set) — pending-approval / draft announcements are never visible.
    query = {
        "is_draft": {"$ne": True},
        "sent_at": {"$ne": None},
        "$or": [
            {"target_roles": role},
            {"audience_type": "all"},
        ],
    }
    anns = await db.announcements.find(query, {"_id": 0}).to_list(200)
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    visible = [a for a in anns if str(a.get("created_at", "")) >= cutoff]
    # Most recent first (created_at is an ISO string → lexicographic == chronological).
    visible.sort(key=lambda a: str(a.get("created_at", "")), reverse=True)
    data = [
        {
            "id": a.get("id"),
            "title": a.get("title"),
            "content": a.get("content"),
            "audience_type": a.get("audience_type"),
            "sent_at": a.get("sent_at"),
            "created_at": a.get("created_at"),
        }
        for a in visible[:50]
    ]
    elapsed = (time.time() - t0) * 1000
    if not data:
        return _empty_result(f"No announcements in the last {days} days.", elapsed)
    return _ok(data, elapsed, f"{len(data)} announcement(s) in the last {days} days.")


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
    from services.memory import can_recall_memories, store as memory_store

    subject = (params.get("subject") or params.get("query") or params.get("search_term") or "").strip()
    if not subject and not params.get("student_id"):
        return _empty_result("Tell me who or what to brief you on (a student, family, or topic).", (time.time() - t0) * 1000)

    sections: dict = {}
    student_ids: list = []

    # 1) Memory recall (owner-scoped; Owner/Principal per Phase-1, plus any roles the
    #    R10.5 MEMORY_ROLES switch grants read-recall to).
    if can_recall_memories(user):
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
    query = scoped_query(query, branch_id=_branch_id(user, scope))
    route_filter = params.get("route_id")

    routes = await db.transport_routes.find(query, {"_id": 0}).to_list(100)

    if route_filter:
        routes = [r for r in routes if r.get("id") == route_filter]

    def _fmt(r: dict) -> dict:
        return {
            "id": r.get("id"),
            "route_name": r.get("route_name"),
            "driver_name": r.get("driver_name"),
            # R4.4: canonical mask (first-2 + last-3), matching redaction.py.
            "driver_phone": _mask_phone(r.get("driver_phone", "")),
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
        "denied": False,
    }


async def tool_get_inventory_status(params: dict, user: dict, scope: dict = None) -> dict:
    """Inventory overview: total items, categories, low-stock alerts."""
    t0 = time.time()
    db = get_db()
    query: dict = {}
    query = scoped_query(query, branch_id=_branch_id(user, scope))

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
            # M3: attendance lives in student_attendance (not `attendance`), and that
            # collection has no branch_id — scope it via this branch's classes.
            branch_classes = await db.classes.find(
                scoped_query({}, branch_id=bid), {"_id": 0, "id": 1}
            ).to_list(200)
            branch_class_ids = [c["id"] for c in branch_classes if c.get("id")]
            if branch_class_ids:
                att_filter = {"class_id": {"$in": branch_class_ids}, "date": today_str}
                # branch-scope: intentional — student_attendance has no branch_id;
                # branch isolation is enforced by restricting class_id to this branch's classes.
                total_today = await db.student_attendance.count_documents(
                    scoped_filter(att_filter)
                )
                today_records = await db.student_attendance.count_documents(
                    scoped_filter({**att_filter, "status": "present"})
                )
            else:
                total_today = 0
                today_records = 0
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
        "meta": {"count": len(expenses), "query_time_ms": round(elapsed, 2)},
        "message": f"{len(expenses)} expense(s) totalling ₹{total:,.2f}",
        "denied": False,
    }


async def tool_create_expense(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over expense_service.create_expense (AD7 shared write path).
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_expense(db, actor_ctx, params)
    except ExpenseValidationError as e:
        return {"success": False, "message": str(e)}
    exp = result["expense"]
    return {
        "success": True,
        "data": exp,
        "message": f"Expense of ₹{float(exp['amount']):,.2f} logged under '{exp['category']}'",
    }


async def tool_update_expense(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over expense_service.update_expense (AD7 shared write path).
    if not params.get("expense_id"):
        return {"success": False, "message": "expense_id is required (use get_expenses to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_update_expense(db, actor_ctx, params)
    except ExpenseNotFoundError:
        return {"success": False, "message": "Expense not found"}
    except ExpenseValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "Expense updated."
    return {"success": True, "data": result["expense"], "message": msg}


async def tool_delete_expense(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over expense_service.delete_expense (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("expense_id"):
        return {"success": False, "message": "expense_id is required (use get_expenses to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_expense(db, actor_ctx, params)
    except ExpenseNotFoundError:
        return {"success": False, "message": "Expense not found"}
    except ExpenseValidationError as e:
        return {"success": False, "message": str(e)}
    exp = result["expense"]
    return {"success": True, "data": result,
            "message": f"Expense '{exp.get('description') or exp.get('category')}' (₹{float(exp.get('amount', 0)):,.2f}) deleted."}


async def tool_create_enquiry(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over enquiry_service.create_enquiry (AD7 shared write path).
    if not params.get("student_name"):
        return {"success": False, "message": "student_name is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_enquiry(db, actor_ctx, params)
    except EnquiryValidationError as e:
        return {"success": False, "message": str(e)}
    enq = result["enquiry"]
    return {"success": True, "data": enq,
            "message": f"Enquiry logged for '{enq['student_name']}' ({enq.get('class_applying') or 'class not specified'})"}


async def tool_update_enquiry_status(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over enquiry_service.update_enquiry (AD7 shared write path).
    # Parity fix: the legacy AI body skipped the stage-transition guard entirely.
    if not params.get("enquiry_id"):
        return {"success": False, "message": "enquiry_id is required"}
    if not params.get("status"):
        return {"success": False, "message": "status is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    svc_params = {**params, "note": params.get("note") or params.get("notes")}
    try:
        result = await svc_update_enquiry(db, actor_ctx, svc_params)
    except EnquiryNotFoundError:
        return {"success": False, "message": f"Enquiry {params['enquiry_id']} not found"}
    except EnquiryConflictError as e:
        return {"success": False, "message": str(e)}
    except EnquiryValidationError as e:
        return {"success": False, "message": str(e)}
    enq = result["enquiry"]
    return {"success": True, "data": enq,
            "message": f"Enquiry for '{enq.get('student_name', params['enquiry_id'])}' status → {enq.get('status')}"}


async def tool_create_incident(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over incident_service.create_incident (AD7 shared write path).
    if not params.get("description"):
        return {"success": False, "message": "description is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_incident(db, actor_ctx, params, fan_out_fn=fan_out_notifications)
    except IncidentValidationError as e:
        return {"success": False, "message": str(e)}
    inc = result["incident"]
    extra = " Owner and Principal notified." if inc.get("severity") == "high" else ""
    return {"success": True, "data": inc,
            "message": f"Incident logged ({inc.get('severity')} severity).{extra}"}


async def tool_mark_staff_attendance(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over staff_attendance_service.mark_staff_attendance (AD7).
    # Convenience: "mark all staff present today" → status with no records expands
    # to every active staff member before hitting the same shared service.
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    records = params.get("records") or []
    if not records:
        status = params.get("status")
        if not status:
            return {"success": False,
                    "message": "Provide records=[{staff_id, status}] or a status to apply to all active staff."}
        staff = await db.staff.find(
            scoped_query({"is_active": {"$ne": False}}, branch_id=_branch_id(user, scope)),
            {"_id": 0, "id": 1},
        ).to_list(500)
        if not staff:
            return {"success": False, "message": "No active staff found."}
        records = [{"staff_id": s["id"], "status": status} for s in staff]
    from services.sse import publish as _sse_publish
    try:
        result = await svc_mark_staff_attendance(
            db, actor_ctx, {"date": params.get("date"), "records": records}, publish_fn=_sse_publish
        )
    except StaffAttendanceValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result,
            "message": f"Staff attendance marked for {result['marked']} staff member(s) on {result['date']}."}


async def tool_correct_fee_transaction(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over fees_service.correct_transaction (AD7 shared write path).
    if not params.get("transaction_id"):
        return {"success": False, "message": "transaction_id is required (use get_fee_transactions to find it)"}
    if not params.get("reason"):
        return {"success": False, "message": "reason is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    from routes.fees import _publish_fee_update
    try:
        result = await svc_correct_fee_transaction(db, actor_ctx, params, publish_fn=_publish_fee_update)
    except FeeTransactionNotFoundError:
        return {"success": False, "message": "Fee transaction not found"}
    except FeeAuthorizationError as e:
        return {"success": False, "message": str(e)}
    except FeeValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["data"], "message": "Fee transaction corrected."}


async def tool_delete_fee_transaction(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over fees_service.delete_transaction (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit. Soft delete — the
    # record is kept with deleted=True for the financial trail.
    if not params.get("transaction_id"):
        return {"success": False, "message": "transaction_id is required (use get_fee_transactions to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    from routes.fees import _publish_fee_update
    try:
        result = await svc_delete_fee_transaction(db, actor_ctx, params, publish_fn=_publish_fee_update)
    except FeeTransactionNotFoundError:
        return {"success": False, "message": "Fee transaction not found"}
    except FeeAuthorizationError as e:
        return {"success": False, "message": str(e)}
    except FeeValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["data"], "message": "Fee transaction deleted (soft — kept in the financial trail)."}


async def tool_trigger_fee_sync(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over fee_sync_service.trigger_sync (AD7 shared write path).
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    from routes.fees import _fetch_external_fee_records, _publish_fee_update
    try:
        result = await svc_trigger_fee_sync(
            db, actor_ctx, fetch_fn=_fetch_external_fee_records, publish_fn=_publish_fee_update
        )
    except FeeSyncUpstreamError as e:
        return {"success": False, "message": f"Fee sync failed upstream: {e}"}
    job = result["job"]
    if result["already_running"]:
        return {"success": True, "data": job, "message": "A fee sync is already in progress."}
    status = job.get("status")
    if status == "conflict":
        msg = (f"Fee sync finished with {job.get('conflict_count', 0)} conflict(s) — "
               f"{job.get('synced_count', 0)} record(s) synced. Resolve conflicts in the Fee Sync panel.")
    elif status == "failed":
        msg = f"Fee sync failed: {job.get('error', 'unknown error')}"
    else:
        msg = f"Fee sync completed — {job.get('synced_count', 0)} record(s) synced."
    return {"success": True, "data": job, "message": msg}


async def tool_get_fee_sync_status(params: dict, user: dict, scope: dict = None) -> dict:
    """Read-only: latest fee sync job(s) and any unresolved conflicts."""
    import time
    t0 = time.time()
    db = get_db()
    bid = _branch_id(user, scope)
    jobs = await db.fee_sync_jobs.find(
        scoped_query({}, branch_id=bid), {"_id": 0}
    ).sort("started_at", -1).to_list(5)
    elapsed = (time.time() - t0) * 1000
    if not jobs:
        return {"success": True, "data": {"jobs": []}, "meta": {"count": 0, "query_time_ms": round(elapsed, 2)},
                "message": "No fee sync has been run yet.", "denied": False}
    latest = jobs[0]
    msg = (f"Latest sync: {latest.get('status')} — {latest.get('synced_count', 0)} synced, "
           f"{latest.get('conflict_count', 0)} conflict(s).")
    return {"success": True, "data": {"jobs": jobs, "latest": latest},
            "meta": {"count": len(jobs), "query_time_ms": round(elapsed, 2)}, "message": msg, "denied": False}



async def tool_create_asset(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over asset_service.create_asset (AD7 shared write path).
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_asset(db, actor_ctx, params)
    except AssetValidationError as e:
        return {"success": False, "message": str(e)}
    a = result["asset"]
    return {"success": True, "data": a, "message": f"Asset '{a['name']}' added (qty {a['quantity']})."}


async def tool_update_asset(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over asset_service.update_asset (AD7 shared write path).
    if not params.get("asset_id"):
        return {"success": False, "message": "asset_id is required (use get_inventory_status to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_update_asset(db, actor_ctx, params)
    except AssetNotFoundError:
        return {"success": False, "message": "Asset not found"}
    except AssetValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "Asset updated."
    return {"success": True, "data": result["asset"], "message": msg}


async def tool_delete_asset(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over asset_service.delete_asset (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("asset_id"):
        return {"success": False, "message": "asset_id is required (use get_inventory_status to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_asset(db, actor_ctx, params)
    except AssetNotFoundError:
        return {"success": False, "message": "Asset not found"}
    except AssetValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": f"Asset '{result['asset'].get('name')}' deleted."}


async def tool_log_visitor(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over visitor_service.log_visitor (AD7 shared write path).
    if not (params.get("visitor_name") or "").strip():
        return {"success": False, "message": "visitor_name is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_log_visitor(db, actor_ctx, params)
    except VisitorDuplicateError as e:
        return {"success": False,
                "message": f"{e} (existing entry: {e.existing_id}) — re-run with force=true to override."}
    except VisitorRateLimitError as e:
        return {"success": False, "message": str(e)}
    except VisitorValidationError as e:
        return {"success": False, "message": str(e)}
    v = result["visitor"]
    return {"success": True, "data": v, "message": f"Visitor '{v['visitor_name']}' checked in."}


async def tool_checkout_visitor(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over visitor_service.checkout_visitor (AD7 shared write path).
    if not params.get("visitor_id"):
        return {"success": False, "message": "visitor_id is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_checkout_visitor(db, actor_ctx, params)
    except VisitorNotFoundError:
        return {"success": False, "message": "Visitor not found"}
    except VisitorValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Visitor checked out."}


async def tool_delete_visitor(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over visitor_service.delete_visitor (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("visitor_id"):
        return {"success": False, "message": "visitor_id is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_visitor(db, actor_ctx, params)
    except VisitorNotFoundError:
        return {"success": False, "message": "Visitor not found"}
    except VisitorValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Visitor log entry deleted."}


async def tool_create_certificate(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over certificate_service.create_certificate (AD7 shared write path).
    if not params.get("student_id"):
        return {"success": False, "message": "student_id is required (use search_students to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_certificate(db, actor_ctx, params)
    except CertificateValidationError as e:
        return {"success": False, "message": str(e)}
    cert = result["certificate"]
    state = "generated" if cert["status"] == "generated" else "queued for principal approval"
    return {"success": True, "data": cert,
            "message": f"{cert['cert_type'].replace('_', ' ').title()} certificate {state} (serial {cert['serial_number']})."}


async def tool_decide_certificate(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over certificate_service approve/reject (AD7 shared write path).
    if not params.get("cert_id"):
        return {"success": False, "message": "cert_id is required"}
    decision = params.get("decision")
    if decision not in ("approve", "reject"):
        return {"success": False, "message": "decision must be approve or reject"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        if decision == "approve":
            result = await svc_approve_certificate(db, actor_ctx, params)
        else:
            result = await svc_reject_certificate(db, actor_ctx, params)
    except CertificateNotFoundError:
        return {"success": False, "message": "Certificate not found"}
    except CertificateStateError as e:
        return {"success": False, "message": str(e)}
    except CertificateValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["certificate"], "message": f"Certificate {decision}d."}


async def tool_create_query_ticket(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over query_ticket_service.create_ticket (AD7 shared write path).
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_query_ticket(db, actor_ctx, params)
    except TicketValidationError as e:
        return {"success": False, "message": str(e)}
    t = result["ticket"]
    return {"success": True, "data": t, "message": f"Ticket '{t['title']}' created ({t['priority']} priority)."}


async def tool_resolve_query_ticket(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over query_ticket_service.resolve_ticket (AD7 shared write path).
    if not params.get("ticket_id"):
        return {"success": False, "message": "ticket_id is required (use query_dashboard_summary to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_resolve_query_ticket(db, actor_ctx, params)
    except TicketNotFoundError:
        return {"success": False, "message": "Ticket not found"}
    except TicketValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Ticket marked resolved."}


async def tool_reopen_query_ticket(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over query_ticket_service.reopen_ticket (AD7 shared write path).
    if not params.get("ticket_id"):
        return {"success": False, "message": "ticket_id is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_reopen_query_ticket(db, actor_ctx, params)
    except TicketNotFoundError:
        return {"success": False, "message": "Ticket not found"}
    except TicketValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Ticket reopened."}


async def tool_assign_query_ticket(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over query_ticket_service.assign_ticket (AD7 shared write path).
    if not params.get("ticket_id"):
        return {"success": False, "message": "ticket_id is required"}
    if not params.get("assigned_to"):
        return {"success": False, "message": "assigned_to is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_assign_query_ticket(db, actor_ctx, params)
    except TicketNotFoundError:
        return {"success": False, "message": "Ticket not found"}
    except TicketValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result["ticket"], "message": "Ticket assigned."}


async def tool_delete_query_ticket(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over query_ticket_service.delete_ticket (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("ticket_id"):
        return {"success": False, "message": "ticket_id is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_query_ticket(db, actor_ctx, params)
    except TicketNotFoundError:
        return {"success": False, "message": "Ticket not found"}
    except TicketValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": "Ticket deleted."}


async def tool_create_transport_route(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over transport_service.create_route (AD7 shared write path).
    if not (params.get("route_name") or params.get("name")):
        return {"success": False, "message": "route_name is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_transport_route(db, actor_ctx, params)
    except TransportValidationError as e:
        return {"success": False, "message": str(e)}
    r = result["route"]
    return {"success": True, "data": r, "message": f"Transport route '{r['route_name']}' created."}


async def tool_update_transport_route(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over transport_service.update_route (AD7 shared write path).
    if not params.get("route_id"):
        return {"success": False, "message": "route_id is required (use get_transport_status to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_update_transport_route(db, actor_ctx, params)
    except TransportNotFoundError:
        return {"success": False, "message": "Route not found"}
    except TransportValidationError as e:
        return {"success": False, "message": str(e)}
    msg = "No changes to apply." if result.get("noop") else "Transport route updated."
    return {"success": True, "data": result["route"], "message": msg}


async def tool_delete_transport_route(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over transport_service.delete_route (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit; blocked while students assigned.
    if not params.get("route_id"):
        return {"success": False, "message": "route_id is required (use get_transport_status to find it)"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_transport_route(db, actor_ctx, params)
    except TransportNotFoundError:
        return {"success": False, "message": "Route not found"}
    except TransportConflictError as e:
        return {"success": False, "message": str(e)}
    except TransportValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": f"Transport route '{result['route'].get('route_name')}' deleted."}


async def tool_add_transport_vehicle(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over transport_service.create_vehicle (AD7 shared write path).
    if not params.get("vehicle_number"):
        return {"success": False, "message": "vehicle_number is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_create_vehicle(db, actor_ctx, params)
    except TransportValidationError as e:
        return {"success": False, "message": str(e)}
    v = result["vehicle"]
    return {"success": True, "data": v, "message": f"Vehicle {v['vehicle_number']} registered."}


async def tool_decide_announcement(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over announcement_service.decide_announcement (AD7 shared write path).
    if not params.get("announcement_id"):
        return {"success": False, "message": "announcement_id is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_decide_announcement(db, actor_ctx, params)
    except AnnouncementNotFoundError:
        return {"success": False, "message": "Announcement not found"}
    except AnnouncementStateError as e:
        return {"success": False, "message": str(e)}
    except AnnouncementValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result, "message": f"Announcement {result['status']}."}


async def tool_delete_announcement(params: dict, user: dict, scope: dict = None) -> dict:
    # Thin adapter over announcement_service.delete_announcement (AD7 shared write path).
    # DESTRUCTIVE: F.10 two-step confirm + deletion audit at the chat layer.
    if not params.get("announcement_id"):
        return {"success": False, "message": "announcement_id is required"}
    db = get_db()
    actor_ctx = actor_ctx_from_user(user, branch_id=_branch_id(user, scope))
    try:
        result = await svc_delete_announcement(db, actor_ctx, params)
    except AnnouncementNotFoundError:
        return {"success": False, "message": "Announcement not found"}
    except AnnouncementValidationError as e:
        return {"success": False, "message": str(e)}
    return {"success": True, "data": result,
            "message": f"Announcement '{result['announcement'].get('title', '')}' deleted."}


# =========================================================================
#  Document generation (UI Sweep Epic 10, Story 10.2)
# =========================================================================

async def tool_draft_document(params: dict, user: dict, scope: dict = None) -> dict:
    """Turn content Flo has already written into a real file the school can use.

    WHY THIS IS A READ-CLASS TOOL, deliberately, and must not be "fixed" into a
    confirm flow: it changes no school record. It formats content that is already in
    the conversation and stores the result as a file. There is nothing to undo, so a
    two-step confirmation would only add friction to "make me a circular".

    WHY THE GATE LOOKS LIKE THIS. Generating a document is a data export, so the
    honest question is "could this person have exported this data anyway?". The
    answer is yes by construction: this tool does NOT query the database. It formats
    what the caller already has, and everything Flo knows it obtained through other
    tools that applied their own role gates. So the gate here is the union of roles
    that can export anything at all (owner, admin, teacher) and students are excluded
    — matching `routes/exports.py`, where no export is open to a student.

    If this tool is ever changed to fetch data itself, that reasoning collapses and
    the gate must become the specific one for the data it reads.
    """
    from services.document_builder import DocumentBuildError
    from services.document_export import (
        DocumentQuotaExceeded,
        DocumentStorageUnavailable,
        create_document,
    )

    doc_type = (params.get("doc_type") or params.get("format") or "").strip().lower()
    if not doc_type:
        return {"success": False, "denied": False, "data": {}, "meta": {"count": 0},
                "message": "Which format? Choose docx, xlsx, pptx, pdf, csv, md or txt."}

    rows = params.get("rows") or []
    headers = params.get("headers") or []
    paragraphs = params.get("paragraphs") or []
    if isinstance(paragraphs, str):
        paragraphs = [paragraphs]

    try:
        result = await create_document(
            user=user,
            doc_type=doc_type,
            filename=params.get("filename", ""),
            title=params.get("title", ""),
            paragraphs=paragraphs,
            headers=headers,
            rows=rows,
            slides=params.get("slides"),
            source="assistant",
        )
    except (DocumentQuotaExceeded, DocumentStorageUnavailable) as exc:
        return {"success": False, "denied": False, "data": {}, "meta": {"count": 0},
                "message": str(exc)}
    except DocumentBuildError as exc:
        return {"success": False, "denied": False, "data": {}, "meta": {"count": 0},
                "message": str(exc)}

    message = f"Created {result['file_name']}."
    if result["truncated"]:
        message += " " + " ".join(result["notes"])

    return {
        "success": True,
        "denied": False,
        "data": result,
        "meta": {"count": 1},
        "message": message,
    }


# =========================================================================
#  COMBINED TOOL_REGISTRY
# =========================================================================

TOOL_REGISTRY = {
    # ---- Document generation (UI Sweep Epic 10) ----
    # Read-class ON PURPOSE: it changes no school record, so it carries no
    # `dispatch_type: "write"` and needs no confirm token. Students are excluded
    # because no export in routes/exports.py is open to them.
    "draft_document": {
        "fn": tool_draft_document,
        "roles": ["owner", "admin", "teacher"],
        "dispatch_type": "read",
        "description": (
            "Create a real downloadable file from content you have written — a Word "
            "document, Excel workbook, PowerPoint deck, PDF, CSV, Markdown or plain "
            "text. Use this whenever someone asks for a circular, notice, letter, fee "
            "sheet, report, template or presentation as a FILE they can print, sign, "
            "email or share. Put prose in `paragraphs` and tabular data in "
            "`headers` + `rows`. Returns a short `file_id` (not a link); append it in a "
            "`file` rich block and the download button fetches a fresh link on tap."
        ),
        "params_schema": {
            "doc_type": {"type": "string", "description": "docx, xlsx, pptx, pdf, csv, md or txt"},
            "title": {"type": "string", "description": "Document title / heading"},
            "filename": {"type": "string", "description": "Optional file name, without extension"},
            "paragraphs": {"type": "array", "description": "Lines of prose, in order"},
            "headers": {"type": "array", "description": "Column headings for tabular data"},
            "rows": {"type": "array", "description": "Rows of tabular data; each row is an array of cells"},
            "slides": {"type": "array", "description": "For pptx: [{title, bullets:[...]}]"},
        },
    },
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
    "get_announcements": {
        "fn": tool_get_announcements,
        "roles": ["student"],
        "description": "School announcements and notices visible to the student.",
        "params_schema": {
            "days": {"type": "integer", "description": "How many days back to look (default 7)"},
        },
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
        # R3.2: IT-tech support reads the same ticket queue (read-only), matching the
        # prompt that advertises this tool to both maintenance and it_tech admins.
        "sub_categories": ["maintenance", "it_tech"],
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
    "update_expense": {
        "fn": tool_update_expense,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "Update an existing expense (category, amount, vendor, description, date).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "expense_id": {"type": "string", "description": "Expense ID to update (required — use get_expenses to find it)"},
            "category": {"type": "string", "description": "Updated category"},
            "amount": {"type": "number", "description": "Updated amount in INR"},
            "description": {"type": "string", "description": "Updated description"},
            "vendor": {"type": "string", "description": "Updated vendor/payee"},
            "date": {"type": "string", "description": "Updated YYYY-MM-DD date"},
        },
    },
    "delete_expense": {
        "fn": tool_delete_expense,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "Permanently delete an expense record. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "expense_id": {"type": "string", "description": "Expense ID to delete (required — use get_expenses to find it)"},
        },
    },
    "mark_staff_attendance": {
        "fn": tool_mark_staff_attendance,
        "roles": ["owner", "admin"],
        "description": "Bulk-mark staff attendance for a date. Either pass records=[{staff_id, status}] or just a status (e.g. 'present') to apply to ALL active staff.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "date": {"type": "string", "description": "YYYY-MM-DD (defaults to today)"},
            "status": {"type": "string", "description": "present | absent | late | half_day | leave — applied to all active staff when records is omitted"},
            "records": {"type": "array", "description": "Per-staff records: [{staff_id, status, check_in?, check_out?}]"},
        },
    },
    "correct_fee_transaction": {
        "fn": tool_correct_fee_transaction,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "Correct a recorded fee transaction (amount, status, dates, payment mode, fee period/head). Requires a reason; keeps the original snapshot.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "transaction_id": {"type": "string", "description": "Fee transaction ID (required — use get_fee_transactions to find it)"},
            "reason": {"type": "string", "description": "Why the correction is needed (required)"},
            "amount": {"type": "number", "description": "Corrected amount"},
            "status": {"type": "string", "description": "Corrected status, e.g. paid | pending | partial | overdue"},
            "payment_mode": {"type": "string", "description": "Corrected payment mode"},
            "due_date": {"type": "string", "description": "Corrected due date YYYY-MM-DD"},
            "paid_date": {"type": "string", "description": "Corrected paid date YYYY-MM-DD"},
            "fee_period": {"type": "string", "description": "Corrected fee period"},
            "fee_head": {"type": "string", "description": "Corrected fee head"},
        },
    },
    "delete_fee_transaction": {
        "fn": tool_delete_fee_transaction,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "Delete a fee transaction (soft delete — kept in the financial trail). Use for duplicate or erroneous entries. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "transaction_id": {"type": "string", "description": "Fee transaction ID to delete (required — use get_fee_transactions to find it)"},
            "reason": {"type": "string", "description": "Why it is being deleted (e.g. duplicate entry)"},
        },
    },
    "trigger_fee_sync": {
        "fn": tool_trigger_fee_sync,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant"],
        "description": "Trigger a fee synchronization with the external fee system. Reports synced records and any conflicts.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {},
    },
    "get_fee_sync_status": {
        "fn": tool_get_fee_sync_status,
        "roles": ["owner", "admin"],
        "sub_categories": ["accountant", "principal"],
        "description": "Show the latest fee sync job status, synced counts, and unresolved conflicts.",
        "params_schema": {},
        "requires_confirmation": False,
    },
    "create_asset": {
        "fn": tool_create_asset,
        "roles": ["owner", "admin"],
        "description": "Add an inventory asset (name, category, quantity, location, status).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "name": {"type": "string", "description": "Asset name (required)"},
            "category": {"type": "string", "description": "e.g. furniture, electronics, sports"},
            "quantity": {"type": "number", "description": "Quantity (default 1)"},
            "location": {"type": "string", "description": "Where it is kept"},
            "status": {"type": "string", "description": "good | needs_repair | damaged (default good)"},
            "purchase_date": {"type": "string", "description": "YYYY-MM-DD"},
            "maintenance_due": {"type": "string", "description": "YYYY-MM-DD"},
        },
    },
    "update_asset": {
        "fn": tool_update_asset,
        "roles": ["owner", "admin"],
        "description": "Update an inventory asset (quantity, location, status, etc.).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "asset_id": {"type": "string", "description": "Asset ID (required)"},
            "name": {"type": "string", "description": "Updated name"},
            "category": {"type": "string", "description": "Updated category"},
            "quantity": {"type": "number", "description": "Updated quantity"},
            "location": {"type": "string", "description": "Updated location"},
            "status": {"type": "string", "description": "Updated condition status"},
            "maintenance_due": {"type": "string", "description": "Updated maintenance date"},
        },
    },
    "delete_asset": {
        "fn": tool_delete_asset,
        "roles": ["owner", "admin"],
        "description": "Permanently delete an inventory asset. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "asset_id": {"type": "string", "description": "Asset ID to delete (required)"},
        },
    },
    "log_visitor": {
        "fn": tool_log_visitor,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal", "receptionist"],
        "description": "Check a visitor in at the front desk (duplicate same-day check-ins are blocked unless force=true).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "visitor_name": {"type": "string", "description": "Visitor full name (required)"},
            "phone": {"type": "string", "description": "Contact number"},
            "purpose": {"type": "string", "description": "Purpose of the visit"},
            "whom_to_meet": {"type": "string", "description": "Person being visited"},
            "id_type": {"type": "string", "description": "ID shown, e.g. aadhaar, driving licence"},
            "force": {"type": "boolean", "description": "Override the same-day duplicate guard"},
        },
    },
    "checkout_visitor": {
        "fn": tool_checkout_visitor,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal", "receptionist"],
        "description": "Check a visitor out (sets their time_out).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "visitor_id": {"type": "string", "description": "Visitor log entry ID (required)"},
        },
    },
    "delete_visitor": {
        "fn": tool_delete_visitor,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal", "receptionist"],
        "description": "Delete a visitor-log entry. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "visitor_id": {"type": "string", "description": "Visitor log entry ID to delete (required)"},
        },
    },
    "create_certificate": {
        "fn": tool_create_certificate,
        "roles": ["owner", "admin"],
        "description": "Request/generate a student certificate (bonafide, tc, character, merit, etc.). Owner/principal issues instantly; other types may queue for approval.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "student_id": {"type": "string", "description": "Student ID (required — use search_students)"},
            "cert_type": {"type": "string", "description": "bonafide | tc | transfer_certificate | character | merit | participation (default bonafide)"},
            "content_data": {"type": "object", "description": "Optional extra fields for the certificate body"},
        },
    },
    "decide_certificate": {
        "fn": tool_decide_certificate,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Approve or reject a pending certificate request (reason required when rejecting).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "cert_id": {"type": "string", "description": "Certificate ID (required)"},
            "decision": {"type": "string", "description": "approve | reject (required)"},
            "reason": {"type": "string", "description": "Rejection reason (required when rejecting)"},
        },
    },
    "create_query_ticket": {
        "fn": tool_create_query_ticket,
        "roles": ["owner", "admin"],
        "description": "Raise an internal support/query ticket (title, description, priority).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "title": {"type": "string", "description": "Ticket title, 1-200 chars (required)"},
            "description": {"type": "string", "description": "Details, 1-2000 chars (required)"},
            "priority": {"type": "string", "description": "low | medium | high | urgent (required)"},
            "category": {"type": "string", "description": "Optional category (default general)"},
            "assigned_to": {"type": "string", "description": "Optional user ID to assign to"},
        },
    },
    "resolve_query_ticket": {
        "fn": tool_resolve_query_ticket,
        "roles": ["owner", "admin"],
        "sub_categories": ["it_tech"],
        "description": "Mark a support/query ticket resolved.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "ticket_id": {"type": "string", "description": "Ticket ID (required)"},
        },
    },
    "reopen_query_ticket": {
        "fn": tool_reopen_query_ticket,
        "roles": ["owner", "admin"],
        "sub_categories": ["it_tech"],
        "description": "Reopen a resolved support/query ticket.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "ticket_id": {"type": "string", "description": "Ticket ID (required)"},
        },
    },
    "assign_query_ticket": {
        "fn": tool_assign_query_ticket,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal", "it_tech", "receptionist"],
        "description": "Assign a support/query ticket to a staff member (sets status in_progress).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "ticket_id": {"type": "string", "description": "Ticket ID (required)"},
            "assigned_to": {"type": "string", "description": "User ID to assign (required)"},
            "status": {"type": "string", "description": "Optional status (default in_progress)"},
        },
    },
    "delete_query_ticket": {
        "fn": tool_delete_query_ticket,
        "roles": ["owner", "admin"],
        "sub_categories": ["it_tech"],
        "description": "Delete a support/query ticket. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "ticket_id": {"type": "string", "description": "Ticket ID to delete (required)"},
        },
    },
    "create_transport_route": {
        "fn": tool_create_transport_route,
        "roles": ["owner", "admin"],
        "description": "Create a transport route/zone (route name, stops, driver, vehicle, fare).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "route_name": {"type": "string", "description": "Route/zone name (required)"},
            "start_point": {"type": "string", "description": "Start point"},
            "end_point": {"type": "string", "description": "End point"},
            "stops": {"type": "array", "description": "List of stop names"},
            "driver_name": {"type": "string", "description": "Driver name"},
            "driver_phone": {"type": "string", "description": "Driver phone"},
            "vehicle_no": {"type": "string", "description": "Vehicle number"},
            "fare": {"type": "number", "description": "Monthly fare"},
            "description": {"type": "string", "description": "Optional zone description"},
        },
    },
    "update_transport_route": {
        "fn": tool_update_transport_route,
        "roles": ["owner", "admin"],
        "description": "Update a transport route (driver, vehicle, stops, fare, active flag).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "route_id": {"type": "string", "description": "Route ID (required — use get_transport_status)"},
            "route_name": {"type": "string", "description": "Updated name"},
            "driver_name": {"type": "string", "description": "Updated driver"},
            "driver_phone": {"type": "string", "description": "Updated driver phone"},
            "vehicle_no": {"type": "string", "description": "Updated vehicle"},
            "fare": {"type": "number", "description": "Updated fare"},
            "is_active": {"type": "boolean", "description": "Activate/deactivate the route"},
        },
    },
    "delete_transport_route": {
        "fn": tool_delete_transport_route,
        "roles": ["owner", "admin"],
        "description": "Delete a transport route. Blocked while active students are assigned. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "route_id": {"type": "string", "description": "Route ID to delete (required)"},
        },
    },
    "add_transport_vehicle": {
        "fn": tool_add_transport_vehicle,
        "roles": ["owner", "admin"],
        "description": "Register a transport vehicle (number, type, capacity, driver).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "vehicle_number": {"type": "string", "description": "Vehicle registration number (required)"},
            "vehicle_type": {"type": "string", "description": "bus | van | auto (default bus)"},
            "capacity": {"type": "number", "description": "Seating capacity"},
            "driver_name": {"type": "string", "description": "Driver name"},
            "driver_phone": {"type": "string", "description": "Driver phone"},
        },
    },
    "decide_announcement": {
        "fn": tool_decide_announcement,
        "roles": ["owner", "admin"],
        "sub_categories": ["principal"],
        "description": "Approve or reject a pending announcement (reason required when rejecting).",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "params_schema": {
            "announcement_id": {"type": "string", "description": "Announcement ID (required)"},
            "decision": {"type": "string", "description": "approve | reject (required)"},
            "reason": {"type": "string", "description": "Rejection reason (required when rejecting)"},
        },
    },
    "delete_announcement": {
        "fn": tool_delete_announcement,
        "roles": ["owner", "admin"],
        "description": "Delete an announcement. Destructive — requires a second confirmation.",
        "dispatch_type": "write",
        "requires_confirmation": True,
        "destructive": True,
        "params_schema": {
            "announcement_id": {"type": "string", "description": "Announcement ID to delete (required)"},
        },
    },
}

WRITE_TOOL_NAMES = {
    name for name, tool in TOOL_REGISTRY.items()
    if tool.get("requires_confirmation") or tool.get("dispatch_type") == "write"
}


def openai_tool_schema(name: str, tool_def: dict, required: "tuple | list" = ()) -> dict:
    """R11.2 AC2: derive a native function-calling schema from ONE registry entry.

    TOOL_REGISTRY is the single source of truth — the same `params_schema` that
    documents each tool becomes the JSON Schema the provider validates against.
    Because the provider constrains the model to the advertised tool names,
    invented tool names become impossible (AC3), and the R3 prompt↔registry
    parity gate becomes structural rather than only test-enforced.
    """
    props = {}
    for key, spec in (tool_def.get("params_schema") or {}).items():
        spec = dict(spec) if isinstance(spec, dict) else {"type": "string"}
        spec.setdefault("type", "string")
        # JSON Schema requires an `items` schema for arrays; supply a permissive
        # default when the registry entry omits it (e.g. attendance rows).
        if spec.get("type") == "array" and "items" not in spec:
            spec["items"] = {}
        props[key] = spec
    parameters = {"type": "object", "properties": props}
    req = [k for k in (required or ()) if k in props]
    if req:
        parameters["required"] = req
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": tool_def.get("description", "") or name.replace("_", " "),
            "parameters": parameters,
        },
    }
