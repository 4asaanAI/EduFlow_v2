from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from database import get_db
from models.schemas import FeeTransaction
from middleware.auth import get_current_user
from datetime import datetime, timedelta
from tenant import get_school_id, scoped_filter
import uuid

router = APIRouter(prefix="/api/fees", tags=["fees"])


def get_user(req: Request):
    return get_current_user(req)


def _serialize(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _fee_query(extra: dict | None = None) -> dict:
    return scoped_filter(extra or {}, get_school_id())


def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value[:10])
    except ValueError:
        return None


async def _audit(db, *, action: str, entity_id: str, user: dict, changes: dict, reason: str | None = None):
    await db.audit_logs.insert_one({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "entity_type": "fee_transaction",
        "entity_id": entity_id,
        "action": action,
        "changed_by": user.get("id"),
        "changed_by_role": user.get("role"),
        "changes": changes,
        "reason": reason,
        "created_at": datetime.now().isoformat(),
    })


async def _student_map(db, txns):
    s_ids = list(set(t["student_id"] for t in txns if t.get("student_id")))
    students = await db.students.find(_fee_query({"id": {"$in": s_ids}}), {"_id": 0, "id": 1, "name": 1, "class_id": 1}).to_list(len(s_ids)) if s_ids else []
    s_map = {s["id"]: s for s in students}
    c_ids = list(set(s.get("class_id") for s in students if s.get("class_id")))
    classes = await db.classes.find(_fee_query({"id": {"$in": c_ids}}), {"_id": 0, "id": 1, "name": 1, "section": 1}).to_list(len(c_ids)) if c_ids else []
    c_map = {c["id"]: c for c in classes}
    return s_map, c_map


@router.get("/structures")
async def get_fee_structures(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    structures = await db.fee_structures.find(_fee_query(), {"_id": 0}).to_list(50)
    return {"success": True, "data": structures}


@router.get("/transactions")
async def get_fee_transactions(request: Request, student_id: str = None, status: str = None, class_id: str = None, overdue_days: int = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    query = _fee_query()
    if student_id:
        query["student_id"] = student_id
    if status:
        query["status"] = status

    if class_id:
        class_students = await db.students.find(_fee_query({"class_id": class_id}), {"_id": 0, "id": 1}).to_list(500)
        query["student_id"] = {"$in": [s["id"] for s in class_students]}

    txns = await db.fee_transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    if overdue_days is not None:
        cutoff = datetime.now() - timedelta(days=overdue_days)
        txns = [
            t for t in txns
            if t.get("status") in ("pending", "overdue", "unpaid")
            and _parse_date(t.get("due_date"))
            and _parse_date(t.get("due_date")) <= cutoff
        ]

    s_map, c_map = await _student_map(db, txns)
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

    classes = await db.classes.find(_fee_query(), {"_id": 0}).to_list(50)
    result = []
    for cls in classes:
        students = await db.students.find(_fee_query({"class_id": cls["id"]}), {"_id": 0, "id": 1}).to_list(200)
        s_ids = [s["id"] for s in students]
        if not s_ids:
            continue
        txns = await db.fee_transactions.find(_fee_query({"student_id": {"$in": s_ids}}), {"_id": 0}).to_list(1000)
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
    student = await db.students.find_one(_fee_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student record not found")
    txns = await db.fee_transactions.find(_fee_query({"student_id": student["id"]}), {"_id": 0}).to_list(50)
    return {"success": True, "data": txns}


@router.post("/transactions")
async def record_payment(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    key = request.headers.get("Idempotency-Key")
    fee_period = body.get("fee_period")
    fee_head = body.get("fee_head") or body.get("fee_type")
    expected_key = f"{body.get('student_id')}:{fee_period}:{fee_head}"
    if not key or key != expected_key:
        raise HTTPException(400, "Idempotency-Key must match student_id:fee_period:fee_head")

    now = datetime.now()
    existing = await db.fee_idempotency_keys.find_one(_fee_query({"key": key}), {"_id": 0})
    if existing and _parse_date(existing.get("expires_at")) and datetime.fromisoformat(existing["expires_at"]) > now:
        txn = await db.fee_transactions.find_one(_fee_query({"id": existing["transaction_id"]}), {"_id": 0})
        if txn:
            return {"success": True, "data": txn, "idempotent": True}

    for field in ("student_id", "amount", "payment_mode", "fee_period"):
        if body.get(field) in (None, ""):
            raise HTTPException(400, f"{field} is required")

    receipt = f"RCP{datetime.now().strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
    is_paid = (body.get("status") or "paid") == "paid"
    txn = FeeTransaction(
        student_id=body["student_id"],
        fee_type=fee_head,
        amount=float(body["amount"]),
        status=body.get("status") or "paid",
        due_date=body.get("due_date"),
        paid_date=datetime.now().strftime("%Y-%m-%d") if is_paid else None,
        payment_mode=body["payment_mode"],
        receipt_number=receipt,
        transaction_ref=body.get("transaction_ref"),
    )
    doc = {**_serialize(txn), "_id": txn.id, "schoolId": get_school_id(), "fee_period": fee_period, "fee_head": fee_head}
    await db.fee_transactions.insert_one(doc)
    await db.fee_idempotency_keys.insert_one({
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "key": key,
        "transaction_id": txn.id,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=24)).isoformat(),
    })
    await _audit(db, action="create", entity_id=txn.id, user=user, changes={"created": {k: v for k, v in doc.items() if k != "_id"}})
    return {"success": True, "data": {k: v for k, v in doc.items() if k != "_id"}}


@router.patch("/transactions/{transaction_id}/correct")
async def correct_fee_transaction(transaction_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    reason = body.get("reason")
    if not reason:
        raise HTTPException(400, "reason is required")
    original = await db.fee_transactions.find_one(_fee_query({"id": transaction_id}), {"_id": 0})
    if not original:
        raise HTTPException(404, "Fee transaction not found")
    allowed = {"amount", "status", "due_date", "paid_date", "payment_mode", "transaction_ref", "fee_period", "fee_head", "fee_type"}
    changes = {k: v for k, v in body.items() if k in allowed}
    if not changes:
        raise HTTPException(400, "No correctable fields supplied")
    correction = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "transaction_id": transaction_id,
        "original_record": original,
        "changes": changes,
        "reason": reason,
        "corrected_by": user["id"],
        "corrected_at": datetime.now().isoformat(),
    }
    await db.fee_transaction_corrections.insert_one(correction)
    await db.fee_transactions.update_one(_fee_query({"id": transaction_id}), {"$set": {**changes, "corrected": True, "updated_at": correction["corrected_at"]}})
    await _audit(db, action="correct", entity_id=transaction_id, user=user, changes=changes, reason=reason)
    updated = await db.fee_transactions.find_one(_fee_query({"id": transaction_id}), {"_id": 0})
    return {"success": True, "data": updated, "correction": {k: v for k, v in correction.items() if k != "_id"}}


@router.post("/contact-log")
async def create_fee_contact_log(request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")
    body = await request.json()
    required = {"student_id", "fee_transaction_id", "date", "contact_type", "outcome", "notes"}
    if any(not body.get(field) for field in required):
        raise HTTPException(400, "student_id, fee_transaction_id, date, contact_type, outcome, and notes are required")
    record = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "student_id": body["student_id"],
        "fee_transaction_id": body["fee_transaction_id"],
        "date": body["date"],
        "contact_type": body["contact_type"],
        "outcome": body["outcome"],
        "notes": body["notes"],
        "created_by": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.fee_contact_logs.insert_one(record)
    await _audit(db, action="contact_log", entity_id=body["fee_transaction_id"], user=user, changes={"contact": {k: v for k, v in record.items() if k != "_id"}})
    return {"success": True, "data": {k: v for k, v in record.items() if k != "_id"}}


@router.get("/summary")
async def get_fee_summary(request: Request, fee_period: str = None):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin"]:
        raise HTTPException(403, "Forbidden")

    query = _fee_query({"fee_period": fee_period}) if fee_period else _fee_query()
    txns = await db.fee_transactions.find(query, {"_id": 0}).to_list(2000)
    total_collected = sum(float(t.get("amount", 0)) for t in txns if t.get("status") == "paid")
    outstanding_txns = [t for t in txns if t.get("status") in ("pending", "overdue", "unpaid")]
    total_outstanding = sum(float(t.get("amount", 0)) for t in outstanding_txns)
    defaulters = len(set(t.get("student_id") for t in outstanding_txns if t.get("student_id")))
    return {"success": True, "data": {
        "total_collected": total_collected,
        "total_outstanding": total_outstanding,
        "defaulters": defaulters,
        "transactions": len(txns),
        "period": fee_period,
        "generated_at": datetime.now().isoformat(),
    }}


@router.get("/status/{student_id}")
async def get_student_fee_status(student_id: str, request: Request):
    db = get_db()
    user = get_user(request)
    if user["role"] not in ["owner", "admin", "teacher", "parent", "student"]:
        raise HTTPException(403, "Forbidden")
    txns = await db.fee_transactions.find(_fee_query({"student_id": student_id}), {"_id": 0}).to_list(200)
    today = datetime.now()
    status = "paid"
    for txn in txns:
        if txn.get("status") in ("overdue", "unpaid"):
            status = "overdue"
            break
        if txn.get("status") == "pending":
            due = _parse_date(txn.get("due_date"))
            status = "overdue" if due and due < today else "unpaid"
    return {"success": True, "data": {"student_id": student_id, "status": status}}


@router.delete("/transactions/{transaction_id}")
async def delete_fee_transaction(transaction_id: str, request: Request):
    raise HTTPException(405, "Fee transactions cannot be hard deleted")
