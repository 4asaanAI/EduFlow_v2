"""Certificate domain service - single shared write path (AD7).

Both the REST routes (`POST /api/ops/certificates`, `PATCH .../approve`,
`PATCH .../reject`) and the AI tools call these functions: same
requires-approval rule (bonafide/tc/transfer/character/merit), same
owner-or-principal auto-issue, same state guards and notifications.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from services.certificate_types import (
    APPROVAL_REQUIRED_TYPES,
    ID_CARD_TYPE,
    canonical_type,
    document_label,
    requires_approval,
)
from services.notification_service import create_notification, fan_out_notifications
from tenant import scoped_query

# R2-9, 2026-08-10: this set used to be spelled out here and disagreed with the printer
# and with Flo's tool schema, so a Transfer Certificate raised from the screen (stored as
# `transfer`) matched nothing and was auto-issued to anybody. `services/certificate_types`
# is now the one place that decides. Re-exported here because callers and tests import it
# from this module.
__all__ = [
    "APPROVAL_REQUIRED_TYPES",
    "CertificateValidationError",
    "CertificateNotFoundError",
    "CertificateStateError",
    "create_certificate",
    "create_id_card_request",
    "approve_certificate",
    "reject_certificate",
    "delete_certificate",
    "is_approved_for_printing",
]


class CertificateValidationError(Exception):
    """Invalid input → HTTP 400."""


class CertificateNotFoundError(Exception):
    """Unknown certificate id within the caller's scope → HTTP 404."""


class CertificateStateError(Exception):
    """Certificate not in pending_approval state → HTTP 422."""


def _is_owner_or_principal(actor_ctx: ActorContext) -> bool:
    return actor_ctx.role == "owner" or (
        actor_ctx.role == "admin" and actor_ctx.sub_category == "principal"
    )


async def create_certificate(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Create a certificate request. params: {student_id, cert_type?, content_data?}"""
    if not params.get("student_id"):
        raise CertificateValidationError("student_id is required")
    # R2-9: store the CANONICAL name. Whatever the caller said - `transfer`, `tc`,
    # `Transfer Certificate` - one word reaches the database, so the approval rule and
    # the printer are asking about the same document.
    cert_type = canonical_type(params.get("cert_type") or params.get("type") or "bonafide")
    needs_approval = requires_approval(cert_type)
    approved_actor = _is_owner_or_principal(actor_ctx)
    auto_issue = approved_actor or not needs_approval
    now = actor_ctx.now()
    cert = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        "student_id": params.get("student_id"),
        "cert_type": cert_type,
        "serial_number": f"CERT{now.strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}",
        "content_data": params.get("content_data", {}),
        "status": "generated" if auto_issue else "pending_approval",
        "issued_date": now.strftime("%Y-%m-%d") if auto_issue else None,
        "issued_by": actor_ctx.user_id if auto_issue else None,
        "requested_by": actor_ctx.user_id,
        "created_at": now.isoformat(),
    }
    await db.certificates.insert_one({**cert, "_id": cert["id"]})
    if cert["status"] == "pending_approval":
        await _notify_approvers(db, actor_ctx, cert["id"], document_label(cert_type))
    return {"certificate": cert}


async def _notify_approvers(db, actor_ctx: ActorContext, cert_id: str, label: str) -> None:
    """Tell the two people who may approve that something is waiting.

    R2-9: this used to look for principals only, so the school's OWNER - who may approve
    and who the school's hierarchy puts above the principal - was never told. Both are
    asked now. The approve and reject routes already admitted both; only the tap on the
    shoulder was missing.
    """
    approvers = await db.users.find(
        scoped_query(
            {
                "$or": [
                    {"role": "owner"},
                    {"role": "admin", "sub_category": "principal"},
                ],
                "is_active": {"$ne": False},
            },
            branch_id=actor_ctx.branch_id,
        ),
        {"_id": 0, "id": 1},
    ).to_list(20)
    await fan_out_notifications(
        db,
        [a["id"] for a in approvers if a.get("id")],
        notification_type="certificate_approval_requested",
        title="Approval required",
        message=f"{label} is waiting for approval.",
        source_id=cert_id,
        source_type="certificate",
    )


async def create_id_card_request(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Ask for a batch of student ID cards to be approved. params: {student_ids}

    Decision 6 of 2026-08-10 puts ID cards under the same rule as certificates: the
    owner and the principal print them directly, everybody else asks first. There is no
    second approval queue - the request is a row in `certificates` with the canonical
    type `id_card`, so `approve_certificate` and `reject_certificate` govern it
    unchanged and the school has one list to look at.

    A batch is ONE request, not one per child. A class of forty would otherwise put
    forty rows in front of the principal, which is how an approval step turns into a
    rubber stamp.
    """
    raw_ids = params.get("student_ids") or []
    student_ids = [str(s).strip() for s in raw_ids if str(s or "").strip()]
    # Same order, no duplicates.
    student_ids = list(dict.fromkeys(student_ids))
    if not student_ids:
        raise CertificateValidationError("student_ids is required")

    auto_issue = _is_owner_or_principal(actor_ctx)
    now = actor_ctx.now()
    cert = {
        "id": str(uuid.uuid4()),
        "schoolId": actor_ctx.school_id,
        # An ID-card batch has no single child, so `student_id` stays empty and the
        # list lives in `student_ids`. The certificate list screen resolves a name from
        # `student_id` and shows "N/A" when there is none, which is honest for a batch.
        "student_id": None,
        "student_ids": student_ids,
        "cert_type": ID_CARD_TYPE,
        "serial_number": f"IDC{now.strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}",
        "content_data": {"student_count": len(student_ids)},
        "status": "generated" if auto_issue else "pending_approval",
        "issued_date": now.strftime("%Y-%m-%d") if auto_issue else None,
        "issued_by": actor_ctx.user_id if auto_issue else None,
        "requested_by": actor_ctx.user_id,
        "created_at": now.isoformat(),
    }
    await db.certificates.insert_one({**cert, "_id": cert["id"]})
    if cert["status"] == "pending_approval":
        await _notify_approvers(
            db,
            actor_ctx,
            cert["id"],
            f"{document_label(ID_CARD_TYPE)} for {len(student_ids)} student(s)",
        )
    return {"certificate": cert}


async def is_approved_for_printing(db, actor_ctx: ActorContext, cert_id: str) -> dict:
    """The approved request behind a print, or raise.

    Returns the certificate record when it exists in the caller's scope and has been
    approved. `generated` is what an approved record's status is called - the field
    records that the document now exists, and `approve_certificate` is what sets it.

    Raises `CertificateNotFoundError` if there is no such record here, and
    `CertificateStateError` if it is still waiting or was refused.
    """
    if not cert_id:
        raise CertificateValidationError("cert_id is required")
    cert = await db.certificates.find_one(
        scoped_query({"id": cert_id}, branch_id=actor_ctx.branch_id), {"_id": 0}
    )
    if not cert:
        raise CertificateNotFoundError(cert_id)
    status = cert.get("status")
    if status == "pending_approval":
        raise CertificateStateError(
            "This document is still waiting for the school's owner or principal to "
            "approve it. It cannot be printed yet."
        )
    if status != "generated":
        raise CertificateStateError(
            f"This document was not approved (it is marked '{status}'), so it cannot be printed."
        )
    return cert


async def approve_certificate(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Approve a pending certificate. params: {cert_id}"""
    cert_id = params.get("cert_id")
    if not cert_id:
        raise CertificateValidationError("cert_id is required")
    bid = actor_ctx.branch_id
    cert = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    if not cert:
        raise CertificateNotFoundError(cert_id)
    if cert.get("status") != "pending_approval":
        raise CertificateStateError("Certificate is not in pending_approval state")
    now = actor_ctx.now()
    update = {
        "status": "generated",
        "issued_date": now.strftime("%Y-%m-%d"),
        "issued_by": actor_ctx.user_id,
        "approved_by": actor_ctx.user_id,
        "approved_at": now.isoformat(),
    }
    await db.certificates.update_one(scoped_query({"id": cert_id}, branch_id=bid), {"$set": update})
    if cert.get("requested_by"):
        await create_notification(
            db,
            user_id=cert["requested_by"],
            notification_type="certificate_approved",
            title="Certificate approved",
            message=f"{cert.get('cert_type', 'Certificate')} approved.",
            source_id=cert_id,
            source_type="certificate",
        )
    updated = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    return {"certificate": updated}


async def reject_certificate(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Reject a pending certificate. params: {cert_id, reason}"""
    cert_id = params.get("cert_id")
    if not cert_id:
        raise CertificateValidationError("cert_id is required")
    reason = (params.get("reason") or "").strip()
    if not reason:
        raise CertificateValidationError("reason is required")
    bid = actor_ctx.branch_id
    cert = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    if not cert:
        raise CertificateNotFoundError(cert_id)
    if cert.get("status") != "pending_approval":
        raise CertificateStateError("Certificate is not in pending_approval state")
    update = {
        "status": "rejected",
        "rejected_by": actor_ctx.user_id,
        "rejected_at": actor_ctx.now_iso(),
        "rejection_reason": reason,
    }
    await db.certificates.update_one(scoped_query({"id": cert_id}, branch_id=bid), {"$set": update})
    if cert.get("requested_by"):
        await create_notification(
            db,
            user_id=cert["requested_by"],
            notification_type="certificate_rejected",
            title="Certificate rejected",
            message=reason,
            source_id=cert_id,
            source_type="certificate",
        )
    updated = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    return {"certificate": updated}


async def delete_certificate(db, actor_ctx: ActorContext, params: dict) -> dict:
    """Delete a certificate record. Owner or principal only.

    Owner instruction 2026-08-07 - a certificate raised in error (wrong pupil, wrong
    type, a duplicate request) could be rejected but never removed.

    A certificate that has been **issued** is a document the family may be holding in
    their hand: the serial number on that paper has to keep meaning something, so
    issued certificates cannot be deleted. Requested and rejected ones can.

    params: ``{cert_id}``
    returns: ``{"deleted": True, "cert_id": <id>, "serial_number": <serial>}``
    """
    cert_id = params.get("cert_id")
    if not cert_id:
        raise CertificateValidationError("cert_id is required")
    if not _is_owner_or_principal(actor_ctx):
        raise CertificateStateError("Only the school's owner or principal may delete a certificate")
    bid = actor_ctx.branch_id
    cert = await db.certificates.find_one(scoped_query({"id": cert_id}, branch_id=bid), {"_id": 0})
    if not cert:
        raise CertificateNotFoundError(cert_id)
    if cert.get("status") == "generated":
        raise CertificateStateError(
            "This certificate has already been issued and may be in the family's hands - "
            "it cannot be deleted"
        )
    await db.certificates.delete_one(scoped_query({"id": cert_id}, branch_id=bid))
    await write_audit_doc(
        db,
        {
            "id": str(uuid.uuid4()),
            "entity_type": "certificate",
            "collection": "certificates",
            "entity_id": cert_id,
            "action": "certificate_delete",
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": {"deleted": cert},
            "reason": params.get("reason"),
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=bid or "",
    )
    return {"deleted": True, "cert_id": cert_id, "serial_number": cert.get("serial_number")}
