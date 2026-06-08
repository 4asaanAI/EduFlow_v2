"""Fixtures for the real-Mongo replica-set test tier (AI Layer Hardening, AD12 / Story D.1).

FakeDb (`tests/backend/conftest.py`) cannot honor multi-document transactions,
session causality, or unique-index enforcement, so the atomicity / idempotency /
precondition / dry-run guarantees of Epic D (AD4–AD6, AD9) are verified here against
a genuine MongoDB replica set.

How a replica set is obtained, in priority order:
  1. ``MONGO_TEST_URL`` env var pointing at an already-running replica set
     (CI sets this; locally: ``mongod --replSet rs0`` + ``rs.initiate()``).
  2. ``testcontainers`` (if installed) starts an ephemeral single-node replica set.

If neither is available the whole tier is **skipped** (never failed) — the default
suite never runs these (pytest.ini deselects ``-m "not mongo_real"``), and a developer
running ``pytest -m mongo_real`` without a replica set gets a clear skip, not red.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

pytestmark = pytest.mark.mongo_real

_TEST_DB_NAME = "eduflow_mongo_real_test"


def _real_mongo_url() -> str | None:
    """Return a replica-set connection string, or None if unavailable."""
    url = os.environ.get("MONGO_TEST_URL")
    if url:
        return url
    try:
        from testcontainers.mongodb import MongoDbContainer  # noqa: F401
    except Exception:
        return None
    return "__testcontainers__"


@pytest_asyncio.fixture(scope="module")
async def mongo_real_client():
    """An AsyncIOMotorClient bound to a real replica set, or skip."""
    url = _real_mongo_url()
    if url is None:
        pytest.skip(
            "No real Mongo replica set available — set MONGO_TEST_URL or install "
            "testcontainers (this tier is nightly/AI-path-only by design)."
        )

    from motor.motor_asyncio import AsyncIOMotorClient

    container = None
    if url == "__testcontainers__":
        from testcontainers.mongodb import MongoDbContainer

        container = MongoDbContainer("mongo:6.0").with_command("--replSet rs0")
        container.start()
        url = container.get_connection_url()
        admin = AsyncIOMotorClient(url)
        try:
            await admin.admin.command("replSetInitiate")
        except Exception:
            pass  # already initiated
        finally:
            admin.close()

    client = AsyncIOMotorClient(url)
    # Fail fast (and skip) if the server is not actually a replica set.
    try:
        hello = await client.admin.command("hello")
        if not hello.get("setName") and not hello.get("isreplicaset"):
            pytest.skip("Connected Mongo is not a replica set; transactions unavailable.")
    except Exception as exc:  # pragma: no cover - environment dependent
        client.close()
        if container is not None:
            container.stop()
        pytest.skip(f"Could not reach a real Mongo replica set: {exc}")

    yield client

    client.close()
    if container is not None:
        container.stop()


@pytest_asyncio.fixture
async def mongo_real_db(mongo_real_client):
    """A clean database per test (dropped before yield)."""
    await mongo_real_client.drop_database(_TEST_DB_NAME)
    yield mongo_real_client[_TEST_DB_NAME]
    await mongo_real_client.drop_database(_TEST_DB_NAME)
