# Real-Mongo replica-set test tier (`@pytest.mark.mongo_real`)

AI Layer Hardening — Architecture Decision **AD12** (Story D.1).

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

```bash
# Option A — point at a replica set you already run
mongod --replSet rs0 --dbpath /tmp/rs0 &
mongosh --eval 'rs.initiate()'
MONGO_TEST_URL='mongodb://localhost:27017/?replicaSet=rs0' pytest -m mongo_real

# Option B — let testcontainers spin one up (requires Docker + `pip install testcontainers`)
pytest -m mongo_real
```

If neither a `MONGO_TEST_URL` nor `testcontainers`+Docker is available, the tier
**skips cleanly** — it never fails the default suite.

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
