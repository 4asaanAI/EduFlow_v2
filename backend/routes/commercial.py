from __future__ import annotations

"""Enterprise school CRM, campus retail, and legal-entity APIs."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError

from database import TransactionUnavailableError, get_db, get_txn_session
from middleware.auth import require_owner, require_owner_or_admin_subcategories
from services.actor_context import actor_ctx_from_user
from services.commercial_service import (
    CommercialConflictError,
    CommercialNotFoundError,
    CommercialValidationError,
    add_crm_activity,
    close_shift,
    commercial_summary,
    create_crm_lead,
    create_entity,
    create_opportunity,
    create_product,
    create_return,
    create_sale,
    crm_pipeline,
    delete_crm_lead,
    delete_legal_entity,
    delete_product,
    entity_record_filter,
    list_entities,
    open_shift,
    replay_retail_request,
    resolve_entity,
    set_default_entity,
    update_crm_lead,
    update_opportunity,
)
from school_identity import default_branch_id
from services.enquiry_service import EnquiryConflictError, EnquiryNotFoundError, EnquiryValidationError
from services.txn_context import reset_current_session, set_current_session
from tenant import get_school_id, scoped_query


router = APIRouter(prefix="/api/commercial", tags=["commercial-operations"])

require_entity_viewer = require_owner_or_admin_subcategories("principal", "accountant", "receptionist")
require_commercial_reporter = require_owner_or_admin_subcategories("principal", "accountant")
require_admissions_operator = require_owner_or_admin_subcategories("principal", "admission", "receptionist")
require_opportunity_editor = require_owner_or_admin_subcategories("principal", "admission")
require_retail_operator = require_owner_or_admin_subcategories("principal", "accountant", "receptionist")
require_retail_configurator = require_owner_or_admin_subcategories("principal", "accountant")


def _actor(user: dict):
    # This deployment intentionally serves one branch. School-level owner tokens
    # may omit branch_id, but commercial postings must never persist unscoped.
    # The fallback lives in school_identity so there is one line to change when a
    # second branch is onboarded (audit A-4, 2026-08-05).
    return actor_ctx_from_user(
        user, school_id=get_school_id(), branch_id=user.get("branch_id") or default_branch_id()
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, (CommercialNotFoundError, EnquiryNotFoundError)):
        return HTTPException(404, str(exc))
    if isinstance(exc, (CommercialConflictError, EnquiryConflictError)):
        return HTTPException(409, str(exc))
    if isinstance(exc, TransactionUnavailableError):
        return HTTPException(503, str(exc))
    return HTTPException(400, str(exc))


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(400, "Request body must be an object")
    return body


@router.get("/entities")
async def get_entities(request: Request, user: dict = Depends(require_entity_viewer)):
    rows = await list_entities(get_db(), _actor(user))
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/entities")
async def post_entity(request: Request, user: dict = Depends(require_commercial_reporter)):
    try:
        row = await _transactional_call(user, create_entity, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/entities/{entity_id}/default")
async def patch_default_entity(entity_id: str, request: Request, user: dict = Depends(require_commercial_reporter)):
    try:
        row = await _transactional_call(user, set_default_entity, entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.delete("/entities/{entity_id}")
async def delete_entity(entity_id: str, request: Request, user: dict = Depends(require_commercial_reporter)):
    """Delete a legal entity. Owner only, and refused while anything is booked to it.

    Owner instruction 2026-08-07 - parity reference for the AI `delete_legal_entity`
    tool, which calls the same service.
    """
    try:
        row = await _transactional_call(user, delete_legal_entity, {"entity_id": entity_id})
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/summary")
async def get_summary(request: Request, entity_id: str | None = None, consolidated: bool = False,
                      user: dict = Depends(require_commercial_reporter)):
    if consolidated and not (
        user.get("role") == "owner"
        or (user.get("role") == "admin" and user.get("sub_category") == "principal")
    ):
        raise HTTPException(403, "Only the school owner or principal can view consolidated entity reporting")
    try:
        data = await commercial_summary(get_db(), _actor(user), entity_id, consolidated=consolidated)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    return {"success": True, "data": data}


@router.get("/crm/leads")
async def get_crm_leads(request: Request, entity_id: str | None = None, status: str | None = None,
                        user: dict = Depends(require_admissions_operator)):
    db, actor = get_db(), _actor(user)
    try:
        entity = await resolve_entity(db, actor, entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    query = entity_record_filter(entity, {"status": status} if status else {})
    rows = await db.enquiries.find(scoped_query(query, branch_id=user.get("branch_id")), {"_id": 0}).sort(
        "created_at", -1
    ).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/crm/leads")
async def post_crm_lead(request: Request, user: dict = Depends(require_admissions_operator)):
    try:
        row = await _transactional_call(user, create_crm_lead, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            EnquiryValidationError, EnquiryConflictError, EnquiryNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/crm/leads/{enquiry_id}")
async def patch_crm_lead(enquiry_id: str, request: Request,
                         user: dict = Depends(require_admissions_operator)):
    try:
        row = await _transactional_call(user, update_crm_lead, enquiry_id, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            EnquiryValidationError, EnquiryConflictError, EnquiryNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.delete("/crm/leads/{enquiry_id}")
async def delete_lead(enquiry_id: str, request: Request, user: dict = Depends(require_admissions_operator)):
    """Delete an admission enquiry entered in error.

    Owner instruction 2026-08-07 - parity reference for the AI `delete_enquiry` tool.
    Refused once the enquiry has become an application or an enrolled student.
    """
    try:
        row = await _transactional_call(user, delete_crm_lead, {"enquiry_id": enquiry_id})
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/crm/leads/{enquiry_id}/activities")
async def get_crm_activities(enquiry_id: str, request: Request,
                             user: dict = Depends(require_admissions_operator)):
    rows = await get_db().crm_activities.find(
        scoped_query({"enquiry_id": enquiry_id}, branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("occurred_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/crm/leads/{enquiry_id}/activities")
async def post_crm_activity(enquiry_id: str, request: Request,
                            user: dict = Depends(require_admissions_operator)):
    try:
        row = await _transactional_call(user, add_crm_activity, enquiry_id, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.post("/crm/leads/{enquiry_id}/opportunities")
async def post_crm_opportunity(enquiry_id: str, request: Request,
                               user: dict = Depends(require_opportunity_editor)):
    try:
        row = await _transactional_call(user, create_opportunity, enquiry_id, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/crm/opportunities")
async def get_crm_opportunities(request: Request, entity_id: str | None = None,
                                enquiry_id: str | None = None,
                                user: dict = Depends(require_admissions_operator)):
    db, actor = get_db(), _actor(user)
    try:
        entity = await resolve_entity(db, actor, entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    base = {"enquiry_id": enquiry_id} if enquiry_id else {}
    rows = await db.crm_opportunities.find(
        scoped_query(entity_record_filter(entity, base), branch_id=actor.branch_id), {"_id": 0}
    ).sort("updated_at", -1).to_list(2000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.patch("/crm/opportunities/{opportunity_id}")
async def patch_crm_opportunity(opportunity_id: str, request: Request,
                                user: dict = Depends(require_opportunity_editor)):
    try:
        # Audit A-3 (2026-08-05): this was the one write in the file that ran outside
        # a transaction, so a stage change that also wrote an audit row could half-land.
        row = await _transactional_call(user, update_opportunity, opportunity_id, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/crm/pipeline")
async def get_crm_pipeline(request: Request, entity_id: str | None = None,
                           user: dict = Depends(require_admissions_operator)):
    try:
        data = await crm_pipeline(get_db(), _actor(user), entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    return {"success": True, "data": data}


@router.get("/products")
async def get_products(request: Request, entity_id: str | None = None,
                       user: dict = Depends(require_retail_operator)):
    db, actor = get_db(), _actor(user)
    try:
        entity = await resolve_entity(db, actor, entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    rows = await db.commercial_products.find(
        scoped_query(entity_record_filter(entity, {"is_active": True}), branch_id=user.get("branch_id")),
        {"_id": 0},
    ).sort("name", 1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/products")
async def post_product(request: Request, user: dict = Depends(require_retail_configurator)):
    try:
        row = await _transactional_call(user, create_product, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.delete("/products/{product_id}")
async def delete_retail_product(product_id: str, request: Request,
                                user: dict = Depends(require_retail_configurator)):
    """Delete a shop product. Refused once it appears on any sale.

    Owner instruction 2026-08-07 - parity reference for the AI `delete_retail_product`
    tool.
    """
    try:
        row = await _transactional_call(user, delete_product, {"product_id": product_id})
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/pos/shifts")
async def get_shifts(request: Request, entity_id: str | None = None, status: str | None = None,
                     user: dict = Depends(require_retail_operator)):
    db, actor = get_db(), _actor(user)
    try:
        entity = await resolve_entity(db, actor, entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    base = {"status": status} if status else {}
    rows = await db.pos_shifts.find(
        scoped_query(entity_record_filter(entity, base), branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("opened_at", -1).to_list(1000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


@router.post("/pos/shifts")
async def post_shift(request: Request, user: dict = Depends(require_retail_operator)):
    try:
        row = await open_shift(get_db(), _actor(user), await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.patch("/pos/shifts/{shift_id}/close")
async def patch_shift_close(shift_id: str, request: Request,
                            user: dict = Depends(require_retail_operator)):
    try:
        row = await _transactional_call(user, close_shift, shift_id, await _body(request))
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.get("/pos/sales")
async def get_sales(request: Request, entity_id: str | None = None, shift_id: str | None = None,
                    user: dict = Depends(require_retail_operator)):
    db, actor = get_db(), _actor(user)
    try:
        entity = await resolve_entity(db, actor, entity_id)
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError) as exc:
        raise _error(exc)
    base = {"shift_id": shift_id} if shift_id else {}
    rows = await db.retail_sales.find(
        scoped_query(entity_record_filter(entity, base), branch_id=user.get("branch_id")), {"_id": 0}
    ).sort("created_at", -1).to_list(2000)
    return {"success": True, "data": rows, "meta": {"count": len(rows)}}


async def _transactional_call(user: dict, operation, *args, **kwargs):
    db, actor = get_db(), _actor(user)
    session = await get_txn_session()
    token = set_current_session(session)
    try:
        async with session:
            async with session.start_transaction():
                return await operation(db, actor, *args, session=session, **kwargs)
    finally:
        reset_current_session(token)


async def _transactional_sale(user: dict, body: dict, key: str, *, sale_id: str | None = None):
    try:
        if sale_id:
            return await _transactional_call(
                user, create_return, sale_id, body, idempotency_key=key
            )
        return await _transactional_call(user, create_sale, body, idempotency_key=key)
    except DuplicateKeyError:
        return await replay_retail_request(
            get_db(), _actor(user), key, body, sale_id=sale_id
        )


@router.post("/pos/sales")
async def post_sale(request: Request, user: dict = Depends(require_retail_operator)):
    try:
        row = await _transactional_sale(user, await _body(request), request.headers.get("Idempotency-Key") or "")
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}


@router.post("/pos/sales/{sale_id}/returns")
async def post_return(sale_id: str, request: Request,
                      user: dict = Depends(require_retail_operator)):
    try:
        row = await _transactional_sale(
            user, await _body(request), request.headers.get("Idempotency-Key") or "", sale_id=sale_id
        )
    except (CommercialValidationError, CommercialConflictError, CommercialNotFoundError,
            TransactionUnavailableError) as exc:
        raise _error(exc)
    return {"success": True, "data": row}
