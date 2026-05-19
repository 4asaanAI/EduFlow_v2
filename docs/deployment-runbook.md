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
set MONGO_URL=mongodb+srv://prod-user:prod-password@cluster.example.mongodb.net/
set DB_NAME=eduflow
set SCHOOL_ID=aaryans-joya
python migrations/run_all.py
```

For PowerShell, prefer process-scoped variables:

```powershell
$env:MONGO_URL = "mongodb+srv://prod-user:prod-password@cluster.example.mongodb.net/"
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
| `STRIPE_SECRET_KEY` | Optional | Stripe secret key for token billing (Story 7-42). Use `sk_live_...` in production. |
| `STRIPE_PUBLISHABLE_KEY` | Optional | Stripe publishable key (reference only, not used server-side). |
| `STRIPE_WEBHOOK_SECRET` | Optional | Stripe webhook signing secret (`whsec_...`). Required for webhook endpoint security. |
| `STRIPE_PRICE_MONTHLY_SCHOOL_STARTER` | Optional | Stripe Price ID for the Starter monthly plan (INR, created in Stripe Dashboard). |
| `STRIPE_PRICE_MONTHLY_SCHOOL_PRO` | Optional | Stripe Price ID for the Pro monthly plan (INR, created in Stripe Dashboard). |
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

