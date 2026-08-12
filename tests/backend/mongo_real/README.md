# Real-Mongo replica-set test tier (`@pytest.mark.mongo_real`)

AI Layer Hardening - Architecture Decision **AD12** (Story D.1).

FakeDb (`tests/backend/conftest.py`) has **no** sessions, transactions, or unique-index
enforcement, so the integrity guarantees introduced by Epic D cannot be honestly
verified on it:

| Guarantee | AD | Story | Why FakeDb can't prove it |
|-----------|----|-------|---------------------------|
| Atomic all-or-nothing writes | AD4 | D.3 | no transaction / rollback |
| Exactly-once idempotency | AD6 | D.4 | no unique-index race enforcement |
| Saga compensation | AD4 | D.5 | no real partial-commit state |
| Optimistic precondition revalidation | AD5 | D.6 | no in-transaction re-read causality |
| Dry-run aborted txn | AD9 | F.5 | no transaction |

These tests therefore live here and carry `@pytest.mark.mongo_real`.

## Running locally

**The one-liner that is known to work on Windows (T10/NEW-06, first real run 2026-08-04).**
No Docker needed. MongoDB **7.0** - the 8.3 build from `winget` will not start on
Windows 10 19045 (it exits with `STATUS_ENTRYPOINT_NOT_FOUND` before printing anything).
Download `mongodb-windows-x86_64-7.0.16.zip` from fastdl.mongodb.org, unzip it, then:

```bash
# 1. start a single-node replica set (transactions need a replSet name, one node is enough)
mongod --dbpath <somewhere>/data --port 27099 --replSet rs0 --bind_ip 127.0.0.1 --logpath <somewhere>/mongod.log

# 2. initiate it, once
python -c "from pymongo import MongoClient; MongoClient('mongodb://127.0.0.1:27099/?directConnection=true').admin.command('replSetInitiate', {'_id':'rs0','members':[{'_id':0,'host':'127.0.0.1:27099'}]})"

# 3. run the tier
MONGO_TEST_URL='mongodb://127.0.0.1:27099/?replicaSet=rs0' MONGO_URL=mongodb://127.0.0.1:27099/eduflow_test DB_NAME=eduflow_test python -m pytest -m mongo_real tests/backend/mongo_real -q
```

Expected: **13 passed**. (The register said 14; the tier collects 13.)

```bash
# Option A - point at a replica set you already run
mongod --replSet rs0 --dbpath /tmp/rs0 &
mongosh --eval 'rs.initiate()'
MONGO_TEST_URL='mongodb://localhost:27017/?replicaSet=rs0' pytest -m mongo_real

# Option B - let testcontainers spin one up (requires Docker + `pip install testcontainers`)
pytest -m mongo_real
```

If neither a `MONGO_TEST_URL` nor `testcontainers`+Docker is available, the tier
**skips cleanly** - it never fails the default suite.

## CI policy (do NOT disable for being slow)

The default suite runs with `-m "not mongo_real"` (see `pytest.ini`), so this tier
does **not** run on every PR. It MUST run:

- **Nightly** (scheduled job) against a replica-set service container, and
- **On pull requests that touch AI-layer paths**:
  `backend/ai/**`, `backend/services/**`, `backend/routes/chat.py`,
  `backend/database.py`, `tests/backend/mongo_real/**`.

Suggested CI job (GitHub Actions sketch):

```yaml
mongo-real:
  if: github.event.schedule || contains-ai-layer-path-changes
  services:
    mongo:
      image: mongo:6.0
      options: --health-cmd "mongosh --eval 'db.runCommand({ping:1})'"
  steps:
    - run: mongosh "$MONGO_TEST_URL" --eval 'rs.initiate()' || true
    - run: pytest -m mongo_real
  env:
    MONGO_TEST_URL: mongodb://localhost:27017/?replicaSet=rs0
```
