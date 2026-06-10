"""Wave-2 dual-entrypoint parity — assets, visitor log, certificates.

Same seed through both write entrypoints (REST routes in `routes/operations.py`
via TestClient, and the AI tools via their real dispatch fns) → identical DB
state except the volatile allowlist. Covers:
  create_asset / update_asset / delete_asset      → services/asset_service.py
  log_visitor / checkout_visitor / delete_visitor → services/visitor_service.py
  create_certificate / decide_certificate         → services/certificate_service.py
"""

from __future__ import annotations

import copy

import pytest
from middleware.auth import create_jwt

from ai import tool_functions_v2

pytestmark = pytest.mark.asyncio

_VOLATILE = {"id", "_id", "created_at", "updated_at", "timestamp", "entity_id", "record_id",
             "time_in", "time_out", "serial_number", "issued_date", "approved_at",
             "rejected_at", "source_id"}

OWNER_USER = {"id": "own-1", "role": "owner", "name": "Owner"}
SCHOOL = "aaryans-joya"


def _owner_headers():
    t = create_jwt({"user_id": "own-1", "role": "owner", "name": "Owner"})
    return {"Authorization": f"Bearer {t}"}


def _scrub(value):
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _mask(docs):
    out = [_scrub(d) for d in copy.deepcopy(docs)]
    return sorted(out, key=lambda d: str(sorted(d.items())))


_COLS = ("assets", "visitor_log", "certificates", "audit_logs", "notifications")


def _clear(fake_db, cols=_COLS):
    for col in cols:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _ai_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db)
    yield
    _clear(fake_db)


# ─── Assets ──────────────────────────────────────────────────────────────────

_ASSET = {"name": "Projector", "category": "electronics", "quantity": 2,
          "location": "Lab 1", "status": "good"}


def _asset_state(fake_db):
    return {
        "assets": _mask(fake_db.assets.docs),
        "audit": _mask([a for a in fake_db.audit_logs.docs if a.get("entity_type") == "asset"]),
    }


def _seed_asset(fake_db):
    fake_db.assets.docs[:] = [{
        "_id": "asset-1", "id": "asset-1", "schoolId": SCHOOL, "name": "Projector",
        "category": "electronics", "quantity": 2, "location": "Lab 1", "status": "good",
        "purchase_date": "", "maintenance_due": "", "created_by": "own-1",
        "created_by_role": "owner", "created_by_sub_category": "",
    }]


async def test_create_asset_parity(client, fake_db):
    resp = client.post("/api/ops/assets", json=_ASSET, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _asset_state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_create_asset(dict(_ASSET), OWNER_USER, None)
    assert out["success"] is True
    assert _asset_state(fake_db) == rest_state
    assert len(rest_state["audit"]) == 1


async def test_update_asset_parity(client, fake_db):
    _seed_asset(fake_db)
    resp = client.patch("/api/ops/assets/asset-1", json={"quantity": 5, "status": "needs_repair"},
                        headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _asset_state(fake_db)

    _clear(fake_db)
    _seed_asset(fake_db)
    out = await tool_functions_v2.tool_update_asset(
        {"asset_id": "asset-1", "quantity": 5, "status": "needs_repair"}, OWNER_USER, None)
    assert out["success"] is True
    assert _asset_state(fake_db) == rest_state
    assert rest_state["assets"][0]["quantity"] == 5


async def test_delete_asset_parity(client, fake_db):
    _seed_asset(fake_db)
    resp = client.delete("/api/ops/assets/asset-1", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _asset_state(fake_db)

    _clear(fake_db)
    _seed_asset(fake_db)
    out = await tool_functions_v2.tool_delete_asset({"asset_id": "asset-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert _asset_state(fake_db) == rest_state
    assert rest_state["assets"] == []
    assert len(rest_state["audit"]) == 1  # F.10 deletion audit


# ─── Visitors ────────────────────────────────────────────────────────────────

_VISITOR = {"visitor_name": "Mr Verma", "phone": "9888877777", "purpose": "fee enquiry",
            "whom_to_meet": "Accountant", "id_type": "aadhaar"}


def _visitor_state(fake_db):
    return {"visitor_log": _mask(fake_db.visitor_log.docs)}


async def test_log_visitor_parity(client, fake_db):
    resp = client.post("/api/ops/visitors", json=_VISITOR, headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _visitor_state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_log_visitor(dict(_VISITOR), OWNER_USER, None)
    assert out["success"] is True
    assert _visitor_state(fake_db) == rest_state


async def test_duplicate_visitor_blocked_on_both_entrypoints(client, fake_db):
    first = await tool_functions_v2.tool_log_visitor(dict(_VISITOR), OWNER_USER, None)
    assert first["success"] is True
    resp = client.post("/api/ops/visitors", json=_VISITOR, headers=_owner_headers())
    assert resp.status_code == 409
    again = await tool_functions_v2.tool_log_visitor(dict(_VISITOR), OWNER_USER, None)
    assert again["success"] is False
    assert "force" in again["message"]
    assert len(fake_db.visitor_log.docs) == 1


async def test_checkout_and_delete_visitor_parity(client, fake_db):
    seed = {"_id": "vis-1", "id": "vis-1", "schoolId": SCHOOL, "visitor_name": "Mr Verma",
            "phone": "", "purpose": "x", "whom_to_meet": "", "id_type": "",
            "time_in": "2026-06-10T09:00:00", "time_out": None, "force_override": False}
    fake_db.visitor_log.docs[:] = [dict(seed)]
    resp = client.patch("/api/ops/visitors/vis-1/checkout", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _visitor_state(fake_db)

    fake_db.visitor_log.docs[:] = [dict(seed)]
    out = await tool_functions_v2.tool_checkout_visitor({"visitor_id": "vis-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert _visitor_state(fake_db) == rest_state
    assert fake_db.visitor_log.docs[0]["time_out"] is not None

    out = await tool_functions_v2.tool_delete_visitor({"visitor_id": "vis-1"}, OWNER_USER, None)
    assert out["success"] is True
    assert fake_db.visitor_log.docs == []
    assert any(a.get("entity_type") == "visitor_log" and a.get("action") == "delete"
               for a in fake_db.audit_logs.docs)  # F.10 deletion audit


# ─── Certificates ────────────────────────────────────────────────────────────

def _cert_state(fake_db):
    return {
        "certificates": _mask(fake_db.certificates.docs),
        "notifications": _mask(fake_db.notifications.docs),
    }


async def test_create_certificate_parity_owner_auto_issues(client, fake_db):
    body = {"student_id": "stu-1", "cert_type": "bonafide"}
    resp = client.post("/api/ops/certificates", json=body, headers=_owner_headers())
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "generated"  # owner auto-issues
    rest_state = _cert_state(fake_db)

    _clear(fake_db)
    out = await tool_functions_v2.tool_create_certificate(dict(body), OWNER_USER, None)
    assert out["success"] is True
    assert _cert_state(fake_db) == rest_state


def _seed_pending_cert(fake_db):
    fake_db.certificates.docs[:] = [{
        "_id": "cert-1", "id": "cert-1", "schoolId": SCHOOL, "student_id": "stu-1",
        "cert_type": "tc", "serial_number": "CERT20260610AAAAAA", "content_data": {},
        "status": "pending_approval", "issued_date": None, "issued_by": None,
        "requested_by": "teacher-1", "created_at": "2026-06-10T08:00:00",
    }]


async def test_decide_certificate_approve_parity(client, fake_db):
    _seed_pending_cert(fake_db)
    resp = client.patch("/api/ops/certificates/cert-1/approve", headers=_owner_headers())
    assert resp.status_code == 200
    rest_state = _cert_state(fake_db)

    _clear(fake_db)
    _seed_pending_cert(fake_db)
    out = await tool_functions_v2.tool_decide_certificate(
        {"cert_id": "cert-1", "decision": "approve"}, OWNER_USER, None)
    assert out["success"] is True
    assert _cert_state(fake_db) == rest_state
    assert rest_state["certificates"][0]["status"] == "generated"
    assert len(rest_state["notifications"]) == 1  # requester notified


async def test_decide_certificate_state_guard_both_entrypoints(client, fake_db):
    _seed_pending_cert(fake_db)
    fake_db.certificates.docs[0]["status"] = "generated"
    resp = client.patch("/api/ops/certificates/cert-1/approve", headers=_owner_headers())
    assert resp.status_code == 422
    out = await tool_functions_v2.tool_decide_certificate(
        {"cert_id": "cert-1", "decision": "approve"}, OWNER_USER, None)
    assert out["success"] is False
