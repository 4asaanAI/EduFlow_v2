# Story 6.34: MongoDB Atlas M10+ Replica Set Confirmation

Status: in-progress
Epic: 6
Priority: Critical — go-live blocker (Blocker B2)
Effort: Small (non-code — infra decision + verification)
Created: 2026-05-17

## Story

**As** the operator (Abhimanyu),
**I want** to confirm the MongoDB Atlas cluster is on M10+ with replica-set topology enabled,
**so that** the platform meets its ≥99.5% monthly uptime SLA, TTL indexes fire reliably, and replica-set features (oplog, retryable writes) are available before go-live.

## Acceptance Criteria

1. **AC1.** Atlas dashboard confirms cluster tier is M10 or above — screenshot saved to `docs/infra/atlas-m10-confirmed.png`.
2. **AC2.** Cluster topology shows a replica set: PRIMARY + at least 2 SECONDARY nodes — visible in Atlas Cluster → Metrics → Replication tab.
3. **AC3.** `MONGO_URL` in `.env.production` (or EB environment config) is a `mongodb+srv://` connection string; `retryWrites=true` is either in the URI or confirmed active via Atlas defaults.
4. **AC4.** A manual failover test is run in staging — force-primary-failover via Atlas, and the app reconnects within 30 seconds without a process restart.
5. **AC5.** TTL index smoke-test: insert a `confirm_tokens` document with `expires_at` 60 seconds in the future; confirm Atlas TTL monitor removes it within 120 seconds (TTL fires every 60s on Atlas M10+).
6. **AC6.** Confirmation documented in `docs/infra/atlas-m10-confirmed.md` with: cluster name, tier, region, replica-set name, failover test outcome, date, and the engineer's name.

## Tasks / Subtasks

- [ ] **T1 — Verify Atlas tier** (AC1, AC2)
  - [ ] Log in to MongoDB Atlas → select the EduFlow cluster
  - [ ] Confirm tier is M10 or above (not M0/M2/M5 shared)
  - [ ] Confirm topology shows PRIMARY + 2 SECONDARY nodes on the Cluster Overview
  - [ ] Take a screenshot → save to `docs/infra/atlas-m10-confirmed.png`

- [ ] **T2 — Verify connection string** (AC3)
  - [ ] Confirm `MONGO_URL` in production EB environment starts with `mongodb+srv://` _(local .env verified ✅; EB console needs operator check)_
  - [x] Check `retryWrites=true` is set — confirmed at `database.py:142`: `"retryWrites": True` in `client_options` (driver-level, always active)
  - [x] Verify `database.py` uses the env var correctly — confirmed `os.environ.get("MONGO_URL")` at `database.py:132`, startup guard enforces `mongodb+srv://` format

- [ ] **T3 — Failover test in staging** (AC4)
  - [ ] On the staging Atlas cluster (M10+ required here too), trigger "Test Failover" via Atlas → Cluster → … → Test Failover
  - [ ] Observe app logs: Motor client should reconnect automatically (retryable writes handle in-flight ops)
  - [ ] Confirm API responds normally within 30 seconds of failover completion
  - [ ] Record result in `docs/infra/atlas-m10-confirmed.md`

- [ ] **T4 — TTL index smoke-test** (AC5)
  - [ ] Via `mongosh` (or Atlas Data Explorer) on staging, insert:
    ```js
    db.confirm_tokens.insertOne({
      token: "ttl-test-token",
      expires_at: new Date(Date.now() + 60_000),
      schoolId: "aaryans-joya"
    })
    ```
  - [ ] Wait ≤ 120 seconds; confirm document is gone via `db.confirm_tokens.findOne({token: "ttl-test-token"})`
  - [ ] This validates that `confirm_tokens.create_index("expires_at", expireAfterSeconds=0)` (database.py:202) will fire in production

- [ ] **T5 — Write confirmation doc** (AC6)
  - [x] Create `docs/infra/atlas-m10-confirmed.md` with all fields per AC6 — template created at `docs/infra/atlas-m10-confirmed.md`; fill in values after T1/T3/T4
  - [ ] Commit `docs/infra/atlas-m10-confirmed.png` + `docs/infra/atlas-m10-confirmed.md` _(after screenshot + operator verification)_

## Dev Notes

### Why this story exists

- **PRD NFR:** "Platform availability target (≥99.5% monthly) requires replica-set database topology — a standalone database instance cannot meet this SLA; the token store requires a TTL-capable backend configured before go-live." [Source: `_bmad-output/planning-artifacts/prd.md` — Database Topology constraint]
- **Pre-Implementation Blocker B2**: "MongoDB Atlas replica-set tier: confirm M10+ (replica set) before go-live for HA." [Source: `_bmad-output/implementation-artifacts/stories.md` line 75]
- TTL indexes (`confirm_tokens.expires_at`, `sms_logs.created_at`) only work reliably on a replica-set cluster — M0/M2/M5 shared clusters do not guarantee TTL firing cadence and have no replica set.

### Atlas tier quick reference

| Tier | Type | Replica Set | TTL reliable | Use for EduFlow |
|------|------|-------------|--------------|-----------------|
| M0 / M2 / M5 | Shared | ❌ No | ❌ No | Dev/demo only |
| **M10+** | Dedicated | ✅ Yes (3 nodes) | ✅ Yes (60s cadence) | **Production** |

- M10 is the minimum for replica-set + TTL + retryable writes.
- Atlas `mongodb+srv://` SRV records automatically discover replica-set members — no need to list individual node hostnames.

### Connection string — what's already wired

`backend/database.py:147` creates `AsyncIOMotorClient(mongo_url, retryWrites=True, maxPoolSize=50, minPoolSize=5)`. The `retryWrites=True` in client_options means even if the Atlas URI omits it, Motor will apply it at the driver level.

**No code changes are required in `database.py`** — it already handles M10 replica-set correctly. This story is pure infrastructure verification and documentation.

### TTL indexes in the codebase

Indexes created at startup by `database.py → _create_indexes()`:
- `confirm_tokens.expires_at` — `expireAfterSeconds=0` (TTL fires when `expires_at` is in the past)
- `sms_logs.created_at` — must be stored as a native `datetime` object (not ISO string) for TTL to fire; fixed in Part 16

Both require replica-set M10+ for reliable TTL operation in production.

### Failover test — what to expect

Motor 3.3.1 uses retryable reads/writes by default. During the ~15–30s Atlas failover window:
- In-flight writes that have not been acknowledged will be transparently retried against the new PRIMARY
- The app will log Motor reconnect events; no application restart is needed
- Connections from the pool will be re-established automatically

If the staging test takes > 30s to recover, check `serverSelectionTimeoutMS=10000` (database.py:141) — this is 10s, which is appropriate.

### Files to create

| File | Type | Notes |
|------|------|-------|
| `docs/infra/atlas-m10-confirmed.png` | Screenshot | Atlas dashboard showing tier + topology |
| `docs/infra/atlas-m10-confirmed.md` | Markdown doc | Confirmation record per AC6 |

**No backend code files modified.**

### Project Structure Notes

- `docs/infra/` directory does not exist yet — create it
- `docs/` is the canonical location for all project documentation [Source: `docs/index.md`]
- Deployment docs pattern: see `docs/deployment-runbook.md` for style reference

### References

- [Source: `_bmad-output/planning-artifacts/prd.md` — "Database topology" NFR constraint]
- [Source: `_bmad-output/implementation-artifacts/stories.md` — Phase 6, Story 34 + Blocker B2]
- [Source: `backend/database.py:130–157` — `connect_db()`, `AsyncIOMotorClient` options]
- [Source: `backend/database.py:201–202` — `confirm_tokens` TTL index creation]
- [Source: `_bmad-output/project-context.md` — "Migration Discipline" section (TTL index notes)]
- [Source: `docs/deployment-runbook.md` — MONGO_URL env var, Atlas connection guidance]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Pre-existing test failure confirmed: `tests/backend/unit/test_receptionist_p11.py::test_visitor_duplicate_returns_409_with_duplicate_field` fails on `HEAD~1` (before any 6-34 changes) — 698/699 pass, not a regression from this story.
- pytest-asyncio 1.3.0 (initially installed) gave wrong test counts; downgraded to 0.23.8 per `requirements.txt` to restore correct 699-test collection.

### Completion Notes List

**Completed by dev agent (2026-05-17):**

✅ T2 (code-verifiable subtasks):
- `database.py:132` — `os.environ.get("MONGO_URL")`: no hardcoded host, env var driven
- `database.py:137` — startup guard enforces `mongodb+srv://` or `mongodb://` format
- `database.py:141–142` — `"retryWrites": True` in `client_options` (active at Motor driver level regardless of URI parameter)
- Local `.env` MONGO_URL: `mongodb+srv://` format confirmed
- `.ebextensions/01_environment.config`: correctly excludes `MONGO_URL` (secrets set via EB console, not config files)

✅ T5 subtask 1:
- Created `docs/infra/` directory (was absent)
- Created `docs/infra/atlas-m10-confirmed.md` — full confirmation template with: cluster detail fields, connection string checks, failover test steps, TTL smoke test steps, sign-off table, and go-live clearance checklist

✅ Regression check: 699 tests collected; 698/699 pass (1 pre-existing failure in p11, confirmed pre-existing via `git stash` test)

---

**⚠️ HALT — Operator action required for remaining tasks:**

The following tasks require live MongoDB Atlas dashboard + staging cluster access that the dev agent cannot perform:

| Task | Action Required | AC |
|------|-----------------|-----|
| T1 | Log into Atlas, confirm cluster tier ≥ M10, confirm PRIMARY+2 SECONDARY topology, take screenshot → `docs/infra/atlas-m10-confirmed.png` | AC1, AC2 |
| T2 (sub 1) | Confirm `MONGO_URL` is set in AWS EB production environment config (via console) | AC3 |
| T3 | Run "Test Failover" in Atlas on staging cluster; confirm app reconnects within 30s | AC4 |
| T4 | Run TTL smoke test via `mongosh` on staging — insert doc, wait 90–120s, confirm deleted | AC5 |
| T5 (sub 2) | Fill in `docs/infra/atlas-m10-confirmed.md` with real values; commit + `docs/infra/atlas-m10-confirmed.png` | AC6 |

Full step-by-step instructions for T3 and T4 are in `docs/infra/atlas-m10-confirmed.md`.

### File List

**Added:**
- `docs/infra/atlas-m10-confirmed.md` — confirmation template (fill in after Atlas checks)

**Pending (operator creates):**
- `docs/infra/atlas-m10-confirmed.png` — Atlas dashboard screenshot

**Modified:**
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — status: `ready-for-dev` → `in-progress`
- `_bmad-output/implementation-artifacts/6-34-mongodb-atlas-m10-replica-set-confirmation.md` — task checkboxes, dev agent record

### Change Log

- 2026-05-17 — Dev agent: T2 code verification complete; T5 doc template created; HALT on T1/T3/T4 (live Atlas access required)
