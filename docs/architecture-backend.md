# Architecture — Backend (FastAPI)

_Generated: 2026-05-15 | Scan: deep | Part: backend_

---

## Executive Summary

EduFlow's backend is a **FastAPI monolith** with a domain-routed layout. It serves a React SPA via REST + SSE endpoints. The architecture emphasises:

1. **JWT authentication** — short-lived access tokens (60 min) + httpOnly refresh tokens
2. **Dual-axis multi-tenancy** — `schoolId` (env-based) + `branch_id` (JWT claim)
3. **AI layer** — Azure OpenAI primary + Gemini secondary, with per-action rate limiting and a token budget
4. **S3-backed file storage** — all uploads go to AWS S3 (local `uploads/` is legacy)
5. **Async-first** — Motor (async MongoDB), async routes throughout

---

## Technology Stack

| Layer | Tech | Version |
|-------|------|---------|
| Framework | FastAPI | 0.110.1 |
| ASGI server | Uvicorn | 0.25.0 |
| Process manager | Gunicorn | 21.2.0 |
| Language | Python | 3.9.x |
| ORM/ODM | Motor (async MongoDB) | 3.3.1 |
| Sync DB (indexes) | pymongo | 4.5.0 |
| Validation | Pydantic v2 | ≥2.6.4 |
| JWT | python-jose | ≥3.3.0 |
| Password hashing | bcrypt | 4.1.3 |
| Primary LLM | Azure OpenAI (openai SDK) | ≥1.30.0 |
| Secondary LLM | google-generativeai | ≥0.8.0 |
| File storage | boto3 (S3) | ≥1.34 |
| SMS | twilio | ≥9.2.0 |
| Database | MongoDB Atlas | — |
| Deployment | AWS Elastic Beanstalk | — |

---

## Architecture Pattern

**Domain-routed REST monolith** with:
- One `APIRouter` per domain in `routes/`
- Shared auth dependency injection (`middleware/auth.py`)
- Service layer for external integrations (`services/`)
- Standalone AI subsystem (`ai/`)
- Database access through `ScopedDatabase` proxy

---

## Layer Diagram

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────┐
│  FastAPI Middleware Stack (server.py)   │
│  ┌─────────────────────────────────┐   │
│  │ 1. CORS (explicit origin list)   │   │
│  │ 2. Security headers             │   │
│  │ 3. Idempotency-Key              │   │
│  │ 4. Request logging              │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  API Router (27 route files)            │
│  GET /api/auth/*, POST /api/students/*, │
│  etc.                                   │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│  Auth Middleware (middleware/auth.py)   │
│  - JWT decode → user dict              │
│  - require_role(*roles) dependency     │
│  - require_owner_or_principal()        │
│  - require_owner()                     │
└─────────────────────────────────────────┘
     │
     ├──────────────────────┐
     ▼                      ▼
┌──────────────┐  ┌──────────────────────┐
│  DB Layer    │  │  Service Layer        │
│  database.py │  │  services/            │
│  - ScopedDB  │  │  - ai_rate_limiter   │
│  - ScopedCol │  │  - auth_tokens       │
│  - MongoDB   │  │  - email_service     │
│    Atlas     │  │  - idempotency       │
└──────────────┘  │  - s3_storage        │
                  │  - sse               │
                  │  - token_service     │
                  └──────────────────────┘
                       │
                  ┌────┴──────────────────┐
                  │  AI Layer (ai/)        │
                  │  - llm_client         │
                  │  - context_builder    │
                  │  - scope_resolver     │
                  │  - tool_functions_v2  │
                  │  - prompts            │
                  │  - content_filter     │
                  └───────────────────────┘
```

---

## Multi-Tenancy

**School isolation (`schoolId`):**
- Value comes from `SCHOOL_ID` env var (default: `aaryans-joya`)
- `ScopedCollection` auto-injects `schoolId` on every write
- Reads add `{$or: [{schoolId: X}, {schoolId: {$exists: false}}]}` — backward-compatible with pre-migration docs
- System collections (`auth_users`, `refresh_tokens`, etc.) bypass scoping

**Branch isolation (`branch_id`):**
- Value from JWT claim `branch_id`
- `scoped_query(query, branch_id=user["branch_id"])` in `tenant.py`
- Callers must pass `branch_id` explicitly — `ScopedCollection` does NOT auto-inject it
- Conflict detection: if query already pins a different `branch_id`, raises `ValueError`

**Known gap (Part 4):** `schoolId` is env-var only — not in JWT. True multi-school deployment requires architectural decision on JWT claim vs. env-per-instance.

---

## Authentication Flow

```
1. POST /api/auth/login
   ├── Validate credentials against auth_users (bcrypt)
   ├── Check login_attempts (lockout if >5 in 15 min)
   ├── create_jwt({user_id, role, name, sub_category?, branch_id?})
   ├── issue_refresh_token() → store in refresh_tokens collection
   └── Set httpOnly refresh cookie + return access token

2. GET /api/* (protected)
   └── get_current_user(request) → decode_jwt(Bearer token) → user dict

3. POST /api/auth/refresh
   ├── Read refresh cookie
   ├── consume_refresh_token() → validate + delete old
   ├── create_jwt() → new access token
   └── issue_refresh_token() → new refresh cookie (rotation)

4. POST /api/auth/logout
   ├── revoke_refresh_token() → delete from DB
   └── clear_refresh_cookie()
```

**Token details:**
- Access token: JWT HS256, 60-min expiry
- Refresh token: Random 48-byte URL-safe, hashed in DB, httpOnly cookie, 7-day expiry
- JWT secret: `JWT_SECRET` env var (required in prod; cached dev secret otherwise)

---

## AI Architecture

```
User message → POST /api/chat/conversations/{id}/messages
                    │
                    ▼
            ai/context_builder.py
            - Builds context from DB based on role/scope
            - ai/scope_resolver.py determines which data to fetch
                    │
                    ▼
            ai/prompts.py
            - Role-specific system prompt selection
                    │
                    ▼
            ai/content_filter.py
            - Safety check on user input
                    │
                    ▼
            ai/llm_client.py
            - Azure OpenAI (primary): gpt-5.3-chat deployment
            - Google Gemini (secondary): image tasks
                    │
                    ▼
            ai/tool_functions_v2.py
            - Tool implementations (DB reads/writes)
            - Each tool enforces scoped_query()
                    │
                    ▼
            services/token_service.py
            - Deduct tokens from branch balance
            - Enforce per-user monthly limits
                    │
                    ▼
            services/sse.py → SSE stream to client
```

**Rate limiting:** `backend/config/ai_rate_limits.yaml` defines per-role, per-action limits tracked in `ai_rate_limit_counters` collection.

---

## API Design

- **REST** — standard HTTP verbs, resource-based URLs, `/api/{domain}/{id}` pattern
- **SSE** — streaming for AI chat responses, attendance stream, fee stream
- **Idempotency** — `Idempotency-Key` header supported on mutating endpoints
- **Pagination** — query param based (`page`, `limit`) in list endpoints
- **Validation** — Pydantic v2 request models on all write endpoints
- **Error format** — `{"detail": "message"}` (Starlette default)

---

## Security Controls

| Control | Implementation |
|---------|---------------|
| Authentication | JWT Bearer + httpOnly refresh cookie |
| Authorization | `require_role()` FastAPI dependency |
| Password hashing | bcrypt (4.1.3) |
| Brute-force protection | `login_attempts` collection, 5-attempt lockout (15 min) |
| NoSQL injection | Input validation in Pydantic models + character blocklist |
| CORS | Explicit origin allowlist from `CORS_ORIGINS` env var |
| Security headers | HSTS (prod), X-Frame-Options DENY, X-Content-Type-Options, CSP |
| Rate limiting (AI) | Per-role per-action counters in MongoDB |
| Idempotency | `Idempotency-Key` header with DB-backed replay |

---

## Deployment Architecture

```
                    AWS Amplify
                    (Frontend)
                       │
                       │ HTTPS fetch()
                       ▼
                AWS Elastic Beanstalk
                (Backend)
                       │
          ┌────────────┼────────────────┐
          ▼            ▼                ▼
    MongoDB Atlas   AWS S3          Azure OpenAI
    (Primary DB)   (File store)    (LLM)
                                        │
                                   Google Gemini
                                   (Secondary LLM)
```

**EB configuration:**
- Entry: `application.py` → `application:application`
- Process: Gunicorn (multi-worker)
- Environment vars: `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS`, `S3_BUCKET`, `AWS_*`, `AZURE_OPENAI_*`, `SCHOOL_ID`

---

## Testing

| Type | Location | Count | Runner |
|------|----------|-------|--------|
| Integration | `tests/backend/` | 48 files, 387 tests | `pytest` |
| E2E | `tests/e2e/` | Playwright | `playwright test` |

**Key test infra:**
- `tests/backend/conftest.py` — TestClient + MongoDB test fixture
- Tests require `APP_AVAILABLE=true` to run (skips if backend can't start)
- `from __future__ import annotations` required at top of any file using `str | None` (Python 3.9 compatibility)
