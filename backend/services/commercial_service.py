from __future__ import annotations

"""Admissions CRM and legal-entity domain rules.

Money is stored in integer paise, posted documents are immutable, and every write is
scoped to the current school, branch, and operating legal entity.

**Campus retail was removed on 2026-08-14, on Abhimanyu's instruction.** The till, the
product catalogue, the cashier shifts, the sales and the returns described a shop that
The Aaryans does not run. The school does have a canteen, but it is an outside vendor
renting space on the premises and running its own business, so the school's interest in
it is rent from a tenant, not a counter of its own to operate.

The rule that decided it, and that governs anything else found in here: **this platform
carries what The Aaryans actually needs, not what a general-purpose school ERP ships
with.** A screen for a business the school does not run is not neutral. It is a menu
entry people have to learn to ignore, and a surface somebody may one day type real
numbers into.

The rows the shop wrote were NOT deleted. Removing a feature must never remove a
school's records; see the guard in `delete_legal_entity`.
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


async def commercial_summary(db, actor: ActorContext, entity_id: Optional[str] = None,
                             *, consolidated: bool = False) -> dict:
    if consolidated:
        entities = [row for row in await list_entities(db, actor) if not row.get("is_group") and row.get("is_active")]
    else:
        entities = [await resolve_entity(db, actor, entity_id)]
    rows = []
    for entity in entities:
        # The shop sales and returns that used to be totalled here are gone with the
        # campus-retail removal of 2026-08-14: The Aaryans runs no shop, and the canteen
        # is an outside vendor renting space rather than a school business.
        opportunities = await _all_docs(db.crm_opportunities.find(
            _scope(actor, entity_record_filter(entity)), {"_id": 0}
        ))
        pipeline = sum(round(int(row.get("amount_paise") or 0) * int(row.get("probability") or 0) / 100)
                       for row in opportunities if row.get("stage") not in {"won", "lost"})
        rows.append({"entity_id": entity["id"], "entity_name": entity["name"],
                     "weighted_pipeline_paise": pipeline})
    return {"consolidated": consolidated, "entities": rows,
            "totals": {"weighted_pipeline_paise": sum(row["weighted_pipeline_paise"] for row in rows)}}


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
            "This is the school's operating entity - make another one the default before deleting it"
        )

    children = await db.legal_entities.count_documents(
        _scope(actor, {"parent_entity_id": entity_id}), **kwargs
    )
    if children:
        raise CommercialConflictError(
            f"Cannot delete an entity with {children} entity/entities reporting to it"
        )

    # The three shop collections are still checked here even though the campus-retail
    # feature was removed on 2026-08-14. The FEATURE is gone; whatever rows it wrote
    # before then are NOT, because removing a screen must never delete a school's
    # records. If any survive, an entity holding them still refuses to be deleted rather
    # than orphaning them. On a school that never used the shop these count zero and the
    # check costs nothing.
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
    entered again afterwards - without this the contact stays locked forever against
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
            "This enquiry has already become an application or an enrolled student - "
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
