"""Notifications API — Story 16: persistent in-app notifications + role-scoped digest"""
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import get_current_user, require_role
from tenant import get_school_id, scoped_filter, add_school_id
from datetime import datetime, date
import uuid

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


def get_user(req: Request):
    return get_current_user(req)


@router.get("")
async def get_notifications(request: Request, page: int = 1, limit: int = 20):
    db = get_db()
    user = get_user(request)
    limit = min(max(limit, 1), 50)
    skip = max(page - 1, 0) * limit

    # Persistent notifications from the notifications collection
    query = scoped_filter({"user_id": user["id"]}, get_school_id())
    total = await db.notifications.count_documents(query)
    persistent = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    # Enrich with digest items only on page 1
    digest = []
    if page == 1:
        role = user["role"]
        today = date.today().strftime("%Y-%m-%d")
        ann_query = {"is_draft": {"$ne": True}}
        recent_ann = await db.announcements.find(ann_query, {"_id": 0, "title": 1, "created_at": 1, "audience_roles": 1}).sort("created_at", -1).to_list(5)

        if role in ["owner", "admin"]:
            pending = await db.leave_requests.count_documents({"status": "pending"})
            if pending > 0:
                digest.append({"type": "warning", "title": "Pending Leave Requests", "message": f"{pending} leave request(s) awaiting approval", "time": "Now", "read": True, "is_digest": True})
            overdue = await db.fee_transactions.count_documents({"status": "overdue"})
            if overdue > 0:
                digest.append({"type": "error", "title": "Fee Overdue", "message": f"{overdue} fee transaction(s) overdue", "time": "Today", "read": True, "is_digest": True})
            open_facility = await db.facility_requests.count_documents({"status": {"$in": ["open", "in_progress"]}})
            if open_facility > 0:
                digest.append({"type": "info", "title": "Open Facility Requests", "message": f"{open_facility} facility request(s) in progress", "time": "Today", "read": True, "is_digest": True})

        elif role == "teacher":
            staff = await db.staff.find_one({"user_id": user["id"]})
            if staff:
                my_leaves = await db.leave_requests.count_documents({"staff_id": staff["id"], "status": "pending"})
                if my_leaves > 0:
                    digest.append({"type": "info", "title": "Leave Status", "message": "Your leave request is pending approval", "time": "Now", "read": True, "is_digest": True})

        elif role == "student":
            own = await db.students.find_one({"user_id": user["id"]})
            if own:
                records = await db.student_attendance.find({"student_id": own["id"]}).to_list(200)
                if records:
                    present = sum(1 for r in records if r["status"] == "present")
                    rate = round(present / len(records) * 100, 1)
                    if rate < 75:
                        digest.append({"type": "error", "title": "Low Attendance", "message": f"Your attendance is {rate}% — below 75% threshold", "time": "Today", "read": True, "is_digest": True})
                overdue = await db.fee_transactions.count_documents({"student_id": own["id"], "status": {"$in": ["overdue", "pending"]}})
                if overdue > 0:
                    digest.append({"type": "warning", "title": "Fee Due", "message": f"{overdue} fee payment(s) pending", "time": "Today", "read": True, "is_digest": True})

        for a in recent_ann[:2]:
            target_roles = a.get("audience_roles", [])
            if not target_roles or "all" in target_roles or role in target_roles:
                digest.append({"type": "info", "title": "Announcement", "message": a["title"], "time": a.get("created_at", "")[:10], "read": True, "is_digest": True})

    combined = persistent + digest
    if not combined and page == 1:
        combined = [{"type": "success", "title": "All Good", "message": "No pending actions for now", "time": "Now", "read": True, "is_digest": True}]

    return {"success": True, "data": combined[:limit + len(digest)], "meta": {"page": page, "limit": limit, "total": total + len(digest)}}


@router.get("/unread-count")
async def get_unread_count(request: Request):
    db = get_db()
    user = get_user(request)
    count = await db.notifications.count_documents(
        scoped_filter({"user_id": user["id"], "read": False}, get_school_id())
    )
    return {"success": True, "data": {"unread_count": count}}


@router.patch("/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    result = await db.notifications.update_one(
        scoped_filter({"id": notification_id, "user_id": user["id"]}, get_school_id()),
        {"$set": {"read": True, "read_at": datetime.now().isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Notification not found")
    return {"success": True}


@router.patch("/mark-all-read")
async def mark_all_read(request: Request):
    db = get_db()
    user = get_user(request)
    await db.notifications.update_many(
        scoped_filter({"user_id": user["id"], "read": False}, get_school_id()),
        {"$set": {"read": True, "read_at": datetime.now().isoformat()}}
    )
    return {"success": True}


@router.post("")
async def create_notification(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    """Internal endpoint: create a notification for a specific user."""
    db = get_db()
    body = await request.json()
    if not body.get("user_id") or not body.get("message"):
        raise HTTPException(400, "user_id and message are required")
    notif = add_school_id({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "user_id": body["user_id"],
        "type": body.get("type", "info"),
        "message": body["message"],
        "source_record_id": body.get("source_record_id", ""),
        "source_record_type": body.get("source_record_type", ""),
        "read": False,
        "created_at": datetime.now().isoformat(),
    })
    await db.notifications.insert_one(notif)
    return {"success": True, "data": {k: v for k, v in notif.items() if k != "_id"}}
