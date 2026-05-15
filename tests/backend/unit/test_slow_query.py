from __future__ import annotations

import logging

import pytest

import database
from database import TimedQuery
from logging_config import request_id_ctx


@pytest.mark.asyncio
async def test_timed_query_logs_when_elapsed_exceeds_threshold(monkeypatch, caplog):
    monkeypatch.setenv("SLOW_QUERY_MS", "50")
    # Use a cycle that never exhausts — logging formatter may call time.time() extra times
    _calls = [100.0, 100.15]; _i = [0]
    def _tick(): v = _calls[min(_i[0], len(_calls)-1)]; _i[0] += 1; return v
    monkeypatch.setattr(database.time, "time", _tick)
    token = request_id_ctx.set("req-123")
    caplog.set_level(logging.DEBUG, logger=database.logger.name)

    try:
        async with TimedQuery(collection_name="students", operation="find", query_shape="students_list"):
            pass
    finally:
        request_id_ctx.reset(token)

    record = next(record for record in caplog.records if record.msg == "slow_query")
    assert record.collection == "students"
    assert record.operation == "find"
    assert record.elapsed_ms == 150.0
    assert record.query_shape == "students_list"
    assert record.request_id == "req-123"


@pytest.mark.asyncio
async def test_timed_query_does_not_log_fast_queries(monkeypatch, caplog):
    monkeypatch.setenv("SLOW_QUERY_MS", "50")
    ticks = iter([100.0, 100.01])
    monkeypatch.setattr(database.time, "time", lambda: next(ticks))
    caplog.set_level(logging.DEBUG, logger=database.logger.name)

    async with TimedQuery(collection_name="students", operation="find", query_shape="students_list"):
        pass

    assert "slow_query" not in caplog.text


@pytest.mark.asyncio
async def test_timed_query_threshold_uses_env(monkeypatch, caplog):
    monkeypatch.setenv("SLOW_QUERY_MS", "5")
    _calls = [100.0, 100.01]; _i = [0]
    def _tick(): v = _calls[min(_i[0], len(_calls)-1)]; _i[0] += 1; return v
    monkeypatch.setattr(database.time, "time", _tick)
    caplog.set_level(logging.DEBUG, logger=database.logger.name)

    async with TimedQuery(collection_name="students", operation="find", query_shape="students_list"):
        pass

    assert "slow_query" in caplog.text
