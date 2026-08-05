from __future__ import annotations

import pytest

import database

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _restore_database_globals():
    original_client = database._client
    original_db = database._db
    yield
    database._client = original_client
    database._db = original_db


class _FakeDatabase:
    async def command(self, name):
        assert name == "ping"
        return {"ok": 1}


class _FakeClient:
    def __init__(self, *_args, **_kwargs):
        self.database = _FakeDatabase()

    def __getitem__(self, _name):
        return self.database


async def _run_connect(monkeypatch, environment: str, create_indexes: str | None):
    calls = []

    async def _indexes():
        calls.append("created")

    monkeypatch.setattr(database, "AsyncIOMotorClient", _FakeClient)
    monkeypatch.setattr(database, "_create_indexes", _indexes)
    monkeypatch.setenv("MONGO_URL", "mongodb://local.test/release")
    monkeypatch.setenv("DB_NAME", "release")
    monkeypatch.setenv("ENVIRONMENT", environment)
    if create_indexes is None:
        monkeypatch.delenv("CREATE_INDEXES_ON_STARTUP", raising=False)
    else:
        monkeypatch.setenv("CREATE_INDEXES_ON_STARTUP", create_indexes)
    await database.connect_db()
    return calls


async def test_production_startup_does_not_change_indexes(monkeypatch):
    assert await _run_connect(monkeypatch, "production", None) == []


async def test_development_startup_keeps_index_bootstrap(monkeypatch):
    assert await _run_connect(monkeypatch, "development", None) == ["created"]


async def test_production_can_explicitly_enable_index_bootstrap(monkeypatch):
    assert await _run_connect(monkeypatch, "production", "true") == ["created"]


async def test_connection_failure_is_not_silently_swallowed(monkeypatch):
    class _BrokenDatabase:
        async def command(self, _name):
            raise RuntimeError("unreachable")

    class _BrokenClient(_FakeClient):
        def __init__(self, *_args, **_kwargs):
            self.database = _BrokenDatabase()

    monkeypatch.setattr(database, "AsyncIOMotorClient", _BrokenClient)
    monkeypatch.setenv("MONGO_URL", "mongodb://local.test/release")
    monkeypatch.setenv("DB_NAME", "release")
    with pytest.raises(RuntimeError, match="unreachable"):
        await database.connect_db()
