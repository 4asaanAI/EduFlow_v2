"""Story 7-41: Advanced reporting endpoints — attendance trends + fee collection summary.

Owner/principal read-only views designed to back small Recharts panels on the
operator dashboards. No real-time requirement; clients fetch once on mount.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Iterable

from fastapi import APIRouter, HTTPException, Request

from database import get_db
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _user(request: Request) -> dict:
    return get_current_user(request)


def _is_principal(user: dict) -> bool:
    return user.get("role") == "admin" and user.get("sub_category") == "principal"


def _is_owner_or_principal(user: dict) -> bool:
    return user.get("role") == "owner" or _is_principal(user)


def _clamp_months(raw: int, lo: int, hi: int) -> int:
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = lo
    return max(lo, min(hi, n))


def _last_n_months(now: datetime, n: int) -> list[str]:
    """Return the last N month buckets as YYYY-MM strings, oldest first."""
    buckets: list[str] = []
    year, month = now.year, now.month
    for _ in range(n):
        buckets.append(f"{year:04d}-{month:02d}")
        # Step back one month
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(buckets))


@router.get("/attendance-trends")
async def attendance_trends(request: Request, months: int = 3):
    """AC1 + AC4. Monthly attendance % overall + per class."""
    user = _user(request)
    if not _is_owner_or_principal(user):
        raise HTTPException(status_code=403, detail="Owner or principal only")

    months = _clamp_months(months, 1, 12)
    db = get_db()
    bucket_keys = _last_n_months(datetime.utcnow(), months)
    earliest_bucket = bucket_keys[0]

    # Pull only rows in the window. `date` is stored as ISO `YYYY-MM-DD` string,
    # so a $gte against the bucket start works lexicographically.
    rows = await db.student_attendance.find(
        {"date": {"$gte": f"{earliest_bucket}-01"}},
        {"_id": 0},
    ).to_list(20000)

    if not rows:
        return {"success": True, "data": [], "empty": True}

    # overall_by_month[month] = {"present": int, "total": int}
    overall: dict[str, dict[str, int]] = defaultdict(lambda: {"present": 0, "total": 0})
    by_class: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"present": 0, "total": 0})
    )

    for r in rows:
        d = (r.get("date") or "")[:7]
        if not d or d not in bucket_keys:
            continue
        status = (r.get("status") or "").lower()
        overall[d]["total"] += 1
        if status == "present":
            overall[d]["present"] += 1
        class_id = r.get("class_id") or "_unknown"
        by_class[class_id][d]["total"] += 1
        if status == "present":
            by_class[class_id][d]["present"] += 1

    def _pct(p: int, t: int) -> float:
        return round((p / t * 100), 2) if t else 0.0

    return {
        "success": True,
        "empty": False,
        "months": bucket_keys,
        "overall": [
            {
                "month": m,
                "present": overall[m]["present"],
                "total": overall[m]["total"],
                "attendance_pct": _pct(overall[m]["present"], overall[m]["total"]),
            }
            for m in bucket_keys
        ],
        "by_class": [
            {
                "class_id": class_id,
                "series": [
                    {
                        "month": m,
                        "present": by_class[class_id][m]["present"],
                        "total": by_class[class_id][m]["total"],
                        "attendance_pct": _pct(by_class[class_id][m]["present"], by_class[class_id][m]["total"]),
                    }
                    for m in bucket_keys
                ],
            }
            for class_id in sorted(by_class.keys())
        ],
    }


@router.get("/fee-collection-summary")
async def fee_collection_summary(request: Request, months: int = 6):
    """AC2 + AC3 + AC4. Owner-only monthly collected vs outstanding."""
    user = _user(request)
    if user.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Owner only — financial data is restricted")

    months = _clamp_months(months, 1, 24)
    db = get_db()
    bucket_keys = _last_n_months(datetime.utcnow(), months)

    rows = await db.fee_transactions.find({}, {"_id": 0}).to_list(20000)

    if not rows:
        return {"success": True, "data": [], "empty": True}

    collected: dict[str, float] = defaultdict(float)
    outstanding: dict[str, float] = defaultdict(float)
    any_in_window = False

    for t in rows:
        try:
            amount = float(t.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        status = (t.get("status") or "").lower()

        if status == "paid":
            paid_date = (t.get("paid_date") or t.get("created_at") or "")[:7]
            if paid_date in bucket_keys:
                collected[paid_date] += amount
                any_in_window = True
        elif status in ("pending", "overdue", "unpaid"):
            due = (t.get("due_date") or t.get("created_at") or "")[:7]
            if due in bucket_keys:
                outstanding[due] += amount
                any_in_window = True

    if not any_in_window:
        return {"success": True, "data": [], "empty": True}

    return {
        "success": True,
        "empty": False,
        "months": bucket_keys,
        "data": [
            {
                "month": m,
                "collected": round(collected[m], 2),
                "outstanding": round(outstanding[m], 2),
            }
            for m in bucket_keys
        ],
    }
