"""Async LayaaStat ingest client — the Python mirror of LayaaStat's `sdk/layaa-monitor.ts`.

A thin, dependency-light client EduFlow's backend uses to *push* telemetry to the
Layaa AI health-check platform (LayaaStat). It speaks the two documented ingest
contracts:

- ``POST /api/ingest`` — custom product events  → ``raw_events``  (idempotent on ``insert_id``)
- ``POST /api/otel``   — GenAI / LLM spans       → ``otel_spans``  (idempotent on ``span_id``)

Both require a tenant-bound ``x-ingest-key`` (``lsk_live_…``) and are **server-side only**.

Design (faithful to the reference SDK):
- Buffers events + spans; flushes on size (``flush_at``) or an explicit/periodic ``flush()``.
- Retries 429 / 5xx / network errors with exponential back-off; drops permanent 4xx
  (bad key/payload) without retrying.
- Stamps an ``insert_id`` per event for idempotency, so a re-delivered batch lands once.
- Store-and-forward: a batch that stays unreachable after retries is kept in a *bounded*
  in-memory FIFO queue and re-sent on the next flush; on overflow the OLDEST batch is
  dropped (counted via :meth:`dropped_count`). Telemetry must never block or crash the app.

This module knows nothing about configuration or whether the integration is enabled —
see ``services.layaastat.__init__`` for the env-gated singleton and public helpers.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Literal, Optional

logger = logging.getLogger(__name__)

_BACKOFF_MS = [250, 500, 1000, 2000, 4000]

SendResult = Literal["ok", "permanent", "unreachable"]

# A failed batch awaiting re-send. ``count`` = number of events+spans it carries.
_Batch = dict  # {"path": str, "body": dict, "count": int}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LayaaMonitor:
    """Buffering, retrying, store-and-forward ingest client. Safe to share process-wide."""

    def __init__(
        self,
        *,
        endpoint: str,
        ingest_key: str,
        service_name: str = "eduflow-api",
        flush_at: int = 20,
        max_retries: int = 4,
        max_buffer_items: int = 10000,
        send_func: Optional[Callable[[str, dict], Awaitable[SendResult]]] = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._ingest_key = ingest_key
        self._service_name = service_name
        self._flush_at = max(1, flush_at)
        self._max_retries = max(0, max_retries)
        self._max_buffer_items = max(1, max_buffer_items)
        # Injectable transport (tests pass a fake); defaults to the real HTTP sender.
        self._send: Callable[[str, dict], Awaitable[SendResult]] = send_func or self._http_send

        self._events: list[dict] = []
        self._spans: list[dict] = []
        self._forward_queue: list[_Batch] = []
        self._dropped = 0
        self._lock = asyncio.Lock()

    # ── Public buffering API ────────────────────────────────────────────────
    async def track(
        self,
        event_name: str,
        *,
        distinct_id: Optional[str] = None,
        properties: Optional[dict] = None,
        session_id: Optional[str] = None,
        source: Optional[str] = None,
        occurred_at: Optional[str] = None,
    ) -> None:
        """Queue a custom product event. Flushes immediately once ``flush_at`` is reached."""
        self._events.append({
            "name": event_name,
            "insert_id": str(uuid.uuid4()),
            "timestamp": occurred_at or _now_iso(),
            "user_id": distinct_id,
            "session_id": session_id,
            "source": source or self._service_name,
            "properties": properties or {},
        })
        if len(self._events) >= self._flush_at:
            await self.flush()

    async def span(self, span: dict) -> None:
        """Queue a GenAI span. ``span_id`` must be present for server-side idempotency."""
        enriched = {"service_id": self._service_name, **span}
        self._spans.append(enriched)
        if len(self._spans) >= self._flush_at:
            await self.flush()

    def buffered_count(self) -> int:
        """Events+spans currently held in the store-and-forward queue (awaiting reconnect)."""
        return sum(b["count"] for b in self._forward_queue)

    def dropped_count(self) -> int:
        """Cumulative events+spans dropped due to buffer overflow (drop-oldest)."""
        return self._dropped

    # ── Flush / lifecycle ───────────────────────────────────────────────────
    async def flush(self) -> None:
        """Drain the store-and-forward queue (oldest first), then send current buffers."""
        async with self._lock:
            # 1) Re-deliver previously-failed batches first; stop early if still down
            #    (preserves ordering).
            while self._forward_queue:
                batch = self._forward_queue[0]
                res = await self._send(batch["path"], batch["body"])
                if res in ("ok", "permanent"):
                    self._forward_queue.pop(0)
                else:
                    break

            # 2) Send the current buffers; on unreachable, enqueue for store-and-forward.
            events, self._events = self._events, []
            spans, self._spans = self._spans, []
            if events:
                await self._deliver_or_buffer({"path": "/api/ingest", "body": {"events": events}, "count": len(events)})
            if spans:
                await self._deliver_or_buffer({"path": "/api/otel", "body": {"spans": spans}, "count": len(spans)})

    async def aclose(self) -> None:
        """Final flush on shutdown."""
        await self.flush()

    # ── Internals ───────────────────────────────────────────────────────────
    async def _deliver_or_buffer(self, batch: _Batch) -> None:
        # If the queue is already non-empty the endpoint is known-down — buffer directly
        # to preserve ordering rather than racing a doomed send.
        res = "unreachable" if self._forward_queue else await self._send(batch["path"], batch["body"])
        if res == "unreachable":
            self._enqueue(batch)
        # "ok" → delivered; "permanent" (4xx) → intentionally dropped (bad payload/key).

    def _enqueue(self, batch: _Batch) -> None:
        self._forward_queue.append(batch)
        buffered = self.buffered_count()
        while buffered > self._max_buffer_items and len(self._forward_queue) > 1:
            evicted = self._forward_queue.pop(0)
            self._dropped += evicted["count"]
            buffered -= evicted["count"]

    async def _http_send(self, path: str, body: dict) -> SendResult:
        """Real transport. Imports httpx lazily so the module loads without it."""
        import httpx

        url = self._endpoint + path
        headers = {"x-ingest-key": self._ingest_key, "content-type": "application/json"}
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(url, json=body, headers=headers)
                if resp.status_code < 300:
                    return "ok"
                # 4xx except 429 = permanent client error (bad key/payload) — don't retry.
                if resp.status_code != 429 and resp.status_code < 500:
                    logger.warning("layaastat ingest rejected (permanent) status=%s path=%s", resp.status_code, path)
                    return "permanent"
                # 429 / 5xx → retryable
            except Exception:
                logger.debug("layaastat ingest transport error path=%s attempt=%s", path, attempt, exc_info=True)
            if attempt < self._max_retries:
                await asyncio.sleep(_BACKOFF_MS[min(attempt, len(_BACKOFF_MS) - 1)] / 1000.0)
        return "unreachable"
