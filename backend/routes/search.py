"""Search API — role-scoped search across all data"""
from fastapi import APIRouter, Request
from database import get_db

router = APIRouter(prefix="/api/search", tags=["search"])

TOOLS_BY_ROLE = {
    "owner": [
        {"id": "school-pulse", "name": "School pulse", "subtitle": "Today's overview", "type": "tool"},
        {"id": "fee-collection", "name": "Fee collection", "subtitle": "Revenue & defaulters", "type": "tool"},
        {"id": "student-strength", "name": "Student strength", "subtitle": "Class-wise overview", "type": "tool"},
        {"id": "attendance-overview", "name": "Attendance overview", "subtitle": "Trends & patterns", "type": "tool"},
        {"id": "staff-attendance-tracker", "name": "Staff tracker", "subtitle": "Attendance & leaves", "type": "tool"},
        {"id": "financial-reports", "name": "Financial reports", "subtitle": "Revenue & expenses", "type": "tool"},
        {"id": "smart-alerts", "name": "Smart alerts", "subtitle": "Exceptions & flags", "type": "tool"},
        {"id": "expense-tracker", "name": "Expense tracker", "subtitle": "Track & approve", "type": "tool"},
        {"id": "complaint-tracker", "name": "Complaints", "subtitle": "Grievance tracker", "type": "tool"},
        {"id": "ai-health-report", "name": "AI health report", "subtitle": "Weekly auto-summary", "type": "tool"},
        {"id": "admission-funnel", "name": "Admission funnel", "subtitle": "Enquiries & conversions", "type": "tool"},
        {"id": "staff-leave-manager", "name": "Leave manager", "subtitle": "Approve / reject", "type": "tool"},
    ],
    "admin": [
        {"id": "student-database", "name": "Student database", "subtitle": "Manage & search", "type": "tool"},
        {"id": "fee-tracker", "name": "Fee tracker", "subtitle": "Reminders & dues", "type": "tool"},
        {"id": "attendance-recorder", "name": "Attendance", "subtitle": "Mark & track", "type": "tool"},
        {"id": "certificate-generator", "name": "Certificates", "subtitle": "TC, Bonafide, etc.", "type": "tool"},
        {"id": "enquiry-register", "name": "Enquiry register", "subtitle": "Admission leads", "type": "tool"},
        {"id": "timetable-builder", "name": "Timetable", "subtitle": "Build & manage", "type": "tool"},
        {"id": "asset-tracker", "name": "Asset tracker", "subtitle": "Inventory & items", "type": "tool"},
        {"id": "visitor-log", "name": "Visitor log", "subtitle": "Entry & exit", "type": "tool"},
    ],
    "teacher": [
        {"id": "class-attendance-marker", "name": "Attendance", "subtitle": "Mark my class", "type": "tool"},
        {"id": "assignment-generator", "name": "Assignments", "subtitle": "Create & manage", "type": "tool"},
        {"id": "report-card-builder", "name": "Report cards", "subtitle": "Enter & generate", "type": "tool"},
        {"id": "leave-application", "name": "Leave application", "subtitle": "Apply for leave", "type": "tool"},
        {"id": "ptm-notes", "name": "PTM notes", "subtitle": "Parent meet notes", "type": "tool"},
        {"id": "curriculum-tracker", "name": "Curriculum tracker", "subtitle": "Track syllabus", "type": "tool"},
    ],
    "student": [
        {"id": "ai-tutor", "name": "AI tutor", "subtitle": "Study help", "type": "tool"},
        {"id": "homework-viewer", "name": "Homework", "subtitle": "My assignments", "type": "tool"},
        {"id": "attendance-self-check", "name": "My attendance", "subtitle": "View records", "type": "tool"},
        {"id": "result-viewer", "name": "My results", "subtitle": "Exam marks", "type": "tool"},
        {"id": "fee-status-viewer", "name": "My fees", "subtitle": "Payment status", "type": "tool"},
    ],
}


def get_user(req: Request):
    return {"id": req.headers.get("X-User-Id", "user-owner-001"), "role": req.headers.get("X-User-Role", "owner")}


@router.get("")
async def search(request: Request, q: str = "", type: str = "all"):
    db = get_db()
    user = get_user(request)
    role = user["role"]
    results = []

    if not q.strip():
        return {"success": True, "data": []}

    q_lower = q.lower()

    # Search tools (all roles)
    if type in ["all", "tool"]:
        for tool in TOOLS_BY_ROLE.get(role, []):
            if q_lower in tool["name"].lower() or q_lower in tool["subtitle"].lower():
                results.append({**tool})

    # Search persons (role-scoped)
    if type in ["all", "persons", "students"] and role in ["owner", "admin", "teacher"]:
        student_query = {"$or": [{"name": {"$regex": q, "$options": "i"}}, {"admission_number": {"$regex": q, "$options": "i"}}], "is_active": True}
        # Teacher: only see their own class students
        if role == "teacher":
            import os
            # Get teacher's classes (via user_id → staff → class_teacher_id)
            pass  # For now show all (scope later with real auth)
        students = await db.students.find(student_query, {"_id": 0, "id": 1, "name": 1, "admission_number": 1, "class_id": 1}).to_list(10)
        for s in students:
            cls = await db.classes.find_one({"id": s.get("class_id")}, {"_id": 0})
            sub_role = f"{cls['name']}-{cls['section']}" if cls else "Student"
            results.append({"id": s["id"], "name": s["name"], "subtitle": sub_role, "type": "student", "role": "student", "sub_role": sub_role})

    if type in ["all", "persons", "staff"] and role in ["owner", "admin"]:
        staff = await db.staff.find(
            {"name": {"$regex": q, "$options": "i"}, "is_active": True},
            {"_id": 0, "id": 1, "name": 1, "staff_type": 1, "department": 1, "specialization": 1}
        ).to_list(8)
        for s in staff:
            # Build sub_role based on staff_type
            st = s.get("staff_type", "")
            dept = s.get("department", "")
            spec = s.get("specialization", "")
            if st == "teacher":
                sub_role = f"Teacher{' · ' + spec if spec else ''}"
            elif st == "principal":
                sub_role = "Principal"
            elif st == "accountant":
                sub_role = "Accounts Dept"
            elif st in ["peon", "aaya", "sweeper", "guard", "gardner"]:
                sub_role = f"Support Staff · {st.capitalize()}"
            elif st in ["receptionist", "medical", "admission"]:
                sub_role = f"Admin Dept · {st.capitalize()}"
            else:
                sub_role = f"{dept or st}".capitalize()
            results.append({"id": s["id"], "name": s["name"], "subtitle": sub_role, "type": "staff", "role": st, "sub_role": sub_role})

    # Search announcements
    if type in ["all", "announcements"]:
        annts = await db.announcements.find(
            {"$or": [{"title": {"$regex": q, "$options": "i"}}, {"content": {"$regex": q, "$options": "i"}}], "is_draft": False},
            {"_id": 0, "id": 1, "title": 1, "created_at": 1}
        ).to_list(5)
        for a in annts:
            results.append({"id": a["id"], "name": a["title"], "subtitle": a.get("created_at", "")[:10], "type": "announcement"})

    # For student role: search own data only
    if role == "student" and type in ["all", "students"]:
        own = await db.students.find_one({"user_id": user["id"]}, {"_id": 0, "name": 1, "id": 1})
        if own and q_lower in own.get("name", "").lower():
            results.append({"name": own["name"], "subtitle": "My profile", "type": "student"})

    return {"success": True, "data": results[:15]}
