"""Drift-gate remediation parity — operations CRUD tools added post-Phase-1.

Same seed through both write entrypoints (REST routes in `routes/operations.py`
via TestClient, and the AI tools via their real dispatch fns) → the domain doc
+ audit row are identical except a volatile allowlist. Covers:
  create_expense / update_expense / delete_expense  → services/expense_service.py
  create_enquiry / update_enquiry_status            → services/enquiry_service.py
  create_incident                                   → services/incident_service.py
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id",
             "corrected_at", "deleted_at", "expires_at", "date"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}
SCHOOL = "aaryans-joya"


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _scrub(value):
    """Recursive mask — nested docs (audit `changes`, enquiry `timeline`) carry
    volatile ids/timestamps too."""
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _mask(docs):
    out = [_scrub(d) for d in copy.deepcopy(docs)]
    return sorted(out, key=lambda d: str(sorted(d.items())))


def _clear(fake_db, cols):
    for col in cols:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _ai_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    cols = ("expenses", "expense_budgets", "enquiries", "incidents", "audit_logs", "notifications")
    _clear(fake_db, cols)
    yield
    _clear(fake_db, cols)


# ─── Expenses ────────────────────────────────────────────────────────────────

_EXPENSE = {"category": "maintenance", "amount": 1200, "description": "AC repair",
            "vendor": "CoolAir", "date": "2026-06-01"}


def _expense_state(fake_db):
    return {
        "expenses": _mask(fake_db.expenses.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("entity_type") == "expense"]),
    }


async def test_create_expense_parity(client, fake_db):
    resp = client.post("/api/ops/expenses", json=_EXPENSE, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _expense_state(fake_db)

    _clear(fake_db, ("expenses", "audit_logs"))
    out = await tool_functions_v2.tool_create_expense(dict(_EXPENSE), OWNER_USER, None)
    assert out["success"] is True
    assert _expense_state(fake_db) == rest_state
    assert rest_state["expenses"][0]["category"] == "maintenance"
    assert len(rest_state["audit"]) == 1


def _seed_expense(fake_db):
    fake_db.expenses.docs[:] = [{
        "_id": "exp-1", "id": "exp-1", "schoolId": SCHOOL, "category": "maintenance",
        "description": "AC repair", "amount": 1200.0, "date": "2026-06-01",
        "vendor": "CoolAir", "approved_by": "own-1", "recorded_by": "own-1",
        "created_at": "2026-06-01T00:00:00",
    }]


async def test_update_expense_parity(client, fake_db):
    _seed_expense(fake_db)
    resp = client.patch("/api/ops/expenses/exp-1", json={"amount": 1500, "vendor": "FrostFix"},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _expense_state(fake_db)

    _clear(fake_db, ("audit_logs",))
    _seed_expense(fake_db)
    out = await tool_functions_v2.tool_update_expense(
        {"expense_id": "exp-1", "amount": 1500, "vendor": "FrostFix"}, OWNER_USER, None)
    assert out["success"] is True
    assert _expense_state(fake_db) == rest_state
    assert rest_state["expenses"][0]["amount"] == 1500.0


async def test_delete_expense_parity(client, fake_db):
    _seed_expense(fake_db)
    resp = client.delete("/api/ops/expenses/exp-1", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _expense_state(fake_db)

    _clear(fake_db, ("audit_logs",))
    _seed_expense(fake_db)
    out = await tool_functions_v2.tool_delete_expense({"expense_id": "exp-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert _expense_state(fake_db) == rest_state
    assert rest_state["expenses"] == []          # hard delete, matching the panel
    assert len(rest_state["audit"]) == 1         # F.10 actor-tagged deletion audit


async def test_expense_budget_guard_blocks_both_entrypoints(client, fake_db):
    fake_db.expense_budgets.docs[:] = [{
        "_id": "bud-1", "id": "bud-1", "schoolId": SCHOOL,
        "category": "maintenance", "monthly_limit": 1000, "remaining_amount": 1000,
    }]
    resp = client.post("/api/ops/expenses", json=_EXPENSE, headers=_owner_headers())
    assert resp.status_code == 400
    out = await tool_functions_v2.tool_create_expense(dict(_EXPENSE), OWNER_USER, None)
    assert out["success"] is False
    assert fake_db.expenses.docs == []


# ─── Enquiries ───────────────────────────────────────────────────────────────

_ENQUIRY = {"student_name": "Rahul Sharma", "parent_name": "S Sharma",
            "phone": "9999999999", "class_applying": "Class 8", "source": "walk_in"}


def _enquiry_state(fake_db):
    return {"enquiries": _mask(fake_db.enquiries.docs)}


async def test_create_enquiry_parity(client, fake_db):
    resp = client.post("/api/ops/enquiries", json=_ENQUIRY, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _enquiry_state(fake_db)

    _clear(fake_db, ("enquiries",))
    out = await tool_functions_v2.tool_create_enquiry(dict(_ENQUIRY), OWNER_USER, None)
    assert out["success"] is True
    assert _enquiry_state(fake_db) == rest_state
    assert rest_state["enquiries"][0]["status"] == "new"


def _seed_enquiry(fake_db):
    fake_db.enquiries.docs[:] = [{
        "_id": "enq-1", "id": "enq-1", "schoolId": SCHOOL, "student_name": "Rahul Sharma",
        "parent_name": "S Sharma", "phone": "9999999999", "class_applying": "Class 8",
        "status": "new", "source": "walk_in", "assigned_to": "own-1",
        "created_at": "2026-06-01T00:00:00",
    }]


async def test_update_enquiry_status_parity(client, fake_db):
    _seed_enquiry(fake_db)
    resp = client.patch("/api/ops/enquiries/enq-1", json={"status": "contacted", "note": "called"},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _enquiry_state(fake_db)

    _seed_enquiry(fake_db)
    out = await tool_functions_v2.tool_update_enquiry_status(
        {"enquiry_id": "enq-1", "status": "contacted", "note": "called"}, OWNER_USER, None)
    assert out["success"] is True
    assert _enquiry_state(fake_db) == rest_state
    assert rest_state["enquiries"][0]["status"] == "contacted"
    assert len(rest_state["enquiries"][0]["timeline"]) == 1


async def test_ai_enquiry_transition_guard_now_matches_rest(client, fake_db):
    """Regression: the legacy AI tool skipped the stage-transition guard."""
    _seed_enquiry(fake_db)
    principal = {"id": "pri-1", "role": "admin", "sub_category": "principal", "name": "P"}
    out = await tool_functions_v2.tool_update_enquiry_status(
        {"enquiry_id": "enq-1", "status": "enrolled"}, principal, None)
    assert out["success"] is False
    assert "Invalid enquiry transition" in out["message"]
    assert fake_db.enquiries.docs[0]["status"] == "new"


# ─── Incidents ───────────────────────────────────────────────────────────────

_INCIDENT = {"title": "Broken window", "description": "Window broken in lab",
             "severity": "low", "category": "general"}


def _incident_state(fake_db):
    return {
        "incidents": _mask(fake_db.incidents.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("action") == "incident_create"]),
    }


async def test_create_incident_parity(client, fake_db):
    resp = client.post("/api/ops/incidents", json=_INCIDENT, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _incident_state(fake_db)

    _clear(fake_db, ("incidents", "audit_logs"))
    out = await tool_functions_v2.tool_create_incident(dict(_INCIDENT), OWNER_USER, None)
    assert out["success"] is True
    assert _incident_state(fake_db) == rest_state
    assert rest_state["incidents"][0]["status"] == "open"
    assert len(rest_state["audit"]) == 1
