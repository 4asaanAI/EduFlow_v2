"""Campus operations services: resources, custody, inventory, procurement, library."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from services.actor_context import ActorContext
from services.accounting_period_service import AccountingPeriodClosedError, assert_posting_allowed
from tenant import scoped_query


class CampusValidationError(Exception):
    pass


class CampusNotFoundError(Exception):
    pass


class CampusConflictError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(params: dict, key: str) -> str:
    value = str(params.get(key) or "").strip()
    if not value:
        raise CampusValidationError(f"{key} is required")
    return value


def _number(params: dict, key: str, *, minimum: float = 0) -> float:
    try:
        value = float(params.get(key))
    except (TypeError, ValueError):
        raise CampusValidationError(f"{key} must be a number")
    if value < minimum:
        raise CampusValidationError(f"{key} must be at least {minimum}")
    return value


def _parse_timestamp(value, key: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise CampusValidationError(f"{key} must be an ISO timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def create_resource(db, actor_ctx: ActorContext, params: dict) -> dict:
    name = _text(params, "name")
    resource_type = str(params.get("resource_type") or "room").strip().lower()
    if resource_type not in {"room", "lab", "hall", "equipment", "sports"}:
        raise CampusValidationError("Invalid resource_type")
    try:
        capacity = int(params.get("capacity") or 1)
    except (TypeError, ValueError):
        raise CampusValidationError("capacity must be an integer")
    if capacity < 1:
        raise CampusValidationError("capacity must be at least 1")
    resource_id = str(uuid.uuid4())
    doc = {
        "_id": resource_id, "id": resource_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "name": name, "resource_type": resource_type,
        "capacity": capacity, "location": params.get("location"),
        "features": params.get("features") if isinstance(params.get("features"), list) else [],
        "is_active": True, "created_by": actor_ctx.user_id, "created_at": _now(),
    }
    await db.resources.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def create_booking(db, actor_ctx: ActorContext, params: dict) -> dict:
    resource_id = _text(params, "resource_id")
    purpose = _text(params, "purpose")
    start = _parse_timestamp(params.get("start_at"), "start_at")
    end = _parse_timestamp(params.get("end_at"), "end_at")
    if end <= start:
        raise CampusValidationError("end_at must be after start_at")
    if (end - start).days > 7:
        raise CampusValidationError("A resource booking cannot exceed 7 days")
    resource = await db.resources.find_one(
        scoped_query({"id": resource_id, "is_active": True}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not resource:
        raise CampusNotFoundError("Resource not found")
    conflict = await db.resource_bookings.find_one(scoped_query({
        "resource_id": resource_id, "status": {"$in": ["confirmed", "pending"]},
        "start_at": {"$lt": end.isoformat()}, "end_at": {"$gt": start.isoformat()},
    }, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1})
    if conflict:
        raise CampusConflictError("Resource is already booked during this time")
    booking_id = str(uuid.uuid4())
    doc = {
        "_id": booking_id, "id": booking_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "resource_id": resource_id,
        "resource_name": resource.get("name"), "purpose": purpose,
        "start_at": start.isoformat(), "end_at": end.isoformat(),
        "attendees": int(params.get("attendees") or 0), "status": "confirmed",
        "booked_by": actor_ctx.user_id, "booked_by_role": actor_ctx.role,
        "created_at": _now(),
    }
    if doc["attendees"] < 0 or doc["attendees"] > resource.get("capacity", 1):
        raise CampusValidationError("attendees exceeds resource capacity")
    await db.resource_bookings.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def cancel_booking(db, actor_ctx: ActorContext, booking_id: str) -> dict:
    booking = await db.resource_bookings.find_one(
        scoped_query({"id": booking_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not booking:
        raise CampusNotFoundError("Booking not found")
    if actor_ctx.role == "teacher" and booking.get("booked_by") != actor_ctx.user_id:
        raise CampusConflictError("Teachers can cancel only their own bookings")
    if booking.get("status") == "cancelled":
        return booking
    await db.resource_bookings.update_one(
        scoped_query({"id": booking_id}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "cancelled", "cancelled_by": actor_ctx.user_id, "cancelled_at": _now()}},
    )
    return {**booking, "status": "cancelled"}


async def checkout_asset(db, actor_ctx: ActorContext, asset_id: str, params: dict) -> dict:
    holder_type = str(params.get("holder_type") or "staff").lower()
    if holder_type not in {"staff", "student", "department"}:
        raise CampusValidationError("holder_type must be staff, student, or department")
    holder_id = _text(params, "holder_id")
    asset = await db.assets.find_one(
        scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not asset:
        raise CampusNotFoundError("Asset not found")
    active = await db.asset_custody.find_one(scoped_query(
        {"asset_id": asset_id, "status": "checked_out"}, branch_id=actor_ctx.branch_id
    ), {"_id": 0})
    if active:
        raise CampusConflictError("Asset is already checked out")
    custody_id = str(uuid.uuid4())
    doc = {
        "_id": custody_id, "id": custody_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "asset_id": asset_id,
        "asset_name": asset.get("name"), "holder_type": holder_type, "holder_id": holder_id,
        "condition_out": params.get("condition") or "good", "notes": params.get("notes"),
        "checked_out_by": actor_ctx.user_id, "checked_out_at": _now(), "status": "checked_out",
    }
    await db.asset_custody.insert_one(doc)
    await db.assets.update_one(
        scoped_query({"id": asset_id}, branch_id=actor_ctx.branch_id),
        {"$set": {"custody_status": "checked_out", "current_holder": holder_id, "updated_at": _now()}},
    )
    return {key: value for key, value in doc.items() if key != "_id"}


async def return_asset(db, actor_ctx: ActorContext, custody_id: str, params: dict) -> dict:
    custody = await db.asset_custody.find_one(
        scoped_query({"id": custody_id, "status": "checked_out"}, branch_id=actor_ctx.branch_id),
        {"_id": 0},
    )
    if not custody:
        raise CampusNotFoundError("Active asset custody record not found")
    now = _now()
    await db.asset_custody.update_one(
        scoped_query({"id": custody_id, "status": "checked_out"}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "returned", "condition_in": params.get("condition") or "good",
                  "return_notes": params.get("notes"), "returned_by": actor_ctx.user_id,
                  "returned_at": now}},
    )
    await db.assets.update_one(
        scoped_query({"id": custody["asset_id"]}, branch_id=actor_ctx.branch_id),
        {"$set": {"custody_status": "available", "current_holder": None, "updated_at": now}},
    )
    return {**custody, "status": "returned", "returned_at": now}


async def create_inventory_item(db, actor_ctx: ActorContext, params: dict) -> dict:
    sku = _text(params, "sku").upper()
    name = _text(params, "name")
    existing = await db.inventory_items.find_one(
        scoped_query({"sku": sku}, branch_id=actor_ctx.branch_id), {"_id": 0, "id": 1}
    )
    if existing:
        raise CampusConflictError("Inventory SKU already exists")
    opening = _number(params, "opening_quantity", minimum=0) if params.get("opening_quantity") is not None else 0
    reorder = _number(params, "reorder_level", minimum=0) if params.get("reorder_level") is not None else 0
    item_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": item_id, "id": item_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "sku": sku, "name": name,
        "category": params.get("category"), "unit": params.get("unit") or "each",
        "on_hand": opening, "quantity": opening, "reserved": 0,
        "reorder_level": reorder, "min_stock": reorder,
        "unit_cost": float(params.get("unit_cost") or 0), "is_active": True,
        "created_by": actor_ctx.user_id, "created_at": now, "updated_at": now,
    }
    await db.inventory_items.insert_one(doc)
    if opening:
        await _post_stock_movement(db, actor_ctx, doc, "opening", opening, "opening_balance", item_id)
    return {key: value for key, value in doc.items() if key != "_id"}


async def _post_stock_movement(db, actor_ctx: ActorContext, item: dict, movement_type: str,
                               quantity: float, reference_type: str, reference_id: str,
                               notes: str | None = None) -> dict:
    movement_id = str(uuid.uuid4())
    direction = 1 if movement_type in {"receipt", "return", "opening", "adjustment_in"} else -1
    doc = {
        "_id": movement_id, "id": movement_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "item_id": item["id"], "sku": item.get("sku"),
        "movement_type": movement_type, "quantity": quantity, "quantity_delta": direction * quantity,
        "reference_type": reference_type, "reference_id": reference_id,
        "notes": notes, "posted_by": actor_ctx.user_id, "posted_at": _now(),
    }
    await db.stock_movements.insert_one(doc)
    return doc


async def adjust_stock(db, actor_ctx: ActorContext, item_id: str, params: dict) -> dict:
    movement_type = str(params.get("movement_type") or "").lower()
    if movement_type not in {"receipt", "issue", "return", "adjustment_in", "adjustment_out"}:
        raise CampusValidationError("Invalid movement_type")
    quantity = _number(params, "quantity", minimum=0.000001)
    try:
        await assert_posting_allowed(db, actor_ctx.branch_id, _now()[:10])
    except AccountingPeriodClosedError as exc:
        raise CampusConflictError(str(exc))
    item = await db.inventory_items.find_one(
        scoped_query({"id": item_id, "is_active": True}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not item:
        raise CampusNotFoundError("Inventory item not found")
    inbound = movement_type in {"receipt", "return", "adjustment_in"}
    stock_field = "on_hand" if "on_hand" in item else "quantity"
    current_stock = float(item.get(stock_field) or 0)
    if not inbound and current_stock - quantity < 0:
        raise CampusConflictError("Stock movement would make on-hand quantity negative")
    delta = quantity if inbound else -quantity
    inc_fields = {stock_field: delta}
    if "on_hand" in item and "quantity" in item:
        inc_fields = {"on_hand": delta, "quantity": delta}
    result = await db.inventory_items.update_one(
        scoped_query({
            "id": item_id,
            **({stock_field: {"$gte": quantity}} if not inbound else {}),
        }, branch_id=actor_ctx.branch_id),
        {"$inc": inc_fields, "$set": {"updated_at": _now()}},
    )
    if result.matched_count == 0:
        raise CampusConflictError("Stock changed; refresh and retry")
    movement = await _post_stock_movement(
        db, actor_ctx, item, movement_type, quantity,
        params.get("reference_type") or "manual", params.get("reference_id") or item_id,
        params.get("notes"),
    )
    return {"movement": {key: value for key, value in movement.items() if key != "_id"},
            "on_hand": current_stock + delta}


async def create_requisition(db, actor_ctx: ActorContext, params: dict) -> dict:
    purpose = _text(params, "purpose")
    lines = params.get("lines")
    if not isinstance(lines, list) or not lines:
        raise CampusValidationError("lines must contain at least one requested item")
    normalized = []
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            raise CampusValidationError(f"lines[{index}] must be an object")
        normalized.append({
            "item_id": line.get("item_id"), "description": _text(line, "description"),
            "quantity": _number(line, "quantity", minimum=0.000001),
            "estimated_unit_cost": float(line.get("estimated_unit_cost") or 0),
        })
    requisition_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": requisition_id, "id": requisition_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "purpose": purpose, "lines": normalized,
        "estimated_total": round(sum(row["quantity"] * row["estimated_unit_cost"] for row in normalized), 2),
        "status": "submitted", "requested_by": actor_ctx.user_id,
        "created_at": now, "updated_at": now,
    }
    await db.purchase_requisitions.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def decide_requisition(db, actor_ctx: ActorContext, requisition_id: str, params: dict) -> dict:
    decision = str(params.get("decision") or "").lower()
    if decision not in {"approve", "reject"}:
        raise CampusValidationError("decision must be approve or reject")
    if decision == "reject" and not str(params.get("reason") or "").strip():
        raise CampusValidationError("reason is required when rejecting")
    requisition = await db.purchase_requisitions.find_one(
        scoped_query({"id": requisition_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not requisition:
        raise CampusNotFoundError("Purchase requisition not found")
    if requisition.get("status") != "submitted":
        raise CampusConflictError("Purchase requisition has already been decided")
    status = "approved" if decision == "approve" else "rejected"
    await db.purchase_requisitions.update_one(
        scoped_query({"id": requisition_id, "status": "submitted"}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": status, "decision_reason": params.get("reason"),
                  "decided_by": actor_ctx.user_id, "decided_at": _now(), "updated_at": _now()}},
    )
    return {**requisition, "status": status}


async def create_purchase_order(db, actor_ctx: ActorContext, requisition_id: str, params: dict) -> dict:
    supplier = _text(params, "supplier")
    requisition = await db.purchase_requisitions.find_one(
        scoped_query({"id": requisition_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not requisition:
        raise CampusNotFoundError("Purchase requisition not found")
    if requisition.get("status") not in {"approved", "ordered"}:
        raise CampusConflictError("Only an approved requisition can become a purchase order")
    existing = await db.purchase_orders.find_one(
        scoped_query({"requisition_id": requisition_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if existing:
        return existing
    order_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": order_id, "id": order_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "requisition_id": requisition_id,
        "supplier": supplier, "supplier_reference": params.get("supplier_reference"),
        "lines": requisition["lines"], "total": requisition["estimated_total"],
        "status": "ordered", "ordered_by": actor_ctx.user_id,
        "ordered_at": now, "created_at": now, "updated_at": now,
    }
    await db.purchase_orders.insert_one(doc)
    await db.purchase_requisitions.update_one(
        scoped_query({"id": requisition_id}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "ordered", "purchase_order_id": order_id, "updated_at": now}},
    )
    return {key: value for key, value in doc.items() if key != "_id"}


async def receive_purchase_order(db, actor_ctx: ActorContext, order_id: str) -> dict:
    order = await db.purchase_orders.find_one(
        scoped_query({"id": order_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not order:
        raise CampusNotFoundError("Purchase order not found")
    if order.get("status") == "received":
        return order
    if order.get("status") != "ordered":
        raise CampusConflictError("Purchase order is not open for receipt")
    try:
        await assert_posting_allowed(db, actor_ctx.branch_id, _now()[:10])
    except AccountingPeriodClosedError as exc:
        raise CampusConflictError(str(exc))
    for line in order.get("lines", []):
        item_id = line.get("item_id")
        if not item_id:
            continue
        item = await db.inventory_items.find_one(
            scoped_query({"id": item_id, "is_active": True}, branch_id=actor_ctx.branch_id), {"_id": 0}
        )
        if not item:
            raise CampusValidationError(f"Inventory item not found for line: {line.get('description')}")
        quantity = float(line["quantity"])
        inc_fields = {"on_hand": quantity, "quantity": quantity} if "on_hand" in item and "quantity" in item else {
            "on_hand" if "on_hand" in item else "quantity": quantity
        }
        await db.inventory_items.update_one(
            scoped_query({"id": item_id}, branch_id=actor_ctx.branch_id),
            {"$inc": inc_fields, "$set": {"updated_at": _now()}},
        )
        await _post_stock_movement(db, actor_ctx, item, "receipt", quantity, "purchase_order", order_id)
    now = _now()
    await db.purchase_orders.update_one(
        scoped_query({"id": order_id, "status": "ordered"}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "received", "received_by": actor_ctx.user_id,
                  "received_at": now, "updated_at": now}},
    )
    await db.purchase_requisitions.update_one(
        scoped_query({"id": order["requisition_id"]}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "received", "updated_at": now}},
    )
    return {**order, "status": "received", "received_at": now}


async def create_library_title(db, actor_ctx: ActorContext, params: dict) -> dict:
    accession_number = _text(params, "accession_number").upper()
    title = _text(params, "title")
    try:
        copies = int(params.get("copies") or 1)
    except (TypeError, ValueError):
        raise CampusValidationError("copies must be an integer")
    if copies < 1:
        raise CampusValidationError("copies must be at least 1")
    duplicate = await db.library_titles.find_one(
        scoped_query({"accession_number": accession_number}, branch_id=actor_ctx.branch_id),
        {"_id": 0, "id": 1},
    )
    if duplicate:
        raise CampusConflictError("Library accession number already exists")
    title_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": title_id, "id": title_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "accession_number": accession_number,
        "isbn": params.get("isbn"), "title": title, "author": params.get("author"),
        "publisher": params.get("publisher"), "category": params.get("category"),
        "copies_total": copies, "copies_available": copies,
        "is_active": True, "created_by": actor_ctx.user_id,
        "created_at": now, "updated_at": now,
    }
    await db.library_titles.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def issue_library_title(db, actor_ctx: ActorContext, title_id: str, params: dict) -> dict:
    borrower_type = str(params.get("borrower_type") or "student").lower()
    if borrower_type not in {"student", "staff"}:
        raise CampusValidationError("borrower_type must be student or staff")
    borrower_id = _text(params, "borrower_id")
    due_at = _parse_timestamp(params.get("due_at"), "due_at")
    if due_at <= datetime.now(timezone.utc):
        raise CampusValidationError("due_at must be in the future")
    title = await db.library_titles.find_one(
        scoped_query({"id": title_id, "is_active": True}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not title:
        raise CampusNotFoundError("Library title not found")
    if int(title.get("copies_available") or 0) < 1:
        raise CampusConflictError("No copy is available")
    existing = await db.library_loans.find_one(scoped_query({
        "title_id": title_id, "borrower_type": borrower_type,
        "borrower_id": borrower_id, "status": "issued",
    }, branch_id=actor_ctx.branch_id), {"_id": 0})
    if existing:
        raise CampusConflictError("Borrower already has this title")
    result = await db.library_titles.update_one(
        scoped_query({"id": title_id, "copies_available": {"$gte": 1}}, branch_id=actor_ctx.branch_id),
        {"$inc": {"copies_available": -1}, "$set": {"updated_at": _now()}},
    )
    if result.matched_count == 0:
        raise CampusConflictError("The last available copy was just issued")
    loan_id = str(uuid.uuid4())
    now = _now()
    doc = {
        "_id": loan_id, "id": loan_id, "schoolId": actor_ctx.school_id,
        "branch_id": actor_ctx.branch_id, "title_id": title_id,
        "title": title.get("title"), "accession_number": title.get("accession_number"),
        "borrower_type": borrower_type, "borrower_id": borrower_id,
        "issued_at": now, "due_at": due_at.isoformat(), "renewal_count": 0,
        "status": "issued", "issued_by": actor_ctx.user_id,
    }
    await db.library_loans.insert_one(doc)
    return {key: value for key, value in doc.items() if key != "_id"}


async def return_library_loan(db, actor_ctx: ActorContext, loan_id: str, params: dict) -> dict:
    loan = await db.library_loans.find_one(
        scoped_query({"id": loan_id, "status": "issued"}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not loan:
        raise CampusNotFoundError("Active library loan not found")
    now_dt = datetime.now(timezone.utc)
    due = _parse_timestamp(loan["due_at"], "due_at")
    overdue_days = max((now_dt.date() - due.date()).days, 0)
    daily_fine = float(params.get("daily_fine") or 0)
    if daily_fine < 0:
        raise CampusValidationError("daily_fine cannot be negative")
    fine = round(overdue_days * daily_fine, 2)
    now = now_dt.isoformat()
    result = await db.library_loans.update_one(
        scoped_query({"id": loan_id, "status": "issued"}, branch_id=actor_ctx.branch_id),
        {"$set": {"status": "returned", "returned_at": now,
                  "returned_by": actor_ctx.user_id, "overdue_days": overdue_days,
                  "fine_amount": fine, "condition_in": params.get("condition") or "good"}},
    )
    if result.matched_count == 0:
        raise CampusConflictError("Loan changed; refresh and retry")
    await db.library_titles.update_one(
        scoped_query({"id": loan["title_id"]}, branch_id=actor_ctx.branch_id),
        {"$inc": {"copies_available": 1}, "$set": {"updated_at": now}},
    )
    return {**loan, "status": "returned", "returned_at": now,
            "overdue_days": overdue_days, "fine_amount": fine}


async def renew_library_loan(db, actor_ctx: ActorContext, loan_id: str, params: dict) -> dict:
    loan = await db.library_loans.find_one(
        scoped_query({"id": loan_id, "status": "issued"}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not loan:
        raise CampusNotFoundError("Active library loan not found")
    if int(loan.get("renewal_count") or 0) >= 2:
        raise CampusConflictError("Maximum renewal count reached")
    if _parse_timestamp(loan["due_at"], "due_at") < datetime.now(timezone.utc):
        raise CampusConflictError("Overdue loans cannot be renewed")
    new_due = _parse_timestamp(params.get("due_at"), "due_at")
    if new_due <= _parse_timestamp(loan["due_at"], "due_at"):
        raise CampusValidationError("New due date must be later than the current due date")
    await db.library_loans.update_one(
        scoped_query({"id": loan_id, "status": "issued"}, branch_id=actor_ctx.branch_id),
        {"$set": {"due_at": new_due.isoformat(), "renewed_at": _now(),
                  "renewed_by": actor_ctx.user_id}, "$inc": {"renewal_count": 1}},
    )
    return {**loan, "due_at": new_due.isoformat(),
            "renewal_count": int(loan.get("renewal_count") or 0) + 1}
