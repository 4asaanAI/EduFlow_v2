# Development Guide — Backend

_Generated: 2026-05-15 | Scan: deep | Part: backend_

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.9.x | Exactly 3.9 — 3.10+ syntax breaks test conftest |
| pip / venv | Any | Use a virtual environment |
| MongoDB | Atlas or local | `MONGO_URL` env var |

---

## Setup

```bash
# 1. Create virtualenv
cd backend
python3.9 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy env file
cp .env.example .env
# Edit .env with your values

# 4. Run development server
uvicorn server:app --reload --port 8000
```

---

## Environment Variables (`.env`)

```bash
# Required
MONGO_URL=mongodb+srv://<DB_USER>:<DB_PASSWORD>@<CLUSTER_HOST>/
DB_NAME=eduflow_dev
JWT_SECRET=your-dev-secret-here

# Optional (dev)
SCHOOL_ID=aaryans-joya
CORS_ORIGINS=http://localhost:3000
ENVIRONMENT=development

# AI (optional in dev — degraded mode if absent)
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_KEY=...
GOOGLE_API_KEY=...

# Storage (optional in dev)
S3_BUCKET=eduflow-uploads
AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# SMS (optional)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+91...

# Email (optional)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...
```

---

## Running Tests

```bash
# From repo root
pytest tests/backend/ -v

# Run with coverage
pytest tests/backend/ --cov=backend --cov-report=term-missing

# Run a specific test file
pytest tests/backend/test_auth.py -v

# Run a specific test
pytest tests/backend/test_auth.py::test_login_success -v
```

**Test requirements:**
- Set `APP_AVAILABLE=true` to run integration tests (they skip otherwise)
- MongoDB must be reachable
- Tests use a test database (configured in `conftest.py`)
- 387 tests, 0 skipped when properly configured

---

## Running Migrations

```bash
cd backend
python migrations/run_all.py
```

Migrations track completion in `_migrations` collection. Idempotent — safe to run multiple times.

> **Check:** Verify migration `014_ensure_maintenance_user` is in `run_all.py` before running against a fresh DB.

---

## Seeding Dev Data

```bash
cd backend
python seed.py
```

Creates default users (owner, admin, teacher, student) and sample data.

---

## Adding a New Route

1. Create `backend/routes/new_domain.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Depends
from database import get_db
from middleware.auth import require_role

router = APIRouter(prefix="/api/new-domain", tags=["new-domain"])

@router.get("/")
async def list_items(user: dict = Depends(require_role("admin", "owner"))):
    db = get_db()
    items = await db.new_domain.find({}).to_list(None)
    return {"items": items}
```

2. Register in `backend/server.py`:

```python
from routes.new_domain import router as new_domain_router
app.include_router(new_domain_router)
```

3. Write tests in `tests/backend/test_new_domain.py`.

---

## Python 3.9 Compatibility Rule

**Critical:** Any file using `str | None` union syntax must have this as the first import:

```python
from __future__ import annotations
```

Without it, Python 3.9 raises `TypeError` at import time, which silently sets `APP_AVAILABLE=False` in conftest and skips all integration tests.

---

## Common Development Tasks

### Check API docs (dev only)
```
http://localhost:8000/api/docs
```
(Disabled in production via `ENVIRONMENT=production` env var.)

### Health check
```
GET http://localhost:8000/api/health
GET http://localhost:8000/api/health/ready
```

### Format code
```bash
black backend/
```

### Lint
```bash
flake8 backend/
```

---

## Code Conventions

| Convention | Rule |
|-----------|------|
| DB access | Always `async`/`await` with Motor; never use pymongo sync client in routes |
| Auth | Import `get_current_user`, `require_role` from `middleware/auth` — never define locally |
| Tenancy | Use `get_db()` (returns ScopedDatabase) for operational collections; `get_raw_db()` for system collections only |
| Branch scope | Pass `branch_id=user["branch_id"]` to `scoped_query()` for branch-scoped reads |
| Validators | Use `@field_validator` (Pydantic v2) — `@validator` is deprecated |
| Error format | Raise `HTTPException(status_code=..., detail="message")` — framework handles JSON serialization |
| Python version | `from __future__ import annotations` at top of any file using `str \| None` |
| Logging | Use `logger = logging.getLogger(__name__)` — do not use `print()` in production code |
