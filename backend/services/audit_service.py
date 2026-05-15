from __future__ import annotations

import logging
import uuid
from datetime import datetime

from tenant import add_school_id

logger = logging.getLogger(__name__)

AUDIT_FAILURE_ALERT_THRESHOLD = 10
_audit_failure_count = 0


def _normalise_doc(doc: dict, *, school_id: str | None = None, branch_id: str = "") -> dict:
    collection = doc.get("collection") or doc.get("entity_type") or ""
    entity_type = doc.get("entity_type") or collection
    entity_id = doc.get("entity_id") or doc.get("record_id") or ""
    created_at = doc.get("created_at") or doc.get("timestamp") or datetime.now().isoformat()
    normalised = {
        "_id": doc.get("_id") or str(uuid.uuid4()),
        "id": doc.get("id") or str(uuid.uuid4()),
        **doc,
        "entity_type": entity_type,
        "collection": collection,
        "entity_id": entity_id,
        "record_id": doc.get("record_id") or entity_id,
        "branch_id": doc.get("branch_id") if doc.get("branch_id") is not None else branch_id,
        "changes": doc.get("changes") or {},
        "reason": doc.get("reason") or "",
        "created_at": created_at,
        "timestamp": doc.get("timestamp") or created_at,
    }
    return add_school_id(normalised, school_id)


async def write_audit(
    db,
    *,
    action: str,
    entity_id: str,
    collection: str,
    changed_by: str,
    changed_by_role: str,
    school_id: str,
    branch_id: str = "",
    changes: dict | None = None,
    reason: str = "",
) -> bool:
    return await write_audit_doc(
        db,
        {
            "action": action,
            "entity_id": entity_id,
            "collection": collection,
            "entity_type": collection,
            "changed_by": changed_by,
            "changed_by_role": changed_by_role,
            "changes": changes or {},
            "reason": reason or "",
        },
        school_id=school_id,
        branch_id=branch_id or "",
    )


async def write_audit_doc(
    db,
    doc: dict,
    *,
    school_id: str | None = None,
    branch_id: str = "",
) -> bool:
    global _audit_failure_count
    try:
        await db.audit_logs.insert_one(_normalise_doc(doc, school_id=school_id, branch_id=branch_id))
        _audit_failure_count = 0
        return True
    except Exception:
        _audit_failure_count += 1
        extra = {
            "event": "audit_write_failed",
            "action": doc.get("action"),
            "entity_id": doc.get("entity_id") or doc.get("record_id"),
            "persistent_audit_failure": _audit_failure_count > AUDIT_FAILURE_ALERT_THRESHOLD,
        }
        if _audit_failure_count > AUDIT_FAILURE_ALERT_THRESHOLD:
            logger.error("audit_write_failed", extra=extra, exc_info=True)
        else:
            logger.warning("audit_write_failed", extra=extra, exc_info=True)
        return False
