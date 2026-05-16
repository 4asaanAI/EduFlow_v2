from __future__ import annotations
import pytest
from datetime import datetime, timezone
from middleware.auth import create_jwt


def _owner_h():
    t = create_jwt({"user_id": "o1", "role": "owner", "name": "O"})
    return {"Authorization": f"Bearer {t}"}


def test_sync_trigger_returns_existing_in_progress_job(client, fake_db):
    """Second sync trigger returns existing job (idempotency)."""
    from tests.backend.conftest import FakeCollection

    # Use a timestamp 1 minute ago — well within the 30-min timeout window
    recent_ts = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    fake_db.fee_sync_jobs = FakeCollection(
        [
            {
                "id": "job-1",
                "schoolId": "aaryans-joya",
                "status": "in_progress",
                "started_at": recent_ts.isoformat(),  # recent — NOT timed out
            }
        ]
    )
    resp1 = client.post("/api/fees/sync/trigger", json={}, headers=_owner_h())
    # Should not create a new job — should return existing
    assert resp1.status_code == 200
    assert len(fake_db.fee_sync_jobs.docs) == 1  # still only 1 job


def test_hung_job_is_expired_and_new_job_created(client, fake_db):
    """A hung job (> SYNC_JOB_TIMEOUT_MINUTES) is failed and a new job created."""
    from tests.backend.conftest import FakeCollection

    fake_db.fee_sync_jobs = FakeCollection(
        [
            {
                "id": "job-old",
                "schoolId": "aaryans-joya",
                "status": "in_progress",
                # Very old timestamp — definitely timed out
                "started_at": "2020-01-01T00:00:00+00:00",
            }
        ]
    )
    # The sync trigger will try to fetch external records; patch the env to avoid 503
    import os
    import unittest.mock as mock

    # Mock _fetch_external_fee_records to avoid needing FEE_API_BASE_URL/KEY
    import routes.fees as fees_routes

    with mock.patch.object(fees_routes, "_fetch_external_fee_records", return_value=[]):
        resp = client.post("/api/fees/sync/trigger", json={}, headers=_owner_h())

    assert resp.status_code == 200
    old_job = next(
        (j for j in fake_db.fee_sync_jobs.docs if j["id"] == "job-old"), None
    )
    if old_job:
        assert old_job["status"] == "failed"
