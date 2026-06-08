"""Pilot observability & metrics for the AI action layer (Story F.7 / FR24-25).

The Owner/Principal acceptance gate is evidence-based: ≥80% adoption, a minimum
mutation volume N, and ZERO parity-diff / torn-state / leakage incidents. To make
that measurable we emit lightweight counter events to `db.ai_metrics` from the
dispatch path. These reuse the Part-7 audit/observability posture: queryable, but
**no PII** — only tool names, outcome codes, ids, and counts (never params/values).

Event taxonomy (the `event` field):
- `plan_executed`            — a confirmed plan/dispatch ran to commit
- `confirmation`             — a confirm token was consumed (one per dispatch)
- `step_outcome`             — per-step result (status committed/ok/failed)
- `parity_diff`              — a parity-harness drift was detected (from F.6)
- `torn_state`               — needs_manual_reconciliation / saga compensation
- `kill_switch_blocked`      — a write was refused by the F.4 kill-switch
- `ai_action` / `ui_action`  — AI-vs-UI action counts for the adoption ratio

Fail-open: a metric write never blocks or fails a dispatch (it is logged on error).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from services.txn_context import session_kwargs

logger = logging.getLogger(__name__)

# Fields that must NEVER be persisted to a metric row (DPDP — no PII in metrics).
_FORBIDDEN_KEYS = {"params", "records", "name", "phone", "email", "address", "dob"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def record_ai_metric(
    db,
    *,
    event: str,
    user_id: str = "",
    tool_name: str = "",
    status: str = "",
    school_id: Optional[str] = None,
    branch_id: Optional[str] = None,
    count: int = 1,
    extra: Optional[dict] = None,
    in_transaction: bool = False,
) -> None:
    """Insert one metric row. PII-free by construction (`extra` is key-filtered).

    `in_transaction=True` enlists the write in the executor's ambient txn so a
    rolled-back dispatch does not leave a phantom `plan_executed` row. The default
    (False) writes outside any session — used for terminal/error-path metrics that
    must survive even when the dispatch txn aborts (kill-switch, torn-state).
    """
    safe_extra = {}
    if extra:
        for k, v in extra.items():
            if str(k).lower() in _FORBIDDEN_KEYS:
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                safe_extra[k] = v
    doc = {
        "_id": str(uuid.uuid4()),
        "event": event,
        "user_id": user_id,
        "tool_name": tool_name,
        "status": status,
        "schoolId": school_id,
        "branch_id": branch_id,
        "count": count,
        "ts": _now(),
        **safe_extra,
    }
    try:
        kwargs = session_kwargs() if in_transaction else {}
        await db.ai_metrics.insert_one(doc, **kwargs)
    except Exception:
        logger.warning("ai_metric_write_failed event=%s", event, exc_info=True)

    # Best-effort forward to LayaaStat (no-op when the integration is disabled). The
    # forwarded payload is the SAME PII-free shape persisted above — only event/tool/
    # status/ids/counts, never params or values.
    try:
        from services import layaastat

        if layaastat.is_enabled():
            await layaastat.track_event(
                f"ai_{event}",
                distinct_id=user_id or None,
                properties={
                    "tool_name": tool_name,
                    "status": status,
                    "schoolId": school_id,
                    "branch_id": branch_id,
                    "count": count,
                    **safe_extra,
                },
                source="ai_metrics",
            )
    except Exception:
        logger.debug("layaastat ai_metric forward failed event=%s", event, exc_info=True)
