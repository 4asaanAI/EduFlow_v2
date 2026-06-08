"""Fee contact-log service — the single shared write path for logging a fee
contact event (AI Layer Hardening, AD7 / Epic A, Story A.5).

Both `POST /api/fees/contact-log` (REST) and the AI `log_contact_event` tool call
`log_contact_event(...)`. The AI tool's convenience of resolving the fee
transaction (by id, or the student's latest) stays in the AI adapter; the service
writes an identical `fee_contact_logs` record + `contact_log` audit given a
resolved `fee_transaction_id` (canonical = REST: audit entity_type `fee_transaction`,
action `contact_log` — the AI tool previously wrote `fee_transactions`/`log_contact_event`).

Services raise domain exceptions, never `HTTPException`.
"""

from __future__ import annotations

from services.txn_context import session_kwargs as _txn_session_kwargs

import uuid
from typing import Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc

_REQUIRED = ("student_id", "fee_transaction_id", "date", "contact_type", "outcome", "notes")


class ContactLogValidationError(Exception):
    """Missing required fields → HTTP 400."""


def _session_kwargs(session) -> dict:
    # AI Layer Hardening D.2: resolve the AMBIENT transaction session when the
    # caller passes none, so a service invoked inside the plan executor's txn
    # auto-enlists. Outside a txn this is {} (identical to pre-D.2 behavior).
    return _txn_session_kwargs(session)


async def log_contact_event(
    db,
    actor_ctx: ActorContext,
    params: dict,
    *,
    session=None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Write a fee contact-log record + its audit row.

    params: ``{student_id, fee_transaction_id, date, contact_type, outcome, notes}``
    returns: ``{"record": <record without _id>}``
    """
    if any(not params.get(f) for f in _REQUIRED):
        raise ContactLogValidationError(
            "student_id, fee_transaction_id, date, contact_type, outcome, and notes are required"
        )

    record = {
        "_id": str(uuid.uuid4()),
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "student_id": params["student_id"],
        "fee_transaction_id": params["fee_transaction_id"],
        "date": params["date"],
        "contact_type": params["contact_type"],
        "outcome": params["outcome"],
        "notes": params["notes"],
        "created_by": actor_ctx.user_id,
        "created_at": actor_ctx.now_iso(),
    }
    await db.fee_contact_logs.insert_one(record, **_session_kwargs(session))
    public = {k: v for k, v in record.items() if k != "_id"}

    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "fee_transaction",
            "entity_id": params["fee_transaction_id"],
            "action": "contact_log",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"contact": public},
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )
    return {"record": public}
