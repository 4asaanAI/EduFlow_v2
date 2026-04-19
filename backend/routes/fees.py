from fastapi import APIRouter, Request, HTTPException
from database import get_db
from models.schemas import FeePaymentRequest, FeeTransaction
from middleware.auth import get_current_user
from datetime import datetime
import uuid

router = APIRouter(prefix="/api/fees", tags=["fees"])


def get_user(req: Request):
    return get_current_user(req)


@router.get("/structures")
async def get_fee_structures(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    structures = await db.fee_structures.find({}, {"_id": 0}).to_list(50)
    return {"success": True, "data": structures}


@router.get("/transactions")
async def get_fee_transactions(request: Request, student_id: str = None, status: str = None, class_id: str = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    query = {}
    if student_id:
        query["student_id"] = student_id
    if status:
        query["status"] = status

    # Filter by class: resolve student IDs in the class first
    if class_id:
        class_students = await db.students.find({"class_id": class_id}, {"_id": 0, "id": 1}).to_list(500)
        query["student_id"] = {"$in": [s["id"] for s in class_students]}

    txns = await db.fee_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    # Batch student lookups (fix N+1)
    s_ids = list(set(t["student_id"] for t in txns if t.get("student_id")))
    students = await db.students.find({"id": {"$in": s_ids}}, {"_id": 0, "id": 1, "name": 1, "class_id": 1}).to_list(len(s_ids)) if s_ids else []
    s_map = {s["id"]: s for s in students}
    # Batch class lookups
    c_ids = list(set(s.get("class_id") for s in students if s.get("class_id")))
    classes = await db.classes.find({"id": {"$in": c_ids}}, {"_id": 0, "id": 1, "name": 1, "section": 1}).to_list(len(c_ids)) if c_ids else []
    c_map = {c["id"]: c for c in classes}
    for t in txns:
        s = s_map.get(t["student_id"], {})
        t["student_name"] = s.get("name", "Unknown")
        cls = c_map.get(s.get("class_id", ""), {})
        t["class_name"] = f"{cls['name']}-{cls['section']}" if cls else "N/A"
    return {"success": True, "data": txns}


@router.get("/class-summary")
async def get_class_fee_summary(request: Request):
    """Returns per-class fee collection summary."""
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    classes = await db.classes.find({}, {"_id": 0}).to_list(50)
    result = []
    for cls in classes:
        students = await db.students.find({"class_id": cls["id"]}, {"_id": 0, "id": 1}).to_list(200)
        s_ids = [s["id"] for s in students]
        if not s_ids:
            continue
        txns = await db.fee_transactions.find({"student_id": {"$in": s_ids}}, {"_id": 0}).to_list(1000)
        paid = sum(t["amount"] for t in txns if t.get("status") == "paid")
        pending = sum(t["amount"] for t in txns if t.get("status") in ("pending", "overdue"))
        result.append({
            "class_id": cls["id"],
            "class_name": f"{cls['name']}-{cls['section']}",
            "total_students": len(s_ids),
            "paid": paid,
            "pending": pending,
            "total": paid + pending,
            "transactions": len(txns),
        })
    result.sort(key=lambda x: x["class_name"])
    return {"success": True, "data": result}


@router.get("/my")
async def get_my_fees(request: Request):
    db = get_db()
    user = get_user(request)
    student = await db.students.find_one({"user_id": user["id"]}, {"_id": 0})
    if not student:
        raise HTTPException(404, "Student record not found")
    txns = await db.fee_transactions.find({"student_id": student["id"]}, {"_id": 0}).to_list(50)
    return {"success": True, "data": txns}


@router.post("/transactions")
async def record_payment(body: FeePaymentRequest, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    receipt = f"RCP{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    is_paid = (body.status or "paid") == "paid"
    txn = FeeTransaction(
        student_id=body.student_id,
        fee_type=body.fee_type,
        amount=body.amount,
        status=body.status or "paid",
        due_date=body.due_date,
        paid_date=datetime.now().strftime("%Y-%m-%d") if is_paid else None,
        payment_mode=body.payment_mode,
        receipt_number=receipt,
        transaction_ref=body.transaction_ref,
    )
    await db.fee_transactions.insert_one({**txn.dict(), "_id": txn.id})
    return {"success": True, "data": txn.dict()}


@router.get("/summary")
async def get_fee_summary(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    pipeline = [{"$group": {"_id": "$status", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
    stats = await db.fee_transactions.aggregate(pipeline).to_list(10)
    return {"success": True, "data": {s["_id"]: {"total": s["total"], "count": s["count"]} for s in stats}}
