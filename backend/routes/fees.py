from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse, Response, JSONResponse
from database import TimedQuery, get_db
from models.schemas import FeeTransaction
from middleware.auth import get_current_user, require_role, require_owner
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from tenant import get_school_id, scoped_filter, scoped_query, add_school_id
from services.audit_service import write_audit_doc
from services.sse import KEEPALIVE_SECONDS, connect as sse_connect, disconnect as sse_disconnect, encode_sse, normalize_session_id, publish
from pymongo import ReturnDocument
import asyncio
import uuid
import os
import io
import csv
import httpx

DISCOUNT_APPROVAL_THRESHOLD = Decimal(os.environ.get("DISCOUNT_APPROVAL_THRESHOLD", "10000"))

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
    await write_audit_doc(db, {
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
    }, school_id=get_school_id(), branch_id=user.get("branch_id"))


async def _student_map(db, txns):
    s_ids = list(set(t["student_id"] for t in txns if t.get("student_id")))
    students = await db.students.find(_fee_query({"id": {"$in": s_ids}}), {"_id": 0, "id": 1, "name": 1, "class_id": 1}).to_list(len(s_ids)) if s_ids else []
    s_map = {s["id"]: s for s in students}
    c_ids = list(set(s.get("class_id") for s in students if s.get("class_id")))
    classes = await db.classes.find(_fee_query({"id": {"$in": c_ids}}), {"_id": 0, "id": 1, "name": 1, "section": 1}).to_list(len(c_ids)) if c_ids else []
    c_map = {c["id"]: c for c in classes}
    return s_map, c_map


async def _fee_summary_payload(db, fee_period: str | None = None) -> dict:
    query = _fee_query({"fee_period": fee_period}) if fee_period else _fee_query()
    txns = await db.fee_transactions.find(query, {"_id": 0}).to_list(2000)
    total_collected = sum(float(t.get("amount", 0)) for t in txns if t.get("status") == "paid")
    outstanding_txns = [t for t in txns if t.get("status") in ("pending", "overdue", "unpaid")]
    total_outstanding = sum(float(t.get("amount", 0)) for t in outstanding_txns)
    defaulters = len(set(t.get("student_id") for t in outstanding_txns if t.get("student_id")))
    return {
        "total_collected": total_collected,
        "total_outstanding": total_outstanding,
        "defaulters": defaulters,
        "transactions": len(txns),
        "period": fee_period,
        "generated_at": datetime.now().isoformat(),
    }


async def _publish_fee_update(db, event_type: str, payload: dict | None = None, fee_period: str | None = None):
    await publish("fees", {
        "type": event_type,
        "data": payload or {},
        "summary": await _fee_summary_payload(db, fee_period),
        "last_updated": datetime.now().isoformat(),
    })


@router.get("/structures")
async def get_fee_structures(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    structures = await db.fee_structures.find(_fee_query(), {"_id": 0}).to_list(50)
    return {"success": True, "data": structures}


@router.post("/structures")
async def create_fee_structure(request: Request, user: dict = Depends(require_owner)):
    """P10.3: Owner-only — create a fee structure for a class."""
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")
    structure = {
        "id": str(uuid.uuid4()),
        "name": body.get("name", ""),
        "class_id": body.get("class_id", ""),
        "fee_heads": body.get("fee_heads", []),
        "academic_year": body.get("academic_year", ""),
        "created_by": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    doc = add_school_id(structure)
    await db.fee_structures.insert_one({**doc, "_id": doc["id"]})
    return {"success": True, "data": doc}


@router.patch("/structures/{structure_id}")
async def update_fee_structure(structure_id: str, request: Request, user: dict = Depends(require_owner)):
    """P10.3: Owner-only — update a fee structure."""
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")
    result = await db.fee_structures.update_one(
        scoped_query({"id": structure_id}, branch_id=bid),
        {"$set": body}
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Fee structure not found")
    return {"success": True}


@router.get("/transactions")
async def get_fee_transactions(request: Request, student_id: str = None, status: str = None, class_id: str = None, overdue_days: int = None, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    query = _fee_query()
    if student_id:
        query["student_id"] = student_id
    if status:
        query["status"] = status

    if class_id:
        class_students = await db.students.find(_fee_query({"class_id": class_id}), {"_id": 0, "id": 1}).to_list(500)
        query["student_id"] = {"$in": [s["id"] for s in class_students]}

    async with TimedQuery(collection_name="fee_transactions", operation="find", query_shape="fee_transactions_list"):
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
async def get_class_fee_summary(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    """Returns per-class fee collection summary."""
    db = get_db()
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
async def get_my_fees(request: Request, user: dict = Depends(require_role("student"))):
    db = get_db()
    student = await db.students.find_one(_fee_query({"user_id": user["id"]}), {"_id": 0})
    if not student:
        raise HTTPException(404, "Student record not found")
    txns = await db.fee_transactions.find(_fee_query({"student_id": student["id"]}), {"_id": 0}).to_list(50)
    return {"success": True, "data": txns}


@router.post("/transactions")
async def record_payment(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
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
    amount = float(body["amount"])
    paid_amount = float(body.get("paid_amount", amount))
    # Determine status: explicit > partial auto-detect > paid default
    if "status" in body and body["status"]:
        status = body["status"]
    elif paid_amount < amount:
        status = "partial"
    else:
        status = "paid"
    is_paid = status in ("paid", "partial")
    txn = FeeTransaction(
        student_id=body["student_id"],
        fee_type=fee_head,
        amount=amount,
        status=status,
        due_date=body.get("due_date"),
        paid_date=datetime.now().strftime("%Y-%m-%d") if is_paid else None,
        payment_mode=body["payment_mode"],
        receipt_number=receipt,
        transaction_ref=body.get("transaction_ref"),
    )
    doc = {**_serialize(txn), "_id": txn.id, "schoolId": get_school_id(), "fee_period": fee_period, "fee_head": fee_head, "paid_amount": paid_amount}
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
    data = {k: v for k, v in doc.items() if k != "_id"}
    await _publish_fee_update(db, "fee_payment_recorded", data, fee_period)
    return {"success": True, "data": data}


@router.patch("/transactions/{transaction_id}/correct")
async def correct_fee_transaction(
    transaction_id: str,
    request: Request,
    user: dict = Depends(require_role("owner", "admin")),
):
    db = get_db()
    body = await request.json()
    reason = body.get("reason")
    if not reason:
        raise HTTPException(400, "reason is required")
    bid = user.get("branch_id")

    original = await db.fee_transactions.find_one(
        scoped_query({"id": transaction_id}, branch_id=bid), {"_id": 0}
    )
    if not original:
        raise HTTPException(404, "Fee transaction not found")

    # EC-10.5: Accountant can only correct their own transactions
    if user.get("role") == "admin" and user.get("sub_category") == "accounts":
        if original.get("created_by") != user["id"]:
            raise HTTPException(403, "Accountant can only correct their own transactions")

    allowed = {"amount", "status", "due_date", "paid_date", "payment_mode", "transaction_ref", "fee_period", "fee_head", "fee_type"}
    changes = {k: v for k, v in body.items() if k in allowed}
    if not changes:
        raise HTTPException(400, "No correctable fields supplied")

    now = datetime.now(timezone.utc).isoformat()
    update_ops: dict = {
        "$set": {
            **changes,
            "corrected": True,
            "corrected_at": now,
            "corrected_by": user["id"],
            "updated_at": now,
        },
        "$inc": {"correction_count": 1},  # EC-10.3: increment, not overwrite
    }

    # Only set original_snapshot on the FIRST correction (preserve pre-correction state)
    if not original.get("original_snapshot"):
        update_ops["$set"]["original_snapshot"] = {
            "amount": original.get("amount"),
            "status": original.get("status"),
            "payment_mode": original.get("payment_mode"),
            "paid_date": original.get("paid_date"),
        }

    await db.fee_transactions.update_one(
        scoped_query({"id": transaction_id}, branch_id=bid),
        update_ops,
    )

    # Insert correction record (existing tests assert on fee_transaction_corrections collection)
    correction = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "transaction_id": transaction_id,
        "original_record": original,
        "changes": changes,
        "reason": reason,
        "corrected_by": user["id"],
        "corrected_at": now,
    }
    await db.fee_transaction_corrections.insert_one(correction)

    await _audit(db, action="correct", entity_id=transaction_id, user=user, changes=changes, reason=reason)

    updated = await db.fee_transactions.find_one(
        scoped_query({"id": transaction_id}, branch_id=bid), {"_id": 0}
    )
    await _publish_fee_update(db, "fee_transaction_corrected", updated, updated.get("fee_period") if updated else None)
    return {"success": True, "data": updated, "correction": {k: v for k, v in correction.items() if k != "_id"}}


@router.post("/contact-log")
async def create_fee_contact_log(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
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
async def get_fee_summary(request: Request, fee_period: str = None, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    return {"success": True, "data": await _fee_summary_payload(db, fee_period)}


@router.get("/stream")
async def fee_stream(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    session_id = normalize_session_id(
        request.headers.get("X-SSE-Session-ID") or request.query_params.get("session_id")
    )
    keepalive = int(request.query_params.get("keepalive", KEEPALIVE_SECONDS))
    once = request.query_params.get("once", "").lower() == "true"
    queue = await sse_connect("fees", session_id)

    async def event_generator():
        try:
            yield encode_sse({
                "type": "snapshot",
                "channel": "fees",
                "summary": await _fee_summary_payload(db),
                "last_updated": datetime.now().isoformat(),
            })
            if once:
                return
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=keepalive)
                except asyncio.TimeoutError:
                    yield encode_sse({"type": "keepalive", "channel": "fees"})
                    continue
                if isinstance(event, str):
                    yield event
                    continue
                if event.get("type") == "close":
                    yield encode_sse(event)
                    break
                yield encode_sse(event)
        finally:
            await sse_disconnect("fees", session_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/status/{student_id}")
async def get_student_fee_status(student_id: str, request: Request, user: dict = Depends(require_role("owner", "admin", "teacher", "parent", "student"))):
    db = get_db()
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


@router.post("/discount-types")
async def create_discount_type(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    body = await request.json()
    required = {"name", "value", "value_type", "recurrence", "reason_note"}
    if any(body.get(field) in (None, "") for field in required):
        raise HTTPException(400, "name, value, value_type, recurrence, and reason_note are required")
    if body["value_type"] not in ("flat", "percentage"):
        raise HTTPException(400, "value_type must be flat or percentage")
    doc = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "name": body["name"],
        "value": float(body["value"]),
        "value_type": body["value_type"],
        "recurrence": body["recurrence"],
        "reason_note": body["reason_note"],
        "is_active": True,
        "created_by": user["id"],
        "created_at": datetime.now().isoformat(),
    }
    await db.fee_discount_types.insert_one(doc)
    await _audit(db, action="discount_type_create", entity_id=doc["id"], user=user, changes={"created": {k: v for k, v in doc.items() if k != "_id"}})
    return {"success": True, "data": {k: v for k, v in doc.items() if k != "_id"}}


@router.get("/discount-types")
async def get_discount_types(request: Request, include_inactive: bool = False, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    query = _fee_query() if include_inactive else _fee_query({"is_active": True})
    items = await db.fee_discount_types.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return {"success": True, "data": items}


@router.patch("/discount-types/{discount_type_id}")
async def update_discount_type(discount_type_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    body = await request.json()
    allowed = {"name", "is_active", "reason_note"}
    changes = {k: v for k, v in body.items() if k in allowed}
    if not changes:
        raise HTTPException(400, "No editable fields supplied")
    existing = await db.fee_discount_types.find_one(_fee_query({"id": discount_type_id}), {"_id": 0})
    if not existing:
        raise HTTPException(404, "Discount type not found")
    await db.fee_discount_types.update_one(_fee_query({"id": discount_type_id}), {"$set": {**changes, "updated_at": datetime.now().isoformat()}})
    await _audit(db, action="discount_type_update", entity_id=discount_type_id, user=user, changes=changes, reason=body.get("reason_note"))
    updated = await db.fee_discount_types.find_one(_fee_query({"id": discount_type_id}), {"_id": 0})
    return {"success": True, "data": updated}


@router.post("/discounts/apply")
async def apply_discount(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    body = await request.json()
    bid = user.get("branch_id")

    student_id = body.get("student_id")
    discount_type_id = body.get("discount_type_id")
    note = body.get("note", "")

    if not student_id or not discount_type_id:
        raise HTTPException(400, "student_id and discount_type_id are required")

    # Accept either the legacy collection name (scoped) or the primary one.
    dtype = await db.fee_discount_types.find_one(_fee_query({"id": discount_type_id}), {"_id": 0})
    if not dtype:
        raise HTTPException(404, "Discount type not found")

    # P10.4: Compute discount amount from the type.
    if dtype.get("value_type") == "flat":
        discount_amount = Decimal(str(dtype.get("value", 0)))
    else:
        # Percentage — simplified; caller may supply original_amount for accuracy.
        discount_amount = Decimal(str(dtype.get("value", 0)))

    # P10.4: Route large discounts through pending approval (EXCLUSIVE upper bound).
    if discount_amount > DISCOUNT_APPROVAL_THRESHOLD:
        pending = add_school_id({
            "id": str(uuid.uuid4()),
            "student_id": student_id,
            "discount_type_id": discount_type_id,
            "discount_amount": float(discount_amount),
            "requested_by": user["id"],
            "note": note,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.pending_discount_approvals.insert_one({**pending, "_id": pending["id"]})
        return JSONResponse(
            status_code=202,
            content={
                "success": True,
                "pending_approval": True,
                "message": (
                    f"Discount of ₹{discount_amount} requires owner approval "
                    f"(threshold: ₹{DISCOUNT_APPROVAL_THRESHOLD})"
                ),
            },
        )

    # Below threshold — apply immediately (original logic preserved).
    original_amount = body.get("original_amount")
    effective_from = body.get("effective_from")
    if original_amount is None or effective_from is None:
        raise HTTPException(400, "original_amount and effective_from are required for immediate discount application")

    application = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": get_school_id(),
        "student_id": student_id,
        "discount_type_id": dtype["id"],
        "original_amount": float(original_amount),
        "effective_from": effective_from,
        "applied_by": user["id"],
        "applied_at": datetime.now().isoformat(),
        "note": note or body.get("note"),
    }
    await db.fee_discounts.insert_one(application)
    await _audit(db, action="discount_apply", entity_id=application["id"], user=user, changes={"applied": {k: v for k, v in application.items() if k != "_id"}}, reason=note or body.get("note"))
    return {"success": True, "data": {k: v for k, v in application.items() if k != "_id"}}


@router.get("/discounts/pending-approvals")
async def list_pending_discount_approvals(request: Request, user: dict = Depends(require_owner)):
    """P10.4: Owner-only — list pending large-discount approval requests."""
    db = get_db()
    bid = user.get("branch_id")
    pending = await db.pending_discount_approvals.find(
        scoped_query({"status": "pending"}, branch_id=bid)
    ).to_list(100)
    return {"success": True, "data": pending}


@router.patch("/discounts/pending-approvals/{approval_id}/approve")
async def approve_pending_discount(approval_id: str, request: Request, user: dict = Depends(require_owner)):
    """P10.4: Owner-only — approve a pending large discount."""
    db = get_db()
    bid = user.get("branch_id")
    pending = await db.pending_discount_approvals.find_one(
        scoped_query({"id": approval_id}, branch_id=bid)
    )
    if not pending:
        raise HTTPException(404, "Pending approval not found")
    discount = {
        **{k: v for k, v in pending.items() if k != "_id"},
        "id": str(uuid.uuid4()),
        "status": "approved",
        "approved_by": user["id"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    discount = add_school_id(discount)
    await db.fee_discounts.insert_one({**discount, "_id": discount["id"]})
    await db.pending_discount_approvals.update_one({"id": approval_id}, {"$set": {"status": "approved"}})
    return {"success": True}


@router.patch("/discounts/pending-approvals/{approval_id}/reject")
async def reject_pending_discount(approval_id: str, request: Request, user: dict = Depends(require_owner)):
    """P10.4: Owner-only — reject a pending large discount."""
    db = get_db()
    bid = user.get("branch_id")
    result = await db.pending_discount_approvals.update_one(
        scoped_query({"id": approval_id}, branch_id=bid),
        {"$set": {"status": "rejected", "rejected_by": user["id"]}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "Pending approval not found")
    return {"success": True}


async def _discount_breakdown(db, student_id: str):
    applications = await db.fee_discounts.find(_fee_query({"student_id": student_id}), {"_id": 0}).sort("applied_at", 1).to_list(200)
    type_ids = [item["discount_type_id"] for item in applications]
    types = await db.fee_discount_types.find(_fee_query({"id": {"$in": type_ids}}), {"_id": 0}).to_list(len(type_ids)) if type_ids else []
    type_map = {item["id"]: item for item in types}
    original_amount = applications[0]["original_amount"] if applications else 0
    lines = []
    total_discount = 0
    for app in applications:
        dtype = type_map.get(app["discount_type_id"], {})
        base = float(app.get("original_amount", original_amount) or original_amount)
        value = float(dtype.get("value", 0))
        amount = min(base, base * value / 100) if dtype.get("value_type") == "percentage" else min(base, value)
        total_discount += amount
        lines.append({
            "application_id": app["id"],
            "label": dtype.get("name", "Discount"),
            "value": value,
            "value_type": dtype.get("value_type"),
            "discount_amount": amount,
            "effective_from": app.get("effective_from"),
            "applied_by": app.get("applied_by"),
        })
    payable = max(float(original_amount) - total_discount, 0)
    return {
        "student_id": student_id,
        "original_amount": original_amount,
        "discounts": lines,
        "total_discount": total_discount,
        "payable_amount": payable,
    }


@router.get("/discounts/{student_id}")
async def get_student_discounts(student_id: str, request: Request, user: dict = Depends(require_role("owner", "admin", "teacher", "parent", "student"))):
    return {"success": True, "data": await _discount_breakdown(get_db(), student_id)}


@router.get("/discount-summary")
async def get_discount_summary(request: Request, user: dict = Depends(require_owner)):
    db = get_db()
    applications = await db.fee_discounts.find(_fee_query(), {"_id": 0}).to_list(2000)
    type_ids = [item["discount_type_id"] for item in applications]
    types = await db.fee_discount_types.find(_fee_query({"id": {"$in": type_ids}}), {"_id": 0}).to_list(len(type_ids)) if type_ids else []
    type_map = {item["id"]: item for item in types}
    expected = sum(float(item.get("original_amount", 0)) for item in applications)
    total_discount = 0
    by_type = {}
    for app in applications:
        dtype = type_map.get(app["discount_type_id"], {})
        base = float(app.get("original_amount", 0))
        value = float(dtype.get("value", 0))
        amount = min(base, base * value / 100) if dtype.get("value_type") == "percentage" else min(base, value)
        total_discount += amount
        bucket = by_type.setdefault(dtype.get("name", "Discount"), {"count": 0, "discount_value": 0})
        bucket["count"] += 1
        bucket["discount_value"] += amount
    return {"success": True, "data": {
        "total_expected_revenue": expected,
        "total_discount_value": total_discount,
        "discount_types": by_type,
    }}


def _fee_sync_config():
    base_url = os.environ.get("FEE_API_BASE_URL")
    api_key = os.environ.get("FEE_API_KEY")
    if not base_url or not api_key:
        raise HTTPException(503, "FEE_API_BASE_URL and FEE_API_KEY must be configured before fee sync")
    return base_url.rstrip("/"), api_key


async def _fetch_external_fee_records():
    base_url, api_key = _fee_sync_config()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{base_url}/fees", headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", payload if isinstance(payload, list) else [])


def _external_key(record: dict):
    return record.get("student_id"), record.get("fee_period") or record.get("period"), record.get("fee_head") or record.get("fee_type")


def _fee_sync_resolution_update(theirs: dict) -> dict:
    return {
        "amount": float(theirs.get("amount", 0)),
        "status": theirs.get("status", "pending"),
        "due_date": theirs.get("due_date"),
        "source": theirs.get("source", "fee_api_sync"),
    }


SYNC_JOB_TIMEOUT_MINUTES = int(os.environ.get("SYNC_JOB_TIMEOUT_MINUTES", "30"))


@router.post("/sync/trigger")
async def trigger_fee_sync(request: Request, user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    bid = user.get("branch_id")
    now = datetime.now(timezone.utc)
    timeout_cutoff = (now - timedelta(minutes=SYNC_JOB_TIMEOUT_MINUTES)).isoformat()

    # EC-10.1: Check for existing in-progress job (idempotency)
    existing_job = await db.fee_sync_jobs.find_one(
        scoped_query({"status": "in_progress"}, branch_id=bid), {"_id": 0}
    )
    if existing_job:
        started_at = existing_job.get("started_at", "")
        if started_at and started_at < timeout_cutoff:
            # Auto-expire hung job
            await db.fee_sync_jobs.update_one(
                scoped_query({"id": existing_job["id"]}, branch_id=bid),
                {"$set": {"status": "failed", "reason": "timeout", "failed_at": now.isoformat()}},
            )
        else:
            # Return existing in-progress job (idempotency)
            return {"success": True, "data": existing_job, "message": "Sync already in progress"}

    job_id = str(uuid.uuid4())
    job = {
        "_id": job_id,
        "id": job_id,
        "schoolId": get_school_id(),
        "status": "running",
        "started_at": now.isoformat(),
        "synced_count": 0,
        "conflict_count": 0,
        "conflicts": [],
        "triggered_by": user["id"],
        "created_at": now.isoformat(),
    }
    if bid:
        job["branch_id"] = bid
    await db.fee_sync_jobs.insert_one(job)
    try:
        records = await _fetch_external_fee_records()
    except HTTPException as exc:
        await db.fee_sync_jobs.update_one(_fee_query({"id": job_id}), {"$set": {"status": "failed", "error": exc.detail, "completed_at": datetime.now().isoformat()}})
        await _audit(db, action="fee_sync_failed", entity_id=job_id, user=user, changes={"error": exc.detail})
        raise
    except Exception as exc:
        message = f"Fee sync failed: {exc}"
        await db.fee_sync_jobs.update_one(_fee_query({"id": job_id}), {"$set": {"status": "failed", "error": message, "completed_at": datetime.now().isoformat()}})
        await _audit(db, action="fee_sync_failed", entity_id=job_id, user=user, changes={"error": message})
        return {"success": True, "data": {"sync_job_id": job_id, "status": "failed", "error": message}}

    conflicts = []
    synced = 0
    for record in records:
        student_id, period, fee_head = _external_key(record)
        if not student_id or not period or not fee_head:
            continue
        existing = await db.fee_transactions.find_one(_fee_query({"student_id": student_id, "fee_period": period, "fee_head": fee_head}), {"_id": 0})
        amount = float(record.get("amount", 0))
        if existing and float(existing.get("amount", 0)) != amount:
            conflicts.append({
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "period": period,
                "fee_head": fee_head,
                "ours": existing,
                "theirs": record,
                "status": "conflict",
            })
            continue
        if not existing:
            txn_id = str(uuid.uuid4())
            await db.fee_transactions.insert_one({
                "_id": txn_id,
                "id": txn_id,
                "schoolId": get_school_id(),
                "student_id": student_id,
                "fee_period": period,
                "fee_head": fee_head,
                "fee_type": fee_head,
                "amount": amount,
                "status": record.get("status", "pending"),
                "due_date": record.get("due_date"),
                "created_at": datetime.now().isoformat(),
                "source": "fee_api_sync",
            })
            synced += 1

    status = "conflict" if conflicts else "completed"
    update = {
        "status": status,
        "synced_count": synced,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "completed_at": datetime.now().isoformat(),
    }
    await db.fee_sync_jobs.update_one(_fee_query({"id": job_id}), {"$set": update})
    await _audit(db, action="fee_sync_completed", entity_id=job_id, user=user, changes=update)
    if synced:
        await _publish_fee_update(db, "fee_sync_completed", {"sync_job_id": job_id, **update})
    return {"success": True, "data": {"sync_job_id": job_id, **update}}


@router.get("/sync/{sync_job_id}")
async def get_fee_sync_job(sync_job_id: str, request: Request, user: dict = Depends(require_role("owner", "admin"))):
    job = await get_db().fee_sync_jobs.find_one(_fee_query({"id": sync_job_id}), {"_id": 0})
    if not job:
        raise HTTPException(404, "Sync job not found")
    return {"success": True, "data": job}


@router.post("/sync/{sync_job_id}/resolve-conflict")
async def resolve_fee_sync_conflict(sync_job_id: str, request: Request, user: dict = Depends(require_owner)):
    db = get_db()
    body = await request.json()
    conflict_id = body.get("conflict_id")
    decision = body.get("decision")
    if not conflict_id or decision not in ("keep_ours", "use_theirs"):
        raise HTTPException(400, "conflict_id and decision keep_ours/use_theirs are required")
    job = await db.fee_sync_jobs.find_one(_fee_query({"id": sync_job_id}), {"_id": 0})
    if not job:
        raise HTTPException(404, "Sync job not found")
    conflicts = job.get("conflicts", [])
    target = next((item for item in conflicts if item.get("id") == conflict_id), None)
    if not target:
        raise HTTPException(404, "Conflict not found")
    resolved_fields = {}
    if decision == "use_theirs":
        theirs = target["theirs"]
        resolved_fields = _fee_sync_resolution_update(theirs)
        await db.fee_transactions.update_one(
            _fee_query({"student_id": target["student_id"], "fee_period": target["period"], "fee_head": target["fee_head"]}),
            {"$set": {**resolved_fields, "updated_at": datetime.now().isoformat()}},
            upsert=True,
        )
    for conflict in conflicts:
        if conflict.get("id") == conflict_id:
            conflict["status"] = "resolved"
            conflict["resolution"] = decision
            conflict["resolved_by"] = user["id"]
            conflict["resolved_at"] = datetime.now().isoformat()
            if resolved_fields:
                conflict["resolved_fields"] = resolved_fields
    unresolved = [item for item in conflicts if item.get("status") == "conflict"]
    update = {"conflicts": conflicts, "conflict_count": len(unresolved), "status": "completed" if not unresolved else "conflict"}
    await db.fee_sync_jobs.update_one(_fee_query({"id": sync_job_id}), {"$set": update})
    await _audit(db, action="fee_sync_conflict_resolved", entity_id=sync_job_id, user=user, changes={"conflict_id": conflict_id, "decision": decision, "resolved_fields": resolved_fields})
    updated = await db.fee_sync_jobs.find_one(_fee_query({"id": sync_job_id}), {"_id": 0})
    if decision == "use_theirs":
        await _publish_fee_update(db, "fee_sync_conflict_resolved", {"sync_job_id": sync_job_id, "conflict_id": conflict_id})
    return {"success": True, "data": updated}


# ─── Story 32: Fee Receipt PDF ────────────────────────────────────────────────

async def _next_receipt_number(db, school_id: str) -> str:
    now = datetime.now()
    period = now.strftime("%Y-%m")
    counter_key = f"{school_id}-{period}"
    result = await db.receipt_counters.find_one_and_update(
        {"key": counter_key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    seq = result.get("seq", 1) if result else 1
    return f"{school_id.upper()}-{period}-{seq:04d}"


@router.get("/transactions/{transaction_id}/receipt")
async def get_fee_receipt(transaction_id: str, request: Request, format: str = "pdf", user: dict = Depends(require_role("owner", "admin"))):
    """Returns a fee receipt.  format=json returns structured JSON; default is PDF."""
    db = get_db()
    bid = user.get("branch_id")
    txn = await db.fee_transactions.find_one(scoped_query({"id": transaction_id}, branch_id=bid), {"_id": 0})
    if not txn:
        raise HTTPException(404, "Transaction not found")
    student = await db.students.find_one(scoped_query({"id": txn.get("student_id")}, branch_id=bid), {"_id": 0})
    school_name = os.environ.get("SCHOOL_NAME", "The Aaryans")
    school_id = get_school_id()

    # Assign receipt number if not already assigned
    receipt_number = txn.get("receipt_number")
    if not receipt_number:
        receipt_number = await _next_receipt_number(db, school_id)
        await db.fee_transactions.update_one(scoped_query({"id": transaction_id}, branch_id=bid), {"$set": {"receipt_number": receipt_number}})

    # JSON receipt (P10.1)
    if format == "json":
        receipt_data = {
            "receipt_number": receipt_number,
            "transaction_id": transaction_id,
            "student_name": student.get("name") if student else "Unknown",
            "student_id": txn.get("student_id"),
            "fee_type": txn.get("fee_type", txn.get("fee_head", "")),
            "fee_period": txn.get("fee_period"),
            "amount": txn.get("amount"),
            "paid_amount": txn.get("paid_amount", txn.get("amount")),
            "status": txn.get("status"),
            "payment_mode": txn.get("payment_mode"),
            "transaction_ref": txn.get("transaction_ref"),
            "paid_date": txn.get("paid_date"),
            "issued_at": datetime.now(timezone.utc).isoformat(),
        }
        return {"success": True, "data": receipt_data}

    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(500, "PDF library not available")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Header
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 60, 120)
    pdf.cell(0, 10, school_name, ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, "Fee Payment Receipt", ln=True, align="C")
    pdf.ln(4)

    # Divider
    pdf.set_draw_color(180, 180, 200)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    # Receipt number + date
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 7, f"Receipt No: {receipt_number}", ln=False)
    paid_date = txn.get("paid_date") or txn.get("updated_at", "")[:10]
    pdf.cell(95, 7, f"Date: {paid_date}", ln=True, align="R")
    pdf.ln(4)

    # Student details table
    def row(label, value):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(240, 242, 255)
        pdf.cell(60, 8, label, border=1, fill=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(110, 8, str(value or ""), border=1, ln=True)

    student_name = student["name"] if student else txn.get("student_name", "N/A")
    student_class = student.get("class_name", "") if student else ""
    row("Student Name", student_name)
    row("Class", student_class)
    row("Fee Head", txn.get("fee_type", txn.get("fee_head", "")))
    row("Amount Paid", f"Rs. {txn.get('amount', 0):,.2f}")
    row("Payment Mode", txn.get("payment_mode", "Cash").title())
    row("Payment Date", paid_date)
    row("Status", txn.get("status", "paid").upper())
    pdf.ln(8)

    # PAID watermark
    pdf.set_font("Helvetica", "B", 40)
    pdf.set_text_color(200, 230, 200)
    pdf.cell(0, 20, "PAID", ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    # Footer
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 6, "This is a computer-generated receipt. No signature required.", ln=True, align="C")

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=receipt-{receipt_number}.pdf"},
    )


@router.get("/export")
async def export_fee_transactions(request: Request, period: str = None, format: str = "csv", user: dict = Depends(require_role("owner", "admin"))):
    db = get_db()
    query = _fee_query({})
    if period:
        query["$and"] = query.get("$and", []) + [{"$or": [
            {"fee_period": period},
            {"paid_date": {"$regex": f"^{period}"}},
        ]}]
    txns = await db.fee_transactions.find(query, {"_id": 0}).sort("paid_date", -1).to_list(500)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["student_name", "class", "fee_head", "amount", "payment_date", "receipt_number", "payment_mode", "status"])
    for t in txns:
        student = await db.students.find_one(_fee_query({"id": t.get("student_id")}), {"_id": 0, "name": 1, "class_name": 1})
        writer.writerow([
            student["name"] if student else "",
            student.get("class_name", "") if student else "",
            t.get("fee_type", t.get("fee_head", "")),
            t.get("amount", ""),
            t.get("paid_date", ""),
            t.get("receipt_number", ""),
            t.get("payment_mode", ""),
            t.get("status", ""),
        ])
    output.seek(0)
    fname = f"fees_{period or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )
