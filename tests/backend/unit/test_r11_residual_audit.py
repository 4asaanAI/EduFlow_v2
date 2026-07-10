"""R11.6 — residual audit sweep, in-run fixes.

Covers the two small/safe hardenings applied from the sweep:
  * idempotency replay re-asserts schoolId (defence-in-depth against a key-hash
    reuse replaying one school's response into another); and
  * ai_metrics strips a wider set of PII-synonym keys so a stray `student`/
    `guardian_phone` can never be persisted into a metric row (DPDP).
The larger findings (rate-limiter ScopedCollection gap, actor_context naive
clock) are logged as deferred new-story items — they change production behaviour
and need real-Mongo verification, so they are not fixed here.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_idempotency_replay_is_school_scoped(fake_db, monkeypatch):
    import services.idempotency as idem
    from datetime import datetime, timezone, timedelta

    fake_db.idempotency_keys.docs[:] = [{
        "_id": "k1", "key": "k1", "schoolId": "school-a",
        "status_code": 200, "content_type": "application/json", "body": "{}",
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
    }]

    monkeypatch.setattr(idem, "get_school_id", lambda: "school-a")
    same = await idem.get_replay_response(fake_db, "k1")
    assert same is not None, "same-school replay must be returned"

    monkeypatch.setattr(idem, "get_school_id", lambda: "school-b")
    cross = await idem.get_replay_response(fake_db, "k1")
    assert cross is None, "another school must never replay this response"


async def test_ai_metrics_strips_pii_synonyms(fake_db):
    from services.ai_metrics import record_ai_metric

    fake_db.ai_metrics.docs[:] = []
    await record_ai_metric(
        fake_db, event="ai_turn_outcome", user_id="u1", status="answered",
        extra={"student": "Rahul Sharma", "guardian_phone": "9876543210",
               "rounds": 2, "ok": True},
    )
    doc = fake_db.ai_metrics.docs[-1]
    # PII synonyms dropped …
    assert "student" not in doc
    assert "guardian_phone" not in doc
    # … benign scalars kept.
    assert doc["rounds"] == 2
    assert doc["ok"] is True
