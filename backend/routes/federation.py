from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from jose import JWTError, jwt

from database import get_raw_db

_PRODUCT_ID = "ebf33922-9d96-46f8-9f18-c7d9849d0e7b"

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
            "slug": "the-aaryans",
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
# token_usage stores created_at as ISO string and tokens_used as a single field.
# EduFlow tracks prepaid token packs (INR), no USD cost — total_cost_usd is null.
@router.get("/cost")
async def federation_cost(
    since: str = Query(..., description="ISO datetime"),
    until: str = Query(..., description="ISO datetime"),
    _: dict = Depends(require_federation_auth),
):
    try:
        since_str = datetime.fromisoformat(since.replace("Z", "+00:00")).isoformat()
        until_str = datetime.fromisoformat(until.replace("Z", "+00:00")).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="since and until must be valid ISO datetimes")

    db = get_raw_db()
    pipeline = [
        {"$match": {"created_at": {"$gte": since_str, "$lte": until_str}}},
        {"$group": {
            "_id": None,
            "event_count": {"$sum": 1},
            "tokens_in": {"$sum": "$tokens_used"},
        }},
    ]
    rows = await db.token_usage.aggregate(pipeline).to_list(1)
    if not rows:
        return []
    r = rows[0]
    return [
        {
            "product_workspace_id": _PRODUCT_ID,
            "event_count": r["event_count"],
            "tokens_in": r["tokens_in"],
            "tokens_out": 0,
            "total_cost_usd": None,
        }
    ]


# GET /api/federation/incidents?since=ISO
# incidents collection uses created_at (ISO string) not detectedAt.
@router.get("/incidents")
async def federation_incidents(
    since: str = Query(..., description="ISO datetime"),
    _: dict = Depends(require_federation_auth),
):
    try:
        since_str = datetime.fromisoformat(since.replace("Z", "+00:00")).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="since must be a valid ISO datetime")

    db = get_raw_db()
    rows = await db.incidents.find(
        {"created_at": {"$gte": since_str}},
        {"_id": 1, "id": 1, "severity": 1, "status": 1, "created_at": 1, "resolved_at": 1},
    ).to_list(10000)
    return [
        {
            "incident_id": i.get("id") or str(i["_id"]),
            "severity": i.get("severity"),
            "status": i.get("status"),
            "source": "eduflow",
            "product_workspace_id": _PRODUCT_ID,
            "detected_at": i.get("created_at"),
            "resolved_at": i.get("resolved_at"),
        }
        for i in rows
    ]


# GET /api/federation/eval-quality
# EduFlow does not run automated eval suites — return empty array.
@router.get("/eval-quality")
async def federation_eval_quality(_: dict = Depends(require_federation_auth)):
    return []
