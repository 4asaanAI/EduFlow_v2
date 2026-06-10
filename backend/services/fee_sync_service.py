"""Fee-sync domain service — single shared write path for triggering an
external fee synchronization job (AI Layer Hardening, AD7).

Both `POST /api/fees/sync/trigger` (REST) and the AI `trigger_fee_sync` tool
call `trigger_sync(...)`: same in-progress idempotency guard, same hung-job
auto-expiry, same conflict detection, same audit + SSE events.

The external fetch is injected (`fetch_fn`) so the route keeps its existing
`_fetch_external_fee_records` behavior and tests can stub it.

Services raise domain exceptions, never `HTTPException`. The adapters map them.
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta
from typing import Awaitable, Callable, Optional

from services.actor_context import ActorContext
from services.audit_service import write_audit_doc
from tenant import scoped_filter, scoped_query

SYNC_JOB_TIMEOUT_MINUTES = int(os.environ.get("SYNC_JOB_TIMEOUT_MINUTES", "30"))


class FeeSyncUpstreamError(Exception):
    """The external fee API failed — job is marked failed; carries the detail."""


def _external_key(record: dict):
    return (
        record.get("student_id"),
        record.get("fee_period") or record.get("period"),
        record.get("fee_head") or record.get("fee_type"),
    )


async def _audit(db, actor_ctx: ActorContext, *, action: str, entity_id: str, changes: dict) -> None:
    await write_audit_doc(
        db,
        {
            "_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "schoolId": actor_ctx.school_id,
            "entity_type": "fee_sync_job",
            "entity_id": entity_id,
            "action": action,
            "changed_by": actor_ctx.user_id,
            "changed_by_role": actor_ctx.role,
            "changes": changes,
            "reason": None,
            "created_at": actor_ctx.now_iso(),
        },
        school_id=actor_ctx.school_id,
        branch_id=actor_ctx.branch_id,
    )


async def trigger_sync(
    db,
    actor_ctx: ActorContext,
    *,
    fetch_fn: Callable[[], Awaitable[list]],
    publish_fn: Optional[Callable[..., Awaitable]] = None,
) -> dict:
    """Run a fee sync job. Returns {"job": <job-or-result dict>, "already_running": bool}.

    Raises FeeSyncUpstreamError if the upstream HTTP call raised an HTTPException-like
    error the route wants to re-raise (detail preserved); plain failures are recorded
    on the job and returned as status="failed".
    """
    school_id = actor_ctx.school_id
    bid = actor_ctx.branch_id
    now = actor_ctx.now_utc()
    timeout_cutoff = (now - timedelta(minutes=SYNC_JOB_TIMEOUT_MINUTES)).isoformat()

    # EC-10.1: one in-progress job at a time (idempotency); auto-expire hung jobs.
    existing_job = await db.fee_sync_jobs.find_one(
        scoped_query({"status": "in_progress"}, branch_id=bid), {"_id": 0}
    )
    if existing_job:
        started_at = existing_job.get("started_at", "")
        if started_at and started_at < timeout_cutoff:
            await db.fee_sync_jobs.update_one(
                scoped_query({"id": existing_job["id"]}, branch_id=bid),
                {"$set": {"status": "failed", "reason": "timeout", "failed_at": now.isoformat()}},
            )
        else:
            return {"job": existing_job, "already_running": True}

    job_id = str(uuid.uuid4())
    job = {
        "_id": job_id,
        "id": job_id,
        "schoolId": school_id,
        "status": "running",
        "started_at": now.isoformat(),
        "synced_count": 0,
        "conflict_count": 0,
        "conflicts": [],
        "triggered_by": actor_ctx.user_id,
        "created_at": now.isoformat(),
    }
    if bid:
        job["branch_id"] = bid
    await db.fee_sync_jobs.insert_one(job)
    try:
        records = await fetch_fn()
    except Exception as exc:
        detail = getattr(exc, "detail", None) or f"Fee sync failed: {exc}"
        await db.fee_sync_jobs.update_one(
            # branch-scope: intentional — job id is a fresh uuid created above; school scope suffices
            scoped_filter({"id": job_id}, school_id),
            {"$set": {"status": "failed", "error": detail, "completed_at": actor_ctx.now_iso()}},
        )
        await _audit(db, actor_ctx, action="fee_sync_failed", entity_id=job_id, changes={"error": detail})
        if getattr(exc, "detail", None) is not None:
            raise FeeSyncUpstreamError(detail) from exc
        return {"job": {"sync_job_id": job_id, "status": "failed", "error": detail}, "already_running": False}

    conflicts = []
    synced = 0
    for record in records:
        student_id, period, fee_head = _external_key(record)
        if not student_id or not period or not fee_head:
            continue
        existing = await db.fee_transactions.find_one(
            # branch-scope: intentional — matches the legacy _fee_query school-wide
            # duplicate check; fee txns are keyed (student, period, head) per school
            scoped_filter({"student_id": student_id, "fee_period": period, "fee_head": fee_head}, school_id),
            {"_id": 0},
        )
        amount = float(record.get("amount", 0))
        if existing and float(existing.get("amount", 0)) != amount:
            conflicts.append({
                "id": str(uuid.uuid4()),
                "student_id": student_id,
                "period": period,
                "fee_head": fee_head,
                "ours": existing,
                "theirs": record,
                "status": "conflict",
            })
            continue
        if not existing:
            txn_id = str(uuid.uuid4())
            await db.fee_transactions.insert_one({
                "_id": txn_id,
                "id": txn_id,
                "schoolId": school_id,
                "student_id": student_id,
                "fee_period": period,
                "fee_head": fee_head,
                "fee_type": fee_head,
                "amount": amount,
                "status": record.get("status", "pending"),
                "due_date": record.get("due_date"),
                "created_at": actor_ctx.now_iso(),
                "source": "fee_api_sync",
            })
            synced += 1

    status = "conflict" if conflicts else "completed"
    update = {
        "status": status,
        "synced_count": synced,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "completed_at": actor_ctx.now_iso(),
    }
    # branch-scope: intentional — job id is a fresh uuid created above; school scope suffices
    await db.fee_sync_jobs.update_one(scoped_filter({"id": job_id}, school_id), {"$set": update})
    await _audit(db, actor_ctx, action="fee_sync_completed", entity_id=job_id, changes=update)
    if synced and publish_fn is not None:
        await publish_fn(db, "fee_sync_completed", {"sync_job_id": job_id, **update})
    return {"job": {"sync_job_id": job_id, **update}, "already_running": False}
