"""Dual-entrypoint parity for the deletes added on 2026-08-07 (owner instruction).

Flo could create nine kinds of record and remove none of them. Each new delete is a
thin adapter over the same domain service its REST route calls, so these prove the two
doors leave the database in the same state - and that the "still in use" guard fires
identically whichever door you come through.

`delete_enquiry` covers records made by both `create_enquiry` and `create_crm_lead`:
they write to one collection, so one delete undoes either.
"""

from __future__ import annotations

import copy

import pytest

from ai import tool_functions_v2
from middleware.auth import create_jwt

_VOLATILE = {
    "id", "_id", "entity_id", "record_id", "structure_id", "incident_id", "cert_id",
    "enquiry_id", "product_id", "staff_id", "student_id", "serial_number",
    "created_at", "updated_at", "deactivated_at", "timestamp", "changed_by",
    "logged_by", "created_by", "requested_by",
}

OWNER_USER = {"id": "owner-1", "role": "owner", "sub_category": "owner", "name": "Aman Litt"}
OWNER_HEADERS = {"Authorization": f"Bearer {create_jwt({'user_id': 'owner-1', 'role': 'owner', 'sub_category': 'owner', 'name': 'Aman Litt'})}"}


def _mask_one(d):
    return {k: v for k, v in d.items() if k not in _VOLATILE}


def _mask(docs):
    out = []
    for d in docs:
        m = _mask_one(d)
        changes = m.get("changes")
        if isinstance(changes, dict):
            m = {**m, "changes": {
                k: (_mask_one(v) if isinstance(v, dict) else v) for k, v in changes.items()
            }}
        out.append(m)
    out.sort(key=lambda d: (str(d.get("action", "")), str(d.get("name", ""))))
    return out


def _is_delete_audit(row) -> bool:
    """Only the audit rows the DELETE itself wrote.

    The setup step creates the record through REST in both halves of each test, and
    creation writes its own rows carrying fresh UUIDs inside `changes` (staff creation
    logs a `credential_issued` row naming the new staff id). Those belong to the create
    parity tests, not these - comparing them here would fail on identifiers that are
    supposed to differ.
    """
    action = str(row.get("action", ""))
    return "delete" in action or action.startswith("enrolment_")


def _snapshot(fake_db, *collections):
    snap = {c: _mask(copy.deepcopy(getattr(fake_db, c).docs)) for c in collections}
    snap["audit_logs"] = _mask(
        [r for r in copy.deepcopy(fake_db.audit_logs.docs) if _is_delete_audit(r)]
    )
    return snap


def _clear(fake_db, *collections):
    for c in (*collections, "audit_logs"):
        getattr(fake_db, c).docs[:] = []


# Every collection any test here writes to. Cleared before AND after each test:
# leaving a seeded row behind made an unrelated fee-config guardrail test fail, because
# it asserts on `fee_structures.docs[0]` and found ours.
_TOUCHED = (
    "fee_structures", "fee_transactions", "incidents", "certificates",
    # NOT auth_users: the session-scoped login fixture lives there, and emptying it
    # made every later auth test fail with "user_not_found".
    "students", "staff", "legal_entities", "enquiries",
    "crm_activities", "crm_contact_keys", "crm_opportunities",
    "commercial_products", "retail_sales", "audit_logs",
)


@pytest.fixture(autouse=True)
def _ai_uses_the_same_db(fake_db, monkeypatch):
    monkeypatch.setattr(tool_functions_v2, "get_db", lambda: fake_db)
    _clear(fake_db, *_TOUCHED)
    yield
    _clear(fake_db, *_TOUCHED)


# ── Fee structure ────────────────────────────────────────────────────────────

def _structure_payload():
    return {
        "name": "Class 1 Tuition", "class_id": "class-1",
        "fee_heads": [{"name": "Tuition", "amount": 1000, "frequency": "monthly"}],
        "academic_year": "2026-27",
    }


async def test_delete_fee_structure_ai_and_rest_identical(client, fake_db):
    _clear(fake_db, "fee_structures")
    created = client.post("/api/fees/structures", headers=OWNER_HEADERS, json=_structure_payload())
    sid = created.json()["data"]["id"]
    assert client.delete(f"/api/fees/structures/{sid}", headers=OWNER_HEADERS).status_code == 200
    rest_state = _snapshot(fake_db, "fee_structures")

    _clear(fake_db, "fee_structures")
    client.post("/api/fees/structures", headers=OWNER_HEADERS, json=_structure_payload())
    sid2 = fake_db.fee_structures.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_fee_structure({"structure_id": sid2}, OWNER_USER, None)

    assert out["success"] is True
    assert _snapshot(fake_db, "fee_structures") == rest_state
    assert fake_db.fee_structures.docs == []


async def test_a_fee_structure_with_charges_is_refused_through_both_doors(client, fake_db):
    _clear(fake_db, "fee_structures", "fee_transactions")
    created = client.post("/api/fees/structures", headers=OWNER_HEADERS, json=_structure_payload())
    sid = created.json()["data"]["id"]
    fake_db.fee_transactions.docs.append({
        "id": "txn-1", "_id": "txn-1", "schoolId": "aaryans-joya",
        "structure_id": sid, "amount": 1000, "status": "pending",
    })

    rest = client.delete(f"/api/fees/structures/{sid}", headers=OWNER_HEADERS)
    ai = await tool_functions_v2.tool_delete_fee_structure({"structure_id": sid}, OWNER_USER, None)

    assert rest.status_code == 409
    assert ai["success"] is False
    assert "charge" in ai["message"].lower()
    assert len(fake_db.fee_structures.docs) == 1, "the structure must survive both refusals"


# ── Incident ─────────────────────────────────────────────────────────────────

def _incident_payload():
    return {"description": "Broken window in the corridor", "severity": "low", "title": "Window"}


async def test_delete_incident_ai_and_rest_identical(client, fake_db):
    _clear(fake_db, "incidents")
    client.post("/api/ops/incidents", headers=OWNER_HEADERS, json=_incident_payload())
    iid = fake_db.incidents.docs[0]["id"]
    assert client.delete(f"/api/ops/incidents/{iid}", headers=OWNER_HEADERS).status_code == 200
    rest_state = _snapshot(fake_db, "incidents")

    _clear(fake_db, "incidents")
    client.post("/api/ops/incidents", headers=OWNER_HEADERS, json=_incident_payload())
    iid2 = fake_db.incidents.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_incident({"incident_id": iid2}, OWNER_USER, None)

    assert out["success"] is True
    assert _snapshot(fake_db, "incidents") == rest_state
    assert fake_db.incidents.docs == []


async def test_a_resolved_incident_is_refused_through_both_doors(client, fake_db):
    """A resolved incident is the school's safeguarding record and must survive."""
    _clear(fake_db, "incidents")
    client.post("/api/ops/incidents", headers=OWNER_HEADERS, json=_incident_payload())
    fake_db.incidents.docs[0]["status"] = "resolved"
    iid = fake_db.incidents.docs[0]["id"]

    rest = client.delete(f"/api/ops/incidents/{iid}", headers=OWNER_HEADERS)
    ai = await tool_functions_v2.tool_delete_incident({"incident_id": iid}, OWNER_USER, None)

    assert rest.status_code == 409
    assert ai["success"] is False
    assert len(fake_db.incidents.docs) == 1


# ── Certificate ──────────────────────────────────────────────────────────────

def _seed_certificate(fake_db, status="pending_approval"):
    fake_db.certificates.docs[:] = [{
        "id": "cert-1", "_id": "cert-1", "schoolId": "aaryans-joya",
        "student_id": "stu-1", "cert_type": "bonafide", "status": status,
        "serial_number": "CERT20260807ABCDEF", "requested_by": "owner-1",
    }]
    return "cert-1"


async def test_delete_certificate_ai_and_rest_identical(client, fake_db):
    _clear(fake_db, "certificates")
    cid = _seed_certificate(fake_db)
    assert client.delete(f"/api/ops/certificates/{cid}", headers=OWNER_HEADERS).status_code == 200
    rest_state = _snapshot(fake_db, "certificates")

    _clear(fake_db, "certificates")
    cid2 = _seed_certificate(fake_db)
    out = await tool_functions_v2.tool_delete_certificate({"cert_id": cid2}, OWNER_USER, None)

    assert out["success"] is True
    assert _snapshot(fake_db, "certificates") == rest_state
    assert fake_db.certificates.docs == []


async def test_an_issued_certificate_is_refused_through_both_doors(client, fake_db):
    """The family may be holding the printed copy - its serial must keep meaning something."""
    _clear(fake_db, "certificates")
    cid = _seed_certificate(fake_db, status="generated")

    rest = client.delete(f"/api/ops/certificates/{cid}", headers=OWNER_HEADERS)
    ai = await tool_functions_v2.tool_delete_certificate({"cert_id": cid}, OWNER_USER, None)

    assert rest.status_code == 422
    assert ai["success"] is False
    assert len(fake_db.certificates.docs) == 1


# ── Student and staff (off the roll, not destroyed) ──────────────────────────

async def test_delete_student_ai_and_rest_identical(client, fake_db):
    _clear(fake_db, "students")
    payload = {"name": "Test Pupil", "admission_number": "ADM-DEL-9", "class_id": "class-1"}
    created = client.post("/api/students", headers=OWNER_HEADERS, json=payload)
    sid = created.json()["data"]["id"]
    assert client.delete(f"/api/students/{sid}", headers=OWNER_HEADERS).status_code == 200
    rest_state = _snapshot(fake_db, "students")

    _clear(fake_db, "students")
    client.post("/api/students", headers=OWNER_HEADERS, json=payload)
    sid2 = fake_db.students.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_student({"student_id": sid2}, OWNER_USER, None)

    assert out["success"] is True
    assert _snapshot(fake_db, "students") == rest_state
    # Neither door destroys the record.
    assert len(fake_db.students.docs) == 1
    assert fake_db.students.docs[0]["is_active"] is False


async def test_delete_staff_ai_and_rest_identical(client, fake_db):
    _clear(fake_db, "staff")
    payload = {
        "name": "Test Teacher", "staff_type": "teacher", "department": "Math",
        "phone": "9220000009", "employee_id": "EMP-DEL", "password": "FixedPass1",
    }
    created = client.post("/api/staff/", headers=OWNER_HEADERS, json=payload)
    stid = created.json()["data"]["id"]
    assert client.delete(f"/api/staff/{stid}", headers=OWNER_HEADERS).status_code == 200
    rest_state = _snapshot(fake_db, "staff")

    _clear(fake_db, "staff")
    client.post("/api/staff/", headers=OWNER_HEADERS, json=payload)
    stid2 = fake_db.staff.docs[0]["id"]
    out = await tool_functions_v2.tool_delete_staff({"staff_id": stid2}, OWNER_USER, None)

    assert out["success"] is True
    assert _snapshot(fake_db, "staff") == rest_state
    assert len(fake_db.staff.docs) == 1
    assert fake_db.staff.docs[0]["is_active"] is False


# ── Commercial three ─────────────────────────────────────────────────────────

def _seed_entity(fake_db, **overrides):
    doc = {
        "id": "ent-1", "_id": "ent-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "name": "Second Trust Arm", "code": "STA", "entity_type": "trust",
        "is_default": False, "owns_legacy_records": False, "is_active": True,
    }
    doc.update(overrides)
    fake_db.legal_entities.docs[:] = [doc]
    return doc["id"]


async def test_delete_legal_entity_ai_and_rest_identical(client, fake_db):
    _clear(fake_db, "legal_entities")
    eid = _seed_entity(fake_db)
    assert client.delete(f"/api/commercial/entities/{eid}", headers=OWNER_HEADERS).status_code == 200
    rest_state = _snapshot(fake_db, "legal_entities")

    _clear(fake_db, "legal_entities")
    eid2 = _seed_entity(fake_db)
    out = await tool_functions_v2.tool_delete_legal_entity({"entity_id": eid2}, OWNER_USER, None)

    assert out["success"] is True
    assert _snapshot(fake_db, "legal_entities") == rest_state
    assert fake_db.legal_entities.docs == []


async def test_the_operating_entity_is_refused_through_both_doors(client, fake_db):
    """Deleting the default would orphan every legacy record attributed to it."""
    _clear(fake_db, "legal_entities")
    eid = _seed_entity(fake_db, is_default=True, owns_legacy_records=True)

    rest = client.delete(f"/api/commercial/entities/{eid}", headers=OWNER_HEADERS)
    ai = await tool_functions_v2.tool_delete_legal_entity({"entity_id": eid}, OWNER_USER, None)

    assert rest.status_code == 409
    assert ai["success"] is False
    assert len(fake_db.legal_entities.docs) == 1


async def test_an_enquiry_that_became_a_student_is_refused_through_both_doors(client, fake_db):
    _clear(fake_db, "enquiries")
    fake_db.enquiries.docs[:] = [{
        "id": "enq-1", "_id": "enq-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "student_name": "Prospect", "phone": "9000000002", "status": "converted",
        "student_id": "stu-99",
    }]

    rest = client.delete("/api/commercial/crm/leads/enq-1", headers=OWNER_HEADERS)
    ai = await tool_functions_v2.tool_delete_enquiry({"enquiry_id": "enq-1"}, OWNER_USER, None)

    assert rest.status_code == 409
    assert ai["success"] is False
    assert len(fake_db.enquiries.docs) == 1


async def test_a_product_that_has_been_sold_is_refused_through_both_doors(client, fake_db):
    _clear(fake_db, "commercial_products", "retail_sales")
    fake_db.commercial_products.docs[:] = [{
        "id": "prod-1", "_id": "prod-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "entity_id": "ent-1", "sku": "TIE-01", "name": "School Tie", "is_active": True,
    }]
    fake_db.retail_sales.docs[:] = [{
        "id": "sale-1", "_id": "sale-1", "schoolId": "aaryans-joya", "branch_id": "branch-joya",
        "entity_id": "ent-1", "lines": [{"product_id": "prod-1", "quantity": 1}],
    }]

    rest = client.delete("/api/commercial/products/prod-1", headers=OWNER_HEADERS)
    ai = await tool_functions_v2.tool_delete_retail_product({"product_id": "prod-1"}, OWNER_USER, None)

    assert rest.status_code == 409
    assert ai["success"] is False
    assert len(fake_db.commercial_products.docs) == 1
