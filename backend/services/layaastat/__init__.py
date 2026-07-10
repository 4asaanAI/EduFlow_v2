"""LayaaStat integration — env-gated push telemetry to the Layaa health-check platform.

EduFlow's path in the Layaa portfolio is **push/ingest** ("OTel spans + custom events"
per LayaaStat's product-ingest onboarding doc), distinct from the federation model used
by sibling products. This package owns a process-wide :class:`LayaaMonitor` and exposes
no-op-when-disabled helpers so call sites never need to check configuration.

Enable by setting two backend env vars (see ``docs/deployment-runbook.md`` §9):

    LAYAASTAT_URL          = https://<your-layaastat-deployment>     # the dashboard base URL
    LAYAASTAT_INGEST_KEY   = lsk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxx    # tenant-scoped, from /registry

Optional:
    LAYAASTAT_SERVICE_NAME      (default "eduflow-api")
    LAYAASTAT_FLUSH_AT          (default 20)
    LAYAASTAT_HEARTBEAT_SECONDS (default 60; 0 disables the periodic heartbeat task)

When either of the two required vars is unset the integration is **fully dormant** —
every helper returns immediately and nothing is buffered, sent, or scheduled.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from services.layaastat.client import LayaaMonitor

logger = logging.getLogger(__name__)

_monitor: Optional[LayaaMonitor] = None
_resolved = False


def is_enabled() -> bool:
    """True iff both the dashboard URL and a tenant-scoped ingest key are configured."""
    return bool(os.environ.get("LAYAASTAT_URL") and os.environ.get("LAYAASTAT_INGEST_KEY"))


def service_name() -> str:
    return os.environ.get("LAYAASTAT_SERVICE_NAME", "eduflow-api")


def heartbeat_seconds() -> int:
    try:
        return int(os.environ.get("LAYAASTAT_HEARTBEAT_SECONDS", "60"))
    except (TypeError, ValueError):
        return 60


def get_monitor() -> Optional[LayaaMonitor]:
    """Return the process-wide monitor, constructing it once. ``None`` when disabled.

    The singleton is resolved lazily and cached. ``reset_monitor()`` clears the cache
    (used by tests that toggle env vars).
    """
    global _monitor, _resolved
    if _resolved:
        return _monitor
    _resolved = True
    if not is_enabled():
        _monitor = None
        return None
    try:
        flush_at = int(os.environ.get("LAYAASTAT_FLUSH_AT", "20"))
    except (TypeError, ValueError):
        flush_at = 20
    _monitor = LayaaMonitor(
        endpoint=os.environ["LAYAASTAT_URL"],
        ingest_key=os.environ["LAYAASTAT_INGEST_KEY"],
        service_name=service_name(),
        flush_at=flush_at,
    )
    logger.info("LayaaStat integration enabled (endpoint=%s)", os.environ["LAYAASTAT_URL"])
    return _monitor


def reset_monitor() -> None:
    """Drop the cached singleton so the next ``get_monitor()`` re-reads the env."""
    global _monitor, _resolved
    _monitor = None
    _resolved = False


# ── Public helpers — all no-op when the integration is disabled ──────────────

async def track_event(
    event_name: str,
    *,
    distinct_id: Optional[str] = None,
    properties: Optional[dict] = None,
    session_id: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    """Buffer a custom product event (best-effort; never raises to the caller)."""
    monitor = get_monitor()
    if monitor is None:
        return
    try:
        await monitor.track(
            event_name,
            distinct_id=distinct_id,
            properties=properties,
            session_id=session_id,
            source=source,
        )
    except Exception:
        logger.debug("layaastat track_event failed event=%s", event_name, exc_info=True)


async def track_span(span: dict) -> None:
    """Buffer a GenAI/LLM span (best-effort; never raises)."""
    monitor = get_monitor()
    if monitor is None:
        return
    try:
        await monitor.span(span)
    except Exception:
        logger.debug("layaastat track_span failed", exc_info=True)


async def record_health_heartbeat(
    *,
    status: str,
    checks: Optional[dict] = None,
    score: Optional[int] = None,
) -> None:
    """Emit a ``service_health`` heartbeat event so LayaaStat can watch EduFlow live.

    PII-free by construction — carries only the overall status, an optional 0-100 score,
    and per-dependency check states (db/ai/s3/sms), never user data.
    """
    props: dict = {"status": status, "service": service_name()}
    if score is not None:
        props["score"] = score
    if checks:
        props["checks"] = checks
    await track_event("service_health", properties=props, source="health")


async def flush() -> None:
    monitor = get_monitor()
    if monitor is not None:
        try:
            await monitor.flush()
        except Exception:
            logger.debug("layaastat flush failed", exc_info=True)


async def aclose() -> None:
    monitor = get_monitor()
    if monitor is not None:
        try:
            await monitor.aclose()
        except Exception:
            logger.debug("layaastat aclose failed", exc_info=True)


# ─── Back-compat API (merged from the former services/layaastat.py module) ────
# auth/chat/memory call emit_event(...) and llm_client calls emit_llm_span(...).
# They predate this package (which uses track_event/track_span). Keep the old
# names as thin adapters over the single package transport so there is ONE client
# and ONE ingest path. Best-effort + no-op when the integration is disabled
# (get_monitor() → None), exactly like the rest of this module.

async def emit_event(
    event_name: str,
    *,
    distinct_id: Optional[str] = None,
    source: str = "eduflow-backend",
    payload: Optional[dict] = None,
) -> None:
    """Legacy product-event API — routes to track_event (payload → properties)."""
    await track_event(
        event_name,
        distinct_id=distinct_id,
        properties=payload or {},
        source=source,
    )


async def emit_llm_span(
    *,
    model: str,
    provider_name: str,
    operation_name: str = "chat",
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    duration_ms: Optional[float] = None,
    error_type: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """Legacy LLM-span API — routes to track_span (best-effort, PII-free)."""
    import uuid

    await track_span({
        "trace_id": trace_id or str(uuid.uuid4()),
        "span_id": str(uuid.uuid4()),
        "operation_name": operation_name,
        "provider_name": provider_name,
        "model": model,
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "error_type": error_type,
    })
