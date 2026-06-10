"""Certificate domain service — single shared write path (AD7).

Both the REST routes (`POST /api/ops/certificates`, `PATCH .../approve`,
`PATCH .../reject`) and the AI tools call these functions: same
requires-approval rule (bonafide/tc/transfer/character/merit), same
owner-or-principal auto-issue, same state guards and notifications.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import uuid

from services.actor_context import ActorContext
from services.notification_service import create_notification, fan_out_notifications
from tenant import scoped_query

APPROVAL_REQUIRED_TYPES = {"bonafide", "tc", "transfer_certificate", "character", "merit"}


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
    cert_type = params.get("cert_type") or params.get("type", "bonafide")
    requires_approval = cert_type in APPROVAL_REQUIRED_TYPES
    approved_actor = _is_owner_or_principal(actor_ctx)
    auto_issue = approved_actor or not requires_approval
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
        principals = await db.users.find(
            scoped_query({"role": "admin", "sub_category": "principal", "is_active": {"$ne": False}},
                         branch_id=actor_ctx.branch_id),
            {"_id": 0, "id": 1},
        ).to_list(20)
        await fan_out_notifications(
            db,
            [p["id"] for p in principals if p.get("id")],
            notification_type="certificate_approval_requested",
            title="Certificate approval required",
            message=f"{cert_type.replace('_', ' ').title()} certificate is waiting for approval.",
            source_id=cert["id"],
            source_type="certificate",
        )
    return {"certificate": cert}


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
