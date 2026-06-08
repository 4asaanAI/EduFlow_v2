"""Story F.7 — pilot observability metrics (PII-free, queryable)."""

from __future__ import annotations

import pytest

from services.ai_metrics import record_ai_metric

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.ai_metrics.docs[:] = []
    yield
    fake_db.ai_metrics.docs[:] = []


async def test_metric_row_written_and_queryable(fake_db):
    await record_ai_metric(
        fake_db, event="plan_executed", user_id="o1", tool_name="mark_attendance",
        status="committed", school_id="aaryans-joya", branch_id="branch-a", count=2,
    )
    rows = await fake_db.ai_metrics.find({"event": "plan_executed"}).to_list(10)
    assert len(rows) == 1
    assert rows[0]["tool_name"] == "mark_attendance"
    assert rows[0]["count"] == 2


async def test_metric_drops_pii_fields(fake_db):
    await record_ai_metric(
        fake_db, event="ai_action", user_id="o1", tool_name="record_fee_payment",
        extra={"name": "Aarav", "phone": "9876543210", "step_count": 3},
    )
    row = (await fake_db.ai_metrics.find({"event": "ai_action"}).to_list(10))[0]
    assert "name" not in row
    assert "phone" not in row
    assert row["step_count"] == 3  # non-PII extras are kept


async def test_metric_write_never_raises(fake_db):
    # Even with a broken collection the call must not raise (fail-open).
    class _Boom:
        async def insert_one(self, *a, **k):
            raise RuntimeError("db down")

    class _DB:
        ai_metrics = _Boom()

    await record_ai_metric(_DB(), event="ai_action", user_id="x")  # no exception
