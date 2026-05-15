# Integration Architecture — EduFlow

_Generated: 2026-05-15 | Scan: deep_

---

## Overview

EduFlow is a two-part system (frontend SPA + backend API) that communicate exclusively via REST HTTP and SSE streaming. There is no GraphQL, no gRPC, no shared memory.

```
┌─────────────────────────────────────┐
│         AWS Amplify                 │
│  React 19 SPA (frontend/)          │
│                                     │
│  lib/api.js ─── fetch() / axios ───┼──► HTTPS ──► backend
│  ChatInterface.js ── SSE listen ───┼──► HTTPS ──► backend SSE
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│      AWS Elastic Beanstalk          │
│  FastAPI (backend/server.py)        │
│                                     │
│  ──► MongoDB Atlas                  │
│  ──► AWS S3                         │
│  ──► Azure OpenAI                   │
│  ──► Google Gemini                  │
│  ──► Twilio SMS                     │
│  ──► SMTP (email)                   │
└─────────────────────────────────────┘
```

---

## Integration Points

### 1. Frontend → Backend (REST)

**Protocol:** HTTPS REST  
**Auth:** `Authorization: Bearer <JWT access_token>` on every request  
**Base URL:** `REACT_APP_API_URL` env var (e.g. `https://api.eduflow.school`)

**Request headers:**
| Header | Purpose | When |
|--------|---------|------|
| `Authorization` | Bearer JWT | All protected endpoints |
| `Content-Type` | `application/json` | POST/PUT/PATCH with JSON body |
| `X-Request-ID` | Correlation ID | Optionally set by client |
| `Idempotency-Key` | Prevent duplicate mutations | POST fee transactions, etc. |
| `X-SSE-Session-ID` | SSE session tracking | SSE connections |

**HTTP client in frontend:**
- `fetch()` — used for all non-upload endpoints (see `frontend/src/lib/api.js`)
- `axios` — used only for multipart file uploads (see `/api/uploads`)

---

### 2. Frontend → Backend (SSE Streams)

**Protocol:** HTTP/1.1 Server-Sent Events  
**Endpoints:**
| SSE Endpoint | Purpose |
|-------------|---------|
| `POST /api/chat/conversations/{id}/messages` | AI response stream |
| `GET /api/attendance/stream` | Real-time attendance updates |
| `GET /api/fees/stream` | Real-time fee update events |

**Client pattern** (in `ChatInterface.js`):
```js
const eventSource = new EventSource(url, { withCredentials: true })
eventSource.onmessage = (e) => { /* append chunk */ }
eventSource.onerror = (e) => { /* handle disconnect */ }
```

**Backend pattern** (in `services/sse.py`):
```python
async def event_generator():
    yield f"data: {chunk}\n\n"
return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

### 3. Backend → MongoDB Atlas

**Protocol:** MongoDB wire protocol (TLS)  
**Client:** Motor 3.3.1 (async)  
**Connection string:** `MONGO_URL` env var (`mongodb+srv://...`)  
**Database:** `DB_NAME` env var

**Access pattern:**
```python
db = get_db()           # Returns ScopedDatabase (auto-injects schoolId)
db.students.find(...)   # Returns ScopedCollection — schoolId filter auto-applied
get_raw_db()            # Unscoped access — system collections only
```

**Tenancy enforcement:** `ScopedCollection` wraps all CRUD operations. `scoped_query()` in `tenant.py` adds `branch_id` when callers pass it.

---

### 4. Backend → AWS S3

**SDK:** boto3 ≥1.34  
**Module:** `backend/services/s3_storage.py`  
**Bucket:** `S3_BUCKET` env var  
**Region:** `AWS_REGION` env var  

**Operations:** upload file, generate presigned URL, delete file.

**Used by:**
- `routes/upload.py` — general file uploads
- `routes/image_gen.py` — AI-generated certificate/ID card images
- `routes/students.py` — student/guardian photos

---

### 5. Backend → Azure OpenAI

**SDK:** openai ≥1.30.0  
**Module:** `backend/ai/llm_client.py`  
**Config:** `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY` env vars  
**Deployment:** `gpt-5.3-chat`  

**Used by:**
- `ai/tool_functions_v2.py` — all AI tool implementations
- `routes/academics.py` — question paper generation
- `routes/image_gen.py` — image generation (via Gemini)

---

### 6. Backend → Google Gemini

**SDK:** google-generativeai ≥0.8.0  
**Module:** `backend/ai/llm_client.py`  
**Config:** `GOOGLE_API_KEY` env var  
**Used for:** Image generation tasks (certificates, ID cards)

---

### 7. Backend → Twilio SMS

**SDK:** twilio ≥9.2.0  
**Module:** `backend/routes/sms.py`  
**Config:** `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` env vars

---

### 8. Backend → SMTP (Email)

**Module:** `backend/services/email_service.py`  
**Config:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` env vars  
**Used for:** Password reset emails

---

## Auth Token Flow (Cross-Part)

```
Frontend                          Backend
   │                                │
   │── POST /api/auth/login ────────►│
   │   {username, password}          │── verify bcrypt
   │                                 │── create JWT (60 min)
   │                                 │── issue refresh token → DB
   │◄─ {access_token} ──────────────│
   │   Set-Cookie: refresh=...; HttpOnly
   │                                 │
   │   [store access_token in memory/localStorage]
   │                                 │
   │── GET /api/students ───────────►│
   │   Authorization: Bearer <AT>    │── decode_jwt()
   │◄─ {students: [...]} ───────────│
   │                                 │
   │   [access token expires after 60 min]
   │                                 │
   │── POST /api/auth/refresh ──────►│ (cookie sent automatically)
   │◄─ {access_token: new} ─────────│── rotate refresh token
   │                                 │
```

---

## CORS Configuration

Backend allows only explicit origins listed in `CORS_ORIGINS` env var (comma-separated):
```
CORS_ORIGINS=https://app.eduflow.school,http://localhost:3000
```

In production: only the Amplify domain is listed. No wildcard.

---

## Environment Variables Required

### Backend
| Variable | Purpose |
|----------|---------|
| `MONGO_URL` | MongoDB Atlas connection string |
| `DB_NAME` | Database name |
| `JWT_SECRET` | JWT signing secret |
| `CORS_ORIGINS` | Allowed frontend origins |
| `SCHOOL_ID` | Tenant identifier |
| `S3_BUCKET` | AWS S3 bucket name |
| `AWS_REGION` | AWS region |
| `AWS_ACCESS_KEY_ID` | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | S3 credentials |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_KEY` | Azure OpenAI key |
| `GOOGLE_API_KEY` | Google Gemini key |
| `TWILIO_ACCOUNT_SID` | Twilio SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth |
| `TWILIO_PHONE_NUMBER` | Twilio sender |
| `SMTP_HOST/PORT/USER/PASS` | Email SMTP config |
| `ENVIRONMENT` | `production` / `development` |

### Frontend
| Variable | Purpose |
|----------|---------|
| `REACT_APP_API_URL` | Backend base URL |

---

## Data Flow Examples

### Student Enrollment
```
Admin browser
  → POST /api/students (JSON: name, class_id, ...)
  → Backend validates + auth check (require_role("admin","owner"))
  → get_db().students.insert_one(doc) — auto-adds schoolId
  → POST /api/notifications (internal) — notify relevant staff
  → 201 + student doc returned
```

### AI Fee Query
```
Teacher: "Show me Priya's fee status"
  → POST /api/chat/conversations/{id}/messages
  → Backend: context_builder fetches teacher's branch data
  → LLM: tool_call → get_fee_status(student_id="priya-id")
  → tool_functions_v2.py: db.fee_transactions.find(scoped_query(...))
  → Result streamed back via SSE
  → Frontend: MessageRenderer displays fee table
```

### File Upload
```
Admin: uploads student certificate PDF
  → POST /api/uploads (multipart, via axios)
  → services/s3_storage.py: put_object → S3
  → returns {file_id, url} 
  → URL stored in student record via PATCH /api/students/{id}
```
