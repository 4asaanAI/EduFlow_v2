"""Export routes — CSV export for major data entities"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from database import get_db
import csv
import io
from datetime import date

router = APIRouter(prefix="/api/export", tags=["export"])


def get_user(req: Request):
    return {"id": req.headers.get("X-User-Id", "user-owner-001"), "role": req.headers.get("X-User-Role", "owner")}


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
async def export_students(request: Request, format: str = "csv"):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    students = await db.students.find({"is_active": True}, {"_id": 0}).to_list(2000)
    headers = ["Name", "Admission No.", "Roll No.", "Gender", "DOB", "Status", "Admission Date"]
    rows = [[s.get("name"), s.get("admission_number", ""), s.get("roll_number", ""), s.get("gender", ""), s.get("dob", ""), s.get("status", ""), s.get("admission_date", "")] for s in students]
    return make_csv_response(rows, headers, f"students_{date.today()}.csv")


@router.get("/fee-transactions")
async def export_fees(request: Request, status: str = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    query = {}
    if status:
        query["status"] = status
    txns = await db.fee_transactions.find(query, {"_id": 0}).to_list(5000)
    headers = ["Student", "Fee Type", "Amount", "Status", "Due Date", "Paid Date", "Payment Mode"]
    rows = []
    for t in txns:
        student = await db.students.find_one({"id": t["student_id"]}, {"_id": 0, "name": 1})
        rows.append([student["name"] if student else "N/A", t.get("fee_type"), t.get("amount"), t.get("status"), t.get("due_date", ""), t.get("paid_date", ""), t.get("payment_mode", "")])
    return make_csv_response(rows, headers, f"fees_{date.today()}.csv")


@router.get("/attendance")
async def export_attendance(request: Request, start_date: str = None, end_date: str = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher"]:
        raise HTTPException(403, "Forbidden")
    query = {}
    if start_date:
        query["date"] = {"$gte": start_date}
    if end_date:
        existing = query.get("date", {})
        existing["$lte"] = end_date
        query["date"] = existing
    records = await db.student_attendance.find(query, {"_id": 0}).sort("date", 1).to_list(10000)
    headers = ["Student ID", "Date", "Status"]
    rows = [[r.get("student_id"), r.get("date"), r.get("status")] for r in records]
    return make_csv_response(rows, headers, f"attendance_{date.today()}.csv")


@router.get("/staff")
async def export_staff(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    staff = await db.staff.find({"is_active": True}, {"_id": 0, "salary": 0}).to_list(500)
    headers = ["Name", "Type", "Employee ID", "Email", "Phone", "Join Date", "Department"]
    rows = [[s.get("name"), s.get("staff_type"), s.get("employee_id", ""), s.get("email", ""), s.get("phone", ""), s.get("join_date", ""), s.get("department", "")] for s in staff]
    return make_csv_response(rows, headers, f"staff_{date.today()}.csv")


@router.get("/expenses")
async def export_expenses(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner"]:
        raise HTTPException(403, "Owner only")
    expenses = await db.expenses.find({}, {"_id": 0}).sort("date", -1).to_list(1000)
    headers = ["Date", "Category", "Description", "Amount", "Vendor"]
    rows = [[e.get("date"), e.get("category"), e.get("description", ""), e.get("amount"), e.get("vendor", "")] for e in expenses]
    return make_csv_response(rows, headers, f"expenses_{date.today()}.csv")


@router.get("/enquiries")
async def export_enquiries(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    enquiries = await db.enquiries.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    headers = ["Student Name", "Parent Name", "Class Applying", "Status", "Source", "Date"]
    rows = [[e.get("student_name"), e.get("parent_name"), e.get("class_applying", ""), e.get("status"), e.get("source", ""), e.get("created_at", "")[:10]] for e in enquiries]
    return make_csv_response(rows, headers, f"enquiries_{date.today()}.csv")


@router.get("/exam-results")
async def export_results(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher"]:
        raise HTTPException(403, "Forbidden")
    results = await db.exam_results.find({}, {"_id": 0}).to_list(10000)
    headers = ["Student ID", "Exam ID", "Subject", "Marks", "Max Marks", "Grade"]
    rows = []
    for r in results:
        subj = await db.subjects.find_one({"id": r.get("subject_id")}, {"_id": 0, "name": 1})
        rows.append([r.get("student_id"), r.get("exam_id"), subj["name"] if subj else "N/A", r.get("marks_obtained"), r.get("max_marks"), r.get("grade", "")])
    return make_csv_response(rows, headers, f"results_{date.today()}.csv")
