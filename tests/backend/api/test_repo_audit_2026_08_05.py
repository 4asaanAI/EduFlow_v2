"""Regression guards for the 2026-08-05 full-repo audit (findings A-1 … A-7).

Each test names the finding it guards and fails on the pre-fix code. The audit
report is `_bmad-output/planning-artifacts/repo-audit-findings-2026-08-05.md`.
"""

from __future__ import annotations

import os

import pytest
from jose import jwt

from middleware.auth import create_jwt

def _headers(user_id: str, role: str, sub_category: str | None = None, branch_id: str = "branch-a"):
    payload = {"user_id": user_id, "role": role, "name": user_id, "branch_id": branch_id}
    if sub_category:
        payload["sub_category"] = sub_category
    return {"Authorization": f"Bearer {create_jwt(payload)}"}


@pytest.fixture(autouse=True)
def _clean(fake_db):
    names = (
        "legal_entities", "commercial_sequences", "enquiries", "crm_activities", "crm_contact_keys",
        "crm_opportunities", "commercial_products", "pos_shifts", "retail_sales",
        "retail_returns", "retail_idempotency", "retail_return_idempotency",
        "inventory_items", "stock_movements", "audit_logs", "students", "guardians",
    )
    originals = {name: list(getattr(fake_db, name).docs) for name in names}
    for name in names:
        getattr(fake_db, name).docs[:] = []
    yield
    for name, docs in originals.items():
        getattr(fake_db, name).docs[:] = docs


# ── A-1: the CRM contact reservation is tenant-safe ──────────────────────────

async def test_a1_two_schools_may_share_a_parent_phone(fake_db):
    """The global unique index on `contact_hash` must not block a second tenant.

    The audit flagged `create_index("contact_hash", unique=True)` as unscoped. It is
    safe because the digest embeds schoolId and branch_id. This proves it, so nobody
    "fixes" the index into a compound one on the strength of the index definition alone.
    """
    from services.actor_context import ActorContext
    from services.commercial_service import _reserve_crm_contacts

    def _actor(school_id: str, branch_id: str) -> ActorContext:
        return ActorContext(
            user_id="u1", role="owner", sub_category=None,
            school_id=school_id, branch_id=branch_id,
        )

    await _reserve_crm_contacts(
        fake_db, _actor("aaryans-joya", "branch-a"), "enq-1", "9999999999", "shared@example.com",
    )
    # Same phone AND same email, different school: must be allowed.
    await _reserve_crm_contacts(
        fake_db, _actor("other-school", "branch-a"), "enq-2", "9999999999", "shared@example.com",
    )
    # Same phone, same school, different branch: also a distinct reservation.
    await _reserve_crm_contacts(
        fake_db, _actor("aaryans-joya", "branch-b"), "enq-3", "9999999999", "shared@example.com",
    )
    digests = {doc["contact_hash"] for doc in fake_db.crm_contact_keys.docs}
    assert len(digests) == 6, "each (school, branch, kind, value) must reserve its own digest"


# ── A-3: the opportunity update runs inside a transaction ────────────────────

def test_a3_opportunity_update_accepts_a_session():
    """`update_opportunity` was the one commercial write with no `session` parameter,
    so routing it through the transactional wrapper would have raised TypeError."""
    import inspect

    from services.commercial_service import update_opportunity

    signature = inspect.signature(update_opportunity)
    assert "session" in signature.parameters
    assert signature.parameters["session"].kind is inspect.Parameter.KEYWORD_ONLY


def test_a3_opportunity_stage_change_still_succeeds(client, fake_db):
    owner = _headers("owner-1", "owner")
    entity = client.post("/api/commercial/entities", headers=owner, json={
        "name": "The Aaryans School", "code": "TAS", "entity_type": "school",
    })
    assert entity.status_code == 200, entity.text
    entity_id = entity.json()["data"]["id"]
    lead = client.post("/api/commercial/crm/leads", headers=owner, json={
        "entity_id": entity_id, "student_name": "Aarav Singh", "phone": "9111111111",
    })
    assert lead.status_code == 200, lead.text
    opportunity = client.post(
        f"/api/commercial/crm/leads/{lead.json()['data']['id']}/opportunities",
        headers=owner, json={"title": "Class 5 admission", "amount": 48000, "probability": 60},
    )
    assert opportunity.status_code == 200, opportunity.text
    opportunity_id = opportunity.json()["data"]["id"]

    lost_without_reason = client.patch(
        f"/api/commercial/crm/opportunities/{opportunity_id}", headers=owner, json={"stage": "lost"},
    )
    assert lost_without_reason.status_code == 400

    won = client.patch(
        f"/api/commercial/crm/opportunities/{opportunity_id}", headers=owner, json={"stage": "won"},
    )
    assert won.status_code == 200, won.text
    assert won.json()["data"]["probability"] == 100


# ── A-4: one definition of the single-branch fallback ────────────────────────

def test_a4_branch_fallback_has_exactly_one_definition():
    from pathlib import Path

    from school_identity import DEFAULT_BRANCH_ID, default_branch_id

    assert default_branch_id() == DEFAULT_BRANCH_ID == "branch-joya"

    backend = Path(__file__).resolve().parents[2].parent / "backend"
    offenders = []
    for path in backend.rglob("*.py"):
        # school_identity owns the value; the seed scripts CREATE the branch record,
        # so naming it there is the data itself, not a fallback.
        if path.name == "school_identity.py" or path.name.startswith("seed_"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for number, line in enumerate(text.splitlines(), start=1):
            if '"branch-joya"' in line and not line.lstrip().startswith("#"):
                offenders.append(f"{path.name}:{number}")
    assert offenders == [], (
        "the single-branch fallback must come from school_identity.default_branch_id(); "
        f"literal found at {offenders}"
    )


def test_a4_branch_fallback_is_environment_overridable(monkeypatch):
    from school_identity import default_branch_id

    monkeypatch.setenv("DEFAULT_BRANCH_ID", "branch-second")
    assert default_branch_id() == "branch-second"


# ── A-5: a federation token with no expiry is refused ────────────────────────

_FED_SECRET = "test-federation-secret"


def _federation_token(*, with_exp: bool, role: str = "federation_reader") -> str:
    from datetime import datetime, timedelta, timezone

    claims = {"aud": "layaa-healthcheck-platform", "iss": "eduflow", "role": role}
    if with_exp:
        claims["exp"] = datetime.now(timezone.utc) + timedelta(minutes=10)
    return jwt.encode(claims, _FED_SECRET, algorithm="HS256")


def test_a5_federation_rejects_a_token_that_never_expires(client, monkeypatch):
    monkeypatch.setenv("FEDERATION_JWT_SECRET", _FED_SECRET)
    forever = _federation_token(with_exp=False)
    response = client.get(
        "/api/federation/products", headers={"Authorization": f"Bearer {forever}"}
    )
    assert response.status_code == 401


def test_a5_federation_accepts_a_normal_token(client, monkeypatch):
    monkeypatch.setenv("FEDERATION_JWT_SECRET", _FED_SECRET)
    response = client.get(
        "/api/federation/products",
        headers={"Authorization": f"Bearer {_federation_token(with_exp=True)}"},
    )
    assert response.status_code == 200
    assert response.json()[0]["slug"] == "the-aaryans"


def test_a5_federation_still_refuses_the_wrong_role_and_no_token(client, monkeypatch):
    monkeypatch.setenv("FEDERATION_JWT_SECRET", _FED_SECRET)
    assert client.get("/api/federation/products").status_code == 401
    wrong = _federation_token(with_exp=True, role="someone_else")
    assert client.get(
        "/api/federation/products", headers={"Authorization": f"Bearer {wrong}"}
    ).status_code == 403


# ── A-2 and A-7 removed with campus retail, 2026-08-14 ──────────────────────
#
# Two audit findings from 2026-08-05 were proven here on the till: A-2, that a reused
# idempotency key replays the original sale instead of surfacing a raw database error in
# chat, and A-7, that a multi-line cart reads its products in ONE query rather than one
# per line.
#
# Both tests went with the feature. **The lessons did not, and are worth carrying:**
# a Flo tool must never let a raw database error escape to the person, and a batch write
# must not issue a query per line. Neither has another exercise in this file today.
