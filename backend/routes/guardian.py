"""Guardian portal: horizontally scoped ward overview."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from database import get_db
from middleware.auth import require_role
from ai.fee_metrics import fee_totals_from_txns
from services import photo_url_service
from tenant import scoped_query


router = APIRouter(prefix="/api/guardian", tags=["guardian"])


async def _ward(db, user: dict, student_id: str) -> dict:
    branch_id = user.get("branch_id")
    link = await db.guardians.find_one(
        scoped_query({"user_id": user["id"], "student_id": student_id}, branch_id=branch_id),
        {"_id": 0},
    )
    if not link:
        raise HTTPException(403, "Guardian is not linked to this student")
    student = await db.students.find_one(
        scoped_query({"id": student_id}, branch_id=branch_id), {"_id": 0}
    )
    if not student:
        raise HTTPException(404, "Student not found")
    # Photographs are answered as freshly signed links to the school's own bucket, the
    # same as everywhere else. Without this the parent portal handed a browser the
    # previous vendor's public CDN address for the child and both parents, which is the
    # exact exposure `photo_url_service` exists to close.
    photo_url_service.apply(student)
    return student


@router.get("/wards")
async def list_wards(request: Request, user: dict = Depends(require_role("parent"))):
    db = get_db()
    bid = user.get("branch_id")
    links = await db.guardians.find(
        scoped_query({"user_id": user["id"]}, branch_id=bid), {"_id": 0, "student_id": 1, "relation": 1}
    ).to_list(100)
    student_ids = [row["student_id"] for row in links if row.get("student_id")]
    students = await db.students.find(
        scoped_query({"id": {"$in": student_ids}}, branch_id=bid), {"_id": 0}
    ).to_list(len(student_ids) or 1)
    photo_url_service.apply_many(students)
    relation = {row["student_id"]: row.get("relation") for row in links if row.get("student_id")}
    data = [{**student, "guardian_relation": relation.get(student["id"])} for student in students]
    return {"success": True, "data": data, "meta": {"count": len(data)}}


@router.get("/wards/{student_id}/dashboard")
async def ward_dashboard(student_id: str, request: Request,
                         user: dict = Depends(require_role("parent"))):
    db = get_db()
    bid = user.get("branch_id")
    student = await _ward(db, user, student_id)
    since = (date.today() - timedelta(days=30)).isoformat()
    attendance = await db.student_attendance.find(
        scoped_query({"student_id": student_id, "date": {"$gte": since}}, branch_id=bid), {"_id": 0}
    ).sort("date", -1).to_list(100)
    results = await db.exam_results.find(
        scoped_query({"student_id": student_id}, branch_id=bid), {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    fees = await db.fee_transactions.find(
        scoped_query({"student_id": student_id, "deleted": {"$ne": True}}, branch_id=bid), {"_id": 0}
    ).sort("due_date", 1).to_list(500)
    assignments = await db.assignments.find(
        scoped_query({"class_id": student.get("class_id")}, branch_id=bid), {"_id": 0}
    ).sort("due_date", -1).to_list(50)
    leaves = await db.student_leave_requests.find(
        scoped_query({"student_id": student_id}, branch_id=bid), {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    loans = await db.library_loans.find(
        scoped_query({"borrower_type": "student", "borrower_id": student_id}, branch_id=bid), {"_id": 0}
    ).sort("issued_at", -1).to_list(50)
    announcements = await db.announcements.find(
        scoped_query({}, branch_id=bid), {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    visible_announcements = [item for item in announcements if (
        item.get("audience") in (None, "all", "parents", "parent")
        or item.get("class_id") == student.get("class_id")
    )][:20]
    attendance_counts = {status: sum(1 for row in attendance if row.get("status") == status)
                         for status in ("present", "absent", "late")}
    return {"success": True, "data": {
        "student": student,
        "attendance": {"last_30_days": attendance_counts, "records": attendance},
        "results": results,
        "fees": {"summary": fee_totals_from_txns(fees), "transactions": fees},
        "assignments": assignments,
        "leave_requests": leaves,
        "library_loans": loans,
        "announcements": visible_announcements,
    }}
