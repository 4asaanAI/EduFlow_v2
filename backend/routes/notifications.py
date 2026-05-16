from __future__ import annotations
"""Notifications API — Story 16: persistent in-app notifications + role-scoped digest"""
from fastapi import APIRouter, Request, HTTPException, Depends
from database import get_db
from middleware.auth import get_current_user, require_role
from services.notification_service import create_notification as create_persistent_notification
from tenant import get_school_id, scoped_filter
from datetime import datetime, date

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
        ann_query = scoped_filter({"is_draft": {"$ne": True}}, get_school_id())
        recent_ann = await db.announcements.find(ann_query, {"_id": 0, "title": 1, "created_at": 1, "audience_roles": 1}).sort("created_at", -1).to_list(5)

        if role in ["owner", "admin"]:
            pending = await db.leave_requests.count_documents(scoped_filter({"status": "pending"}, get_school_id()))
            if pending > 0:
                digest.append({"type": "warning", "title": "Pending Leave Requests", "message": f"{pending} leave request(s) awaiting approval", "time": "Now", "read": True, "is_digest": True})
            overdue = await db.fee_transactions.count_documents(scoped_filter({"status": "overdue"}, get_school_id()))
            if overdue > 0:
                digest.append({"type": "error", "title": "Fee Overdue", "message": f"{overdue} fee transaction(s) overdue", "time": "Today", "read": True, "is_digest": True})
            open_facility = await db.facility_requests.count_documents(scoped_filter({"status": {"$in": ["open", "in_progress"]}}, get_school_id()))
            if open_facility > 0:
                digest.append({"type": "info", "title": "Open Facility Requests", "message": f"{open_facility} facility request(s) in progress", "time": "Today", "read": True, "is_digest": True})

        elif role == "teacher":
            staff = await db.staff.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()))
            if staff:
                my_leaves = await db.leave_requests.count_documents(scoped_filter({"staff_id": staff["id"], "status": "pending"}, get_school_id()))
                if my_leaves > 0:
                    digest.append({"type": "info", "title": "Leave Status", "message": "Your leave request is pending approval", "time": "Now", "read": True, "is_digest": True})

        elif role == "student":
            own = await db.students.find_one(scoped_filter({"user_id": user["id"]}, get_school_id()))
            if own:
                records = await db.student_attendance.find(scoped_filter({"student_id": own["id"]}, get_school_id())).to_list(200)
                if records:
                    present = sum(1 for r in records if r["status"] == "present")
                    rate = round(present / len(records) * 100, 1)
                    if rate < 75:
                        digest.append({"type": "error", "title": "Low Attendance", "message": f"Your attendance is {rate}% — below 75% threshold", "time": "Today", "read": True, "is_digest": True})
                overdue = await db.fee_transactions.count_documents(scoped_filter({"student_id": own["id"], "status": {"$in": ["overdue", "pending"]}}, get_school_id()))
                if overdue > 0:
                    digest.append({"type": "warning", "title": "Fee Due", "message": f"{overdue} fee payment(s) pending", "time": "Today", "read": True, "is_digest": True})

        for a in recent_ann[:2]:
            target_roles = a.get("audience_roles", [])
            if not target_roles or "all" in target_roles or role in target_roles:
                digest.append({"type": "info", "title": "Announcement", "message": a["title"], "time": a.get("created_at", "")[:10], "read": True, "is_digest": True})

    digest_count = len(digest)
    combined = persistent + digest
    has_fallback = False
    if not combined and page == 1:
        has_fallback = True
        combined = [{"type": "success", "title": "All Good", "message": "No pending actions for now", "time": "Now", "read": True, "is_digest": True}]

    return {
        "success": True,
        "data": combined[:limit + digest_count],
        "meta": {
            "page": page,
            "limit": limit,
            "total": total,
            "digest_count": digest_count,
            "has_fallback": has_fallback,
        },
    }


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
    request_start = datetime.now().isoformat()
    await db.notifications.update_many(
        scoped_filter(
            {"user_id": user["id"], "read": False, "created_at": {"$lt": request_start}},
            get_school_id(),
        ),
        {"$set": {"read": True, "read_at": request_start}}
    )
    return {"success": True}


@router.post("")
async def create_notification(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    """Internal endpoint: create a notification for a specific user."""
    db = get_db()
    body = await request.json()
    if not body.get("user_id") or not body.get("title") or not body.get("message"):
        raise HTTPException(400, "user_id, title, and message are required")
    ok = await create_persistent_notification(
        db,
        user_id=body["user_id"],
        notification_type=body.get("type", "info"),
        title=body["title"],
        message=body["message"],
        source_id=body.get("source_record_id", ""),
        source_type=body.get("source_record_type", ""),
    )
    if not ok:
        raise HTTPException(503, "Notification could not be created")
    created = await db.notifications.find_one(
        scoped_filter(
            {
                "user_id": body["user_id"],
                "title": body["title"],
                "message": body["message"],
            },
            get_school_id(),
        ),
        {"_id": 0},
    )
    return {"success": True, "data": created}
