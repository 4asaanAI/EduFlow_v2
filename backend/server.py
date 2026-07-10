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
import asyncio
import time
import uuid
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from database import connect_db, disconnect_db, get_db, get_raw_db
from tenant import validate_school_id
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
from routes.image_gen import router as image_gen_router
from routes.import_data import router as import_router
from routes.issues import router as issues_router
from routes.audit import router as audit_router
from routes.chat_upload import router as chat_upload_router
from routes.activities import router as activities_router
from routes.operator import router as operator_router
from routes.payroll import router as payroll_router
from routes.reports import router as reports_router
from routes.federation import router as federation_router
from routes.learning import router as learning_router
from services.idempotency import (
    get_replay_response,
    record_key,
    should_handle_idempotency,
    store_response,
)
from services.sse import keepalive_loop as sse_keepalive_loop, validate_multi_worker_config as _validate_sse_worker_config
from middleware.auth import get_current_user

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

# Starlette middleware is LIFO — registered last = executes first.
# SchoolContextMiddleware must run after CORS (registered before) so CORS preflight
# is handled before school injection.
from middleware.school_context import SchoolContextMiddleware
app.add_middleware(SchoolContextMiddleware)


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
        headers=dict(exc.headers) if exc.headers else None,
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
    origin = request.headers.get("origin")
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(self), geolocation=()"
    if os.environ.get("ENVIRONMENT") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Belt-and-suspenders: FastAPI dependency 4xx responses can bypass the
    # CORSMiddleware send wrapper. Ensure CORS headers are always present on
    # every response for allowed origins so the browser never blocks them.
    if origin and origin in allowed_origins:
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
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
        content={"detail": "An internal error occurred"},
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
app.include_router(image_gen_router)
app.include_router(import_router)
app.include_router(issues_router)
app.include_router(audit_router)
app.include_router(chat_upload_router)
app.include_router(activities_router)
app.include_router(operator_router)
app.include_router(payroll_router)
app.include_router(reports_router)
app.include_router(federation_router)
app.include_router(learning_router)


async def _layaastat_heartbeat_loop():
    """Periodically push a PII-free health heartbeat to LayaaStat (env-gated).

    Lets the live platform watch EduFlow's backend. A lightweight DB ping drives the
    overall status; nothing here ever raises (telemetry must not affect the app).
    """
    from services import layaastat

    interval = max(15, layaastat.heartbeat_seconds())
    while True:
        try:
            await asyncio.sleep(interval)
            try:
                from database import get_db

                await get_db().command("ping")
                db_ok = True
            except Exception:
                db_ok = False
            await layaastat.record_health_heartbeat(
                status="ok" if db_ok else "degraded",
                checks={"db": "ok" if db_ok else "error"},
                score=100 if db_ok else 50,
            )
            await layaastat.flush()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("layaastat heartbeat tick failed", exc_info=True)


@app.on_event("startup")
async def startup():
    validate_school_id()
    _validate_sse_worker_config()  # R14.1: refuse multi-worker without shared broker

    # R9.1 (C2): fail loud on missing Azure config outside development, the same
    # way SCHOOL_ID does — a silently-unconfigured AI client was the incident.
    from ai.llm_client import validate_ai_config
    validate_ai_config()

    # EC-15.1: SKIP_CONSENT_CHECK cannot be enabled in production/staging
    if os.getenv("SKIP_CONSENT_CHECK", "").lower() == "true":
        env = os.getenv("ENVIRONMENT", "development").lower()
        if env not in ("development", "test", "testing"):
            raise ValueError(
                "SKIP_CONSENT_CHECK cannot be true in production/staging environments. "
                "This env var bypasses the DPDP parental consent gate and is development-only."
            )
        else:
            logger.warning("SKIP_CONSENT_CHECK enabled — DPDP consent gate bypassed (dev mode only)")

    await connect_db()
    app.state.sse_keepalive_task = asyncio.create_task(sse_keepalive_loop())

    # R6.4 (XM10): the memory vector index is in-process and empty after a redeploy.
    # Rebuild it from the durable Mongo memories so recall isn't silently degraded.
    # No-op (and cheap) when the vector path is disabled — the common default.
    try:
        from services.memory.vector import rebuild_index_from_mongo

        await rebuild_index_from_mongo(get_db())
    except Exception:
        logger.warning("memory vector rebuild on startup failed", exc_info=True)

    # LayaaStat health heartbeat — only when the integration is configured AND the
    # heartbeat interval is non-zero. Dormant (no task) otherwise.
    from services import layaastat

    app.state.layaastat_heartbeat_task = None
    if layaastat.is_enabled() and layaastat.heartbeat_seconds() > 0:
        app.state.layaastat_heartbeat_task = asyncio.create_task(_layaastat_heartbeat_loop())
        logger.info("LayaaStat heartbeat task started")

    logger.info("EduFlow API started")


@app.on_event("shutdown")
async def shutdown():
    task = getattr(app.state, "sse_keepalive_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    hb_task = getattr(app.state, "layaastat_heartbeat_task", None)
    if hb_task is not None:
        hb_task.cancel()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass
    # Final flush so buffered telemetry isn't lost on a clean shutdown.
    from services import layaastat

    await layaastat.aclose()

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
    # R9.1 (C2 AC3): the readiness check must also verify the KEY is present —
    # a configured endpoint with no key still can't call the model.
    from ai.llm_client import get_azure_key
    if not endpoint or not get_azure_key():
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


async def _check_s3() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME") or os.environ.get("S3_BUCKET")
    if not bucket:
        return "not_configured"

    def _call():
        from services.s3_storage import get_s3_client
        get_s3_client().list_objects_v2(Bucket=bucket, MaxKeys=1)

    try:
        await asyncio.wait_for(asyncio.to_thread(_call), timeout=3.0)
        return "ok"
    except Exception:
        logger.warning("readiness s3 check degraded", exc_info=True)
        return "degraded"


async def _check_sms() -> str:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid:
        return "not_configured"
    if not token:
        logger.warning("readiness sms check degraded", extra={"reason": "missing_twilio_auth_token"})
        return "degraded"
    try:
        async with httpx.AsyncClient(timeout=3.0, auth=(sid, token)) as client:
            response = await client.get(f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json")
        return "ok" if response.status_code < 500 else "degraded"
    except Exception:
        logger.warning("readiness sms check degraded", exc_info=True)
        return "degraded"


@app.get("/api/health/ready")
async def health_ready():
    db_status = await _check_db()
    ai_status = await _check_ai()
    s3_status = await _check_s3()
    sms_status = await _check_sms()
    school_id_configured = bool(os.environ.get("SCHOOL_ID"))
    response = {
        "db": db_status,
        "ai": ai_status,
        "s3": s3_status,
        "sms": sms_status,
        "school_id_configured": school_id_configured,
    }
    if os.environ.get("BIOMETRIC_ENABLED", "").lower() == "true":
        response["biometric"] = await _check_biometric()

    if db_status == "error":
        response["overall"] = "down"
        # EC-16.3: Return 503 when DB is down so AWS/monitoring detects outage
        return JSONResponse(status_code=503, content=response)
    elif any(value == "degraded" for value in response.values()):
        overall = "degraded"
    else:
        overall = "ready"

    response["overall"] = overall
    return response


@app.get("/api/health/system")
async def health_system(request: Request):
    user = get_current_user(request)
    if not (user.get("role") == "owner" or (user.get("role") == "admin" and user.get("sub_category") == "it_tech")):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})
    ready = await health_ready()
    db = get_raw_db()
    counts = {}
    for name in ("auth_users", "students", "staff", "queries", "audit_logs"):
        collection = getattr(db, name, None)
        if collection is None:
            continue
        try:
            counts[name] = await collection.count_documents({})
        except Exception:
            counts[name] = "unavailable"
    return {
        "success": True,
        "status": ready.get("overall"),
        "checks": ready,
        "counts": counts,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
