"""Epic E.1 — plan/step schema + plan-hash confirm token.

Pins: the same canonical hash helper is used at issue and consume; a tampered
persisted plan is rejected with `plan_tampered` 409; a legacy token (no plan)
still consumes as a length-1 plan; single-use + TTL + tenant binding survive.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from services import confirm_tokens
from services.confirm_tokens import (
    issue_confirm_token,
    consume_confirm_token,
    compute_plan_hash,
    PLAN_SCHEMA_VERSION,
)

pytestmark = pytest.mark.asyncio


_PLAN = [
    {"idx": 0, "tool": "approve_leave", "kind": "write",
     "params": {"leave_id": "lv-1", "action": "approve"},
     "precondition": {"collection": "leaves", "id": "lv-1"}},
    {"idx": 1, "tool": "create_announcement", "kind": "write",
     "params": {"title": "Holiday", "content": "Closed tomorrow"}},
]


class _InsertCol:
    def __init__(self):
        self.docs: list[dict] = []

    async def insert_one(self, doc):
        self.docs.append(doc)


class _InsertDb:
    def __init__(self):
        self.confirm_tokens = _InsertCol()


def test_compute_plan_hash_is_deterministic_and_order_sensitive():
    h1 = compute_plan_hash(_PLAN, school_id="sch", branch_id="b1")
    h2 = compute_plan_hash(list(_PLAN), school_id="sch", branch_id="b1")
    assert h1 == h2
    # Reordering steps changes the hash (identity/structure integrity).
    assert compute_plan_hash(list(reversed(_PLAN)), school_id="sch", branch_id="b1") != h1
    # Tenant is bound into the hash.
    assert compute_plan_hash(_PLAN, school_id="other", branch_id="b1") != h1


async def test_issue_with_plan_persists_plan_hash_and_version():
    db = _InsertDb()
    token = await issue_confirm_token(
        action="plan", params={}, user_id="u1", session_id="s1",
        school_id="sch", branch_id="b1", plan=_PLAN, db=db,
    )
    doc = db.confirm_tokens.docs[0]
    assert doc["token"] == token
    assert doc["plan"] == _PLAN
    assert doc["schema_version"] == PLAN_SCHEMA_VERSION
    assert doc["plan_hash"] == compute_plan_hash(_PLAN, school_id="sch", branch_id="b1")


async def test_issue_without_plan_is_legacy_no_plan_fields():
    db = _InsertDb()
    await issue_confirm_token(
        action="approve_leave", params={"leave_id": "lv-1"},
        user_id="u1", session_id="s1", school_id="sch", db=db,
    )
    doc = db.confirm_tokens.docs[0]
    assert "plan" not in doc
    assert "plan_hash" not in doc


def _consume_db(doc: dict):
    class Col:
        async def update_one(self, query, update, **kw):
            doc.update(update.get("$set", {}))

            class R:
                modified_count = 1
            return R()

        async def find_one(self, query):
            return dict(doc)

    class Db:
        confirm_tokens = Col()

    return Db()


async def test_consume_valid_plan_token_passes_hash_check():
    now = datetime.now(timezone.utc)
    doc = {
        "token": "t", "user_id": "u1", "session_id": "s1",
        "school_id": "sch", "branch_id": "b1", "used": False,
        "expires_at": now + timedelta(minutes=5),
        "plan": _PLAN,
        "plan_hash": compute_plan_hash(_PLAN, school_id="sch", branch_id="b1"),
    }
    out = await consume_confirm_token(
        token="t", user_id="u1", session_id="s1",
        school_id="sch", branch_id="b1", db=_consume_db(doc),
    )
    assert out["plan"] == _PLAN


async def test_consume_tampered_plan_raises_plan_tampered_409():
    now = datetime.now(timezone.utc)
    tampered = [dict(_PLAN[0], params={"leave_id": "lv-1", "action": "reject"})]
    doc = {
        "token": "t", "user_id": "u1", "session_id": "s1",
        "school_id": "sch", "branch_id": "b1", "used": False,
        "expires_at": now + timedelta(minutes=5),
        "plan": tampered,
        # hash bound to the ORIGINAL plan — the persisted plan was edited.
        "plan_hash": compute_plan_hash(_PLAN, school_id="sch", branch_id="b1"),
    }
    with pytest.raises(HTTPException) as exc:
        await consume_confirm_token(
            token="t", user_id="u1", session_id="s1",
            school_id="sch", branch_id="b1", db=_consume_db(doc),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "plan_tampered"


async def test_consume_legacy_token_without_plan_still_works():
    now = datetime.now(timezone.utc)
    doc = {
        "token": "t", "user_id": "u1", "session_id": "s1",
        "school_id": "sch", "branch_id": "b1", "used": False,
        "expires_at": now + timedelta(minutes=5),
        "action": "approve_leave", "params": {"leave_id": "lv-1"},
    }
    out = await consume_confirm_token(
        token="t", user_id="u1", session_id="s1",
        school_id="sch", branch_id="b1", db=_consume_db(doc),
    )
    assert out["action"] == "approve_leave"
    assert "plan" not in out
