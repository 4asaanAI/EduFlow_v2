# Story D.1 — Real-Mongo replica-set test tier + FakeDb session shim

**Epic:** D — Safe execution — atomic, idempotent, never torn
**Status:** DONE (3 new FakeDb-tier tests green; 2 mongo_real sample tests collect + skip cleanly; zero new failures vs pinned 25-failure baseline)
**ADs:** AD12 (gates AD4–AD6). **FRs/NFRs:** NFR10/11/20/23/24.

## Acceptance Criteria (from epics doc)
1. A `@pytest.mark.mongo_real` tier is added (ephemeral Mongo as a single-node
   replica set via testcontainers or CI `--replSet`+`rs.initiate()`).
2. A no-op `session=` shim is added to `FakeCollection`.
3. A sample transaction test commits/rolls back on the real tier.
4. The FakeDb shim accepts `session=` without asserting atomicity.
5. The existing tests stay green (pinned baseline 25 fail / 867 pass → now 870 pass).
6. The tier runs nightly + on AI-layer path changes (NOT every PR), documented.

## What shipped
- `pytest.ini`: registered the `mongo_real` marker (with `--strict-markers` on) and
  added `-m "not mongo_real"` to default `addopts` so the tier is **deselected by
  default** — the per-PR suite never runs it.
- `tests/backend/mongo_real/conftest.py`: `mongo_real_client` / `mongo_real_db`
  fixtures. A replica set is sourced from `MONGO_TEST_URL` first, else `testcontainers`;
  if neither is available the tier **skips** (never fails). Verifies `hello.setName`
  so a non-replica-set Mongo skips instead of erroring on `start_transaction`.
- `tests/backend/mongo_real/README.md`: how to run + the **CI policy** (nightly +
  AI-layer-path PRs; the exact glob set and a GH Actions sketch) so it isn't quietly
  disabled for being slow.
- `tests/backend/mongo_real/test_transaction_sample_d1.py`: commit-both + rollback-both
  proofs (`@pytest.mark.mongo_real`).
- `tests/backend/conftest.py` — `FakeCollection`:
  - every op (`find_one/find/count_documents/insert_one/update_one/update_many/
    find_one_and_update/delete_one/delete_many/aggregate`) now accepts `**kwargs`,
    absorbing `session=` and **ignoring it** (asserts nothing about atomicity).
  - **opt-in** unique-index enforcement (`_enforce_unique`): inert unless a test
    registers a `unique=True` index on that collection (no baseline test does), so
    D.4 can exercise DuplicateKey on FakeDb sequentially while the 870 stay green.
- `tests/backend/unit/test_fakedb_session_shim_d1.py`: shim accepts `session=` on all
  ops; documents FakeDb is NOT transactional (atomicity lives on mongo_real); proves
  unique enforcement is opt-in.

## Notes
- `database.get_txn_session()` (the no-op session for the FakeDb path + real session
  for prod) is delivered in **Story D.2** together with `ScopedCollection` forwarding;
  D.1 is purely the test substrate + shim.
- `_session_kwargs(session)` already threads through the Epic A/B/C services
  (returns `{}` when session is None), so the executor can pass `session=` without
  touching those services.
