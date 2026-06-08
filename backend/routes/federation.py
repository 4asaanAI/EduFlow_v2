from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from jose import JWTError, jwt

from database import get_raw_db

_PRODUCT_ID = "the-aaryans"

router = APIRouter(prefix="/api/federation", tags=["federation"])

_ALGORITHM = "HS256"
_AUDIENCE = "layaa-healthcheck-platform"
_ISSUER = "eduflow"


def _federation_secret() -> str:
    secret = os.environ.get("FEDERATION_JWT_SECRET", "")
    if not secret:
        raise HTTPException(status_code=500, detail="FEDERATION_JWT_SECRET not configured")
    return secret


async def require_federation_auth(request: Request) -> dict:
    auth_header = request.headers.get("authorization", "")
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(
            token,
            _federation_secret(),
            algorithms=[_ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("role") != "federation_reader":
        raise HTTPException(status_code=403, detail="Wrong role")
    return payload


# GET /api/federation/products
# EduFlow is a single-workspace app — the school itself is the product
@router.get("/products")
async def federation_products(_: dict = Depends(require_federation_auth)):
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "source_product_id": _PRODUCT_ID,
            "slug": _PRODUCT_ID,
            "name": "The Aaryans",
            "stage": "production",
            "tenant_id": None,
            "created_at": now,
            "updated_at": now,
        }
    ]


# GET /api/federation/tenants
@router.get("/tenants")
async def federation_tenants(_: dict = Depends(require_federation_auth)):
    db = get_raw_db()
    tenants = await db["tenants"].find({}, {"_id": 1, "slug": 1, "name": 1, "createdAt": 1, "updatedAt": 1}).to_list(5000)
    return [
        {
            "source_tenant_id": str(t["_id"]),
            "slug": t.get("slug"),
            "name": t.get("name"),
            "created_at": t["createdAt"].isoformat() if isinstance(t.get("createdAt"), datetime) else t.get("createdAt"),
            "updated_at": t["updatedAt"].isoformat() if isinstance(t.get("updatedAt"), datetime) else t.get("updatedAt"),
        }
        for t in tenants
    ]


# GET /api/federation/cost?since=ISO&until=ISO
@router.get("/cost")
async def federation_cost(
    since: str = Query(..., description="ISO datetime"),
    until: str = Query(..., description="ISO datetime"),
    _: dict = Depends(require_federation_auth),
):
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        until_dt = datetime.fromisoformat(until.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="since and until must be valid ISO datetimes")

    db = get_raw_db()
    pipeline = [
        {"$match": {"createdAt": {"$gte": since_dt, "$lte": until_dt}}},
        {"$group": {
            "_id": "$productId",
            "event_count": {"$sum": 1},
            "tokens_in": {"$sum": "$tokensIn"},
            "tokens_out": {"$sum": "$tokensOut"},
            "total_cost_usd": {"$sum": "$costUsd"},
        }},
    ]
    rows = await db["token_usage"].aggregate(pipeline).to_list(10000)
    return [
        {
            "product_workspace_id": _PRODUCT_ID,
            "event_count": r["event_count"],
            "tokens_in": r["tokens_in"],
            "tokens_out": r["tokens_out"],
            "total_cost_usd": r["total_cost_usd"],
        }
        for r in rows
    ]


# GET /api/federation/incidents?since=ISO
@router.get("/incidents")
async def federation_incidents(
    since: str = Query(..., description="ISO datetime"),
    _: dict = Depends(require_federation_auth),
):
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="since must be a valid ISO datetime")

    db = get_raw_db()
    rows = await db["incidents"].find(
        {"detectedAt": {"$gte": since_dt}},
        {"_id": 1, "severity": 1, "status": 1, "source": 1, "productId": 1, "detectedAt": 1, "resolvedAt": 1},
    ).to_list(10000)
    return [
        {
            "incident_id": str(i["_id"]),
            "severity": i.get("severity"),
            "status": i.get("status"),
            "source": i.get("source"),
            "product_workspace_id": _PRODUCT_ID,
            "detected_at": i["detectedAt"].isoformat() if isinstance(i.get("detectedAt"), datetime) else i.get("detectedAt"),
            "resolved_at": i["resolvedAt"].isoformat() if isinstance(i.get("resolvedAt"), datetime) else None,
        }
        for i in rows
    ]


# GET /api/federation/eval-quality
@router.get("/eval-quality")
async def federation_eval_quality(_: dict = Depends(require_federation_auth)):
    db = get_raw_db()
    rows = await db["eval_runs"].find(
        {"status": "completed"},
        {"_id": 1, "productId": 1, "casesTotal": 1, "casesPassed": 1, "finishedAt": 1},
    ).to_list(10000)
    return [
        {
            "product_workspace_id": _PRODUCT_ID,
            "eval_run_id": str(e["_id"]),
            "pass_rate": (e["casesPassed"] / e["casesTotal"]) if e.get("casesTotal") else None,
            "cases_total": e.get("casesTotal"),
            "cases_passed": e.get("casesPassed"),
            "finished_at": e["finishedAt"].isoformat() if isinstance(e.get("finishedAt"), datetime) else e.get("finishedAt"),
        }
        for e in rows
    ]
