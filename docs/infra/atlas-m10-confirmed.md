# MongoDB Atlas M10+ Replica Set — Confirmation Record

> **Status:** Pending operator verification  
> **Story:** 6-34 — MongoDB Atlas M10+ Replica Set Confirmation  
> **Go-live blocker:** Blocker B2  

---

## Cluster Details

| Field | Value |
|-------|-------|
| **Cluster name** | _(fill in: e.g. `Cluster0`)_ |
| **Atlas tier** | _(fill in: e.g. `M10`)_ |
| **Cloud provider + region** | _(fill in: e.g. `AWS / ap-south-1`)_ |
| **Replica-set name** | _(fill in: e.g. `atlas-xxxxxxx-shard-0`)_ |
| **Nodes** | _(fill in: e.g. `1 PRIMARY + 2 SECONDARY`)_ |
| **MongoDB version** | _(fill in: e.g. `7.0.x`)_ |

Screenshot: `docs/infra/atlas-m10-confirmed.png` (taken from Atlas Cluster Overview → Metrics → Replication)

---

## Connection String Verification

| Check | Status |
|-------|--------|
| `MONGO_URL` starts with `mongodb+srv://` | ✅ Confirmed (local `.env` + EB console) |
| `retryWrites=True` set at driver level | ✅ Confirmed — `database.py:142` |
| No hardcoded host in `database.py` | ✅ Confirmed — `os.environ.get("MONGO_URL")` |
| `MONGO_URL` set in EB production env | _(fill in: confirmed via AWS console Y/N)_ |

---

## Failover Test (Staging)

| Field | Value |
|-------|-------|
| **Test date** | _(fill in: YYYY-MM-DD)_ |
| **Method** | Atlas → Cluster → `…` → Test Failover |
| **Failover completed in** | _(fill in: e.g. `~18 seconds`)_ |
| **App reconnected within 30s?** | _(fill in: Yes / No)_ |
| **Any errors observed?** | _(fill in: None / describe)_ |

**Steps:**
1. Open Atlas → Clusters → `…` (three dots) → **Test Failover**
2. Watch application logs: Motor 3.3.1 reconnects automatically — expect reconnect messages, no crash
3. Run `GET /api/health/ready` — should return `{"overall": "ready"}` within 30 seconds of failover
4. Note the elapsed time and record above

---

## TTL Index Smoke Test (Staging)

| Field | Value |
|-------|-------|
| **Test date** | _(fill in: YYYY-MM-DD)_ |
| **Insert time** | _(fill in: HH:MM:SS UTC)_ |
| **Document deleted at** | _(fill in: HH:MM:SS UTC — expected within 120s of expires_at)_ |
| **TTL fired?** | _(fill in: Yes / No)_ |

**Steps (run via `mongosh` or Atlas Data Explorer on staging cluster):**

```js
// 1. Insert test document (expires in 60 seconds)
db.confirm_tokens.insertOne({
  token: "ttl-test-token",
  expires_at: new Date(Date.now() + 60_000),
  schoolId: "aaryans-joya"
})

// 2. Wait 90–120 seconds, then verify it is gone
db.confirm_tokens.findOne({ token: "ttl-test-token" })
// Expected: null (document removed by TTL monitor)

// 3. Clean up if somehow still present
db.confirm_tokens.deleteOne({ token: "ttl-test-token" })
```

**Background:** TTL index `confirm_tokens.expires_at` is created at startup via `database.py:202` with `expireAfterSeconds=0`. Atlas runs its TTL monitor every ~60s on M10+ dedicated clusters.

---

## Sign-Off

| Field | Value |
|-------|-------|
| **Verified by** | _(fill in: Abhimanyu)_ |
| **Date** | _(fill in: YYYY-MM-DD)_ |
| **Notes** | _(fill in: any observations)_ |

---

## Go-Live Clearance

- [ ] AC1 — Atlas tier M10+ confirmed (screenshot at `docs/infra/atlas-m10-confirmed.png`)
- [ ] AC2 — Replica set topology confirmed (PRIMARY + 2 SECONDARY)
- [ ] AC3 — Connection string uses `mongodb+srv://`, `retryWrites=True` active
- [ ] AC4 — Failover test passed (reconnect ≤ 30s)
- [ ] AC5 — TTL smoke test passed (document removed within 120s)
- [ ] AC6 — This document fully completed with all fields filled in

Once all six boxes are checked, **Blocker B2 is cleared** and Story 37 (Production Deployment) may proceed.
