"""Setting and explaining a child's fee concessions - one shared path.

Release 2, finishing plan step 10. Abhimanyu's standing rule: anything that can be done
by hand, Flo must be able to do on request, through the same service, proven by a parity
test. The AI chat is the difference between this platform and an ordinary school ERP, so
a capability that exists only on a screen is only half built.

``concession_service.py`` holds the RULES (what a concession is worth). This holds the
WRITES (which children carry which mark) and the reading that explains one child's fee in
full. Both the REST routes under ``/api/fees/concessions`` and the Flo tools call these
functions, so the two doors cannot drift apart.

--------------------------------------------------------------------------------
What may be set, and what may not
--------------------------------------------------------------------------------

* ``employee_child`` - the child of an employee of the school. 50%.
* ``sibling`` - an elder child in a family. Flat per quarter by band.
* ``admission_discount`` - the one-time amount agreed at admission. **Must name who
  authorised it**, because Aman and Adesh decide these and Sonu applies them. Refused
  outright once an instalment has consumed it, so it can never be handed out twice.
* ``rte_place`` - a government-paid place. Set through ``set_right_to_education`` rather
  than here, because it is not a concession: it decides whether the child owes any school
  fee at all.

Services raise domain exceptions, never ``HTTPException``. The adapters map them.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.concession_service import (
    SIBLING_BY_QUARTERLY_BAND,
    ConcessionRuleError,
    compute_concessions,
    employee_child_amount,
    sibling_amount,
)
from services.fee_lifecycle_service import recompute_open_charges
from services.late_fine_service import LateFineError, assess_quarters
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter


class ConcessionValidationError(Exception):
    """Invalid input → HTTP 400."""


class ConcessionNotFoundError(Exception):
    """No such child in scope → HTTP 404."""


class ConcessionConflictError(Exception):
    """The change would give the same money twice → HTTP 409."""


SETTABLE = {"employee_child", "sibling"}


def _session(session) -> dict:
    return _txn_session_kwargs(session)


async def _load(db, actor_ctx: ActorContext, student_id: str, session=None) -> dict:
    student = await db.students.find_one(
        scoped_filter({"id": student_id}, actor_ctx.school_id), {"_id": 0}, **_session(session)
    )
    if not student:
        raise ConcessionNotFoundError("Student not found")
    return student


async def _audit(db, actor_ctx: ActorContext, *, student_id, action, changes, reason=None):
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "student",
            "entity_id": student_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": changes,
            "reason": reason,
            "created_at": actor_ctx.now().isoformat(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


async def set_concession(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Turn a recurring concession on or off for one child.

    params: ``{student_id, concession, granted}`` where concession is
    ``employee_child`` or ``sibling``.
    """
    student_id = params.get("student_id")
    concession = (params.get("concession") or "").strip()
    if not student_id:
        raise ConcessionValidationError("student_id is required")
    if concession not in SETTABLE:
        raise ConcessionValidationError(
            f"concession must be one of {sorted(SETTABLE)}. The one-time amount agreed at "
            "admission is set with record_admission_concession, and a Right to Education "
            "place is not a concession at all."
        )
    granted = bool(params.get("granted", True))
    student = await _load(db, actor_ctx, student_id, session)
    before = (student.get("concessions") or {}).get(concession)

    await db.students.update_one(
        scoped_filter({"id": student_id}, actor_ctx.school_id),
        {"$set": {f"concessions.{concession}": granted}},
        **_session(session),
    )
    await _audit(db, actor_ctx, student_id=student_id, action="concession_set",
                 changes={concession: {"previous": before, "new": granted}})
    # A concession that does not reach a bill already raised is a concession the family
    # never gets. Bills with money against them are never touched and are reported back.
    reworked = await recompute_open_charges(db, actor_ctx, student_id, session=session)
    return {"student_id": student_id, "concession": concession, "granted": granted,
            "bills_reworked": reworked}


async def record_admission_concession(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Record the one-time amount Aman or Adesh agreed at admission.

    params: ``{student_id, amount, authorised_by, note?}``

    Refused once an instalment has consumed it. A one-time concession that can be
    re-recorded is not one-time.
    """
    student_id = params.get("student_id")
    authorised_by = (params.get("authorised_by") or "").strip()
    if not student_id:
        raise ConcessionValidationError("student_id is required")
    if not authorised_by:
        raise ConcessionValidationError(
            "authorised_by is required: Aman or Adesh decide a one-time concession and "
            "the accountant head applies it, so the record must name who agreed to it."
        )
    try:
        amount = float(params.get("amount"))
    except (TypeError, ValueError):
        raise ConcessionValidationError("amount must be a number")
    if amount <= 0:
        raise ConcessionValidationError("amount must be greater than zero")

    student = await _load(db, actor_ctx, student_id, session)
    existing = (student.get("concessions") or {}).get("admission_discount") or {}
    if existing.get("applied_to"):
        raise ConcessionConflictError(
            f"this child's one-time concession was already used on instalment "
            f"{existing['applied_to']}. It is a once-only amount, so it cannot be "
            "recorded again."
        )

    record = {
        "amount": amount,
        "authorised_by": authorised_by,
        "authorised_on": actor_ctx.now().date().isoformat(),
        "recorded_by": actor_ctx.user_id,
        "note": params.get("note", ""),
    }
    await db.students.update_one(
        scoped_filter({"id": student_id}, actor_ctx.school_id),
        {"$set": {"concessions.admission_discount": record}},
        **_session(session),
    )
    await _audit(db, actor_ctx, student_id=student_id, action="admission_concession_recorded",
                 changes={"admission_discount": {"previous": existing or None, "new": record}},
                 reason=params.get("note"))
    reworked = await recompute_open_charges(db, actor_ctx, student_id, session=session)
    return {"student_id": student_id, "admission_discount": record,
            "bills_reworked": reworked}


async def set_right_to_education(db, actor_ctx: ActorContext, params: dict, *, session=None) -> dict:
    """Mark or unmark a government-paid Right to Education place.

    params: ``{student_id, holds_place, reason}``

    This is not a concession and is not a discount: it decides whether the child owes any
    school fee at all. ``reason`` is required in both directions, because taking the mark
    off starts billing a family the government pays for.
    """
    student_id = params.get("student_id")
    reason = (params.get("reason") or "").strip()
    if not student_id:
        raise ConcessionValidationError("student_id is required")
    if not reason:
        raise ConcessionValidationError(
            "reason is required: this decides whether a family is billed school fees at "
            "all, in both directions."
        )
    holds = bool(params.get("holds_place", True))
    student = await _load(db, actor_ctx, student_id, session)
    before = bool(student.get("rte_place"))

    await db.students.update_one(
        scoped_filter({"id": student_id}, actor_ctx.school_id),
        {"$set": {
            "rte_place": holds,
            "rte_source": f"set by {actor_ctx.user_id}: {reason}",
            "rte_marked_at": actor_ctx.now().isoformat(),
        }},
        **_session(session),
    )
    await _audit(db, actor_ctx, student_id=student_id, action="right_to_education_set",
                 changes={"rte_place": {"previous": before, "new": holds}}, reason=reason)
    reworked = await recompute_open_charges(db, actor_ctx, student_id, session=session)
    return {"student_id": student_id, "holds_place": holds, "reason": reason,
            "bills_reworked": reworked}


async def explain_student_fee(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Everything that decides one child's fee, in one answer.

    params: ``{student_id, as_of?}``

    This is the question the office actually asks: why is this family's bill this figure.
    It answers with the class band, every concession and what each is worth, whether the
    child holds a Right to Education place, who their brothers and sisters are, what they
    have paid, and what they owe in late fines today.
    """
    student = await _load(db, actor_ctx, params.get("student_id"))
    structure = await db.fee_structures.find_one(
        scoped_filter({"class_id": student.get("class_id"), "status": "active"}, actor_ctx.school_id),
        {"_id": 0},
    )
    quarterly = float(structure.get("quarterly_amount") or 0) if structure else 0.0

    holds_rte = bool(student.get("rte_place"))
    concessions: dict[str, Any] = {"lines": [], "total": 0.0, "gross": quarterly, "net": quarterly}
    note: Optional[str] = None
    if holds_rte:
        concessions = {"lines": [], "total": 0.0, "gross": 0.0, "net": 0.0}
        note = ("This child holds a government-paid Right to Education place, so no school "
                "fee applies at all. It is not a discount and there is nothing to reduce. "
                "If they use the bus, the bus is charged and fined normally.")
    elif quarterly:
        try:
            concessions = compute_concessions(
                student, quarterly_amount=quarterly, installment_code=params.get("installment_code", "q1")
            )
        except ConcessionRuleError as exc:
            note = str(exc)

    paid = await db.fee_transactions.find(
        scoped_filter({"student_id": student["id"]}, actor_ctx.school_id),
        {"_id": 0, "fee_head": 1, "fee_period": 1, "paid_amount": 1, "discount_amount": 1,
         "payment_date": 1, "receipt_number": 1},
    ).to_list(500)

    fines = None
    as_of = params.get("as_of")
    if as_of and params.get("outstanding_by_quarter"):
        try:
            fines = assess_quarters(
                params["outstanding_by_quarter"],
                session_start_year=int(params.get("session_start_year") or 2026),
                as_of=as_of,
            )
        except LateFineError as exc:
            fines = {"could_not_be_worked_out": str(exc)}

    return {
        "student": {
            "id": student["id"],
            "name": student.get("name"),
            "admission_number": student.get("admission_number"),
            "class_id": student.get("class_id"),
            "stream": student.get("stream"),
        },
        "band": {
            "quarterly_amount": quarterly,
            "annual_amount": quarterly * 4,
            "structure_name": structure.get("name") if structure else None,
            "from": "the class's fee structure" if structure else
                    "no fee structure is loaded for this child's class",
        },
        "right_to_education": holds_rte,
        "concessions": concessions,
        "what_each_concession_is_worth": {
            "sibling": (sibling_amount(quarterly)
                        if quarterly in SIBLING_BY_QUARTERLY_BAND else None),
            "employee_child": employee_child_amount(quarterly) if quarterly else None,
        },
        "siblings": student.get("siblings") or [],
        "transport": {
            "uses_the_bus": bool(student.get("uses_transport")),
            "monthly_fare": student.get("transport_monthly_fare"),
            "route": student.get("bus_route"),
            "note": "Transport carries no concession of any kind, and is billed for "
                    "eleven months: June is not charged.",
        },
        "payments": paid,
        "total_paid": sum(float(row.get("paid_amount") or 0) for row in paid),
        "late_fines": fines,
        "note": note,
    }
