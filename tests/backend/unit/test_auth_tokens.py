from datetime import timedelta

import pytest
from fastapi import HTTPException

from backend.services import auth_tokens


class FakeCollection:
    def __init__(self):
        self.docs = []
        self.modified_count = 0

    async def insert_one(self, doc):
        doc = {**doc, "_id": len(self.docs) + 1}
        self.docs.append(doc)

    async def find_one(self, query):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                return doc
        return None

    async def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                self.modified_count = 1
                return type("Result", (), {"modified_count": 1})()
        return type("Result", (), {"modified_count": 0})()

    async def update_many(self, query, update):
        count = 0
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update.get("$set", {}))
                count += 1
        return type("Result", (), {"modified_count": count})()


class FakeDb:
    def __init__(self):
        self.refresh_tokens = FakeCollection()


@pytest.mark.asyncio
async def test_refresh_token_is_single_use():
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-1")

    record = await auth_tokens.consume_refresh_token(db, raw)

    assert record["user_id"] == "user-1"
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "rotated"
    with pytest.raises(HTTPException) as exc:
        await auth_tokens.consume_refresh_token(db, raw)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_refresh_token_rejected():
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-1")
    db.refresh_tokens.docs[0]["expires_at"] = auth_tokens.utc_now() - timedelta(seconds=1)

    with pytest.raises(HTTPException) as exc:
        await auth_tokens.consume_refresh_token(db, raw)

    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_revoke_user_refresh_tokens():
    db = FakeDb()
    await auth_tokens.issue_refresh_token(db, "user-1")
    await auth_tokens.issue_refresh_token(db, "user-2")

    count = await auth_tokens.revoke_user_refresh_tokens(db, "user-1")

    assert count == 1
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "user_deactivated"
    assert db.refresh_tokens.docs[1]["revoked_at"] is None


# ─── Part 1 (Auth + RBAC) — adversarial concurrency tests ──────────────────


@pytest.mark.asyncio
async def test_concurrent_refresh_only_one_succeeds():
    """Two simultaneous consume_refresh_token calls on the same token.

    Exactly one must succeed (rotate the token); the other must raise 401.
    The atomic guard is `update_one({revoked_at: None}, {$set: {revoked_at}})`
    + `modified_count` check — verifies the second writer cannot also pass.
    """
    import asyncio

    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-race")

    results = await asyncio.gather(
        auth_tokens.consume_refresh_token(db, raw),
        auth_tokens.consume_refresh_token(db, raw),
        return_exceptions=True,
    )

    successes = [r for r in results if isinstance(r, dict)]
    failures = [r for r in results if isinstance(r, HTTPException)]
    assert len(successes) == 1, f"expected exactly 1 success, got {len(successes)}"
    assert len(failures) == 1, f"expected exactly 1 failure, got {len(failures)}"
    assert failures[0].status_code == 401


@pytest.mark.asyncio
async def test_concurrent_revoke_and_consume_revoke_wins():
    """If revocation lands first, the concurrent consume must fail.

    Models the password-reset-during-refresh scenario: user submits a password
    reset (revoking all refresh tokens) at the same moment another tab tries
    to refresh. The reset wins; the in-flight refresh fails closed.
    """
    import asyncio

    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-race")

    # Force ordering: revoke is awaited first, then consume.
    await auth_tokens.revoke_refresh_token(db, raw, reason="password_reset")
    with pytest.raises(HTTPException) as exc:
        await auth_tokens.consume_refresh_token(db, raw)
    assert exc.value.status_code == 401
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "password_reset"


@pytest.mark.asyncio
async def test_double_revoke_is_idempotent():
    """Revoke twice — second call is a no-op (no exception, no second update)."""
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-1")

    await auth_tokens.revoke_refresh_token(db, raw, reason="logout")
    await auth_tokens.revoke_refresh_token(db, raw, reason="logout")
    # The second revoke leaves the token in its already-revoked state.
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "logout"
