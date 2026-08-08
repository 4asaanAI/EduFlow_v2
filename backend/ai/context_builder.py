from __future__ import annotations

from contextvars import ContextVar
from datetime import datetime, date
from database import get_db
from tenant import get_school_id, scoped_filter, scoped_query
from ai.fee_metrics import DEFAULTER_STATUSES, compute_fee_totals

# Flo's ambient context follows the active branch. EduFlow serves Joya only today,
# but this prevents future branch data entering the prompt before tool authorization.


_active_branch: ContextVar[str | None] = ContextVar("flo_context_branch", default=None)


def _tenant_query(query: dict | None = None) -> dict:
    school_query = scoped_filter(query or {}, get_school_id())
    branch_id = _active_branch.get()
    return scoped_query(school_query, branch_id=branch_id) if branch_id else school_query


def _tenant_match(query: dict | None = None) -> dict:
    return {"$match": _tenant_query(query)}


async def _get_house_standings(db) -> list:
    """Return the 4 houses sorted by points (descending)."""
    houses = await db.houses.find(
        _tenant_query({"is_active": {"$ne": False}}),
        {"_id": 0, "name": 1, "points": 1},
    ).sort("points", -1).to_list(4)
    return [
        {"house": house.get("name", ""), "points": house.get("points", 0)}
        for house in houses
        if house.get("name")
    ]


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
    """Return total outstanding fees (canonical shared formula, R7.1/M5)."""
    totals = await compute_fee_totals(db, _tenant_query({}))
    return _format_currency(totals["outstanding"])


async def _get_fee_defaulter_count(db) -> int:
    """Distinct students carrying any outstanding balance (R7.1/AC3 — canonical
    defaulter definition, not only status='overdue')."""
    rows = await db.fee_transactions.find(
        _tenant_query({"status": {"$in": list(DEFAULTER_STATUSES)}}),
        {"_id": 0, "student_id": 1},
    ).to_list(20000)
    return len({r.get("student_id") for r in rows if r.get("student_id")})


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
    title_collection = getattr(db, "library_titles", None)
    titles = await title_collection.find(
        _tenant_query({"is_active": True}),
        {"_id": 0, "id": 1, "isbn": 1, "accession_number": 1, "title": 1, "copies_total": 1},
    ).to_list(5000) if title_collection is not None else []
    legacy_title_collection = getattr(db, "library_books", None)
    legacy_titles = await legacy_title_collection.find(
        _tenant_query(), {"_id": 0, "id": 1, "isbn": 1, "accession_number": 1, "title": 1, "copies_total": 1}
    ).to_list(10000) if legacy_title_collection is not None else []
    def title_key(row):
        return row.get("isbn") or row.get("accession_number") or row.get("id") or row.get("title")
    modern_keys = {title_key(row) for row in titles if title_key(row)}
    legacy_only = [row for row in legacy_titles if title_key(row) not in modern_keys]
    total_books = sum(int(row.get("copies_total") or 1) for row in [*titles, *legacy_only])
    loan_collection = getattr(db, "library_loans", None)
    loans = await loan_collection.find(
        _tenant_query({"status": "issued"}), {"_id": 0, "id": 1, "due_at": 1}
    ).to_list(10000) if loan_collection is not None else []
    legacy_loan_collection = getattr(db, "library_transactions", None)
    legacy_loans = await legacy_loan_collection.find(
        _tenant_query({"status": {"$in": ["issued", "overdue"]}}), {"_id": 0, "id": 1, "due_date": 1, "status": 1}
    ).to_list(10000) if legacy_loan_collection is not None else []
    loan_ids = {row.get("id") for row in loans if row.get("id")}
    legacy_only_loans = [row for row in legacy_loans if not row.get("id") or row.get("id") not in loan_ids]
    books_issued = len(loans) + len(legacy_only_loans)
    today = date.today().isoformat()
    overdue_returns = sum(1 for row in loans if str(row.get("due_at") or "")[:10] < today)
    overdue_returns += sum(
        1 for row in legacy_only_loans
        if row.get("status") == "overdue" or (row.get("due_date") and str(row["due_date"])[:10] < today)
    )
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
    item_collection = getattr(db, "inventory_items", None)
    items = await item_collection.find(
        _tenant_query({"is_active": True}),
        {"_id": 0, "id": 1, "sku": 1, "name": 1, "on_hand": 1, "quantity": 1,
         "reorder_level": 1, "min_stock": 1},
    ).to_list(10000) if item_collection is not None else []
    legacy_collection = getattr(db, "inventory", None)
    legacy = await legacy_collection.find(
        _tenant_query(), {"_id": 0, "id": 1, "sku": 1, "name": 1, "quantity": 1, "reorder_level": 1}
    ).to_list(10000) if legacy_collection is not None else []
    def item_key(row):
        return row.get("sku") or row.get("id") or row.get("name")
    modern_keys = {item_key(row) for row in items if item_key(row)}
    combined = [*items, *[row for row in legacy if item_key(row) not in modern_keys]]
    return sum(
        1 for item in combined
        if float(item.get("on_hand", item.get("quantity", 0)) or 0)
        <= float(item.get("reorder_level", item.get("min_stock", 0)) or 0)
    )


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
    ctx["fee_defaulters"] = await _get_fee_defaulter_count(db)
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
    ctx["fee_defaulters"] = await _get_fee_defaulter_count(db)
    ctx["pending_invoices"] = await db.fee_transactions.count_documents(_tenant_query({"status": "pending"}))
    return ctx


# ---------------------------------------------------------------------------
# Transport head: transport context only
# ---------------------------------------------------------------------------
async def _build_transport_head_context(db, today: str) -> dict:
    ctx = await _get_transport_stats(db, today)

    # Route-level detail (top 10 routes)
    school_id = get_school_id()
    routes = await db.transport_routes.find(
        scoped_filter({}, school_id),
        {"_id": 0, "name": 1, "route_number": 1, "is_active": 1, "stops": 1},
    ).to_list(10)

    route_summary = []
    for r in routes:
        status = "active" if r.get("is_active", True) else "inactive"
        stop_count = len(r.get("stops", []))
        route_summary.append(
            f"Route {r.get('route_number', '?')} ({r.get('name', 'unnamed')}): {stop_count} stops, {status}"
        )

    ctx["routes"] = route_summary if route_summary else ["No routes configured"]
    return ctx


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
            start, end = (int(part.strip()) for part in coordinator_range.split("-", 1))
            if start <= end:
                patterns = [rf"(?:Class\s*)?{number}(?:st|nd|rd|th)?\b" for number in range(start, end + 1)]
                classes = await db.classes.find(
                    _tenant_query({"name": {"$regex": "^(?:" + "|".join(patterns) + ")", "$options": "i"}})
                ).to_list(100)
        except (ValueError, TypeError):
            classes = []
    elif coordinator_range:
        classes = await db.classes.find(
            _tenant_query({"name": {"$regex": re.escape(coordinator_range), "$options": "i"}})
        ).to_list(100)
    else:
        classes = []

    ctx["classes_in_range"] = len(classes)

    # Per-class attendance for coordinator's range
    class_ids = [c["id"] for c in classes if "id" in c]

    class_attendance = []
    shown_classes = classes[:8]  # cap at 8 classes to keep context size manageable
    # NEW-04/T7: two batched reads for all 8 classes, then group in memory
    # (was 2 count_documents per class — 16 round trips on every context build).
    shown_ids = [c["id"] for c in shown_classes if c.get("id")]
    present_by_class: dict = {}
    roll_by_class: dict = {}
    if shown_ids:
        present_rows = await db.student_attendance.find(
            _tenant_query({"class_id": {"$in": shown_ids}, "date": today, "status": "present"}),
            {"_id": 0, "class_id": 1},
        ).to_list(20000)
        for row in present_rows:
            present_by_class[row.get("class_id")] = present_by_class.get(row.get("class_id"), 0) + 1
        roll_rows = await db.students.find(
            _tenant_query({"class_id": {"$in": shown_ids}, "is_active": True}),
            {"_id": 0, "class_id": 1},
        ).to_list(20000)
        for row in roll_rows:
            roll_by_class[row.get("class_id")] = roll_by_class.get(row.get("class_id"), 0) + 1

    for cls in shown_classes:
        present = present_by_class.get(cls["id"], 0)
        total = roll_by_class.get(cls["id"], 0)
        pct = round(present / total * 100, 1) if total else 0
        class_attendance.append(f"{cls.get('name', '')} {cls.get('section', '')}: {pct}% ({present}/{total})")

    ctx["class_attendance_breakdown"] = class_attendance if class_attendance else ["No classes in range"]

    # Aggregate summary for backward compat
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
            present_total = await db.student_attendance.count_documents(_tenant_query({
                "student_id": {"$in": student_ids},
                "date": today,
                "status": "present",
            }))
            if marked > 0:
                rate = round(present_total / marked * 100, 1)
                ctx["overall_attendance"] = f"{rate}% ({present_total}/{marked})"
            else:
                ctx["overall_attendance"] = "Not yet marked"
        else:
            ctx["overall_attendance"] = "No students found"
    else:
        ctx["overall_attendance"] = "No classes in range"

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

    # Resolve class name from class_id
    class_doc = await db.classes.find_one({"id": student.get("class_id")}, {"_id": 0, "name": 1, "section": 1})
    if class_doc:
        ctx["class_name"] = f"{class_doc.get('name', '')} {class_doc.get('section', '')}".strip()
    else:
        ctx["class_name"] = ctx.get("class_id", "Unknown Class")

    # Next upcoming exam (school-wide, exams use start_date not exam_date)
    today_iso = today
    try:
        next_exam = await db.exams.find_one(
            _tenant_query({"start_date": {"$gte": today_iso}}),
            sort=[("start_date", 1)],
            projection={"_id": 0, "name": 1, "start_date": 1, "exam_type": 1},
        )
    except AttributeError:
        next_exam = None
    if next_exam:
        ctx["next_exam"] = f"{next_exam.get('name')} ({next_exam.get('exam_type', '')}) starting {next_exam.get('start_date')}"
    else:
        ctx["next_exam"] = "No upcoming exams scheduled"

    # Is student currently in an active exam period?
    try:
        active_exam = await db.exams.find_one(_tenant_query({
            "start_date": {"$lte": today_iso},
            "end_date": {"$gte": today_iso},
        }))
    except AttributeError:
        active_exam = None
    ctx["is_exam_period"] = active_exam is not None
    ctx["current_exam_name"] = active_exam.get("name") if active_exam else None

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
        house_doc = await db.houses.find_one(
            _tenant_query({"name": house}), {"_id": 0, "points": 1}
        )
        ctx["house"] = house
        ctx["house_points"] = house_doc.get("points", 0) if house_doc else 0
    else:
        ctx["house"] = None
        ctx["house_points"] = 0

    return ctx


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def build_school_context(role: str, user_id: str, branch_id: str | None = None) -> dict:
    token = _active_branch.set(branch_id)
    try:
        return await _build_school_context(role, user_id)
    finally:
        _active_branch.reset(token)


async def _build_school_context(role: str, user_id: str) -> dict:
    db = get_db()
    today = date.today().strftime("%Y-%m-%d")

    # Load school settings once for all roles
    # Epic 4 / Story 4.4: the projection is widened, NOT joined by a second query —
    # this runs once per chat turn, so an extra round trip would cost every user of
    # the assistant permanently. `principal` (not `principal_name`) is the field the
    # record actually stores; the prompt builder used to look for the wrong one.
    settings = await db.school_settings.find_one(
        {}, {
            "_id": 0, "principal": 1, "owner_name": 1, "school_name": 1,
            "board": 1, "city": 1, "state": 1, "address": 1,
            "phone": 1, "email": 1, "website": 1,
            "affiliation_no": 1, "school_code": 1, "ai_context": 1,
        }
    )
    settings = settings or {}

    # Fetch current academic year name
    ay_doc = await db.academic_years.find_one(_tenant_query({"is_current": True}), {"_id": 0, "name": 1})
    academic_year = (ay_doc or {}).get("name", "2025-26")

    # Determine sub_category for scoped context
    if role == "student":
        role_ctx = await _build_student_context(db, today, user_id)
        role_ctx["_school_settings"] = settings
        role_ctx["academic_year"] = academic_year
        return role_ctx

    # For all staff roles, look up sub_category
    staff = await db.staff.find_one(_tenant_query({"user_id": user_id}))
    sub_category = staff.get("sub_category", role) if staff else role

    def _with_school(ctx: dict) -> dict:
        ctx["_school_settings"] = settings
        ctx["academic_year"] = academic_year
        return ctx

    # Owner: everything
    if role == "owner":
        return _with_school(await _build_owner_context(db, today))

    # Admin sub-categories.
    # Normalize + alias-map the raw sub_category the SAME way scope_resolver
    # does (._resolve_admin_scope), so a legacy/mis-cased value like
    # "Accountant", "accounts", "transport", or "front_desk" gets its proper
    # operational context instead of falling through to the minimal context
    # (which would under-inform a user the resolver has already granted tool
    # access to).
    if role == "admin":
        effective = str(sub_category or "").strip().lower()
        if effective == "principal":
            return _with_school(await _build_principal_context(db, today))
        if effective in ("accountant", "accounts"):
            return _with_school(await _build_accounts_context(db, today))
        if effective in ("transport_head", "transport"):
            return _with_school(await _build_transport_head_context(db, today))
        if effective in ("receptionist", "front_desk"):
            return _with_school(await _build_receptionist_context(db, today))
        # R5 (fail-closed, DEFERRED row 18): admin sub_categories WITHOUT an
        # explicit operational context (it_tech, maintenance, management,
        # support_staff, or an unrecognised/legacy value) must NOT inherit the
        # principal's school-wide view. scope_resolver already denies them
        # principal-level tool access; the chat context is aligned to that —
        # minimal, not principal (was a silent over-exposure of school-wide data).
        return _with_school({
            "role": "admin",
            "sub_category": sub_category,
            "note": (
                "Limited administrative access — no school-wide operational data "
                "in context. Ask the principal or owner for school-wide reports."
            ),
        })

    # Teacher sub-categories
    if role == "teacher":
        if sub_category == "class_teacher":
            return _with_school(await _build_class_teacher_context(db, today, user_id))
        if str(sub_category).lower() == "hod":
            return _with_school(await _build_hod_context(db, today, user_id))
        if sub_category == "coordinator":
            return _with_school(await _build_coordinator_context(db, today, user_id))
        # Default teacher gets class_teacher view
        return _with_school(await _build_class_teacher_context(db, today, user_id))

    # Fallback: return minimal context
    return _with_school({"role": role, "note": "No scoped context available for this role"})


def detect_language(text: str) -> str:
    """Detect if text is Hindi (Devanagari) or English."""
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return "hi"
    return "en"
