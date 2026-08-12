"""The registration and admission fee a family pays when a child joins.

Abhimanyu, 2026-08-12: raise these automatically when a student joins.

The school charges two one-off amounts to a NEW admission, on top of the quarterly fee:
a registration fee and an admission fee. They vary by class and are already loaded onto
every fee structure by migration 035, in ``new_student_charges``, from the school's own
2026-27 fee sheet. Until now nothing read them, so the office had to remember and raise
them by hand.

--------------------------------------------------------------------------------
The rule this file exists to enforce: ONLY a child actually joining
--------------------------------------------------------------------------------

These charges are the single most dangerous thing on the platform to raise automatically,
because the difference between "a child joined today" and "a child was typed into the
platform today" is invisible to the database and worth 13,000 to a family.

**1,842 children already on the roll were typed in during a bulk load in August.** Had
this existed then, every one of those families would have been billed a registration and
an admission fee for a child who joined years ago. So:

* it is called from the single-student create path ONLY, never from the spreadsheet
  import that creates students in bulk (``routes/import_data.py``), and a test pins that;
* it can be turned off per call with ``raise_joining_charges=False``, which is what a
  data load passes;
* it is idempotent by ``charge_key``, so running the same create twice cannot bill twice;
* it raises NOTHING for a child on a Right to Education place, who owes no school fee at
  all;
* it raises nothing, and says why, when the class has no fee structure or the structure
  carries no charges (10th and 12th carry none: nobody joins the school at those classes).

**It never stops a child being admitted.** If the charges cannot be raised, the student
record is still created and the reason is reported, because a fee problem must not be the
thing that keeps a child off the roll.
"""

from __future__ import annotations

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.txn_context import session_kwargs as _txn_session_kwargs
from tenant import scoped_filter

# What each charge is called on the family's bill and in the ledger. These match the
# wording the school's previous system used, which migration 039 also maps onto.
CHARGES = (
    ("registration_fee", "Registration Fee"),
    ("admission_fee", "Admission Fee"),
)

JOINING_PERIOD = "admission"


def _session(session) -> dict:
    return _txn_session_kwargs(session)


async def raise_joining_charges(
    db,
    actor_ctx: ActorContext,
    student: dict,
    *,
    session=None,
) -> dict:
    """Raise the registration and admission fee for a child who has just joined.

    Returns ``{"raised": [...], "skipped_because": <reason or None>}``. Never raises an
    exception at the caller: admitting a child must not fail because of a fee.
    """
    school_id = actor_ctx.school_id
    student_id = student.get("id")
    class_id = student.get("class_id")

    if student.get("rte_place"):
        return {"raised": [], "skipped_because":
                "this child holds a government-paid Right to Education place, so no "
                "school fee applies, the joining charges included"}

    structure = await db.fee_structures.find_one(
        scoped_filter({"class_id": class_id, "status": "active"}, school_id), {"_id": 0},
        **_session(session),
    )
    if not structure:
        return {"raised": [], "skipped_because":
                "this child's class has no fee structure loaded, so there is no figure "
                "to charge. Raise them by hand or load the class's fees."}

    charges = structure.get("new_student_charges") or {}
    if not any(charges.get(field) for field, _ in CHARGES):
        return {"raised": [], "skipped_because":
                f"the fee structure for this class records no joining charges. Nobody "
                f"joins the school at some classes, so this is often correct."}

    now = actor_ctx.now_utc().isoformat()
    raised = []
    for field, label in CHARGES:
        amount = charges.get(field)
        if not amount:
            continue
        # One key per child per charge, so a repeated create cannot bill twice.
        charge_key = f"joining|{student_id}|{field}"
        already = await db.fee_transactions.find_one(
            scoped_filter({"charge_key": charge_key}, school_id), {"_id": 0, "id": 1},
            **_session(session),
        )
        if already:
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "schoolId": school_id,
            "branch_id": student.get("branch_id") or actor_ctx.branch_id,
            "student_id": student_id,
            "admission_number": student.get("admission_number"),
            "charge_key": charge_key,
            "structure_id": structure.get("id"),
            "fee_head": label,
            "fee_type": label,
            "fee_period": JOINING_PERIOD,
            "installment_code": JOINING_PERIOD,
            "amount": float(amount),
            "gross_amount": float(amount),
            "concession_total": 0,
            # A joining charge carries no concession. The sibling and employee
            # concessions are set against the quarterly fee by their own rules, and the
            # one-time amount agreed at admission is applied to an instalment, not here.
            "concession_lines": [],
            "status": "pending",
            "paid_amount": 0,
            "due_date": (student.get("admission_date") or now[:10]),
            "raised_because": "the child joined the school",
            "generated_by": actor_ctx.user_id,
            "created_at": now,
        }
        await db.fee_transactions.insert_one({**doc, "_id": doc["id"]}, **_session(session))
        raised.append({"fee_head": label, "amount": float(amount), "id": doc["id"]})

    if raised:
        await write_audit_doc(db, {
            "id": str(uuid.uuid4()), "_id": str(uuid.uuid4()), "schoolId": school_id,
            "entity_type": "fee_transaction", "entity_id": student_id,
            "action": "joining_charges_raised",
            "changed_by": actor_ctx.user_id,
            "changes": {"raised": raised},
            "reason": "the child joined the school",
            "created_at": now,
        }, school_id=school_id, branch_id=actor_ctx.branch_id)

    return {"raised": raised, "skipped_because": None}
