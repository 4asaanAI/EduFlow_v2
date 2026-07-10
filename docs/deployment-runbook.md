# EduFlow Deployment Runbook

This runbook covers a per-school EduFlow deployment using AWS Elastic Beanstalk for the FastAPI backend, AWS Amplify or S3 plus CloudFront for the React frontend, MongoDB Atlas for data, and S3 for uploaded files.

## 1. Pre-Deploy Checklist

Run these checks before any production deploy:

```bash
python -m pytest tests/backend -q
cd frontend
npm run build
```

Confirm:

- `SCHOOL_ID` is set for staging and production.
- `ENVIRONMENT=production` is set in production.
- `JWT_SECRET` is a strong production-only value.
- `MONGO_URL` points at the intended Atlas cluster and database.
- `python backend/migrations/run_all.py` has been tested against a staging clone.
- `GET /api/health/ready` is healthy in the currently deployed environment before starting the deploy.
- No unresolved migration or seed script is being run against the wrong database.

## 2. Backend Deploy Steps

Package the backend from the repository root:

```bash
make package-backend
```

Deploy with Elastic Beanstalk:

```bash
eb use eduflow-prod
eb deploy
eb status
```

Verify after deploy:

```bash
curl -fsS https://api.example.com/api/health/ready
curl -fsS https://api.example.com/api/health/system -H "Authorization: Bearer <owner-or-it-token>"
```

Expected result for readiness is HTTP `200` with `db_connected: true` and `school_id_configured: true`.

## 3. Migration Procedure

Migrations must be idempotent and must run against the explicit production Atlas URI.

```bash
cd backend
set MONGO_URL=mongodb+srv://<DB_USER>:<DB_PASSWORD>@<CLUSTER_HOST>/
set DB_NAME=eduflow
set SCHOOL_ID=aaryans-joya
python migrations/run_all.py
```

For PowerShell, prefer process-scoped variables:

```powershell
$env:MONGO_URL = "mongodb+srv://<DB_USER>:<DB_PASSWORD>@<CLUSTER_HOST>/"
$env:DB_NAME = "eduflow"
$env:SCHOOL_ID = "aaryans-joya"
python backend\migrations\run_all.py
```

Expected output should show migrations as applied or already applied. Stop immediately if the target database name or school id is not the production value you intended.

## 4. Rollback Procedure

Rollback application code first when the database schema remains backward compatible:

```bash
eb use eduflow-prod
eb appversion
eb deploy <previous-application-version-label>
```

If data rollback is required, follow the Atlas restore procedure in `docs/operations.md`:

1. Freeze traffic.
2. Restore the selected snapshot or point-in-time timestamp into a temporary cluster.
3. Validate row counts and login flows.
4. Update `MONGO_URL` to the restored cluster.
5. Restart Elastic Beanstalk.
6. Verify `GET /api/health/ready`.
7. Re-enable traffic.

## 5. Environment Variables

Every variable from `backend/.env.example` must be reviewed for each environment:

| Variable | Required | Notes |
|---|---:|---|
| `MONGO_URL` | Yes | MongoDB Atlas connection string. |
| `DB_NAME` | Yes | Production database name. |
| `CORS_ORIGINS` | Yes | Comma-separated frontend origins. |
| `ENVIRONMENT` | Yes | Use `production` in production. |
| `SCHOOL_ID` | Yes | Tenant identifier; required outside development. |
| `SCHOOL_NAME` | Yes | Display name and SMS context. |
| `JWT_SECRET` | Yes | Strong production-only secret. |
| `AZURE_OPENAI_API_KEY` | Yes | Required for AI chat. |
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI endpoint. |
| `AZURE_OPENAI_DEPLOYMENT` | Yes | Deployment name. |
| `OPENAI_SPEND_ALERT_INR` | Recommended | Spend alert threshold. |
| `BIOMETRIC_ENABLED` | Optional | Enables biometric dependency health check. |
| `BIOMETRIC_HEALTH_URL` | Optional | Biometric provider health URL. |
| `FRONTEND_URL` | Yes | Password reset link origin. |
| `SMTP_HOST` | Yes | Password reset email host. |
| `SMTP_PORT` | Yes | SMTP port. |
| `SMTP_USER` | Yes | SMTP username. |
| `SMTP_PASS` | Yes | SMTP password. |
| `SMTP_FROM` | Yes | Sender label/address. |
| `GEMINI_API_KEY` | Optional | Image-generation workflows. |
| `LLM_MODEL` | Optional | Model selector for image/document generation. |
| `AWS_ACCESS_KEY_ID` | Yes | S3 file access. |
| `AWS_SECRET_ACCESS_KEY` | Yes | S3 file access. |
| `AWS_REGION` | Yes | AWS region, normally `ap-south-1`. |
| `S3_BUCKET_NAME` | Yes | Preferred S3 bucket variable. |
| `S3_BUCKET` | Optional | Backward-compatible alias. |
| `FEE_API_BASE_URL` | Optional | External fee software sync. |
| `FEE_API_KEY` | Optional | External fee software key. |
| `TWILIO_ACCOUNT_SID` | Optional | SMS integration. |
| `TWILIO_AUTH_TOKEN` | Optional | SMS integration. |
| `TWILIO_PHONE_NUMBER` | Optional | SMS sender number. |
| `TWILIO_WHATSAPP_FROM` | Optional | WhatsApp-enabled Twilio number for template messages (Story 7-40). |
| `TWILIO_WHATSAPP_FEE_TEMPLATE_SID` | Optional | Twilio Content Template SID for fee reminder WhatsApp messages (Story 7-40). |
| `TWILIO_WHATSAPP_ATTENDANCE_TEMPLATE_SID` | Optional | Twilio Content Template SID for attendance alert WhatsApp messages (Story 7-40). |
| `RAZORPAY_KEY_ID` | Optional | Razorpay key id for token billing (Story 7-42; vendor change 2026-06-08). Use `rzp_live_...` in production. |
| `RAZORPAY_KEY_SECRET` | Optional | Razorpay key secret (server-side; pairs with `RAZORPAY_KEY_ID`). |
| `RAZORPAY_WEBHOOK_SECRET` | Optional | Razorpay webhook signing secret. Required for webhook endpoint security (verifies `X-Razorpay-Signature`). |
| `RAZORPAY_PLAN_MONTHLY_SCHOOL_STARTER` | Optional | Razorpay Plan ID for the Starter monthly plan (INR, created in Razorpay Dashboard). |
| `RAZORPAY_PLAN_MONTHLY_SCHOOL_PRO` | Optional | Razorpay Plan ID for the Pro monthly plan (INR, created in Razorpay Dashboard). |
| `GOOGLE_MAPS_API_KEY` | Optional | Google Maps Geocoding API key for transport route optimisation (Story 7-46). Enable Geocoding API in Google Cloud Console; restrict to server IP. |
| `OPERATOR_NOTIFY_EMAIL` | Optional | Email address that receives school onboarding completion notifications (Story 7-44). |
| `OPERATOR_SLACK_WEBHOOK_URL` | Optional | Slack incoming webhook URL for school onboarding completion alerts (Story 7-44). |

`MONGODB_URI` is not used by this codebase; use `MONGO_URL`.

## 6. Seed Procedure

Run seed scripts only on a new or intentionally reset environment.

```bash
cd backend
python seed.py
```

Before running seed data:

- Confirm `MONGO_URL`, `DB_NAME`, and `SCHOOL_ID`.
- Confirm the target database has no production school data unless this is an approved reset.
- Take an Atlas snapshot first if there is any chance the environment contains useful data.

Never run seed scripts against an active production school database.

## 7. Multi-School Setup

The supported production model is one isolated deployment per school.

For a second school:

1. Create a new Elastic Beanstalk environment.
2. Create or select the school-specific Atlas database.
3. Create or select the school-specific S3 bucket or prefix.
4. Set a distinct `SCHOOL_ID`.
5. Set school-specific CORS, frontend URL, SMTP, and SMS settings.
6. Run migrations against the new database.
7. Run seed only if this is a fresh school setup.
8. Verify owner login and `GET /api/health/ready`.

Use branch-level isolation inside a school through `branch_id`; do not use branch ids as a substitute for `SCHOOL_ID` across different schools.


## 8. AI Action Layer — Safety Operations (AI Layer Hardening, Epic F)

The AI assistant can perform writes (attendance, fees, approvals, announcements, …)
through the same shared service layer as the UI. Three operator controls govern it.

### 8.1 Kill-switch — stop all AI writes instantly (Story F.4)

The flag lives in `db.system_flags` keyed `ai_writes_enabled`. When off, the
`/api/chat/confirm` dispatch refuses every write; **reads keep working**.

**Cross-worker timing (R9.3 / M8):** the confirm/write path reads the flag
**fresh from Mongo on every confirmed write** (`ai_writes_enabled(db,
force_fresh=True)`), so flipping the switch OFF takes effect on the **next
confirmed write across ALL Elastic Beanstalk workers immediately** — it does not
wait for any per-worker cache to expire. The ≤30s in-process cache
(`CACHE_TTL_SECONDS`) now only serves non-write reads; it no longer bounds how
fast a disable reaches a worker on the write path.

```js
// Disable (mongosh)
db.system_flags.updateOne({key:"ai_writes_enabled"}, {$set:{key:"ai_writes_enabled", enabled:false}}, {upsert:true})
// Re-enable
db.system_flags.updateOne({key:"ai_writes_enabled"}, {$set:{enabled:true}}, {upsert:true})
```

Programmatic: `services.ai_kill_switch.set_ai_writes_enabled(db, enabled=False, actor_id=...)`
(invalidates the in-process cache immediately).

### 8.2 Shadow / dry-run mode (Story F.5)

Flag `ai_dry_run` in `db.system_flags`. When on, confirmed plans run inside an
always-aborted transaction and report the would-be diff — **committing nothing**;
post-commit SMS/email never fire. Use it during the pilot to accumulate parity
evidence at zero write-risk before enabling live writes.

```js
db.system_flags.updateOne({key:"ai_dry_run"}, {$set:{key:"ai_dry_run", enabled:true}}, {upsert:true})
```

### 8.3 Reverting a bad AI write — remediation runbook (Story F.9)

Every AI dispatch is recorded write-ahead in `db.ai_dispatch_audit_log` (one row
per dispatch, `_id = ai-dispatch-<confirm-token>`), and each domain write also
emits a row in `db.audit_logs`. To reverse a specific bad AI write:

1. **Stop the bleeding.** Flip the kill-switch off (8.1) so no new AI writes land
   while you investigate.
2. **Identify the dispatch.** Find the offending row in `ai_dispatch_audit_log`:
   ```js
   db.ai_dispatch_audit_log.find({user_id:"<actor>", status:"success"}).sort({executed_at:-1}).limit(20)
   ```
   The row carries `tool_name`, `params`, `user_id`, `session_id`, `confirmed_at`,
   `school_id`, `branch_id`. For a multi-step plan the `params.steps[]` lists every
   step in order.
3. **Reconstruct the blast radius.** Cross-reference `db.audit_logs` for the same
   actor/time window. Each domain audit row carries `collection`, `entity_id`,
   `action`, and `changes` (before/after where the service records them).
4. **Reverse it through the UI/service layer**, never with an ad-hoc raw write —
   re-open the affected record in the panel and apply the inverse operation
   (e.g. re-mark attendance, reverse/void the fee transaction, un-approve the
   leave). This keeps the correction itself scoped, validated, and audited.
5. **Destructive (delete) dispatches** are tagged in `audit_logs` with
   `action="delete"` and `changes.actor` / `changes.actor_name` — query
   "who deleted what, when":
   ```js
   db.audit_logs.find({action:"delete"}).sort({created_at:-1})
   ```
   Restore the deleted record from the most recent backup/snapshot (deletes are
   not soft-deletes); there is no automatic undo.
6. **Re-enable** AI writes (8.1) once the data is corrected and the root cause is
   understood.

Pilot metrics for the acceptance review live in `db.ai_metrics` (Story F.7):
`event ∈ {plan_executed, confirmation, step_outcome, ai_action, torn_state,
kill_switch_blocked, parity_diff}`. These rows are PII-free by construction.

## 9. LayaaStat health-check integration (push telemetry)

EduFlow pushes telemetry to **LayaaStat** (the Layaa AI health-check platform) so the
backend can be watched live. EduFlow's portfolio path is **push/ingest** — custom
product events to `POST /api/ingest` and GenAI/LLM spans to `POST /api/otel`, plus a
periodic `service_health` heartbeat — authenticated by a tenant-scoped ingest key.

**The integration is fully dormant until both env vars below are set** — no buffering,
no network, no heartbeat task. All call sites are no-ops when disabled, and telemetry
failures never affect a request (best-effort, fail-open).

| Env var | Required | Where it comes from |
|---|---|---|
| `LAYAASTAT_URL` | yes | Your deployed LayaaStat dashboard base URL (the Vercel deployment). |
| `LAYAASTAT_INGEST_KEY` | yes | LayaaStat `/registry` → Add Product (EduFlow) → Add Tenant → Add Environment → **Generate Ingest Key** (`lsk_live_…`). Tenant-scoped; never commit it. |
| `LAYAASTAT_SERVICE_NAME` | no | Service label (default `eduflow-api`). |
| `LAYAASTAT_FLUSH_AT` | no | Buffer size that triggers a flush (default `20`). |
| `LAYAASTAT_HEARTBEAT_SECONDS` | no | Heartbeat interval (default `60`; `0` disables the heartbeat task). |

**To turn it on:** register EduFlow in the deployed LayaaStat dashboard, generate the
ingest key, set `LAYAASTAT_URL` + `LAYAASTAT_INGEST_KEY` in the EB environment, and
redeploy. Verify on LayaaStat: `/platform-health` ingest rate rises and the EduFlow tile
appears on `/portfolio` within ~15 min (next rollup tick). To turn it off, unset either var.
