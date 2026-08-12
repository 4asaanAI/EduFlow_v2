"""R4-3 - the two retention endpoints, and who may reach them.

Thinning is the only thing on the platform that deletes the school's history, so the
guard on it matters more than the guard on almost anything else. The route-ordering test
is here because `/{record_id}` is declared in the same file and matches any single path
segment: registered after it, `/retention/plan` answers as a lookup for a record called
"retention", 404s, and reads exactly like a feature that was never built.
"""

from __future__ import annotations

import pytest

from middleware.auth import create_jwt


def _headers(role="owner", sub_category="owner", user_id="aman"):
    payload = {"user_id": user_id, "role": role, "sub_category": sub_category, "name": "T"}
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


# ---------------------------------------------------------------------------
# Security convention: unauthenticated and wrong-role, for both new endpoints
# ---------------------------------------------------------------------------

def test_retention_plan_unauthenticated_returns_401(client):
    assert client.get("/api/audit-log/retention/plan").status_code == 401


def test_retention_run_unauthenticated_returns_401(client):
    assert client.post("/api/audit-log/retention/run").status_code == 401


def test_retention_plan_wrong_role_returns_403(client):
    resp = client.get("/api/audit-log/retention/plan",
                      headers=_headers(role="student", sub_category=""))
    assert resp.status_code == 403


def test_retention_run_wrong_role_returns_403(client):
    resp = client.post("/api/audit-log/retention/run",
                       headers=_headers(role="student", sub_category=""))
    assert resp.status_code == 403


def test_the_principal_may_read_the_audit_log_but_not_thin_it(client):
    """Decision 5 keeps Aman's changes out of Adesh's view of the trail.

    A principal who could thin the trail could remove the very entries that decision
    exists to protect, so this is a permission boundary and not a tidy-up.
    """
    principal = _headers(role="admin", sub_category="principal", user_id="adesh")
    assert client.get("/api/audit-log", headers=principal).status_code == 200
    assert client.get("/api/audit-log/retention/plan", headers=principal).status_code == 403
    assert client.post("/api/audit-log/retention/run", headers=principal).status_code == 403


# ---------------------------------------------------------------------------
# The routes actually resolve, and looking is separate from acting
# ---------------------------------------------------------------------------

def test_the_plan_route_is_not_swallowed_by_the_record_lookup(client):
    """`/{record_id}` is declared in the same file and matches any single segment."""
    resp = client.get("/api/audit-log/retention/plan", headers=_headers())
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["retention_years"] == 2
    assert "cutoff" in body


def test_the_plan_route_changes_nothing(client, fake_db):
    before = list(fake_db.audit_logs.docs)
    client.get("/api/audit-log/retention/plan", headers=_headers())
    assert fake_db.audit_logs.docs == before


def test_run_refuses_a_month_count_below_one(client):
    resp = client.post("/api/audit-log/retention/run?max_months=0", headers=_headers())
    assert resp.status_code == 400


def test_run_defaults_to_one_month(client):
    """Thinning years of history must never be what you get by leaving a value off."""
    resp = client.post("/api/audit-log/retention/run", headers=_headers())
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]["months_processed"]) <= 1
