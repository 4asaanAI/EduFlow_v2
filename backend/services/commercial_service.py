from __future__ import annotations

"""School CRM, campus retail, and legal-entity domain rules.

This adapts useful ERPNext concepts without importing its framework or accounting
model. Money is stored in integer paise, posted documents are immutable, and every
write is scoped to the current school, branch, and operating legal entity.
"""

import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from services.accounting_period_service import (
    AccountingPeriodClosedError,
    AccountingPeriodValidationError,
    assert_posting_allowed,
)
from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.enquiry_service import create_enquiry, update_enquiry
from services.txn_context import session_kwargs
from tenant import scoped_query


class CommercialValidationError(Exception):
    pass


class CommercialNotFoundError(Exception):
    pass


class CommercialConflictError(Exception):
    pass


ENTITY_TYPES = {"group", "trust", "school", "company"}
PAYMENT_MODES = {"cash", "card", "upi", "bank_transfer", "credit"}
CUSTOMER_TYPES = {"student", "guardian", "walk_in"}
OPPORTUNITY_STAGES = {"qualification", "visit", "application", "offer", "won", "lost"}


def _clean(value) -> str:
    return str(value or "").strip()


def _required(params: dict, key: str) -> str:
    value = _clean(params.get(key))
    if not value:
        raise CommercialValidationError(f"{key} is required")
    return value


def _paise(value, key: str, *, allow_zero: bool = True) -> int:
    try:
        decimal_value = Decimal(str(value))
        if not decimal_value.is_finite():
            raise InvalidOperation
        amount = int((decimal_value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        raise CommercialValidationError(f"{key} must be a valid amount")
    if amount < 0 or (not allow_zero and amount == 0):
        raise CommercialValidationError(f"{key} must be {'positive' if not allow_zero else 'zero or positive'}")
    return amount


def _positive_int(value, key: str) -> int:
    if isinstance(value, bool):
        raise CommercialValidationError(f"{key} must be a positive whole number")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise CommercialValidationError(f"{key} must be a positive whole number")
    if parsed <= 0 or parsed != float(value):
        raise CommercialValidationError(f"{key} must be a positive whole number")
    return parsed


def _probability(value) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        raise CommercialValidationError("probability must be between 0 and 100")
    if not 0 <= parsed <= 100:
        raise CommercialValidationError("probability must be between 0 and 100")
    return parsed


def _fingerprint(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _assert_replay_matches(record: dict, params: dict) -> None:
    stored = record.get("request_fingerprint")
    if stored and stored != _fingerprint(params):
        raise CommercialConflictError("Idempotency key was already used for a different request")


async def _reserve_crm_contacts(db, actor: ActorContext, enquiry_id: str,
                                phone: str, email: str, *, session=None) -> None:
    for kind, value in (("phone", phone), ("email", email)):
        normalized = value.strip().lower()
        if not normalized:
            continue
        digest = hashlib.sha256(
            f"{actor.school_id}:{actor.branch_id}:{kind}:{normalized}".encode("utf-8")
        ).hexdigest()
        try:
            await db.crm_contact_keys.insert_one({
                "_id": digest, "schoolId": actor.school_id, "branch_id": actor.branch_id,
                "kind": kind, "contact_hash": digest, "enquiry_id": enquiry_id,
                "created_at": actor.now_iso(),
            }, **session_kwargs(session))
        except DuplicateKeyError:
            owner = await db.crm_contact_keys.find_one(
                {"_id": digest}, {"_id": 0, "enquiry_id": 1}, **session_kwargs(session)
            )
            if not owner or owner.get("enquiry_id") != enquiry_id:
                raise CommercialConflictError(f"An enquiry already uses this {kind}")


async def _assert_unique_active_contacts(db, actor: ActorContext, enquiry_id: str,
                                         phone: str, email: str, *, session=None) -> None:
    candidates = []
    if phone:
        candidates.append({"phone": phone})
    if email:
        candidates.append({"email": email.lower()})
    if not candidates:
        return
    duplicate = await db.enquiries.find_one(
        _scope(actor, {"id": {"$ne": enquiry_id}, "$or": candidates,
                       "status": {"$nin": ["lost", "closed"]}}),
        {"_id": 0, "id": 1}, **session_kwargs(session),
    )
    if duplicate:
        raise CommercialConflictError("Another active enquiry already uses this phone or email")


async def replay_retail_request(db, actor: ActorContext, key: str, params: dict,
                                *, sale_id: Optional[str] = None) -> dict:
    collection = db.retail_return_idempotency if sale_id else db.retail_idempotency
    record = await collection.find_one(_scope(actor, {"key": key}), {"_id": 0})
    if not record:
        raise CommercialConflictError("A concurrent retail request conflicted; retry safely with the same key")
    payload = {"sale_id": sale_id, **params} if sale_id else params
    _assert_replay_matches(record, payload)
    target = db.retail_returns if sale_id else db.retail_sales
    record_id = record["return_id"] if sale_id else record["sale_id"]
    row = await target.find_one(_scope(actor, {"id": record_id}), {"_id": 0})
    if not row:
        raise CommercialConflictError("Idempotent retail result is not available yet; retry with the same key")
    return row


def _public(doc: dict) -> dict:
    return {key: value for key, value in doc.items() if key != "_id"}


async def _all_docs(cursor) -> list[dict]:
    """Consume a scoped cursor without silently truncating financial totals."""
    return [row async for row in cursor]


def _scope(actor: ActorContext, query: Optional[dict] = None) -> dict:
    return scoped_query(query or {}, branch_id=actor.branch_id)


def entity_record_filter(entity: dict, query: Optional[dict] = None) -> dict:
    """Map legacy records without entity_id to the configured default on reads."""
    base = query or {}
    owns_legacy = entity.get("owns_legacy_records", entity.get("is_default"))
    ownership = ({"$or": [{"entity_id": entity["id"]}, {"entity_id": {"$exists": False}}]}
                 if owns_legacy else {"entity_id": entity["id"]})
    return {"$and": [base, ownership]} if base else ownership


async def _audit(db, actor: ActorContext, action: str, collection: str,
                 record_id: str, changes: Optional[dict] = None, reason: str = "") -> None:
    await write_audit_doc(db, {
        "action": action, "collection": collection, "entity_id": record_id,
        "changed_by": actor.user_id, "changed_by_role": actor.role,
        "changes": changes or {}, "reason": reason,
    }, school_id=actor.school_id, branch_id=actor.branch_id or "")


async def list_entities(db, actor: ActorContext) -> list[dict]:
    return await db.legal_entities.find(_scope(actor), {"_id": 0}).sort("name", 1).to_list(200)


async def resolve_entity(db, actor: ActorContext, entity_id: Optional[str] = None,
                         *, allow_group: bool = False, session=None) -> dict:
    if entity_id is not None and not isinstance(entity_id, str):
        raise CommercialValidationError("entity_id must be a string")
    kwargs = session_kwargs(session)
    if entity_id:
        entity = await db.legal_entities.find_one(
            _scope(actor, {"id": entity_id, "is_active": True}), {"_id": 0}, **kwargs
        )
    else:
        defaults = await db.legal_entities.find(
            _scope(actor, {"is_default": True, "is_active": True}), {"_id": 0}, **kwargs
        ).limit(2).to_list(2)
        if len(defaults) > 1:
            raise CommercialConflictError("Multiple default legal entities are configured")
        if defaults:
            entity = defaults[0]
        else:
            active = await db.legal_entities.find(
                _scope(actor, {"is_active": True}), {"_id": 0}, **kwargs
            ).limit(2).to_list(2)
            if not active:
                raise CommercialConflictError("Configure an operating legal entity first")
            if len(active) > 1:
                raise CommercialConflictError("Select a legal entity; no default is configured")
            entity = active[0]
    if not entity:
        raise CommercialNotFoundError("Legal entity not found")
    if entity.get("is_group") and not allow_group:
        raise CommercialValidationError("Group entities cannot post transactions")
    return entity


async def create_entity(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    kwargs = session_kwargs(session)
    name = _required(params, "name")
    code = _required(params, "code").upper()
    entity_type = _clean(params.get("entity_type") or "school").lower()
    if entity_type not in ENTITY_TYPES:
        raise CommercialValidationError("entity_type must be group, trust, school, or company")
    is_group = entity_type == "group" or bool(params.get("is_group"))
    if await db.legal_entities.find_one(_scope(actor, {"code": code}), {"_id": 0, "id": 1}, **kwargs):
        raise CommercialConflictError("Legal entity code already exists")
    parent_id = _clean(params.get("parent_entity_id")) or None
    if parent_id:
        parent = await resolve_entity(db, actor, parent_id, allow_group=True, session=session)
        if not parent.get("is_group"):
            raise CommercialValidationError("Parent legal entity must be a group")
    requested_default = bool(params.get("is_default"))
    if is_group and requested_default:
        raise CommercialValidationError("A group entity cannot be the operating default")
    existing_default = await db.legal_entities.find_one(
        _scope(actor, {"is_default": True, "is_active": True}), {"_id": 0, "id": 1}, **kwargs
    )
    legacy_owner = await db.legal_entities.find_one(
        _scope(actor, {"owns_legacy_records": True}), {"_id": 0, "id": 1}, **kwargs
    )
    is_default = requested_default or (not is_group and not existing_default)
    if requested_default:
        await db.legal_entities.update_many(
            _scope(actor, {"is_default": True}), {"$set": {"is_default": False}}, **kwargs
        )
    entity_id = str(uuid.uuid4())
    now = actor.now_iso()
    doc = {
        "_id": entity_id, "id": entity_id, "schoolId": actor.school_id,
        "branch_id": actor.branch_id, "name": name, "code": code,
        "entity_type": entity_type, "is_group": is_group, "parent_entity_id": parent_id,
        "currency": _clean(params.get("currency") or "INR").upper(),
        "tax_id": _clean(params.get("tax_id")) or None,
        "registration_number": _clean(params.get("registration_number")) or None,
        "is_default": is_default, "is_active": True,
        "owns_legacy_records": bool(is_default and not legacy_owner),
        "created_by": actor.user_id, "created_at": now, "updated_at": now,
    }
    try:
        await db.legal_entities.insert_one(doc, **kwargs)
    except DuplicateKeyError:
        raise CommercialConflictError("Legal entity code or operating default already exists")
    await _audit(db, actor, "legal_entity_create", "legal_entities", entity_id,
                 {"code": code, "entity_type": entity_type, "is_default": is_default})
    return _public(doc)


async def set_default_entity(db, actor: ActorContext, entity_id: str, *, session=None) -> dict:
    kwargs = session_kwargs(session)
    entity = await resolve_entity(db, actor, entity_id, session=session)
    legacy_owner = await db.legal_entities.find_one(
        _scope(actor, {"owns_legacy_records": True}), {"_id": 0, "id": 1}, **kwargs
    )
    if not legacy_owner:
        previous = await db.legal_entities.find_one(
            _scope(actor, {"is_default": True}), {"_id": 0, "id": 1}, **kwargs
        )
        if previous:
            legacy_owner = previous
            await db.legal_entities.update_one(
                _scope(actor, {"id": previous["id"]}), {"$set": {"owns_legacy_records": True}}, **kwargs
            )
    target_owns_legacy = not legacy_owner or legacy_owner["id"] == entity_id
    await db.legal_entities.update_many(_scope(actor, {"is_default": True}), {
        "$set": {"is_default": False, "updated_at": actor.now_iso()}
    }, **kwargs)
    await db.legal_entities.update_one(_scope(actor, {"id": entity_id}), {
        "$set": {"is_default": True,
                 "owns_legacy_records": target_owns_legacy,
                 "updated_at": actor.now_iso()}
    }, **kwargs)
    await _audit(db, actor, "legal_entity_set_default", "legal_entities", entity_id)
    return {**entity, "is_default": True,
            "owns_legacy_records": target_owns_legacy,
            "updated_at": actor.now_iso()}


async def _next_number(db, actor: ActorContext, entity: dict, kind: str, *, session=None) -> str:
    year = actor.now().year
    row = await db.commercial_sequences.find_one_and_update(
        _scope(actor, {"entity_id": entity["id"], "kind": kind, "year": year}),
        {"$inc": {"value": 1}, "$setOnInsert": {
            "schoolId": actor.school_id, "branch_id": actor.branch_id,
            "entity_id": entity["id"], "kind": kind, "year": year,
        }},
        upsert=True, return_document=ReturnDocument.AFTER, **session_kwargs(session),
    )
    prefix = {"sale": "SALE", "return": "RET", "shift": "SHIFT"}.get(kind, kind.upper())
    return f"{entity['code']}-{prefix}-{year}-{int(row.get('value') or 0):06d}"


async def create_crm_lead(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    phone = _clean(params.get("phone"))
    email = _clean(params.get("email")).lower()
    duplicate_filters = []
    if phone:
        duplicate_filters.append({"phone": phone})
    if email:
        duplicate_filters.append({"email": email})
    if duplicate_filters:
        duplicate = await db.enquiries.find_one(
            _scope(actor, {"$or": duplicate_filters, "status": {"$nin": ["lost", "closed"]}}),
            {"_id": 0, "id": 1}, **session_kwargs(session),
        )
        if duplicate:
            raise CommercialConflictError("An active enquiry already uses this phone or email")
    entity = await resolve_entity(db, actor, params.get("entity_id"), session=session)
    enquiry_id = str(uuid.uuid4())
    await _reserve_crm_contacts(db, actor, enquiry_id, phone, email, session=session)
    extra = {
        "branch_id": actor.branch_id, "entity_id": entity["id"], "email": email or None,
        "lead_type": _clean(params.get("lead_type") or "admission").lower(),
        "campaign": _clean(params.get("campaign")) or None,
        "next_follow_up": _clean(params.get("next_follow_up")) or None,
        "estimated_value_paise": _paise(params.get("estimated_value") or 0, "estimated_value"),
        "probability": _probability(params.get("probability")),
        "updated_at": actor.now_iso(),
    }
    result = await create_enquiry(
        db, actor, params, session=session, extra_fields={"id": enquiry_id, **extra}
    )
    row = result["enquiry"]
    await _audit(db, actor, "crm_lead_create", "enquiries", row["id"], {"entity_id": entity["id"]})
    return row


async def _validate_conversion_links(db, actor: ActorContext, enquiry_id: str,
                                     application_id: Optional[str], student_id: Optional[str],
                                     *, session=None) -> None:
    application = None
    if application_id:
        application = await db.admission_applications.find_one(
            _scope(actor, {"id": application_id, "enquiry_id": enquiry_id}), {"_id": 0, "id": 1}
            , **session_kwargs(session)
        )
        if not application:
            raise CommercialValidationError("application_id must belong to this enquiry and branch")
    if student_id:
        links = [{"enquiry_id": enquiry_id}]
        if application_id:
            links.append({"admission_application_id": application_id})
        student = await db.students.find_one(
            _scope(actor, {"id": student_id, "$or": links}), {"_id": 0, "id": 1}
            , **session_kwargs(session)
        )
        if not student:
            raise CommercialValidationError("student_id must belong to this enquiry or application")


async def update_crm_lead(db, actor: ActorContext, enquiry_id: str, params: dict, *, session=None) -> dict:
    existing = await db.enquiries.find_one(
        _scope(actor, {"id": enquiry_id}), {"_id": 0}, **session_kwargs(session)
    )
    if not existing:
        raise CommercialNotFoundError("CRM lead not found")
    status = _clean(params.get("status")).lower()
    if status == "lost" and not _clean(params.get("lost_reason")):
        raise CommercialValidationError("lost_reason is required when a lead is lost")
    application_id = (_clean(params.get("application_id")) or None
                      if "application_id" in params else existing.get("application_id"))
    student_id = (_clean(params.get("student_id")) or None
                  if "student_id" in params else existing.get("student_id"))
    if status == "enrolled" and (not application_id or not student_id):
        raise CommercialValidationError(
            "An enrolled CRM lead must link its admission application and student record"
        )
    allowed = {"email", "lead_type", "campaign", "next_follow_up", "lost_reason",
               "application_id", "student_id", "assigned_to"}
    extra = {key: params[key] for key in allowed if key in params}
    if "estimated_value" in params:
        extra["estimated_value_paise"] = _paise(params["estimated_value"], "estimated_value")
    if "probability" in params:
        extra["probability"] = _probability(params["probability"])
    await _validate_conversion_links(
        db, actor, enquiry_id, application_id, student_id, session=session,
    )
    await _assert_unique_active_contacts(
        db, actor, enquiry_id,
        _clean(params.get("phone")) if "phone" in params else "",
        _clean(params.get("email")) if "email" in params else "",
        session=session,
    )
    await _reserve_crm_contacts(
        db, actor, enquiry_id,
        _clean(params.get("phone")) if "phone" in params else "",
        _clean(params.get("email")) if "email" in params else "",
        session=session,
    )
    if extra:
        extra["updated_at"] = actor.now_iso()
    service_params = {**params, "enquiry_id": enquiry_id}
    result = await update_enquiry(
        db, actor, service_params, session=session, extra_fields=extra
    )
    updated = result["enquiry"]
    await _audit(db, actor, "crm_lead_update", "enquiries", enquiry_id, extra,
                 _clean(params.get("lost_reason")))
    return updated


async def add_crm_activity(db, actor: ActorContext, enquiry_id: str, params: dict, *, session=None) -> dict:
    kwargs = session_kwargs(session)
    lead = await db.enquiries.find_one(
        _scope(actor, {"id": enquiry_id}), {"_id": 0, "entity_id": 1}, **kwargs
    )
    if not lead:
        raise CommercialNotFoundError("CRM lead not found")
    entity = await resolve_entity(db, actor, lead.get("entity_id"), session=session)
    activity_type = _clean(params.get("activity_type") or "note").lower()
    if activity_type not in {"note", "call", "email", "meeting", "visit", "follow_up"}:
        raise CommercialValidationError("Invalid activity_type")
    activity_id = str(uuid.uuid4())
    doc = {
        "_id": activity_id, "id": activity_id, "schoolId": actor.school_id,
        "branch_id": actor.branch_id, "entity_id": entity["id"],
        "enquiry_id": enquiry_id, "activity_type": activity_type,
        "subject": _required(params, "subject"), "notes": _clean(params.get("notes")),
        "occurred_at": _clean(params.get("occurred_at")) or actor.now_iso(),
        "next_follow_up": _clean(params.get("next_follow_up")) or None,
        "created_by": actor.user_id, "created_at": actor.now_iso(),
    }
    await db.crm_activities.insert_one(doc, **kwargs)
    if doc["next_follow_up"]:
        await db.enquiries.update_one(_scope(actor, {"id": enquiry_id}), {
            "$set": {"next_follow_up": doc["next_follow_up"], "updated_at": actor.now_iso()}
        }, **kwargs)
    await _audit(db, actor, "crm_activity_create", "crm_activities", activity_id,
                 {"enquiry_id": enquiry_id, "activity_type": activity_type})
    return _public(doc)


async def create_opportunity(db, actor: ActorContext, enquiry_id: str, params: dict, *, session=None) -> dict:
    kwargs = session_kwargs(session)
    lead = await db.enquiries.find_one(_scope(actor, {"id": enquiry_id}), {"_id": 0}, **kwargs)
    if not lead:
        raise CommercialNotFoundError("CRM lead not found")
    entity = await resolve_entity(db, actor, lead.get("entity_id"), session=session)
    requested_entity = _clean(params.get("entity_id")) or entity["id"]
    if requested_entity != entity["id"]:
        raise CommercialValidationError("Opportunity legal entity must match its CRM lead")
    probability = _probability(params.get("probability"))
    opportunity_id = str(uuid.uuid4())
    doc = {
        "_id": opportunity_id, "id": opportunity_id, "schoolId": actor.school_id,
        "branch_id": actor.branch_id, "entity_id": entity["id"], "enquiry_id": enquiry_id,
        "title": _required(params, "title"), "stage": "qualification",
        "amount_paise": _paise(params.get("amount") or 0, "amount"),
        "probability": probability, "expected_close_date": _clean(params.get("expected_close_date")) or None,
        "owner_id": _clean(params.get("owner_id")) or actor.user_id,
        "created_by": actor.user_id, "created_at": actor.now_iso(), "updated_at": actor.now_iso(),
    }
    await db.crm_opportunities.insert_one(doc, **kwargs)
    await _audit(db, actor, "crm_opportunity_create", "crm_opportunities", opportunity_id,
                 {"enquiry_id": enquiry_id, "amount_paise": doc["amount_paise"]})
    return _public(doc)


async def update_opportunity(db, actor: ActorContext, opportunity_id: str, params: dict,
                             *, session=None) -> dict:
    kwargs = session_kwargs(session)
    existing = await db.crm_opportunities.find_one(_scope(actor, {"id": opportunity_id}), {"_id": 0},
                                                   **kwargs)
    if not existing:
        raise CommercialNotFoundError("CRM opportunity not found")
    stage = _clean(params.get("stage") or existing.get("stage")).lower()
    if stage not in OPPORTUNITY_STAGES:
        raise CommercialValidationError("Invalid opportunity stage")
    if stage == "lost" and not _clean(params.get("lost_reason")):
        raise CommercialValidationError("lost_reason is required when an opportunity is lost")
    allowed = {"title", "expected_close_date", "owner_id", "lost_reason", "conversion_reference"}
    update = {key: params[key] for key in allowed if key in params}
    update["stage"] = stage
    if "amount" in params:
        update["amount_paise"] = _paise(params["amount"], "amount")
    if "probability" in params:
        update["probability"] = _probability(params["probability"])
    if stage == "won":
        update["probability"] = 100
        update["closed_at"] = actor.now_iso()
    elif stage == "lost":
        update["probability"] = 0
        update["closed_at"] = actor.now_iso()
    update["updated_at"] = actor.now_iso()
    await db.crm_opportunities.update_one(_scope(actor, {"id": opportunity_id}), {"$set": update},
                                          **kwargs)
    await _audit(db, actor, "crm_opportunity_update", "crm_opportunities", opportunity_id, update,
                 _clean(params.get("lost_reason")))
    return {**existing, **update}


async def crm_pipeline(db, actor: ActorContext, entity_id: Optional[str] = None) -> dict:
    entity = await resolve_entity(db, actor, entity_id)
    leads = await _all_docs(db.enquiries.find(_scope(actor, entity_record_filter(entity)), {"_id": 0}))
    opportunities = await _all_docs(db.crm_opportunities.find(
        _scope(actor, entity_record_filter(entity)), {"_id": 0}
    ))
    stages = {}
    for row in opportunities:
        stage = row.get("stage") or "qualification"
        bucket = stages.setdefault(stage, {"count": 0, "amount_paise": 0, "weighted_paise": 0})
        bucket["count"] += 1
        bucket["amount_paise"] += int(row.get("amount_paise") or 0)
        bucket["weighted_paise"] += round(int(row.get("amount_paise") or 0) * int(row.get("probability") or 0) / 100)
    due = [row for row in leads if row.get("next_follow_up") and str(row["next_follow_up"])[:10] <= date.today().isoformat()
           and row.get("status") not in {"lost", "closed", "enrolled"}]
    return {"entity": entity, "lead_count": len(leads), "follow_ups_due": len(due), "stages": stages}


async def create_product(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    kwargs = session_kwargs(session)
    entity = await resolve_entity(db, actor, params.get("entity_id"), session=session)
    sku = _required(params, "sku").upper()
    if await db.commercial_products.find_one(
        _scope(actor, {"entity_id": entity["id"], "sku": sku}), {"_id": 0}, **kwargs
    ):
        raise CommercialConflictError("Retail SKU already exists for this legal entity")
    inventory_item_id = _required(params, "inventory_item_id")
    item = await db.inventory_items.find_one(
        _scope(actor, entity_record_filter(entity, {"id": inventory_item_id, "is_active": True})),
        {"_id": 0}, **kwargs
    )
    if not item:
        raise CommercialNotFoundError("Inventory item not found")
    try:
        tax_rate_bps = int(round(float(params.get("tax_rate_percent") or 0) * 100))
    except (TypeError, ValueError):
        raise CommercialValidationError("tax_rate_percent must be between 0 and 100")
    if not 0 <= tax_rate_bps <= 10000:
        raise CommercialValidationError("tax_rate_percent must be between 0 and 100")
    if item.get("on_hand") is None:
        legacy_quantity = item.get("quantity") or 0
        try:
            whole_quantity = int(legacy_quantity)
        except (TypeError, ValueError):
            raise CommercialValidationError("Retail inventory quantity must be a whole number")
        if isinstance(legacy_quantity, bool) or whole_quantity < 0 or whole_quantity != float(legacy_quantity):
            raise CommercialValidationError("Retail inventory quantity must be a non-negative whole number")
        await db.inventory_items.update_one(
            _scope(actor, entity_record_filter(entity, {"id": inventory_item_id, "on_hand": {"$exists": False}})),
            {"$set": {"on_hand": whole_quantity, "updated_at": actor.now_iso()}}, **kwargs,
        )
    product_id = str(uuid.uuid4())
    doc = {
        "_id": product_id, "id": product_id, "schoolId": actor.school_id,
        "branch_id": actor.branch_id, "entity_id": entity["id"], "sku": sku,
        "name": _required(params, "name"), "category": _clean(params.get("category")) or "general",
        "inventory_item_id": inventory_item_id,
        "unit_price_paise": _paise(params.get("unit_price"), "unit_price", allow_zero=False),
        "tax_rate_bps": tax_rate_bps, "is_active": True,
        "created_by": actor.user_id, "created_at": actor.now_iso(), "updated_at": actor.now_iso(),
    }
    await db.commercial_products.insert_one(doc, **kwargs)
    await _audit(db, actor, "retail_product_create", "commercial_products", product_id,
                 {"sku": sku, "entity_id": entity["id"]})
    return _public(doc)


async def open_shift(db, actor: ActorContext, params: dict) -> dict:
    entity = await resolve_entity(db, actor, params.get("entity_id"))
    requested_cashier = _clean(params.get("cashier_id")) or actor.user_id
    if actor.role != "owner" and requested_cashier != actor.user_id:
        raise CommercialValidationError("Only the school owner can open a shift for another cashier")
    cashier_id = requested_cashier
    existing = await db.pos_shifts.find_one(
        _scope(actor, {"entity_id": entity["id"], "cashier_id": cashier_id, "status": "open"}), {"_id": 0}
    )
    if existing:
        raise CommercialConflictError("This cashier already has an open shift for the legal entity")
    shift_id = str(uuid.uuid4())
    doc = {
        "_id": shift_id, "id": shift_id, "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "entity_id": entity["id"], "shift_number": await _next_number(db, actor, entity, "shift"),
        "cashier_id": cashier_id, "register_name": _required(params, "register_name"),
        "opening_cash_paise": _paise(params.get("opening_cash") or 0, "opening_cash"),
        "status": "open", "opened_by": actor.user_id, "opened_at": actor.now_iso(),
    }
    try:
        await db.pos_shifts.insert_one(doc)
    except DuplicateKeyError:
        raise CommercialConflictError("This cashier already has an open shift for the legal entity")
    await _audit(db, actor, "pos_shift_open", "pos_shifts", shift_id, {"entity_id": entity["id"]})
    return _public(doc)


async def _open_shift(db, actor: ActorContext, shift_id: str, entity_id: str, *, session=None) -> dict:
    shift = await db.pos_shifts.find_one(
        _scope(actor, {"id": shift_id, "entity_id": entity_id, "status": "open"}),
        {"_id": 0}, **session_kwargs(session),
    )
    if not shift:
        raise CommercialConflictError("POS shift is not open for this legal entity")
    if actor.role != "owner" and shift.get("cashier_id") != actor.user_id:
        raise CommercialConflictError("This POS shift belongs to another cashier")
    return shift


def _normalise_payments(payments, total_paise: int) -> list[dict]:
    if not isinstance(payments, list) or not payments:
        raise CommercialValidationError("payments must contain at least one payment")
    rows = []
    for index, payment in enumerate(payments):
        if not isinstance(payment, dict):
            raise CommercialValidationError(f"payments[{index}] must be an object")
        mode = _clean(payment.get("mode")).lower()
        if mode not in PAYMENT_MODES:
            raise CommercialValidationError(f"payments[{index}].mode is invalid")
        rows.append({"mode": mode, "amount_paise": _paise(payment.get("amount"), f"payments[{index}].amount"),
                     "reference": _clean(payment.get("reference")) or None})
    if sum(row["amount_paise"] for row in rows) != total_paise:
        raise CommercialValidationError("Payment total must exactly match the sale total")
    return rows


def _normalise_refund_payments(payments, total_paise: int, sale: dict,
                               previous_returns: list[dict]) -> list[dict]:
    sold_by_mode = {}
    for payment in sale.get("payments") or []:
        sold_by_mode[payment.get("mode")] = sold_by_mode.get(payment.get("mode"), 0) + int(payment.get("amount_paise") or 0)
    already_refunded = {}
    for prior in previous_returns:
        for payment in prior.get("payments") or []:
            already_refunded[payment.get("mode")] = already_refunded.get(payment.get("mode"), 0) + int(payment.get("amount_paise") or 0)
    if not payments:
        remaining = total_paise
        rows = []
        for mode, sold_amount in sold_by_mode.items():
            available = max(0, sold_amount - already_refunded.get(mode, 0))
            allocated = min(remaining, available)
            if allocated:
                rows.append({"mode": mode, "amount_paise": allocated, "reference": None})
                remaining -= allocated
            if remaining == 0:
                break
        if remaining:
            raise CommercialConflictError("Refund exceeds the remaining original payments")
        return rows
    rows = _normalise_payments(payments, total_paise)
    requested = {}
    for payment in rows:
        mode = payment["mode"]
        requested[mode] = requested.get(mode, 0) + payment["amount_paise"]
    for mode, amount in requested.items():
        if mode not in sold_by_mode:
            raise CommercialValidationError(f"Refund mode {mode} was not used on the original sale")
        if already_refunded.get(mode, 0) + amount > sold_by_mode[mode]:
            raise CommercialConflictError(f"Refund exceeds the original {mode} payment")
    return rows


async def create_sale(db, actor: ActorContext, params: dict, *, idempotency_key: str,
                      session=None) -> dict:
    key = _clean(idempotency_key)
    if not key:
        raise CommercialValidationError("Idempotency-Key header is required")
    existing = await db.retail_idempotency.find_one(_scope(actor, {"key": key}), {"_id": 0},
                                                    **session_kwargs(session))
    if existing:
        _assert_replay_matches(existing, params)
        sale = await db.retail_sales.find_one(_scope(actor, {"id": existing["sale_id"]}), {"_id": 0},
                                              **session_kwargs(session))
        return sale
    entity = await resolve_entity(db, actor, params.get("entity_id"))
    shift = await _open_shift(db, actor, _required(params, "shift_id"), entity["id"], session=session)
    try:
        await assert_posting_allowed(db, actor.branch_id, params.get("posting_date") or date.today().isoformat(),
                                     entity_id=entity["id"], session=session)
    except AccountingPeriodValidationError as exc:
        raise CommercialValidationError(str(exc))
    except AccountingPeriodClosedError as exc:
        raise CommercialConflictError(str(exc))
    customer_type = _clean(params.get("customer_type") or "walk_in").lower()
    if customer_type not in CUSTOMER_TYPES:
        raise CommercialValidationError("customer_type must be student, guardian, or walk_in")
    customer_id = _clean(params.get("customer_id")) or None
    customer_name = _clean(params.get("customer_name")) or "Walk-in"
    if customer_type == "student":
        if not customer_id:
            raise CommercialValidationError("customer_id is required for a student sale")
        customer = await db.students.find_one(
            _scope(actor, {"id": customer_id, "is_active": True}),
            {"_id": 0, "id": 1, "name": 1}, **session_kwargs(session),
        )
        if not customer:
            raise CommercialNotFoundError("Student customer not found")
        customer_name = _clean(customer.get("name")) or "Student"
    elif customer_type == "guardian":
        if not customer_id:
            raise CommercialValidationError("customer_id is required for a guardian sale")
        customer = await db.guardians.find_one(
            _scope(actor, {"id": customer_id}), {"_id": 0, "id": 1, "name": 1},
            **session_kwargs(session),
        )
        if not customer:
            raise CommercialNotFoundError("Guardian customer not found")
        customer_name = _clean(customer.get("name")) or "Guardian"
    raw_lines = params.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise CommercialValidationError("lines must contain at least one product")
    grouped_lines = {}
    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            raise CommercialValidationError(f"lines[{index}] must be an object")
        product_id = _required(raw, "product_id")
        quantity = _positive_int(raw.get("quantity"), f"lines[{index}].quantity")
        prior = grouped_lines.get(product_id)
        if prior and raw.get("unit_price") is not None and prior.get("unit_price") not in {None, raw.get("unit_price")}:
            raise CommercialValidationError("Duplicate product lines must use the same unit price")
        grouped_lines[product_id] = {
            "product_id": product_id,
            "quantity": quantity + int(prior.get("quantity") or 0) if prior else quantity,
            "unit_price": raw.get("unit_price") if raw.get("unit_price") is not None else (prior or {}).get("unit_price"),
        }
    lines = []
    subtotal = tax_total = 0
    # Audit A-7 (2026-08-05): one batched read for the whole cart instead of a query
    # per line, per CLAUDE.md's no-loop-queries rule.
    product_ids = [_required(raw, "product_id") for raw in grouped_lines.values()]
    products_by_id = {
        row["id"]: row
        for row in await db.commercial_products.find(
            _scope(actor, {"id": {"$in": product_ids}, "entity_id": entity["id"], "is_active": True}),
            {"_id": 0}, **session_kwargs(session),
        ).to_list(len(product_ids))
    }
    for index, raw in enumerate(grouped_lines.values()):
        product = products_by_id.get(_required(raw, "product_id"))
        if not product:
            raise CommercialNotFoundError(f"Product not found at lines[{index}]")
        quantity = _positive_int(raw.get("quantity"), f"lines[{index}].quantity")
        price = int(product["unit_price_paise"])
        if raw.get("unit_price") is not None and _paise(raw["unit_price"], "unit_price") != price:
            raise CommercialConflictError(f"Price changed for {product['name']}; refresh and retry")
        net = price * quantity
        tax = round(net * int(product.get("tax_rate_bps") or 0) / 10000)
        subtotal += net
        tax_total += tax
        lines.append({"product_id": product["id"], "inventory_item_id": product["inventory_item_id"],
                      "sku": product["sku"], "name": product["name"], "quantity": quantity,
                      "unit_price_paise": price, "tax_rate_bps": int(product.get("tax_rate_bps") or 0),
                      "net_paise": net, "tax_paise": tax, "total_paise": net + tax})
    total = subtotal + tax_total
    payments = _normalise_payments(params.get("payments"), total)
    sale_id = str(uuid.uuid4())
    receipt = await _next_number(db, actor, entity, "sale", session=session)
    now = actor.now_iso()
    shift_touch = await db.pos_shifts.update_one(
        _scope(actor, {"id": shift["id"], "entity_id": entity["id"], "status": "open"}),
        {"$inc": {"activity_version": 1}}, **session_kwargs(session),
    )
    if shift_touch.matched_count == 0:
        raise CommercialConflictError("POS shift closed while the sale was being posted")
    for line in lines:
        result = await db.inventory_items.update_one(
            _scope(actor, entity_record_filter(entity, {"id": line["inventory_item_id"], "is_active": True,
                                                        "on_hand": {"$gte": line["quantity"]}})),
            {"$inc": {"on_hand": -line["quantity"], "quantity": -line["quantity"]},
             "$set": {"updated_at": now}}, **session_kwargs(session),
        )
        if result.matched_count == 0:
            raise CommercialConflictError(f"Insufficient or changed stock for {line['name']}")
        movement_id = str(uuid.uuid4())
        await db.stock_movements.insert_one({
            "_id": movement_id, "id": movement_id, "schoolId": actor.school_id,
            "branch_id": actor.branch_id, "entity_id": entity["id"],
            "item_id": line["inventory_item_id"], "sku": line["sku"],
            "movement_type": "issue", "quantity": line["quantity"],
            "quantity_delta": -line["quantity"], "reference_type": "retail_sale",
            "reference_id": sale_id, "posted_by": actor.user_id, "posted_at": now,
        }, **session_kwargs(session))
    sale = {
        "_id": sale_id, "id": sale_id, "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "entity_id": entity["id"], "receipt_number": receipt, "shift_id": shift["id"],
        "customer_type": customer_type, "customer_id": customer_id,
        "customer_name": customer_name,
        "lines": lines, "subtotal_paise": subtotal, "tax_paise": tax_total, "total_paise": total,
        "payments": payments, "status": "posted", "posting_date": params.get("posting_date") or date.today().isoformat(),
        "created_by": actor.user_id, "created_at": now,
    }
    await db.retail_sales.insert_one(sale, **session_kwargs(session))
    await db.retail_idempotency.insert_one({
        "_id": str(uuid.uuid4()), "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "key": key, "sale_id": sale_id, "request_fingerprint": _fingerprint(params), "created_at": now,
    }, **session_kwargs(session))
    await _audit(db, actor, "retail_sale_post", "retail_sales", sale_id,
                 {"receipt_number": receipt, "entity_id": entity["id"], "total_paise": total})
    return _public(sale)


async def create_return(db, actor: ActorContext, sale_id: str, params: dict, *,
                        idempotency_key: str, session=None) -> dict:
    key = _clean(idempotency_key)
    if not key:
        raise CommercialValidationError("Idempotency-Key header is required")
    prior_key = await db.retail_return_idempotency.find_one(_scope(actor, {"key": key}), {"_id": 0},
                                                           **session_kwargs(session))
    if prior_key:
        _assert_replay_matches(prior_key, {"sale_id": sale_id, **params})
        return await db.retail_returns.find_one(_scope(actor, {"id": prior_key["return_id"]}), {"_id": 0},
                                                **session_kwargs(session))
    sale = await db.retail_sales.find_one(_scope(actor, {"id": sale_id, "status": "posted"}), {"_id": 0},
                                          **session_kwargs(session))
    if not sale:
        raise CommercialNotFoundError("Posted retail sale not found")
    entity = await resolve_entity(db, actor, params.get("entity_id") or sale.get("entity_id"))
    if entity["id"] != sale.get("entity_id"):
        raise CommercialValidationError("Return legal entity must match the original sale")
    shift = await _open_shift(db, actor, _required(params, "shift_id"), entity["id"], session=session)
    try:
        await assert_posting_allowed(db, actor.branch_id, params.get("posting_date") or date.today().isoformat(),
                                     entity_id=entity["id"], session=session)
    except AccountingPeriodValidationError as exc:
        raise CommercialValidationError(str(exc))
    except AccountingPeriodClosedError as exc:
        raise CommercialConflictError(str(exc))
    previous = await _all_docs(db.retail_returns.find(
        _scope(actor, {"sale_id": sale_id, "status": "posted"}),
        {"_id": 0}, **session_kwargs(session)
    ))
    returned = {}
    for row in previous:
        for line in row.get("lines") or []:
            returned[line["product_id"]] = returned.get(line["product_id"], 0) + int(line["quantity"])
    sold = {line["product_id"]: line for line in sale.get("lines") or []}
    raw_lines = params.get("lines")
    if not isinstance(raw_lines, list) or not raw_lines:
        raise CommercialValidationError("lines must contain at least one returned product")
    requested_quantities = {}
    for index, raw in enumerate(raw_lines):
        if not isinstance(raw, dict):
            raise CommercialValidationError(f"lines[{index}] must be an object")
        product_id = _required(raw, "product_id")
        requested_quantities[product_id] = requested_quantities.get(product_id, 0) + _positive_int(
            raw.get("quantity"), f"lines[{index}].quantity"
        )
    lines = []
    total = 0
    for index, (product_id, quantity) in enumerate(requested_quantities.items()):
        original = sold.get(product_id)
        if not original:
            raise CommercialValidationError(f"Product at lines[{index}] was not on the original sale")
        if returned.get(product_id, 0) + quantity > int(original["quantity"]):
            raise CommercialConflictError(f"Return quantity exceeds remaining quantity for {original['name']}")
        ratio_net = round(int(original["net_paise"]) * quantity / int(original["quantity"]))
        ratio_tax = round(int(original["tax_paise"]) * quantity / int(original["quantity"]))
        ratio_total = ratio_net + ratio_tax
        lines.append({**original, "quantity": quantity, "net_paise": ratio_net,
                      "tax_paise": ratio_tax, "total_paise": ratio_total})
        total += ratio_total
    payments = _normalise_refund_payments(params.get("payments"), total, sale, previous)
    return_id = str(uuid.uuid4())
    number = await _next_number(db, actor, entity, "return", session=session)
    now = actor.now_iso()
    shift_touch = await db.pos_shifts.update_one(
        _scope(actor, {"id": shift["id"], "entity_id": entity["id"], "status": "open"}),
        {"$inc": {"activity_version": 1}}, **session_kwargs(session),
    )
    if shift_touch.matched_count == 0:
        raise CommercialConflictError("POS shift closed while the return was being posted")
    for line in lines:
        result = await db.inventory_items.update_one(
            _scope(actor, entity_record_filter(entity, {"id": line["inventory_item_id"], "is_active": True})),
            {"$inc": {"on_hand": line["quantity"], "quantity": line["quantity"]},
             "$set": {"updated_at": now}}, **session_kwargs(session),
        )
        if result.matched_count == 0:
            raise CommercialConflictError(f"Inventory item is unavailable for {line['name']}")
        movement_id = str(uuid.uuid4())
        await db.stock_movements.insert_one({
            "_id": movement_id, "id": movement_id, "schoolId": actor.school_id,
            "branch_id": actor.branch_id, "entity_id": entity["id"],
            "item_id": line["inventory_item_id"], "sku": line["sku"],
            "movement_type": "return", "quantity": line["quantity"],
            "quantity_delta": line["quantity"], "reference_type": "retail_return",
            "reference_id": return_id, "posted_by": actor.user_id, "posted_at": now,
        }, **session_kwargs(session))
    doc = {
        "_id": return_id, "id": return_id, "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "entity_id": entity["id"], "return_number": number, "sale_id": sale_id,
        "receipt_number": sale.get("receipt_number"), "shift_id": shift["id"],
        "lines": lines, "total_paise": total, "payments": payments,
        "reason": _required(params, "reason"), "status": "posted",
        "posting_date": params.get("posting_date") or date.today().isoformat(),
        "created_by": actor.user_id, "created_at": now,
    }
    await db.retail_returns.insert_one(doc, **session_kwargs(session))
    await db.retail_return_idempotency.insert_one({
        "_id": str(uuid.uuid4()), "schoolId": actor.school_id, "branch_id": actor.branch_id,
        "key": key, "return_id": return_id,
        "request_fingerprint": _fingerprint({"sale_id": sale_id, **params}), "created_at": now,
    }, **session_kwargs(session))
    await _audit(db, actor, "retail_return_post", "retail_returns", return_id,
                 {"sale_id": sale_id, "total_paise": total}, doc["reason"])
    return _public(doc)


async def close_shift(db, actor: ActorContext, shift_id: str, params: dict, *, session=None) -> dict:
    shift = await db.pos_shifts.find_one(
        _scope(actor, {"id": shift_id, "status": "open"}), {"_id": 0}, **session_kwargs(session)
    )
    if not shift:
        raise CommercialNotFoundError("Open POS shift not found")
    if actor.role != "owner" and shift.get("cashier_id") != actor.user_id:
        raise CommercialConflictError("This POS shift belongs to another cashier")
    sales = await _all_docs(db.retail_sales.find(
        _scope(actor, {"shift_id": shift_id, "status": "posted"}), {"_id": 0}, **session_kwargs(session)
    ))
    returns = await _all_docs(db.retail_returns.find(
        _scope(actor, {"shift_id": shift_id, "status": "posted"}), {"_id": 0}, **session_kwargs(session)
    ))
    cash_sales = sum(p["amount_paise"] for row in sales for p in row.get("payments") or [] if p.get("mode") == "cash")
    cash_returns = sum(p["amount_paise"] for row in returns for p in row.get("payments") or [] if p.get("mode") == "cash")
    expected = int(shift.get("opening_cash_paise") or 0) + cash_sales - cash_returns
    counted = _paise(params.get("counted_cash"), "counted_cash")
    variance = counted - expected
    if variance and not _clean(params.get("variance_reason")):
        raise CommercialValidationError("variance_reason is required when counted cash differs")
    update = {
        "status": "closed", "expected_cash_paise": expected, "counted_cash_paise": counted,
        "variance_paise": variance, "variance_reason": _clean(params.get("variance_reason")) or None,
        "sales_count": len(sales), "returns_count": len(returns),
        "closed_by": actor.user_id, "closed_at": actor.now_iso(),
    }
    result = await db.pos_shifts.update_one(
        _scope(actor, {"id": shift_id, "status": "open",
                       "activity_version": shift.get("activity_version", {"$exists": False})}),
        {"$set": update}, **session_kwargs(session),
    )
    if result.matched_count == 0:
        raise CommercialConflictError("POS shift was already closed")
    await _audit(db, actor, "pos_shift_close", "pos_shifts", shift_id, update, update["variance_reason"] or "")
    return {**shift, **update}


async def commercial_summary(db, actor: ActorContext, entity_id: Optional[str] = None,
                             *, consolidated: bool = False) -> dict:
    if consolidated:
        entities = [row for row in await list_entities(db, actor) if not row.get("is_group") and row.get("is_active")]
    else:
        entities = [await resolve_entity(db, actor, entity_id)]
    rows = []
    for entity in entities:
        sales = await _all_docs(db.retail_sales.find(
            _scope(actor, entity_record_filter(entity, {"status": "posted"})), {"_id": 0}
        ))
        returns = await _all_docs(db.retail_returns.find(
            _scope(actor, entity_record_filter(entity, {"status": "posted"})), {"_id": 0}
        ))
        opportunities = await _all_docs(db.crm_opportunities.find(
            _scope(actor, entity_record_filter(entity)), {"_id": 0}
        ))
        gross = sum(int(row.get("total_paise") or 0) for row in sales)
        refunds = sum(int(row.get("total_paise") or 0) for row in returns)
        pipeline = sum(round(int(row.get("amount_paise") or 0) * int(row.get("probability") or 0) / 100)
                       for row in opportunities if row.get("stage") not in {"won", "lost"})
        rows.append({"entity_id": entity["id"], "entity_name": entity["name"],
                     "gross_sales_paise": gross, "returns_paise": refunds,
                     "net_sales_paise": gross - refunds, "weighted_pipeline_paise": pipeline})
    return {"consolidated": consolidated, "entities": rows,
            "totals": {"net_sales_paise": sum(row["net_sales_paise"] for row in rows),
                       "weighted_pipeline_paise": sum(row["weighted_pipeline_paise"] for row in rows)}}


# ───────────────────── Deletes (owner instruction, 2026-08-07) ─────────────────
#
# The school's owner asked for delete to be available for every kind of record,
# through Flo as well as the screens. These are the commercial three. Each follows
# the same shape as the deletes that already existed (class, house, discount type):
# hard-delete, blocked when something still points at the record, with the whole
# deleted document written into the audit trail first so it can be reconstructed.


async def delete_legal_entity(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    """Delete a legal entity. Blocked while it owns any commercial record.

    params: ``{entity_id}``  returns: ``{"deleted": True, "entity_id": <id>}``
    """
    kwargs = session_kwargs(session)
    entity_id = _required(params, "entity_id")
    existing = await db.legal_entities.find_one(_scope(actor, {"id": entity_id}), {"_id": 0}, **kwargs)
    if not existing:
        raise CommercialNotFoundError("Legal entity not found")

    # The operating default is what every legacy record without an entity_id is
    # attributed to. Deleting it would orphan the school's own books.
    if existing.get("is_default") or existing.get("owns_legacy_records"):
        raise CommercialConflictError(
            "This is the school's operating entity — make another one the default before deleting it"
        )

    children = await db.legal_entities.count_documents(
        _scope(actor, {"parent_entity_id": entity_id}), **kwargs
    )
    if children:
        raise CommercialConflictError(
            f"Cannot delete an entity with {children} entity/entities reporting to it"
        )

    for collection, label in (
        (db.retail_sales, "sale"),
        (db.enquiries, "enquiry"),
        (db.commercial_products, "product"),
        (db.pos_shifts, "till shift"),
    ):
        used = await collection.count_documents(_scope(actor, {"entity_id": entity_id}), **kwargs)
        if used:
            raise CommercialConflictError(
                f"Cannot delete this entity: {used} {label}(s) are still booked to it"
            )

    await db.legal_entities.delete_one(_scope(actor, {"id": entity_id}), **kwargs)
    await _audit(db, actor, "legal_entity_delete", "legal_entities", entity_id,
                 {"deleted": existing}, reason=_clean(params.get("reason")))
    return {"deleted": True, "entity_id": entity_id}


async def delete_crm_lead(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    """Delete an admission enquiry. Blocked once it has become a real application.

    Releases the phone/email reservation the enquiry held, so the same family can be
    entered again afterwards — without this the contact stays locked forever against
    an enquiry that no longer exists.

    params: ``{enquiry_id}``  returns: ``{"deleted": True, "enquiry_id": <id>}``
    """
    kwargs = session_kwargs(session)
    enquiry_id = _required(params, "enquiry_id")
    existing = await db.enquiries.find_one(_scope(actor, {"id": enquiry_id}), {"_id": 0}, **kwargs)
    if not existing:
        raise CommercialNotFoundError("Enquiry not found")

    if existing.get("student_id") or existing.get("application_id"):
        raise CommercialConflictError(
            "This enquiry has already become an application or an enrolled student — "
            "it cannot be deleted"
        )

    opportunities = await db.crm_opportunities.count_documents(
        _scope(actor, {"enquiry_id": enquiry_id}), **kwargs
    )
    if opportunities:
        raise CommercialConflictError(
            f"Cannot delete an enquiry with {opportunities} open opportunity/opportunities"
        )

    await db.enquiries.delete_one(_scope(actor, {"id": enquiry_id}), **kwargs)
    # Free the contact reservation, and the activity trail that only described it.
    await db.crm_contact_keys.delete_many({"enquiry_id": enquiry_id}, **kwargs)
    await db.crm_activities.delete_many(_scope(actor, {"enquiry_id": enquiry_id}), **kwargs)
    await _audit(db, actor, "crm_lead_delete", "enquiries", enquiry_id,
                 {"deleted": existing}, reason=_clean(params.get("reason")))
    return {"deleted": True, "enquiry_id": enquiry_id}


async def delete_product(db, actor: ActorContext, params: dict, *, session=None) -> dict:
    """Delete a shop product. Blocked once it has ever been sold.

    A product that has been sold is part of the sales record: deleting it would leave
    receipts pointing at nothing. Those are retired with `is_active` instead, which is
    what `update` already does.

    params: ``{product_id}``  returns: ``{"deleted": True, "product_id": <id>}``
    """
    kwargs = session_kwargs(session)
    product_id = _required(params, "product_id")
    existing = await db.commercial_products.find_one(
        _scope(actor, {"id": product_id}), {"_id": 0}, **kwargs
    )
    if not existing:
        raise CommercialNotFoundError("Retail product not found")

    sold = await db.retail_sales.count_documents(
        _scope(actor, {"lines.product_id": product_id}), **kwargs
    )
    if sold:
        raise CommercialConflictError(
            f"Cannot delete a product that appears on {sold} sale(s) — mark it inactive instead"
        )

    await db.commercial_products.delete_one(_scope(actor, {"id": product_id}), **kwargs)
    await _audit(db, actor, "retail_product_delete", "commercial_products", product_id,
                 {"deleted": existing}, reason=_clean(params.get("reason")))
    return {"deleted": True, "product_id": product_id}
