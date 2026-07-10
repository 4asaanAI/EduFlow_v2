"""Export routes — CSV export for major data entities"""
from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from database import get_db
from middleware.auth import require_owner, require_role, get_current_user, require_owner_or_principal
from tenant import get_school_id, scoped_filter, scoped_query
import csv
import io
from datetime import date

router = APIRouter(prefix="/api/export", tags=["export"])


def _require_owner_or_accountant(request: Request) -> dict:
    """Allow owner, OR admin with sub_category=accountant (canonical name only)."""
    user = get_current_user(request)
    if user.get("role") == "owner":
        return user
    if user.get("role") == "admin" and user.get("sub_category") == "accountant":
        return user
    raise HTTPException(status_code=403, detail="Forbidden")


def make_csv_response(rows: list, headers: list, filename: str):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/students")
async def export_students(request: Request, format: str = "csv", user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    bid = user.get("branch_id")
    students = await db.students.find(scoped_query({"is_active": True}, branch_id=bid), {"_id": 0}).to_list(2000)
    headers = ["Name", "Admission No.", "Roll No.", "Gender", "DOB", "Status", "Admission Date"]
    rows = [[s.get("name"), s.get("admission_number", ""), s.get("roll_number", ""), s.get("gender", ""), s.get("dob", ""), s.get("status", ""), s.get("admission_date", "")] for s in students]
    return make_csv_response(rows, headers, f"students_{date.today()}.csv")


@router.get("/fee-transactions")
async def export_fees(request: Request, status: str = None, fee_period: str = None, user: dict = Depends(_require_owner_or_accountant)):
    db = get_db()
    bid = user.get("branch_id")
    query: dict = {}
    if status:
        query["status"] = status
    if fee_period:
        query["fee_period"] = fee_period
    txns = await db.fee_transactions.find(scoped_query(query, branch_id=bid), {"_id": 0}).to_list(5000)

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
    return make_csv_response(rows, headers, f"fees_{date.today()}.csv")


@router.get("/attendance")
async def export_attendance(request: Request, start_date: str = None, end_date: str = None, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
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
            return make_csv_response([], ["Student ID", "Date", "Status"], f"attendance_{date.today()}.csv")
        query["class_id"] = {"$in": class_ids}
        records = await db.student_attendance.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("date", 1).to_list(10000)
    else:
        records = await db.student_attendance.find(scoped_query(query, branch_id=bid), {"_id": 0}).sort("date", 1).to_list(10000)
    headers = ["Student ID", "Date", "Status"]
    rows = [[r.get("student_id"), r.get("date"), r.get("status")] for r in records]
    return make_csv_response(rows, headers, f"attendance_{date.today()}.csv")


@router.get("/staff")
async def export_staff(request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    bid = user.get("branch_id")
    staff = await db.staff.find(scoped_query({"is_active": True}, branch_id=bid), {"_id": 0, "salary": 0}).to_list(2000)
    headers = ["Name", "Type", "Employee ID", "Email", "Phone", "Join Date", "Department"]
    rows = [[s.get("name"), s.get("staff_type"), s.get("employee_id", ""), s.get("email", ""), s.get("phone", ""), s.get("join_date", ""), s.get("department", "")] for s in staff]
    return make_csv_response(rows, headers, f"staff_{date.today()}.csv")


@router.get("/expenses")
async def export_expenses(request: Request, user: dict = Depends(_require_owner_or_accountant)):
    db = get_db()
    expenses = await db.expenses.find(scoped_filter({}, get_school_id()), {"_id": 0}).sort("date", -1).to_list(1000)
    headers = ["Date", "Category", "Description", "Amount", "Vendor"]
    rows = [[e.get("date"), e.get("category"), e.get("description", ""), e.get("amount"), e.get("vendor", "")] for e in expenses]
    return make_csv_response(rows, headers, f"expenses_{date.today()}.csv")


@router.get("/enquiries")
async def export_enquiries(request: Request, user: dict = Depends(require_owner_or_principal)):
    db = get_db()
    bid = user.get("branch_id")
    enquiries = await db.enquiries.find(scoped_query({}, branch_id=bid), {"_id": 0}).sort("created_at", -1).to_list(1000)
    headers = ["Student Name", "Parent Name", "Class Applying", "Status", "Source", "Date"]
    rows = [[e.get("student_name"), e.get("parent_name"), e.get("class_applying", ""), e.get("status"), e.get("source", ""), e.get("created_at", "")[:10]] for e in enquiries]
    return make_csv_response(rows, headers, f"enquiries_{date.today()}.csv")


@router.get("/exam-results")
async def export_results(request: Request, user: dict = Depends(require_role("owner", "admin", "teacher"))):
    db = get_db()
    bid = user.get("branch_id")
    results_query: dict = {}
    if user.get("role") == "teacher":
        # Scope teacher to their own classes only
        teacher_classes = await db.classes.find(
            scoped_query({"class_teacher_id": user["id"]}, branch_id=bid), {"_id": 0, "id": 1}
        ).to_list(100)
        teacher_class_ids = [c["id"] for c in teacher_classes]
        if not teacher_class_ids:
            return make_csv_response([], ["Student ID", "Exam ID", "Subject", "Marks", "Max Marks", "Grade"], f"results_{date.today()}.csv")
        results_query["class_id"] = {"$in": teacher_class_ids}
    results = await db.exam_results.find(scoped_query(results_query, branch_id=bid), {"_id": 0}).to_list(10000)

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
    return make_csv_response(rows, headers, f"results_{date.today()}.csv")
