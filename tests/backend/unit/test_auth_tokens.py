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


# ─── Part 1 (Auth + RBAC) - adversarial concurrency tests ──────────────────


@pytest.mark.asyncio
async def test_concurrent_refresh_only_one_succeeds():
    """Two simultaneous consume_refresh_token calls on the same token.

    Exactly one must succeed (rotate the token); the other must raise 401.

    Part 1.5 Patch C: the previous version of this test ran on a FakeCollection
    whose async methods had no await yield points, so `asyncio.gather` ran the
    two consumers strictly sequentially and the test passed *for the wrong
    reason* - it would have remained green even if the atomic guard
    `update_one({revoked_at: None}, ...)` were dropped from production code.

    The RaceyCollection below interleaves the two consumers deterministically:
    both reach `update_one` before either completes, so the modified_count
    guard is the only thing distinguishing winner from loser. If the guard
    is removed, BOTH writers succeed and the test fails.
    """
    import asyncio

    class RaceyCollection(FakeCollection):
        """Forces the two consumers to both reach update_one before either applies.

        Strategy: a barrier counter - when the first update_one arrives we
        suspend until the second one arrives; then both proceed and the
        `revoked_at: None` predicate eliminates the loser.
        """
        def __init__(self):
            super().__init__()
            self._barrier = asyncio.Event()
            self._arrived = 0
            self._expected = 2

        async def update_one(self, query, update):
            self._arrived += 1
            if self._arrived >= self._expected:
                # Last arriver releases everyone.
                self._barrier.set()
            else:
                # First arriver waits for the second.
                await asyncio.wait_for(self._barrier.wait(), timeout=1.0)
            # Now both apply, but the second sees revoked_at already set.
            return await super().update_one(query, update)

    db = FakeDb()
    db.refresh_tokens = RaceyCollection()
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
    """Revoke twice - second call is a no-op (no exception, no second update)."""
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-1")

    await auth_tokens.revoke_refresh_token(db, raw, reason="logout")
    await auth_tokens.revoke_refresh_token(db, raw, reason="logout")
    # The second revoke leaves the token in its already-revoked state.
    assert db.refresh_tokens.docs[0]["revoked_reason"] == "logout"


@pytest.mark.asyncio
async def test_revoke_refresh_token_returns_modified_count():
    """Part 1.5 Patch L: revoke_refresh_token reports outcome to caller."""
    db = FakeDb()
    raw = await auth_tokens.issue_refresh_token(db, "user-rc")

    first = await auth_tokens.revoke_refresh_token(db, raw, reason="logout")
    assert first == 1
    # Second call hits an already-revoked record → 0.
    second = await auth_tokens.revoke_refresh_token(db, raw, reason="logout")
    assert second == 0


@pytest.mark.asyncio
async def test_revoke_unknown_token_returns_zero():
    db = FakeDb()
    n = await auth_tokens.revoke_refresh_token(db, "nope-not-a-real-token")
    assert n == 0


def test_clear_refresh_cookie_evicts_both_paths():
    """Part 1.5 Patch F: logout must clear cookies at both / and /api/auth.

    Pre-deploy users have cookies stored at the old /api/auth path. Without
    the dual-clear those zombie cookies leak for 7 days and can cause
    intermittent logout/login loops.
    """
    from fastapi import Response
    from services import auth_tokens as at

    response = Response()
    at.clear_refresh_cookie(response)

    set_cookie_headers = [
        v for k, v in response.raw_headers if k.lower() == b"set-cookie"
    ]
    # Two delete-cookie headers, one per path.
    paths = [h for h in set_cookie_headers if b"eduflow_refresh_token=" in h]
    assert len(paths) == 2, f"expected 2 delete-cookie headers, got: {paths}"
    joined = b" || ".join(paths).decode("utf-8")
    assert "Path=/api/auth" in joined
    # `Path=/` will substring-match both - assert a header exists with exactly Path=/;
    assert any(b"Path=/;" in h or h.rstrip(b"; ").endswith(b"Path=/") for h in paths), joined


# ─── The refresh cookie has to survive a cross-site request ──────────────────
#
# Owner request 3, 2026-08-06. The cookie was SameSite=Strict, and the site
# (amplifyapp.com) and the API (cloudfront.net) are different registrable domains,
# so the browser never attached it to /api/auth/refresh. The silent renewal could
# not run, and every person was signed out exactly JWT_EXPIRY_MINUTES after signing
# in regardless of what they were doing. These tests are what notices if someone
# "hardens" it back to strict without also putting both onto one domain.


def _samesite_with_environment(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", value)
    return auth_tokens.cookie_samesite()


def test_production_refresh_cookie_is_samesite_none(monkeypatch):
    assert _samesite_with_environment(monkeypatch, "production") == "none"


def test_production_refresh_cookie_is_secure_because_none_requires_it(monkeypatch):
    # SameSite=None without Secure is rejected outright by every current browser,
    # so these two must move together.
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert auth_tokens.cookie_samesite() == "none"
    assert auth_tokens.cookie_secure() is True


@pytest.mark.parametrize("environment", [None, "development", "staging", "test"])
def test_non_production_keeps_the_stricter_setting(monkeypatch, environment):
    # Off production the site and the API are both on localhost - same site - so
    # strict works and is the better choice. Secure would break plain http there.
    assert _samesite_with_environment(monkeypatch, environment) == "strict"
    assert auth_tokens.cookie_secure() is False


def test_every_cookie_call_uses_the_same_setting(monkeypatch):
    # Setting the cookie with one SameSite and deleting it with another leaves the
    # browser holding a cookie the server believes it removed.
    monkeypatch.setenv("ENVIRONMENT", "production")
    seen = []

    class RecordingResponse:
        def set_cookie(self, **kwargs):
            seen.append(kwargs["samesite"])

        def delete_cookie(self, **kwargs):
            seen.append(kwargs["samesite"])

    response = RecordingResponse()
    auth_tokens.set_refresh_cookie(response, "t")
    auth_tokens.clear_refresh_cookie(response)
    auth_tokens.clear_legacy_refresh_cookie(response)

    assert seen, "no cookie calls were recorded"
    assert set(seen) == {"none"}
