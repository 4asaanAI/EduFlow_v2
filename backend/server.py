from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import time
import uuid
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from database import connect_db, disconnect_db, get_raw_db
from logging_config import (
    configure_logging,
    duration_ms_ctx,
    method_ctx,
    path_ctx,
    request_id_ctx,
    status_code_ctx,
)
from routes.chat import router as chat_router
from routes.students import router as students_router
from routes.staff import router as staff_router
from routes.fees import router as fees_router
from routes.attendance import router as attendance_router
from routes.tools import router as tools_router
from routes.settings import router as settings_router
from routes.academics import router as academics_router
from routes.operations import router as operations_router, workflow_router, transport_router
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
from routes.import_data import router as import_router
from routes.issues import router as issues_router
from routes.audit import router as audit_router
from routes.chat_upload import router as chat_upload_router
from routes.activities import router as activities_router
from services.idempotency import (
    get_replay_response,
    record_key,
    should_handle_idempotency,
    store_response,
)

configure_logging()
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
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "Idempotency-Key", "X-SSE-Session-ID"],
)


def _add_cors(response: JSONResponse, origin: str | None) -> JSONResponse:
    """Inject CORS headers onto exception responses that bypass middleware."""
    if origin and origin in allowed_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )
    return _add_cors(response, request.headers.get("origin"))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    response = JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors(), custom_encoder={ValueError: str})},
    )
    return _add_cors(response, request.headers.get("origin"))


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


# ─── Generic Idempotency-Key middleware ─────────────────────────────────────

@app.middleware("http")
async def idempotency_keys(request: Request, call_next):
    if not should_handle_idempotency(request):
        return await call_next(request)

    try:
        db = get_raw_db()
        key = record_key(request)
        replay = await get_replay_response(db, key)
        if replay:
            return replay
    except Exception:
        logger.warning("idempotency lookup failed; request will execute normally", exc_info=True)
        db = None
        key = None

    response = await call_next(request)
    if not db or not key:
        return response
    if "text/event-stream" in response.headers.get("content-type", ""):
        return response

    body = b""
    async for chunk in response.body_iterator:
        body += chunk

    await store_response(db, key=key, request=request, response=response, body=body)
    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )


# ─── Request logging middleware ──────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request_id_token = request_id_ctx.set(request_id)
    method_token = method_ctx.set(request.method)
    path_token = path_ctx.set(request.url.path)
    status_token = status_code_ctx.set(None)
    duration_token = duration_ms_ctx.set(None)
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    status_code_ctx.set(response.status_code)
    duration_ms_ctx.set(duration)
    if not request.url.path.startswith("/api/health"):
        logger.info("request completed")
    request_id_ctx.reset(request_id_token)
    method_ctx.reset(method_token)
    path_ctx.reset(path_token)
    status_code_ctx.reset(status_token)
    duration_ms_ctx.reset(duration_token)
    return response


# ─── Global error handler ───────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled request error", exc_info=(type(exc), exc, exc.__traceback__))
    response = JSONResponse(
        status_code=500,
        content={"success": False, "detail": "An internal error occurred"},
    )
    return _add_cors(response, request.headers.get("origin"))


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
app.include_router(workflow_router)
app.include_router(transport_router)
app.include_router(search_router)
app.include_router(notifications_router)
app.include_router(exports_router)
app.include_router(upload_router)
app.include_router(sms_router)
app.include_router(tokens_router)
app.include_router(queries_router)
app.include_router(assistant_router)
app.include_router(image_gen_router)
app.include_router(import_router)
app.include_router(issues_router)
app.include_router(audit_router)
app.include_router(chat_upload_router)
app.include_router(activities_router)


@app.on_event("startup")
async def startup():
    await connect_db()
    logger.info("EduFlow API started")


@app.on_event("shutdown")
async def shutdown():
    await disconnect_db()


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "EduFlow API"}


async def _check_db() -> str:
    try:
        await get_raw_db().command("ping")
        return "ok"
    except Exception:
        logger.warning("readiness db check failed", exc_info=True)
        return "error"


async def _check_ai() -> str:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        return "degraded"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(endpoint.rstrip("/"))
        return "ok" if response.status_code < 500 else "degraded"
    except Exception:
        logger.warning("readiness ai check degraded", exc_info=True)
        return "degraded"


async def _check_biometric() -> str:
    endpoint = os.environ.get("BIOMETRIC_HEALTH_URL")
    if not endpoint:
        return "degraded"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(endpoint)
        return "ok" if response.status_code < 500 else "degraded"
    except Exception:
        logger.warning("readiness biometric check degraded", exc_info=True)
        return "degraded"


@app.get("/api/health/ready")
async def health_ready():
    db_status = await _check_db()
    ai_status = await _check_ai()
    response = {
        "db": db_status,
        "ai": ai_status,
    }
    if os.environ.get("BIOMETRIC_ENABLED", "").lower() == "true":
        response["biometric"] = await _check_biometric()

    if db_status == "error":
        overall = "down"
    else:
        overall = "ready"

    response["overall"] = overall
    return response
