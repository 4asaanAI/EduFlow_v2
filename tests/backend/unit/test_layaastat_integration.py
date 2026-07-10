"""LayaaStat push-integration tests — client buffering/retry/idempotency + env gating."""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, "backend"))

pytestmark = pytest.mark.asyncio

from services.layaastat.client import LayaaMonitor
from services import layaastat


# ─── A capturing fake transport ──────────────────────────────────────────────

class _FakeSender:
    """Records (path, body) calls and returns a scripted SendResult per call."""

    def __init__(self, results=None):
        self.calls = []
        self._results = list(results or [])

    async def __call__(self, path, body):
        self.calls.append((path, body))
        return self._results.pop(0) if self._results else "ok"


# ─── Client: buffering, flush, idempotency ───────────────────────────────────

async def test_track_buffers_until_flush_then_sends_to_ingest():
    sender = _FakeSender()
    m = LayaaMonitor(endpoint="https://dash.example/", ingest_key="lsk_live_x", send_func=sender, flush_at=100)
    await m.track("fee_recorded", distinct_id="owner-1", properties={"amount": 5000})
    assert sender.calls == []          # buffered, not yet sent
    await m.flush()
    assert len(sender.calls) == 1
    path, body = sender.calls[0]
    assert path == "/api/ingest"
    assert body["events"][0]["name"] == "fee_recorded"
    assert body["events"][0]["user_id"] == "owner-1"
    # Idempotency key stamped per event.
    assert body["events"][0]["insert_id"]


async def test_flush_at_triggers_auto_flush():
    sender = _FakeSender()
    m = LayaaMonitor(endpoint="https://dash.example", ingest_key="k", send_func=sender, flush_at=2)
    await m.track("a")
    assert sender.calls == []
    await m.track("b")                 # reaching flush_at auto-flushes
    assert len(sender.calls) == 1
    assert len(sender.calls[0][1]["events"]) == 2


async def test_span_goes_to_otel_endpoint():
    sender = _FakeSender()
    m = LayaaMonitor(endpoint="https://dash.example", ingest_key="k", send_func=sender, flush_at=100)
    await m.span({"trace_id": "t1", "span_id": "s1", "operation_name": "chat", "model": "claude-opus-4-8"})
    await m.flush()
    path, body = sender.calls[0]
    assert path == "/api/otel"
    assert body["spans"][0]["span_id"] == "s1"
    assert body["spans"][0]["service_id"] == "eduflow-api"


# ─── Client: retry / store-and-forward / permanent drop ──────────────────────

async def test_unreachable_batch_is_buffered_and_redelivered():
    # First flush: endpoint unreachable → batch retained. Second flush: ok → drained.
    sender = _FakeSender(results=["unreachable", "ok"])
    m = LayaaMonitor(endpoint="https://dash.example", ingest_key="k", send_func=sender, flush_at=100)
    await m.track("x")
    await m.flush()
    assert m.buffered_count() == 1     # kept for store-and-forward
    await m.flush()                    # endpoint recovered
    assert m.buffered_count() == 0


async def test_permanent_4xx_is_dropped_not_buffered():
    sender = _FakeSender(results=["permanent"])
    m = LayaaMonitor(endpoint="https://dash.example", ingest_key="bad", send_func=sender, flush_at=100)
    await m.track("x")
    await m.flush()
    assert m.buffered_count() == 0     # dropped, not retried


async def test_overflow_drops_oldest():
    sender = _FakeSender(results=["unreachable"] * 10)
    m = LayaaMonitor(endpoint="https://dash.example", ingest_key="k", send_func=sender,
                     flush_at=100, max_buffer_items=2)
    for i in range(5):
        await m.track(f"e{i}")
        await m.flush()                # each flush enqueues one unreachable batch
    assert m.buffered_count() <= 2
    assert m.dropped_count() >= 1


# ─── Module gating: dormant unless both env vars are set ─────────────────────

@pytest.fixture(autouse=True)
def _reset_layaastat_env(monkeypatch):
    monkeypatch.delenv("LAYAASTAT_URL", raising=False)
    monkeypatch.delenv("LAYAASTAT_INGEST_KEY", raising=False)
    layaastat.reset_monitor()
    yield
    layaastat.reset_monitor()


async def test_disabled_by_default_is_noop():
    assert layaastat.is_enabled() is False
    assert layaastat.get_monitor() is None
    # Helpers must not raise when disabled.
    await layaastat.track_event("anything", distinct_id="u1")
    await layaastat.flush()
    await layaastat.record_health_heartbeat(status="ok")


async def test_enabled_when_both_env_vars_set(monkeypatch):
    monkeypatch.setenv("LAYAASTAT_URL", "https://dash.example")
    monkeypatch.setenv("LAYAASTAT_INGEST_KEY", "lsk_live_abc")
    layaastat.reset_monitor()
    assert layaastat.is_enabled() is True
    monitor = layaastat.get_monitor()
    assert monitor is not None
    # Swap in a fake transport and verify the helper routes through it.
    sender = _FakeSender()
    monitor._send = sender
    await layaastat.track_event("login", distinct_id="u1")
    await layaastat.flush()
    assert sender.calls[0][0] == "/api/ingest"
    assert sender.calls[0][1]["events"][0]["name"] == "login"


async def test_only_url_set_stays_disabled(monkeypatch):
    monkeypatch.setenv("LAYAASTAT_URL", "https://dash.example")
    layaastat.reset_monitor()
    assert layaastat.is_enabled() is False
    assert layaastat.get_monitor() is None


async def test_ai_metrics_forwarded_when_enabled(monkeypatch):
    monkeypatch.setenv("LAYAASTAT_URL", "https://dash.example")
    monkeypatch.setenv("LAYAASTAT_INGEST_KEY", "lsk_live_abc")
    layaastat.reset_monitor()
    monitor = layaastat.get_monitor()
    sender = _FakeSender()
    monitor._send = sender

    from services.ai_metrics import record_ai_metric

    class _FakeMetricsCol:
        async def insert_one(self, doc, **kw):
            return None

    class _FakeDb:
        ai_metrics = _FakeMetricsCol()

    await record_ai_metric(_FakeDb(), event="plan_executed", user_id="owner-1",
                           tool_name="record_fee_payment", status="committed")
    await layaastat.flush()
    names = [e["name"] for c in sender.calls for e in c[1].get("events", [])]
    assert "ai_plan_executed" in names
    # PII-free: only the safe fields are forwarded.
    ev = next(e for c in sender.calls for e in c[1]["events"] if e["name"] == "ai_plan_executed")
    assert ev["properties"]["tool_name"] == "record_fee_payment"
    assert ev["user_id"] == "owner-1"
