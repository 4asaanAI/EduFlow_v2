"""Notifications API — role-scoped notifications"""
from fastapi import APIRouter, Request
from database import get_db
from middleware.auth import get_current_user
from datetime import datetime, date, timedelta

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def get_user(req: Request):
    return get_current_user(req)


@router.get("")
async def get_notifications(request: Request):
    db = get_db()
    user = get_user(request)
    role = user["role"]
    notifs = []
    today = date.today().strftime("%Y-%m-%d")

    # Fetch announcements once — use $ne True so docs without the field also match
    ann_query = {"is_draft": {"$ne": True}}
    recent_ann = await db.announcements.find(ann_query, {"_id": 0, "title": 1, "created_at": 1}).sort("created_at", -1).to_list(3)

    if role in ["owner", "admin"]:
        # Pending leaves
        pending = await db.leave_requests.count_documents({"status": "pending"})
        if pending > 0:
            notifs.append({"type": "warning", "title": "Pending Leave Requests", "message": f"{pending} leave request(s) awaiting approval", "time": "Now"})

        # Fee overdue
        overdue = await db.fee_transactions.count_documents({"status": "overdue"})
        if overdue > 0:
            notifs.append({"type": "error", "title": "Fee Overdue", "message": f"{overdue} fee transaction(s) overdue", "time": "Today"})

        # Announcements
        for a in recent_ann[:2]:
            notifs.append({"type": "info", "title": "Announcement", "message": a["title"], "time": a.get("created_at", "")[:10]})

    elif role == "teacher":
        # My pending leave
        staff = await db.staff.find_one({"user_id": user["id"]})
        if staff:
            my_leaves = await db.leave_requests.count_documents({"staff_id": staff["id"], "status": "pending"})
            if my_leaves > 0:
                notifs.append({"type": "info", "title": "Leave Status", "message": "Your leave request is pending approval", "time": "Now"})

        # Announcements (always shown for teacher)
        for a in recent_ann:
            notifs.append({"type": "info", "title": "Announcement", "message": a["title"], "time": a.get("created_at", "")[:10]})

    elif role == "student":
        own = await db.students.find_one({"user_id": user["id"]})
        if own:
            # Check attendance below 75%
            records = await db.student_attendance.find({"student_id": own["id"]}).to_list(200)
            if records:
                present = sum(1 for r in records if r["status"] == "present")
                rate = round(present / len(records) * 100, 1)
                if rate < 75:
                    notifs.append({"type": "error", "title": "Low Attendance", "message": f"Your attendance is {rate}% — below 75% threshold", "time": "Today"})

            # Pending fees
            overdue = await db.fee_transactions.count_documents({"student_id": own["id"], "status": {"$in": ["overdue", "pending"]}})
            if overdue > 0:
                notifs.append({"type": "warning", "title": "Fee Due", "message": f"{overdue} fee payment(s) pending", "time": "Today"})

        # Announcements (always shown for student)
        for a in recent_ann:
            notifs.append({"type": "info", "title": "Announcement", "message": a["title"], "time": a.get("created_at", "")[:10]})

    if not notifs:
        notifs.append({"type": "success", "title": "All Good", "message": "No pending actions for now", "time": "Now"})

    return {"success": True, "data": notifs[:8]}
