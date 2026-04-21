from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import time
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from database import connect_db, disconnect_db
from routes.chat import router as chat_router
from routes.students import router as students_router
from routes.staff import router as staff_router
from routes.fees import router as fees_router
from routes.attendance import router as attendance_router
from routes.tools import router as tools_router
from routes.settings import router as settings_router
from routes.academics import router as academics_router
from routes.operations import router as operations_router
from routes.search import router as search_router
from routes.notifications import router as notifications_router
from routes.exports import router as exports_router
from routes.upload import router as upload_router
from routes.auth import router as auth_router
from routes.sms import router as sms_router
from routes.tokens import router as tokens_router
from routes.queries import router as queries_router
from routes.assistant import router as assistant_router
from routes.image_gen import router as image_gen_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EduFlow API",
    version="1.0.0",
    docs_url="/api/docs" if os.environ.get("ENVIRONMENT") != "production" else None,
    redoc_url=None,
)

# ─── CORS — explicit origins only, no wildcard ──────────────────────────────

cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# ─── Security headers middleware ─────────────────────────────────────────────

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.environ.get("ENVIRONMENT") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ─── Request logging middleware ──────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 1)
    if not request.url.path.startswith("/api/health"):
        logger.info(f"{request.method} {request.url.path} → {response.status_code} ({duration}ms)")
    return response


# ─── Global error handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {str(exc)[:200]}")
    response = JSONResponse(
        status_code=500,
        content={"success": False, "detail": "An internal error occurred"},
    )
    # Add CORS headers manually
    origin = request.headers.get("origin")
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


# ─── Routers ────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(students_router)
app.include_router(staff_router)
app.include_router(fees_router)
app.include_router(attendance_router)
app.include_router(tools_router)
app.include_router(settings_router)
app.include_router(academics_router)
app.include_router(operations_router)
app.include_router(search_router)
app.include_router(notifications_router)
app.include_router(exports_router)
app.include_router(upload_router)
app.include_router(sms_router)
app.include_router(tokens_router)
app.include_router(queries_router)
app.include_router(assistant_router)
app.include_router(image_gen_router)


@app.on_event("startup")
async def startup():
    await connect_db()
    logger.info("EduFlow API started — MongoDB connected")


@app.on_event("shutdown")
async def shutdown():
    await disconnect_db()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "EduFlow API"}
