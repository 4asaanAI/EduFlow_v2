"""
API Tests: External fee software sync - EduFlow Backend.
"""

from middleware.auth import create_jwt


def _owner_headers():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'owner-1', 'role': 'owner', 'name': 'Owner'})}"}


def _admin_headers():
    return {"Authorization": f"Bearer {create_jwt({'user_id': 'admin-2', 'role': 'admin', 'name': 'Admin'})}"}


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": self._data}


class _FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers):
        return _FakeResponse([
            {"student_id": "student-1", "fee_period": "2026-05", "fee_head": "tuition", "amount": 3200, "status": "pending", "due_date": "2026-05-20"},
            {"student_id": "student-1", "fee_period": "2026-06", "fee_head": "tuition", "amount": 3000, "status": "pending", "due_date": "2026-06-20"},
        ])


class TestFeeSync:
    def test_sync_requires_external_fee_env(self, client, auth_headers, monkeypatch):
        monkeypatch.delenv("FEE_API_BASE_URL", raising=False)
        monkeypatch.delenv("FEE_API_KEY", raising=False)

        response = client.post("/api/fees/sync/trigger", headers=auth_headers)

        # A missing external-fee integration config surfaces as 502: the config
        # guard raises inside the injected fetch callback, and fee_sync_service
        # maps any fetch-path failure to FeeSyncUpstreamError → 502. (Arguably a
        # 503 would read better, but that lives in the service's error taxonomy;
        # this test pins the shipped behavior, it does not prescribe it.)
        assert response.status_code == 502

    def test_sync_surfaces_conflicts_and_blocks_completion(self, client, auth_headers, fake_db, monkeypatch):
        monkeypatch.setenv("FEE_API_BASE_URL", "https://fees.example.test")
        monkeypatch.setenv("FEE_API_KEY", "secret")
        monkeypatch.setattr("routes.fees.httpx.AsyncClient", _FakeAsyncClient)
        fake_db.fee_transactions.docs.append({
            "_id": "fee-existing",
            "id": "fee-existing",
            "schoolId": "aaryans-joya",
            "student_id": "student-1",
            "fee_period": "2026-05",
            "fee_head": "tuition",
            "fee_type": "tuition",
            "amount": 2500,
            "status": "pending",
            "created_at": "2026-05-01T00:00:00",
        })

        triggered = client.post("/api/fees/sync/trigger", headers=auth_headers)
        job_id = triggered.json()["data"]["sync_job_id"]
        fetched = client.get(f"/api/fees/sync/{job_id}", headers=auth_headers)

        assert triggered.status_code == 200
        assert fetched.json()["data"]["status"] == "conflict"
        assert fetched.json()["data"]["conflict_count"] == 1
        assert fetched.json()["data"]["synced_count"] == 1
        assert fake_db.audit_logs.docs[-1]["action"] == "fee_sync_completed"

    def test_owner_resolves_conflict_with_external_record(self, client, auth_headers, fake_db, monkeypatch):
        monkeypatch.setenv("FEE_API_BASE_URL", "https://fees.example.test")
        monkeypatch.setenv("FEE_API_KEY", "secret")
        monkeypatch.setattr("routes.fees.httpx.AsyncClient", _FakeAsyncClient)
        fake_db.fee_transactions.docs.append({
            "_id": "fee-existing",
            "id": "fee-existing",
            "schoolId": "aaryans-joya",
            "student_id": "student-1",
            "fee_period": "2026-05",
            "fee_head": "tuition",
            "fee_type": "tuition",
            "amount": 2500,
            "status": "pending",
            "created_at": "2026-05-01T00:00:00",
        })
        job = client.post("/api/fees/sync/trigger", headers=auth_headers).json()["data"]
        conflict_id = job["conflicts"][0]["id"]
        stored_job = next(item for item in fake_db.fee_sync_jobs.docs if item["id"] == job["sync_job_id"])
        stored_job["conflicts"][0]["theirs"]["hacked_field"] = "must-not-land"
        stored_job["conflicts"][0]["theirs"]["status"] = "paid"

        forbidden = client.post(f"/api/fees/sync/{job['sync_job_id']}/resolve-conflict", json={"conflict_id": conflict_id, "decision": "use_theirs"}, headers=_admin_headers())
        resolved = client.post(f"/api/fees/sync/{job['sync_job_id']}/resolve-conflict", json={"conflict_id": conflict_id, "decision": "use_theirs"}, headers=_owner_headers())

        assert forbidden.status_code == 403
        assert resolved.json()["data"]["status"] == "completed"
        updated = next(item for item in fake_db.fee_transactions.docs if item["id"] == "fee-existing")
        assert updated["amount"] == 3200
        assert updated["status"] == "paid"
        assert "hacked_field" not in updated
        resolved_conflict = resolved.json()["data"]["conflicts"][0]
        assert set(resolved_conflict["resolved_fields"]) == {"amount", "status", "due_date", "source"}
        assert fake_db.audit_logs.docs[-1]["action"] == "fee_sync_conflict_resolved"
