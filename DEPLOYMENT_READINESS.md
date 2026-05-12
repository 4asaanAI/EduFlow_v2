# EduFlow Deployment Readiness Assessment — AWS Elastic Beanstalk

**Date:** 2026-04-30  
**Status:** ⚠️ **PARTIALLY READY** — Requires critical changes before production deployment

---

## Executive Summary

EduFlow has a **solid architectural foundation** for cloud deployment, but **cannot be deployed to Elastic Beanstalk as-is**. The main blocker is **persistent file storage on ephemeral disk** (uploads). Additionally, the backend and frontend need configuration changes and some EB-specific setup.

**Critical blockers:** 2  
**Major issues:** 4  
**Minor issues:** 5

---

## ✅ Backend — FastAPI (8/10 Ready)

### Strengths

| Item | Status | Notes |
|------|--------|-------|
| **ASGI Framework** | ✅ Ready | FastAPI with uvicorn is production-grade |
| **Health Check** | ✅ Ready | `/api/health` endpoint present for EB monitoring |
| **Security Headers** | ✅ Ready | Proper HSTS, CSP, X-Frame-Options configured |
| **CORS** | ✅ Ready | Environment-driven, exception handlers add headers |
| **Rate Limiting** | ✅ Ready | Login attempt tracking with 15-min lockout |
| **Authentication** | ✅ Ready | JWT with bcrypt password hashing (7-day expiry) |
| **Database Indexes** | ✅ Ready | Created at startup for 8+ collections |
| **Error Handling** | ✅ Ready | Global exception handler + logging |
| **Logging** | ✅ Ready | Request logging, errors logged with context |
| **Input Validation** | ✅ Ready | Pydantic models, NoSQL injection checks |

### Critical Issues

**1. ❌ BLOCKER: File Storage on Ephemeral Disk**
- **Location:** `backend/routes/upload.py` (line 14-59)
- **Problem:** Files saved to `backend/uploads/` directory on instance disk
- **Risk:** Files lost on EB instance termination/replacement
- **Impact:** ALL uploaded documents, certificates, ID cards lost
- **Solution Required:** Migrate to AWS S3
  ```python
  # Current (broken for EB):
  UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
  file_path.write_bytes(contents)  # Saved to disk
  
  # Needed:
  s3_client.put_object(
    Bucket=os.environ['S3_BUCKET'],
    Key=f"uploads/{file_id}.{ext}",
    Body=content
  )
  ```

**2. ❌ BLOCKER: Missing Gunicorn for EB**
- **Location:** `backend/requirements.txt`
- **Problem:** No production WSGI/ASGI server specified
- **Impact:** EB won't know how to run the app
- **Solution:** Add `gunicorn==21.2.0` to requirements.txt
  - EB expects `gunicorn` or explicit `Procfile`
  - Alternative: Create `Procfile` with `web: uvicorn backend.server:app --host 0.0.0.0 --port 8000`

### Major Issues

**3. 🟠 Missing Environment Variables Documentation**
- **Missing keys:**
  - `AZURE_OPENAI_API_KEY` (used in chat routes)
  - `AZURE_OPENAI_DEPLOYMENT` (model name)
  - `AZURE_OPENAI_ENDPOINT` (API base URL)
  - `GEMINI_API_KEY` (exists but not in .env.example)
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (for S3)
  - `AWS_REGION` (for S3 and other services)
  - `S3_BUCKET` (new, for file uploads)

- **.env.example needs update:**
  ```bash
  # Azure OpenAI (Chat)
  AZURE_OPENAI_API_KEY=your_azure_key_here
  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
  AZURE_OPENAI_DEPLOYMENT=gpt-5.3-chat
  
  # Google Gemini (Image generation)
  GEMINI_API_KEY=your_gemini_key_here
  
  # AWS (S3 for file storage)
  AWS_ACCESS_KEY_ID=your_aws_access_key
  AWS_SECRET_ACCESS_KEY=your_aws_secret_key
  AWS_REGION=us-east-1
  S3_BUCKET=eduflow-uploads-prod
  
  # Twilio (SMS notifications)
  TWILIO_ACCOUNT_SID=...
  TWILIO_AUTH_TOKEN=...
  TWILIO_PHONE_NUMBER=...
  ```

**4. 🟠 Database Connection Not Validated at Startup**
- **Location:** `backend/database.py` (line 20-26)
- **Problem:** Connection test exists but only prints to stdout, doesn't fail fast
- **Risk:** EB instance becomes unhealthy if DB is unreachable
- **Impact:** Deployment appears successful but requests fail at runtime
- **Fix:** Raise exception if ping fails (already does), but ensure logging goes to stderr
  ```python
  except Exception as e:
      logger.error(f"MongoDB connection failed: {e}")
      raise  # Already raises, but ensure it's not caught silently
  ```

**5. 🟠 No MongoDB URI Validation**
- **Problem:** `MONGO_URL` env var assumed to be valid
- **Risk:** Typo in connection string causes runtime failures
- **Solution:** Validate URI format at app startup
  ```python
  if not mongo_url.startswith("mongodb+srv://"):
      raise ValueError("MONGO_URL must be a MongoDB Atlas connection string")
  ```

**6. 🟠 JWT_SECRET Has Weak Default**
- **Location:** `backend/middleware/auth.py` (line 22)
- **Current:** `JWT_SECRET=os.environ.get("JWT_SECRET", "eduflow-dev-secret-change-in-production")`
- **Risk:** If `JWT_SECRET` env var not set, app uses weak default
- **Solution:** Require JWT_SECRET and fail if not set
  ```python
  JWT_SECRET = os.environ.get("JWT_SECRET")
  if not JWT_SECRET:
      raise ValueError("JWT_SECRET environment variable is required")
  ```

### Minor Issues

**7. 📋 No Request ID Tracking**
- Missing correlation IDs for debugging distributed requests
- Each request should get a unique ID for tracing across logs
- Use `X-Request-ID` header or UUID

**8. 📋 Log Format Not Structured**
- Current: `%(asctime)s %(levelname)s [%(name)s] %(message)s`
- Should use JSON for EB CloudWatch ingestion
- Needs: `{"timestamp": "...", "level": "...", "message": "...", "request_id": "..."}`

**9. 📋 No Health Check Liveness/Readiness**
- Has `/api/health` but no separate readiness check
- EB needs to distinguish "app running" vs "app ready to serve traffic"
- Add `/api/health/ready` that checks DB connectivity

**10. 📋 File Upload Cleanup Missing**
- When file is deleted from DB, disk file should be deleted too
- Currently handles it, but no cleanup for orphaned files

**11. 📋 Uvicorn Not Configured for Production**
- No `--workers` setting
- No `--worker-class` for concurrent requests
- Needs: 4 workers, sync workers for I/O-bound operations

---

## ✅ Frontend — React (7/10 Ready)

### Strengths

| Item | Status | Notes |
|------|--------|-------|
| **Build Tool** | ✅ Ready | Create-react-app with craco, npm scripts present |
| **Environment Variables** | ✅ Ready | Uses `REACT_APP_BACKEND_URL` from .env |
| **API Client** | ✅ Ready | Centralized `lib/api.js` with Bearer token auth |
| **Auth Handling** | ✅ Ready | Clears token on 401, redirects to login |
| **Routing** | ✅ Ready | React Router v7.5.1 for client-side routing |
| **UI Framework** | ✅ Ready | Tailwind CSS v3.4 for styling |
| **State Management** | ✅ Ready | Context API (UserContext, ThemeContext) |

### Major Issues

**1. 🟠 Missing Build Output Directory**
- **Problem:** No `build/` directory in repo (correctly gitignored)
- **Impact:** EB needs to run `npm run build` during deployment
- **Solution:** EB must have build step configured (see Procfile section below)

**2. 🟠 External Scripts Load from CDN**
- **Location:** `public/index.html` (lines 26, 148)
- **Issue:** Loads `https://assets.emergent.sh/` and PostHog analytics
- **Risk:** Blocks page load if CDN is unreachable
- **Solution:** Make these optional or self-host
  ```html
  <!-- Should be async + noop fallback -->
  <script async src="..."></script>
  ```

**3. 🟠 .env.example Too Sparse**
- **Current:** Only `REACT_APP_BACKEND_URL=http://localhost:8000`
- **Problem:** Developers don't know what production URL should be
- **Solution:**
  ```bash
  REACT_APP_BACKEND_URL=https://api.eduflow.example.com
  REACT_APP_ENVIRONMENT=production
  ```

**4. 🟠 No Error Boundary for Production**
- **Problem:** Unhandled React errors crash app without UI feedback
- **Solution:** Add Error Boundary component at App level
  ```jsx
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
  ```

### Minor Issues

**5. 📋 LocalStorage Not Secure for PII**
- `localStorage` stores JWT token and user object
- Can be accessed by any script on page
- Consider using `httpOnly` cookies for JWT (requires backend support)

**6. 📋 No Service Worker**
- No offline support or caching
- Acceptable for now, but consider PWA features later

**7. 📋 Yarn Package Manager in package.json**
- Uses `yarn@1.22.22` but npm can also be used
- EB will use npm by default
- Either commit `package-lock.json` or configure `npm ci`

---

## 🔧 Infrastructure & Deployment

### Missing Elastic Beanstalk Configuration

**1. ❌ No Procfile**
- **Location:** Root directory
- **Required:** Tells EB how to start the app
- **Create:** `/Procfile`
  ```
  web: cd backend && gunicorn server:app --bind 0.0.0.0:8000 --workers 4 --worker-class uvicorn.workers.UvicornWorker --access-logfile - --error-logfile -
  ```
  OR if using npm + frontend:
  ```
  web: npm run build && npm run start
  ```
  **Note:** For a monorepo (backend + frontend), you need a different strategy (see below).

**2. ❌ No .ebextensions Configuration**
- **Location:** `.ebextensions/` directory (missing)
- **Required:** EB-specific configurations
- **Create:** `.ebextensions/01_environment.config`
  ```yaml
  option_settings:
    aws:elasticbeanstalk:container:python:
      WSGIPath: backend/server:app
    aws:elasticbeanstalk:application:environment:
      NODE_ENV: production
      ENVIRONMENT: production
  ```

**3. ❌ No Docker Support**
- Elastic Beanstalk can use Docker for more control
- Create: `Dockerfile` for backend + `docker-compose.yml` for orchestration
- Recommended for monorepo (separate backend and frontend)

---

## 📋 Deployment Checklist

### Pre-Deployment Tasks (Backend)

- [ ] Add `gunicorn==21.2.0` to `backend/requirements.txt`
- [ ] Add `boto3` (AWS SDK) to requirements for S3 access
- [ ] Create `backend/s3.py` module for file upload handling
- [ ] Update `backend/routes/upload.py` to use S3 instead of disk
- [ ] Update `backend/.env.example` with all required variables
- [ ] Create `Procfile` at root
- [ ] Create `.ebextensions/01_environment.config`
- [ ] Add JWT_SECRET validation to `backend/middleware/auth.py`
- [ ] Add MongoDB connection validation to `backend/database.py`
- [ ] Create `/api/health/ready` endpoint for readiness checks
- [ ] Configure structured JSON logging

### Pre-Deployment Tasks (Frontend)

- [ ] Update `frontend/.env.example` with production URL
- [ ] Test build: `npm run build` (creates `build/` dir)
- [ ] Add Error Boundary component
- [ ] Make external CDN scripts optional/async
- [ ] Ensure `REACT_APP_BACKEND_URL` points to correct API

### Pre-Deployment Tasks (Infrastructure)

- [ ] Create S3 bucket for file uploads: `eduflow-uploads-prod`
- [ ] Create IAM role for EB instance with S3 access
- [ ] Configure MongoDB Atlas to accept connections from EB security group
- [ ] Create RDS (optional) or use MongoDB Atlas
- [ ] Set up CloudWatch for centralized logging
- [ ] Configure domain name / SSL certificate
- [ ] Set environment variables in EB console:
  - `MONGO_URL`
  - `DB_NAME`
  - `JWT_SECRET` (strong random string)
  - `CORS_ORIGINS` (your domain)
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_DEPLOYMENT`
  - `GEMINI_API_KEY`
  - `AWS_REGION`
  - `S3_BUCKET`
  - `TWILIO_*` (if using SMS)

---

## 🏗️ Recommended Deployment Architecture

Since you have a **monorepo (backend + frontend)**, here are two strategies:

### Strategy 1: Separate EB Environments (Recommended)

```
eduflow-backend-prod
├── Elastic Beanstalk (Python)
├── Runs: FastAPI + uvicorn
├── Env vars: MONGO_URL, JWT_SECRET, S3_BUCKET, etc.
└── Port: 8000

eduflow-frontend-prod
├── Elastic Beanstalk (Node.js)
├── Runs: Nginx serving React build
├── Env vars: REACT_APP_BACKEND_URL=https://api.eduflow.example.com
└── Port: 3000 (or 80 for HTTP)

CloudFront / Route53
├── Points to frontend EB
├── Backend API routed to backend EB
└── SSL certificates
```

**SSE route requirement:** `GET /api/chat/conversations/{id}/messages`, `GET /api/attendance/stream`, and `GET /api/fees/stream` must terminate on a path with a backend idle timeout of at least 300 seconds. Configure the backend ALB with `idle_timeout.timeout_seconds=300`, forward `Authorization`, `Idempotency-Key`, and `X-SSE-Session-ID`, and disable caching on `/api/*`. If CloudFront cannot preserve long-lived API streams in the deployment account, route `REACT_APP_BACKEND_URL` to the HTTPS ALB/API domain instead of the frontend CloudFront distribution.

**Pros:** Separate scaling, independent deployments  
**Cons:** More complex setup

### Strategy 2: Single EB Environment with Docker

```
eduflow-prod
├── Elastic Beanstalk (Docker multi-container)
├── Services:
│   ├── api: FastAPI on :8000
│   ├── web: Nginx + React build on :80
└── docker-compose.yml orchestrates both
```

**Pros:** Single deployment, simpler  
**Cons:** Must build Docker images, shared resources

**Recommendation:** Use **Strategy 1** (separate) for production scalability.

---

## 📊 Deployment Ready Score

| Component | Score | Comments |
|-----------|-------|----------|
| **Backend Code** | 8/10 | Good structure, needs S3 migration |
| **Frontend Code** | 7/10 | Ready, needs error handling |
| **Security** | 8/10 | Good headers, needs env var validation |
| **Infrastructure** | 2/10 | No EB config, no Docker, file storage issue |
| **Monitoring** | 4/10 | Basic logging, needs structured JSON |
| **Documentation** | 3/10 | Missing deployment guides |
| **Database** | 9/10 | MongoDB Atlas is cloud-ready |
| **Overall** | 5.8/10 | **NOT READY** — fix blockers first |

---

## 🚀 Next Steps

### Immediate (Critical - Block Deployment)

1. **Migrate file storage to S3**
   - Create S3 module
   - Update upload.py
   - Test locally with moto (S3 mock)

2. **Add gunicorn + Procfile**
   - Install gunicorn
   - Create Procfile with uvicorn worker
   - Test locally: `gunicorn server:app`

3. **Add EB configuration**
   - Create .ebextensions/
   - Configure Python platform settings

### Important (Complete Before Going Live)

4. **Implement structured logging**
   - JSON format for CloudWatch
   - Request ID correlation

5. **Environment variable validation**
   - Check JWT_SECRET, MONGO_URL at startup
   - Fail fast on config errors

6. **Error handling improvements**
   - Add React Error Boundary
   - Test error scenarios

### Nice-to-Have (Post-Deployment)

7. **Add readiness/liveness endpoints**
8. **Configure auto-scaling policies**
9. **Set up monitoring dashboards**
10. **Implement request ID tracking**

---

## 📞 Questions to Answer

1. **What's your expected traffic?** (Affects EB instance type + auto-scaling)
2. **Where will MongoDB be?** (Atlas vs RDS? Already configured?)
3. **Do you need separate frontend domain?** (Affects Route53 setup)
4. **How critical is file upload data?** (S3 backup strategy?)
5. **Do you have AWS account + EB experience?** (May need consulting help)

---

## Summary

EduFlow has **solid code but needs infrastructure work** before EB deployment. The two critical issues are:

1. **File storage on ephemeral disk** → Must migrate to S3
2. **Missing production server** → Must add gunicorn + Procfile

Once these are fixed, deployment should be straightforward. Estimated effort: **2-3 days** for an experienced AWS developer, **1-2 weeks** if new to AWS/EB.
