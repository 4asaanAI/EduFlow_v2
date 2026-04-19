from fastapi import APIRouter, Request, HTTPException
from database import get_db
from middleware.auth import get_current_user
from datetime import datetime

router = APIRouter(prefix="/api/staff", tags=["staff"])


def get_user(req: Request):
    return get_current_user(req)


@router.get("/")
async def list_staff(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    staff = await db.staff.find({"is_active": True}, {"_id": 0, "salary": 0}).to_list(100)
    return {"success": True, "data": staff}


@router.get("/{staff_id}/leave-requests")
async def get_leave_requests(staff_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    leaves = await db.leave_requests.find({"staff_id": staff_id}, {"_id": 0}).to_list(50)
    return {"success": True, "data": leaves}


@router.get("/leaves/my")
async def get_my_leaves(request: Request):
    """Get current user's own leave requests (for teacher role)"""
    db = get_db()
    user = get_user(request)
    # First try direct user_id match (newer docs have this field)
    leaves = await db.leave_requests.find({"user_id": user["id"]}, {"_id": 0}).sort("applied_at", -1).to_list(20)
    if not leaves:
        # Fallback: look up via staff record for older docs
        staff = await db.staff.find_one({"user_id": user["id"]}, {"_id": 0})
        if staff:
            leaves = await db.leave_requests.find({"staff_id": staff["id"]}, {"_id": 0}).sort("applied_at", -1).to_list(20)
    return {"success": True, "data": leaves}


@router.get("/leaves/pending")
async def get_pending_leaves(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    leaves = await db.leave_requests.find({"status": "pending"}, {"_id": 0}).to_list(50)
    # Batch staff lookups (fix N+1)
    s_ids = list(set(lr["staff_id"] for lr in leaves if lr.get("staff_id")))
    staff_list = await db.staff.find({"id": {"$in": s_ids}}, {"_id": 0, "salary": 0}).to_list(len(s_ids)) if s_ids else []
    staff_map = {s["id"]: s for s in staff_list}
    enriched = [{**lr, "staff": staff_map.get(lr["staff_id"])} for lr in leaves]
    return {"success": True, "data": enriched}


@router.patch("/leaves/{leave_id}")
async def update_leave(leave_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    body = await request.json()
    update = {
        "status": body.get("status"),
        "approved_by": user["id"],
        "approved_at": datetime.now().isoformat(),
    }
    if body.get("rejection_reason"):
        update["rejection_reason"] = body["rejection_reason"]
    await db.leave_requests.update_one({"id": leave_id}, {"$set": update})
    return {"success": True}
