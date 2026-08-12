"""Export routes - the school's records as a CSV or an Excel workbook.

TWO THINGS WERE FIXED HERE ON 2026-08-12 (Release 3), and both were live.

1. EVERY EXPORT SILENTLY CUT ROWS OFF
   Each route ended in a hardcoded `to_list(N)`: students 2000, fees 5000, staff
   2000, expenses 1000, enquiries 1000, attendance and results 10000. There was no
   count, no total and no warning anywhere. Students at 2,000 left 124 rows of
   headroom on a roll of 1,876, so the next intake would have started dropping
   children out of the file with nothing to show it had happened.

   A truncated export is worse than a truncated screen. It leaves the building. It
   gets mailed to the trust, filed as a record, and reconciled against. So an
   export is now COMPLETE OR REFUSED - see `_read_all` below. It never ships short.

2. THE PERMISSION GATES DID NOT MATCH THE PERMISSION TABLE
   They were hand-written role checks predating Release 2's grant table, and they
   disagreed with it in both directions: the accountant head could not export the
   student list he works in every day, while the fee export used its own local
   helper. Abhimanyu's decision of 2026-08-12 is that **a download is not a way
   around the permission table** - an export respects who is looking. So the gate
   is now derived from `services/profile_matrix.py` rather than re-stated here.
   See `EXPORT_SCREENS`.

Exports need NO confirm step and NO approval, on screen or through Flo (same
decision). Reading data you may already read is not an action that needs guarding;
it is the WHO that needs guarding, and that is what the gate above does.
"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from database import get_db
# Only `get_current_user` is needed now. The four role helpers this module used to
# import (require_owner, require_role, require_owner_or_principal and a local
# owner-or-accountant helper) were the hand-written gates that had drifted from the
# permission table; `require_export` below replaced all of them.
#
# `require_owner_or_principal` is the exception, and it is not a hand-written gate:
# the whole-school workbook is Aman and Adesh only (Abhimanyu, 2026-08-12) and that
# helper already means exactly those two people.
from middleware.auth import get_current_user, require_owner_or_principal
from services import profile_matrix
from tenant import scoped_query
from services.document_builder import build_document, build_workbook, DocumentBuildError
import csv
import io
import re
from datetime import date

router = APIRouter(prefix="/api/export", tags=["export"])


# ── How many rows one export may contain ─────────────────────────────────────
#
# This is a REFUSAL threshold, not a truncation point. Nothing is ever silently
# dropped at it; the request fails and says so. It exists only so that one
# download cannot ask the server to hold an unbounded collection in memory.
#
# 100,000 is roughly ten times the school's longest list (the payment ledger, about
# 10,700 rows), so no real export can reach it. If one ever does, the right answer
# is a date range on the request, and the error message says that.
EXPORT_MAX_ROWS = 100_000


async def _read_all(cursor, what: str) -> list:
    """Every matching row, or an error. Never a short list.

    `cursor` is a Motor cursor that has NOT been given a limit. We ask for one row
    more than we will accept: getting it back is how we know rows were left behind,
    which a plain `to_list(N)` can never tell you.
    """
    rows = await cursor.to_list(EXPORT_MAX_ROWS + 1)
    if len(rows) > EXPORT_MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"There are more than {EXPORT_MAX_ROWS:,} {what} to export, which is "
                "too many for one file. Narrow it with a date range and export in "
                "parts. Nothing has been left out of a file: this request produced "
                "no file at all."
            ),
        )
    return rows


# ── Who may export what ──────────────────────────────────────────────────────
#
# An export is a READ of a screen's data, so it is allowed exactly when the caller
# may open a screen that shows that data. Mapping to screens rather than to roles
# is what keeps this honest: when the permission table changes, the exports follow
# it, and there is no second list of role names to forget to update.
#
# A data set can be reachable from more than one screen (staff appear in both the
# School Directory and the Staff Tracker). Holding ANY of the listed screens is
# enough, because holding it means the person may already read these rows.
EXPORT_SCREENS = {
    "students": ("student-database",),
    "staff": ("student-database", "staff-tracker"),
    "fee-transactions": ("fee-collection", "fee-tracker", "financial-reports"),
    "expenses": ("expense-tracker",),
    "enquiries": ("enquiry-register", "admission-funnel"),
    "attendance": ("attendance-overview", "attendance-recorder"),
    "exam-results": ("exam-manager",),
    # Added with the whole-school workbook (Release 3). Both data sets already had a
    # screen; they had no export until the workbook needed them, and putting them in
    # `EXPORT_BUILDERS` makes them reachable by Flo too, so they need a gate here or
    # they would fall to `may_export`'s default deny and read as broken.
    "classes": ("academic-structure", "timetable-builder"),
    "transport": ("transport-hub", "transport-manager", "transport-optimisation"),
}

# Roles that are NOT in the permission table but still hold an export, and the
# narrowing that goes with it. Teachers are not a matrix profile - the table
# governs the owner and the eight admin desks - but a class teacher has always been
# able to export their OWN classes' attendance and results, and each handler still
# scopes the query to the classes they teach. Removing that would take away
# something they use, which is not what this release is for.
EXPORT_EXTRA_ROLES = {
    "attendance": ("teacher",),
    "exam-results": ("teacher",),
}


def require_export(export_key: str):
    """Dependency: may this caller download this data set?

    Default deny. Three ways to pass, in this order:

    1. A LIVE profile in the permission table that may open one of the screens the
       data appears on.
    2. A role listed in `EXPORT_EXTRA_ROLES` for this export (teachers only).
    3. Nothing else.

    **Dormant profiles are refused on purpose, even when they hold the screen.**
    The front desk and the transport head are both granted `student-database` in
    the table, so mirroring screen access alone would hand either of them a
    download of all 1,876 children the moment their profile is switched on. Release
    2 was explicit that it must not be what gives a dormant profile new powers, and
    a whole-roll download is a bigger thing than a paged screen. Switching a
    profile on therefore includes deciding what it may export, as a decision
    somebody writes down rather than a side effect.
    """
    screens = EXPORT_SCREENS.get(export_key, ())
    extra_roles = EXPORT_EXTRA_ROLES.get(export_key, ())

    def _gate(request: Request) -> dict:
        user = get_current_user(request)
        profile = profile_matrix.profile_of(user)
        if profile:
            if profile_matrix.PROFILE_MATRIX[profile]["status"] != "live":
                raise HTTPException(status_code=403, detail="Forbidden")
            if any(profile_matrix.may_open_screen(user, s) for s in screens):
                return user
            # A matrix profile that lacks the screen is refused here and does not
            # fall through to the role check below. Falling through is how a
            # subtraction rule gets reintroduced by accident.
            raise HTTPException(status_code=403, detail="Forbidden")
        if user.get("role") in extra_roles:
            return user
        raise HTTPException(status_code=403, detail="Forbidden")

    # `scripts/audit_profile_reach.py` names each route's guard by its function name
    # in order to work out who can reach what. An anonymous closure would land in
    # that script's "guards I do not understand" list, which it prints rather than
    # skips - so the audit would still be honest, but it would stop being useful for
    # seven routes. Naming it keeps the reach report complete.
    _gate.__name__ = f"require_export({export_key})"
    return _gate


# Cells that a spreadsheet would run instead of showing.
#
# Excel and LibreOffice treat a cell opening with "=" as a formula, and one opening
# with "@" as a function call. A name, a note or an address that begins with either
# would therefore be EXECUTED rather than read when the school opens the file. This
# matters most for the table export below, whose rows are whatever the screen was
# showing, but there is no reason the older seven should be treated differently, so
# the guard sits in the one place both go through.
#
# "+" and "-" are the other two characters usually named in this advice, and they are
# deliberately NOT guarded here: the school's data is full of "+91" phone numbers and
# negative amounts, and prefixing those would turn real numbers into text and break
# the arithmetic the office does on the file. The cure would be worse than the
# disease. "=" and "@" never legitimately open a value in this data.
_FORMULA_STARTERS = ("=", "@")


def _safe_cell(value):
    """A value the spreadsheet will SHOW rather than run."""
    if isinstance(value, str) and value[:1] in _FORMULA_STARTERS:
        return "'" + value
    return value


def _safe_rows(rows: list) -> list:
    return [[_safe_cell(c) for c in row] for row in rows]


def make_csv_response(rows: list, headers: list, filename: str):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(_safe_rows(rows))
    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def make_export_response(rows: list, headers: list, basename: str, fmt: str = "csv", title: str = ""):
    """Return an export in the requested format.

    Epic 10 / Story 10.4. A fee sheet as raw commas loses its columns the moment it
    is opened; the same data as a workbook opens readable. The data, the query and
    above all the ROLE GATE are untouched - this changes packaging only, which is
    why it needed no product decision.

    An unrecognised format falls back to CSV rather than erroring, matching how
    Epic 3 handled an unrecognised sort field: the client's option list is a
    convenience, never the enforcement.
    """
    if (fmt or "").lower() in ("xlsx", "excel"):
        built = build_document(
            doc_type="xlsx",
            filename=basename,
            title=title or basename.replace("_", " ").title(),
            headers=headers,
            rows=_safe_rows(rows),
            # The builder's own default is 5,000 rows and it TRUNCATES at it. That
            # would have quietly halved an Excel download of the payment ledger
            # (about 10,700 rows) while `_read_all` above was promising the file was
            # complete - the same fault this module was rewritten to remove, one
            # layer further down. The export's ceiling is the only one that applies,
            # and it refuses rather than trims.
            max_rows=EXPORT_MAX_ROWS,
        )
        return StreamingResponse(
            iter([built.content]),
            media_type=built.content_type,
            headers={"Content-Disposition": f'attachment; filename="{built.filename}"'},
        )
    return make_csv_response(rows, headers, f"{basename}.csv")


async def build_students(db, user, params=None):
    """(headers, rows, title) for the student list."""
    bid = user.get("branch_id")
    students = await _read_all(db.students.find(scoped_query({"is_active": True}, branch_id=bid), {"_id": 0}), "students")
    headers = ["Name", "Admission No.", "Roll No.", "Gender", "DOB", "Status", "Admission Date"]
    rows = [[s.get("name"), s.get("admission_number", ""), s.get("roll_number", ""), s.get("gender", ""), s.get("dob", ""), s.get("status", ""), s.get("admission_date", "")] for s in students]
    return headers, rows, "Students"


async def build_fees(db, user, params=None):
    """(headers, rows, title) for the payment ledger. Honours `status`, `fee_period`."""
    params = params or {}
    status = params.get("status")
    fee_period = params.get("fee_period")
    bid = user.get("branch_id")
    query: dict = {}
    if status:
        query["status"] = status
    if fee_period:
        query["fee_period"] = fee_period
    txns = await _read_all(db.fee_transactions.find(scoped_query(query, branch_id=bid), {"_id": 0}), "fee transactions")

    # Pre-fetch all students in ONE query (no N+1)
    student_ids = list({t["student_id"] for t in txns if t.get("student_id")})
    students_list = await db.students.find(
        scoped_query({"id": {"$in": student_ids}}, branch_id=bid),
        {"_id": 0, "id": 1, "name": 1, "class_id": 1},
    ).to_list(None) if student_ids else []
    student_map = {s["id"]: s for s in students_list}

    # Pre-fetch class names
    class_ids = list({s.get("class_id") for s in students_list if s.get("class_id")})
    classes_list = await db.classes.find(
        {"id": {"$in": class_ids}},
        {"_id": 0, "id": 1, "name": 1, "section": 1},
    ).to_list(None) if class_ids else []
    class_map = {c["id"]: f"{c.get('name', '')} {c.get('section', '')}".strip() for c in classes_list}

    headers = [
        "Student", "Class", "Fee Type", "Period", "Amount", "Paid Amount",
        "Status", "Due Date", "Paid Date", "Payment Mode",
        "Transaction Ref", "Receipt No", "Corrected",
    ]
    rows = []
    for t in txns:
        stu = student_map.get(t.get("student_id") or "")
        stu_name = stu["name"] if stu else "N/A"
        class_name = class_map.get(stu.get("class_id") or "") if stu else ""
        rows.append([
            stu_name,
            class_name,
            t.get("fee_type", ""),
            t.get("fee_period", ""),
            t.get("amount"),
            t.get("paid_amount", t.get("amount")),
            t.get("status", ""),
            t.get("due_date", ""),
            t.get("paid_date", ""),
            t.get("payment_mode", ""),
            t.get("transaction_ref", ""),
            t.get("receipt_number", ""),
            t.get("corrected", False),
        ])
    return headers, rows, "Fee Transactions"


async def build_attendance(db, user, params=None):
    """(headers, rows, title) for attendance. Honours `start_date`, `end_date`."""
    params = params or {}
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    bid = user.get("branch_id")
    query = {}
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing = query.get("date", {})
        existing["$lte"] = end_date
        query["date"] = existing
    if user.get("role") == "teacher":
        # Scope teacher to their own classes only
        teacher_classes = await db.classes.find(
            scoped_query({"class_teacher_id": user["id"]}, branch_id=bid), {"_id": 0, "id": 1}
        ).to_list(100)
        class_ids = [c["id"] for c in teacher_classes]
        if not class_ids:
            return ["Student ID", "Date", "Status"], [], "Attendance"
        query["class_id"] = {"$in": class_ids}
        records = await _read_all(db.student_attendance.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("date", 1), "attendance records")
    else:
        records = await _read_all(db.student_attendance.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("date", 1), "attendance records")
    headers = ["Student ID", "Date", "Status"]
    rows = [[r.get("student_id"), r.get("date"), r.get("status")] for r in records]
    return headers, rows, "Attendance"


async def build_staff(db, user, params=None):
    """(headers, rows, title) for the staff list. Salary is projected out."""
    bid = user.get("branch_id")
    staff = await _read_all(db.staff.find(scoped_query({"is_active": True}, branch_id=bid), {"_id": 0, "salary": 0}), "staff members")
    headers = ["Name", "Type", "Employee ID", "Email", "Phone", "Join Date", "Department"]
    rows = [[s.get("name"), s.get("staff_type"), s.get("employee_id", ""), s.get("email", ""), s.get("phone", ""), s.get("join_date", ""), s.get("department", "")] for s in staff]
    return headers, rows, "Staff"


async def build_expenses(db, user, params=None):
    """(headers, rows, title) for expenses."""
    # D-29 CLOSED 2026-08-04 by the owner's decision ("Aaryans has only one branch, make
    # EduFlow one-branch specific"). This was the one export that read school-wide while
    # every neighbour scoped to the caller's branch. It now matches them.
    #
    # No visible change today: there is exactly one branch (branch-joya) and all 1,802
    # students sit on it, so the same rows come back. What changes is that a branch-bound
    # accountant can no longer see another branch's spending the day a second branch
    # exists. An owner carries no branch_id and still reads across, by design.
    bid = user.get("branch_id")
    expenses = await _read_all(db.expenses.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("date", -1), "expenses")
    headers = ["Date", "Category", "Description", "Amount", "Vendor"]
    rows = [[e.get("date"), e.get("category"), e.get("description", ""), e.get("amount"), e.get("vendor", "")] for e in expenses]
    return headers, rows, "Expenses"


async def build_enquiries(db, user, params=None):
    """(headers, rows, title) for the enquiry register."""
    bid = user.get("branch_id")
    enquiries = await _read_all(db.enquiries.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("created_at", -1), "enquiries")
    headers = ["Student Name", "Parent Name", "Class Applying", "Status", "Source", "Date"]
    rows = [[e.get("student_name"), e.get("parent_name"), e.get("class_applying", ""), e.get("status"), e.get("source", ""), e.get("created_at", "")[:10]] for e in enquiries]
    return headers, rows, "Enquiries"


async def build_results(db, user, params=None):
    """(headers, rows, title) for exam results."""
    bid = user.get("branch_id")
    results_query: dict = {}
    if user.get("role") == "teacher":
        # Scope teacher to their own classes only
        teacher_classes = await db.classes.find(
            scoped_query({"class_teacher_id": user["id"]}, branch_id=bid), {"_id": 0, "id": 1}
        ).to_list(100)
        teacher_class_ids = [c["id"] for c in teacher_classes]
        if not teacher_class_ids:
            return ["Student ID", "Exam ID", "Subject", "Marks", "Max Marks", "Grade"], [], "Exam Results"
        results_query["class_id"] = {"$in": teacher_class_ids}
    results = await _read_all(db.exam_results.find(scoped_query(results_query, branch_id=bid), {"_id": 0}), "exam results")

    # Pre-fetch all subjects in ONE query (no N+1)
    subject_ids = list({r.get("subject_id") for r in results if r.get("subject_id")})
    subjects_list = await db.subjects.find(
        scoped_query({"id": {"$in": subject_ids}}, branch_id=bid),
        {"_id": 0, "id": 1, "name": 1},
    ).to_list(None) if subject_ids else []
    subject_map = {s["id"]: s for s in subjects_list}

    # Pre-fetch all classes in ONE query (no N+1)
    class_ids = list({r.get("class_id") for r in results if r.get("class_id")})
    classes_list = await db.classes.find(
        scoped_query({"id": {"$in": class_ids}}, branch_id=bid),
        {"_id": 0, "id": 1, "name": 1, "section": 1},
    ).to_list(None) if class_ids else []
    class_map = {c["id"]: f"{c.get('name', '')} {c.get('section', '')}".strip() for c in classes_list}

    headers = ["Student ID", "Exam ID", "Subject", "Marks", "Max Marks", "Grade"]
    rows = []
    for r in results:
        subj_name = subject_map.get(r.get("subject_id"), {}).get("name", "Unknown")
        rows.append([r.get("student_id"), r.get("exam_id"), subj_name, r.get("marks_obtained"), r.get("max_marks"), r.get("grade", "")])
    return headers, rows, "Exam Results"


async def build_classes(db, user, params=None):
    """(headers, rows, title) for the class list, with each class's strength.

    Added for the whole-school workbook (Release 3, item B). It goes in the SAME
    dictionary as the other seven rather than being written beside the workbook: a
    query that exists in only one file is the next thing to drift.
    """
    bid = user.get("branch_id")
    classes = await _read_all(db.classes.find(scoped_query({}, branch_id=bid), {"_id": 0}), "classes")

    # One read for the roll, counted in memory. A count per class would be 48 queries.
    strength: dict = {}
    students = await db.students.find(
        scoped_query({"is_active": True}, branch_id=bid), {"_id": 0, "class_id": 1}
    ).to_list(EXPORT_MAX_ROWS)
    for s in students:
        cid = s.get("class_id")
        strength[cid] = strength.get(cid, 0) + 1

    teacher_ids = [c.get("class_teacher_id") for c in classes if c.get("class_teacher_id")]
    teachers = await db.staff.find(
        scoped_query({"id": {"$in": teacher_ids}}, branch_id=bid), {"_id": 0, "id": 1, "name": 1}
    ).to_list(None) if teacher_ids else []
    teacher_map = {t["id"]: t.get("name", "") for t in teachers}

    headers = ["Class", "Section", "Class Teacher", "Students", "Room", "Academic Year"]
    rows = [[
        c.get("name", ""),
        c.get("section", ""),
        teacher_map.get(c.get("class_teacher_id") or "", ""),
        strength.get(c.get("id"), 0),
        c.get("room", ""),
        c.get("academic_year", ""),
    ] for c in classes]
    return headers, rows, "Classes"


async def build_transport(db, user, params=None):
    """(headers, rows, title) for the bus routes, with the children on each."""
    bid = user.get("branch_id")
    routes = await _read_all(db.transport_routes.find(scoped_query({}, branch_id=bid), {"_id": 0}), "transport routes")

    riders: dict = {}
    if routes:
        rows_on_routes = await db.students.find(
            scoped_query({"route_zone_id": {"$in": [r.get("id") for r in routes]},
                          "is_active": {"$ne": False}}, branch_id=bid),
            {"_id": 0, "route_zone_id": 1},
        ).to_list(EXPORT_MAX_ROWS)
        for row in rows_on_routes:
            zid = row.get("route_zone_id")
            riders[zid] = riders.get(zid, 0) + 1

    headers = ["Route", "From", "To", "Stops", "Driver", "Driver Phone",
               "Vehicle No.", "Capacity", "Students", "Fare", "Active"]
    rows = []
    for r in routes:
        stops = r.get("stops") or []
        rows.append([
            r.get("route_name", ""),
            r.get("start_point", ""),
            r.get("end_point", ""),
            # Stops are a list. Joined rather than dropped: a route sheet without its
            # stops is not a record of a route.
            ", ".join(str(s) for s in stops) if isinstance(stops, list) else str(stops),
            r.get("driver_name", ""),
            r.get("driver_phone", ""),
            r.get("vehicle_no", ""),
            r.get("capacity", ""),
            riders.get(r.get("id"), 0),
            r.get("fare", 0),
            "Yes" if r.get("is_active", True) else "No",
        ])
    return headers, rows, "Transport"


# ── One definition of each export, two ways in ───────────────────────────────
#
# The seven builders above return (headers, rows, title). They do NOT format a file
# and they do NOT check permission, so the same query can be reached by the download
# button on a screen AND by Flo, without either of them restating what the export is.
#
# WHY FLO NEEDED THIS (2026-08-12). Flo could already make an Excel file, but only out
# of rows it happened to be holding in the conversation - it would fetch a page of
# students with a read tool and hand those rows to `draft_document`. Ask it for "all
# 1,876 children in Excel" and you would get a sheet holding whatever it had seen,
# with nothing on the sheet to say so. That is this release's defining fault in the
# worst place it could happen: a short file, that leaves the building, and is filed.
#
# So `export_data_file` reads the rows HERE, from the database, complete or refused,
# through the same gate as the route. Nothing passes through the model.
EXPORT_BUILDERS = {
    "students": build_students,
    "fee-transactions": build_fees,
    "attendance": build_attendance,
    "staff": build_staff,
    "expenses": build_expenses,
    "enquiries": build_enquiries,
    "exam-results": build_results,
    "classes": build_classes,
    "transport": build_transport,
}


def may_export(user: dict, export_key: str) -> bool:
    """The gate in `require_export`, as a plain question.

    Same rules, same order, same default deny - dormant profiles included. It is a
    separate function only because a FastAPI dependency cannot be asked a question
    outside a request; it must never become a SECOND set of rules.
    """
    screens = EXPORT_SCREENS.get(export_key, ())
    extra_roles = EXPORT_EXTRA_ROLES.get(export_key, ())
    profile = profile_matrix.profile_of(user)
    if profile:
        if profile_matrix.PROFILE_MATRIX[profile]["status"] != "live":
            return False
        return any(profile_matrix.may_open_screen(user, s) for s in screens)
    return user.get("role") in extra_roles


async def build_export(export_key: str, user: dict, params: dict = None):
    """(headers, rows, title) for a named export, or a 400 if the name is unknown."""
    builder = EXPORT_BUILDERS.get(export_key)
    if not builder:
        raise HTTPException(
            status_code=400,
            detail=(
                f"There is no export called '{export_key}'. Choose one of: "
                + ", ".join(sorted(EXPORT_BUILDERS))
            ),
        )
    return await builder(get_db(), user, params or {})


async def _respond(export_key: str, user: dict, fmt: str, params: dict = None):
    headers, rows, title = await build_export(export_key, user, params)
    basename = f"{export_key.replace('-', '_')}_{date.today()}"
    return make_export_response(rows, headers, basename, fmt, title)


@router.get("/students")
async def export_students(request: Request, format: str = "csv", user: dict = Depends(require_export("students"))):
    return await _respond("students", user, format)


@router.get("/fee-transactions")
async def export_fees(request: Request, status: str = None, fee_period: str = None, format: str = "csv", user: dict = Depends(require_export("fee-transactions"))):
    return await _respond("fee-transactions", user, format, {"status": status, "fee_period": fee_period})


@router.get("/attendance")
async def export_attendance(request: Request, start_date: str = None, end_date: str = None, format: str = "csv", user: dict = Depends(require_export("attendance"))):
    return await _respond("attendance", user, format, {"start_date": start_date, "end_date": end_date})


@router.get("/staff")
async def export_staff(request: Request, format: str = "csv", user: dict = Depends(require_export("staff"))):
    return await _respond("staff", user, format)


@router.get("/expenses")
async def export_expenses(request: Request, format: str = "csv", user: dict = Depends(require_export("expenses"))):
    return await _respond("expenses", user, format)


@router.get("/enquiries")
async def export_enquiries(request: Request, format: str = "csv", user: dict = Depends(require_export("enquiries"))):
    return await _respond("enquiries", user, format)


@router.get("/exam-results")
async def export_results(request: Request, format: str = "csv", user: dict = Depends(require_export("exam-results"))):
    return await _respond("exam-results", user, format)


# ── The whole school in one file ─────────────────────────────────────────────
#
# Aman (owner) and Adesh (principal) only - Abhimanyu, 2026-08-12 - which is exactly
# what `require_owner_or_principal` already means, so no new gate was invented for it.
#
# It is built by LOOPING `EXPORT_BUILDERS` above, not by writing nine fresh queries.
# Nine more queries would be nine more places for a row ceiling and a scoping rule to
# drift away from the download button on the screen, which is most of what this
# release has been spent undoing.
#
# The sheet order is the order somebody works down it: the people first, then the
# money, then the day-to-day.
WHOLE_SCHOOL_SHEETS = (
    ("students", "Children"),
    ("staff", "Staff"),
    ("fee-transactions", "Fees and Payments"),
    ("attendance", "Attendance"),
    ("exam-results", "Exam Results"),
    ("classes", "Classes"),
    ("transport", "Transport"),
    ("expenses", "Expenses"),
    ("enquiries", "Enquiries"),
)


async def build_school_workbook(user: dict):
    """(BuiltDocument, [(sheet name, row count)]) for the whole school.

    Never trimmed. Each builder is complete or it raises, and `build_workbook`
    refuses a sheet over the ceiling rather than shortening it.
    """
    db = get_db()
    sheets = []
    counts = []
    for key, sheet_name in WHOLE_SCHOOL_SHEETS:
        headers, rows, _title = await EXPORT_BUILDERS[key](db, user, {})
        sheets.append({"name": sheet_name, "headers": headers, "rows": _safe_rows(rows)})
        counts.append((sheet_name, len(rows)))
    try:
        built = build_workbook(
            sheets=sheets,
            filename=f"the_aaryans_whole_school_{date.today()}",
            # The refusal ceiling, not the builder's own 5,000-row trim point.
            max_rows=EXPORT_MAX_ROWS,
        )
    except DocumentBuildError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    return built, counts


@router.get("/school-workbook")
async def export_school_workbook(request: Request, user: dict = Depends(require_owner_or_principal)):
    """Every area of the school as one Excel file, a sheet per area.

    Owner and principal only. No confirm step, like every other export.
    """
    built, counts = await build_school_workbook(user)
    return StreamingResponse(
        iter([built.content]),
        media_type=built.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{built.filename}"',
            # The counts on the response too, so the screen can say what it saved
            # without opening the file. A download that says nothing about its size is
            # how a short one goes unnoticed.
            "X-Export-Row-Counts": "; ".join(f"{n}: {c}" for n, c in counts),
        },
    )


# ── The other 28 tables ──────────────────────────────────────────────────────
#
# Seven data sets have a server export above. The platform has about 35 tables, so
# most screens have no query here to call, and writing 28 more hand-rolled route
# handlers would mean 28 more places for a row ceiling and a role check to drift -
# which is precisely the pair of faults that had to be dug back out of the seven.
#
# So the packaging is separated from the reading. A screen fetches EVERY row it is
# showing through its own list endpoint - already permission-gated, already scoped to
# the school and branch, already walked page by page by `lib/fetchAllRows.js` so it
# cannot come back short - and then posts those rows here to be turned into a file.
#
# WHY THIS IS NOT A WAY AROUND THE PERMISSION TABLE. This route reads no data. It
# formats what the caller sent back to the caller, and the caller could only have got
# it by passing the gate on the list endpoint it came from. There is nothing here to
# widen: a person who cannot open the fee screen cannot obtain fee rows to post.
#
# It is still a downloadable file, so it is the one place where a value that a
# spreadsheet would EXECUTE could arrive from outside - see `_safe_cell` above.

# A generous ceiling on one posted table. Well above the longest list the school has
# (the payment ledger, about 10,700 rows) and far below the point where formatting
# one request would strain a small instance. Over it, the request is refused - never
# trimmed, for the reason this whole module carries at the top.
TABLE_EXPORT_MAX_ROWS = 50_000
TABLE_EXPORT_MAX_COLUMNS = 60


@router.post("/table")
async def export_table(request: Request, user: dict = Depends(get_current_user)):
    """Turn the rows a screen is showing into a CSV or an Excel file.

    Body: `{ title, headers: [...], rows: [[...]], format: "csv" | "xlsx" }`.

    Exports need no confirm step and no approval (Abhimanyu, 2026-08-12), so there
    is none here. The guarding an export needs is on WHO may read the rows, and that
    happened before they got to this request.
    """
    body = await request.json() if await request.body() else {}
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Expected an object describing the table to export.")

    headers = body.get("headers") or []
    rows = body.get("rows") or []
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="`headers` and `rows` must both be lists.")
    if not headers:
        raise HTTPException(status_code=400, detail="An export needs column headings.")
    if len(headers) > TABLE_EXPORT_MAX_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"A table export may have at most {TABLE_EXPORT_MAX_COLUMNS} columns.",
        )
    if len(rows) > TABLE_EXPORT_MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"That is more than {TABLE_EXPORT_MAX_ROWS:,} rows, which is too many for "
                "one file. Narrow it with a filter or a date range and export in parts. "
                "Nothing has been left out of a file: this request produced no file at all."
            ),
        )

    clean_rows = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            raise HTTPException(status_code=400, detail="Every row must be a list of cell values.")
        clean_rows.append(list(row)[:TABLE_EXPORT_MAX_COLUMNS])

    title = str(body.get("title") or "Export")[:120]
    basename = re.sub(r"[^A-Za-z0-9_-]+", "_", title).strip("_").lower() or "export"
    fmt = body.get("format") or "csv"
    return make_export_response(clean_rows, headers, f"{basename}_{date.today()}", fmt, title)
