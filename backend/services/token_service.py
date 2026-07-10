"""
Token budget enforcement service for EduFlow.

Tracks LLM token usage per user per branch and enforces monthly limits
by role. Supports personal top-ups (Razorpay) and school-level top-ups.

Collections used:
  - token_balances   : one doc per branch — monthly plan pool + top-ups
  - token_usage      : append-only log of every LLM call
  - token_purchases  : payment receipts for top-up packs

Graceful fallback: if no token_balance document exists for a branch,
all calls are allowed (unlimited) so dev-mode and new branches work
without prior setup.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from database import get_db

logger = logging.getLogger(__name__)

# ─── Token packs ─────────────────────────────────────────────────────────────

PACKS = {
    "micro":    {"tokens": 50_000,    "price_inr": 49},
    "basic":    {"tokens": 200_000,   "price_inr": 149},
    "standard": {"tokens": 500_000,   "price_inr": 349},
    "power":    {"tokens": 1_200_000, "price_inr": 699},
    "school":   {"tokens": 3_000_000, "price_inr": 1499},
}

# Default per-role monthly token limits (can be overridden per branch)
DEFAULT_ROLE_LIMITS = {
    "owner":   1_000_000,
    "admin":   1_000_000,
    "teacher": 1_000_000,
    "student": 1_000_000,
}

# Sub-category overrides — checked before the role-level limit
DEFAULT_SUBCATEGORY_LIMITS: dict[str, int] = {
    "principal": 1_000_000,
}

# Warning threshold — flag when usage exceeds this fraction of the limit
WARNING_THRESHOLD = 0.80


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _current_month_key() -> str:
    """Return 'YYYY-MM' string for the current UTC month."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _resolve_branch_id(user: dict) -> str:
    """
    Extract branch_id from user dict.  Falls back to a dev default so
    the system never crashes when branch_id is absent.
    """
    return user.get("branch_id") or "branch-aaryans-joya"


# ─── check_and_reserve_tokens ────────────────────────────────────────────────

async def check_and_reserve_tokens(
    user: dict,
    branch_id: str,
    estimated_tokens: int = 2000,
) -> dict:
    """
    Called BEFORE every LLM call.

    Returns:
      {
        "allowed": bool,
        "source": "plan" | "personal_topup" | "school_topup" | "unlimited",
        "message": str,
        "can_recharge": bool,
      }
    """
    db = get_db()
    month = _current_month_key()
    role = user.get("role", "student")
    user_id = user.get("id", "unknown")

    # 1. Fetch branch token balance document
    balance_doc = await db.token_balances.find_one({"branch_id": branch_id})

    # Graceful fallback — no balance doc means unlimited (dev / new branch)
    if not balance_doc:
        return {
            "allowed": True,
            "source": "unlimited",
            "message": "No token budget configured — unlimited mode.",
            "can_recharge": False,
        }

    # 2. Per-role monthly limit (sub_category overrides role if defined)
    sub_category = user.get("sub_category") or ""
    role_limits = balance_doc.get("role_limits", DEFAULT_ROLE_LIMITS)
    sub_limits = balance_doc.get("sub_category_limits", DEFAULT_SUBCATEGORY_LIMITS)
    if sub_category and sub_category in sub_limits:
        role_limit = sub_limits[sub_category]
    else:
        role_limit = role_limits.get(role, DEFAULT_ROLE_LIMITS.get(role, 20_000))

    # -1 means unlimited for this role
    if role_limit == -1:
        return {
            "allowed": True,
            "source": "plan",
            "message": "Unlimited tokens for your role.",
            "can_recharge": False,
        }

    # 3. Calculate user's monthly usage so far
    user_monthly_usage = await db.token_usage.aggregate([
        {
            "$match": {
                "branch_id": branch_id,
                "user_id": user_id,
                "month": month,
            }
        },
        {
            "$group": {
                "_id": None,
                "total": {"$sum": "$tokens_used"},
            }
        },
    ]).to_list(1)

    used_this_month = user_monthly_usage[0]["total"] if user_monthly_usage else 0

    remaining_plan = max(0, role_limit - used_this_month)

    # 4. If plan quota covers the estimated call, allow from plan
    if remaining_plan >= estimated_tokens:
        return {
            "allowed": True,
            "source": "plan",
            "message": f"{remaining_plan:,} tokens remaining this month.",
            "can_recharge": False,
        }

    # 5. Check personal top-up balance
    personal_topup = balance_doc.get("personal_topups", {}).get(user_id, 0)
    if personal_topup >= estimated_tokens:
        return {
            "allowed": True,
            "source": "personal_topup",
            "message": f"Using personal top-up balance ({personal_topup:,} tokens left).",
            "can_recharge": True,
        }

    # 6. Check school-level top-up pool
    school_topup = balance_doc.get("school_topup_pool", 0)
    if school_topup >= estimated_tokens:
        return {
            "allowed": True,
            "source": "school_topup",
            "message": f"Using school top-up pool ({school_topup:,} tokens left).",
            "can_recharge": True,
        }

    # 7. Exhausted — determine if self-recharge is possible
    self_recharge_enabled = balance_doc.get("self_recharge_enabled", True)

    return {
        "allowed": False,
        "source": "exhausted",
        "message": (
            "Your monthly AI token limit has been reached. "
            + ("You can purchase a top-up pack to continue."
               if self_recharge_enabled
               else "Please contact your school administrator.")
        ),
        "can_recharge": self_recharge_enabled,
    }


# ─── record_usage ────────────────────────────────────────────────────────────

async def record_usage(
    user: dict,
    branch_id: str,
    tokens_used: int,
    source: str,
    conversation_id: str = None,
    tool_name: str = None,
) -> None:
    """
    Called AFTER every LLM call. Inserts a usage log entry and updates
    the appropriate balance (plan counter, personal top-up, or school pool).
    """
    if tokens_used <= 0:
        return

    db = get_db()
    month = _current_month_key()
    user_id = user.get("id", "unknown")
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Insert usage log
    usage_entry = {
        "branch_id": branch_id,
        "user_id": user_id,
        "role": user.get("role", "unknown"),
        "sub_category": user.get("sub_category") or "",
        "month": month,
        "tokens_used": tokens_used,
        "source": source,
        "conversation_id": conversation_id,
        "tool_name": tool_name,
        "created_at": now_iso,
    }
    try:
        await db.token_usage.insert_one(usage_entry)
    except Exception:
        logger.error("token_usage_insert_failed", exc_info=True)

    # 2. Update balance depending on source
    if source == "personal_topup":
        try:
            # R15.1 (P-L6): floor the debit at 0 so a burst of concurrent calls
            # can never drive a personal top-up balance negative. An aggregation
            # pipeline update keeps this atomic (single server-side op) while
            # clamping — mirrors R12.3's atomic credit path on the spend side.
            field = f"personal_topups.{user_id}"
            await db.token_balances.update_one(
                {"branch_id": branch_id},
                [{"$set": {field: {"$max": [0, {"$subtract": [{"$ifNull": [f"${field}", 0]}, tokens_used]}]}}}],
            )
        except Exception:
            logger.error("personal_topup_balance_update_failed", exc_info=True)

    elif source == "school_topup":
        try:
            await db.token_balances.update_one(
                {"branch_id": branch_id},
                {"$inc": {"school_topup_pool": -tokens_used}},
            )
        except Exception:
            logger.error("school_topup_pool_update_failed", exc_info=True)

    # For "plan" and "unlimited" sources, the usage is tracked in
    # token_usage only — the plan quota is computed dynamically from
    # the aggregation in check_and_reserve_tokens.

    # 3. Check if approaching limit and flag for notification
    if source in ("plan", "unlimited"):
        try:
            balance_doc = await db.token_balances.find_one({"branch_id": branch_id})
            if balance_doc:
                role_limits = balance_doc.get("role_limits", DEFAULT_ROLE_LIMITS)
                role_limit = role_limits.get(user.get("role", "student"), -1)
                if role_limit > 0:
                    agg = await db.token_usage.aggregate([
                        {
                            "$match": {
                                "branch_id": branch_id,
                                "user_id": user_id,
                                "month": month,
                            }
                        },
                        {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
                    ]).to_list(1)
                    total_used = agg[0]["total"] if agg else 0
                    usage_ratio = total_used / role_limit
                    if usage_ratio >= WARNING_THRESHOLD:
                        await db.token_balances.update_one(
                            {"branch_id": branch_id},
                            {
                                "$set": {
                                    f"warnings.{user_id}": {
                                        "month": month,
                                        "usage_ratio": round(usage_ratio, 3),
                                        "total_used": total_used,
                                        "limit": role_limit,
                                        "flagged_at": now_iso,
                                    }
                                }
                            },
                        )
        except Exception:
            logger.warning("token_warning_check_failed", exc_info=True)


# ─── get_usage_stats ─────────────────────────────────────────────────────────

async def get_usage_stats(
    branch_id: str,
    user_id: str = None,
    role: str = None,
    sub_category: str = None,
) -> dict:
    """
    Returns usage statistics for dashboard display.

    If user_id is given  -> that user's usage this month.
    If user_id is None   -> branch-level stats (for owner dashboard).
    role / sub_category  -> caller should pass these so the correct limit
                            is returned even when the user has zero usage.
    """
    db = get_db()
    month = _current_month_key()

    # ── User-level stats ──
    if user_id:
        pipeline = [
            {"$match": {"branch_id": branch_id, "user_id": user_id, "month": month}},
            {"$group": {"_id": None, "total_used": {"$sum": "$tokens_used"}}},
        ]
        agg = await db.token_usage.aggregate(pipeline).to_list(1)
        total_used = agg[0]["total_used"] if agg else 0

        # Look up the user's role limit
        balance_doc = await db.token_balances.find_one({"branch_id": branch_id})

        # Resolve role: prefer caller-supplied, fall back to last usage entry
        if not role:
            last_entry = await db.token_usage.find_one(
                {"branch_id": branch_id, "user_id": user_id, "month": month},
                sort=[("created_at", -1)],
            )
            role = last_entry["role"] if last_entry else "student"
            if not sub_category:
                sub_category = last_entry.get("sub_category", "") if last_entry else ""

        sub_category = sub_category or ""

        if balance_doc:
            role_limits = balance_doc.get("role_limits", DEFAULT_ROLE_LIMITS)
            sub_limits = balance_doc.get("sub_category_limits", DEFAULT_SUBCATEGORY_LIMITS)
            if sub_category and sub_category in sub_limits:
                role_limit = sub_limits[sub_category]
            else:
                role_limit = role_limits.get(role, DEFAULT_ROLE_LIMITS.get(role, 20_000))
            personal_topup = balance_doc.get("personal_topups", {}).get(user_id, 0)
            self_recharge_enabled = balance_doc.get("self_recharge_enabled", True)
        else:
            # No budget doc — use default limits (dev / new branch), never -1
            if sub_category and sub_category in DEFAULT_SUBCATEGORY_LIMITS:
                role_limit = DEFAULT_SUBCATEGORY_LIMITS[sub_category]
            else:
                role_limit = DEFAULT_ROLE_LIMITS.get(role, 20_000)
            personal_topup = 0
            self_recharge_enabled = True

        # Daily breakdown for the current month
        daily_pipeline = [
            {"$match": {"branch_id": branch_id, "user_id": user_id, "month": month}},
            {
                "$group": {
                    "_id": {"$substr": ["$created_at", 0, 10]},
                    "tokens": {"$sum": "$tokens_used"},
                }
            },
            {"$sort": {"_id": 1}},
        ]
        daily_agg = await db.token_usage.aggregate(daily_pipeline).to_list(31)
        breakdown_by_day = {d["_id"]: d["tokens"] for d in daily_agg}

        return {
            "user_id": user_id,
            "month": month,
            "total_used": total_used,
            "role_limit": role_limit if role_limit != -1 else None,
            "unlimited": role_limit == -1,
            "personal_topup_balance": personal_topup,
            "self_recharge_enabled": self_recharge_enabled,
            "breakdown_by_day": breakdown_by_day,
        }

    # ── Branch-level stats (owner view) ──
    pipeline = [
        {"$match": {"branch_id": branch_id, "month": month}},
        {
            "$group": {
                "_id": "$role",
                "total_used": {"$sum": "$tokens_used"},
                "unique_users": {"$addToSet": "$user_id"},
            }
        },
    ]
    agg = await db.token_usage.aggregate(pipeline).to_list(20)

    breakdown_by_role = {}
    grand_total = 0
    for entry in agg:
        role = entry["_id"]
        used = entry["total_used"]
        grand_total += used
        breakdown_by_role[role] = {
            "total_used": used,
            "unique_users": len(entry["unique_users"]),
        }

    # Daily breakdown (all users)
    daily_pipeline = [
        {"$match": {"branch_id": branch_id, "month": month}},
        {
            "$group": {
                "_id": {"$substr": ["$created_at", 0, 10]},
                "tokens": {"$sum": "$tokens_used"},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    daily_agg = await db.token_usage.aggregate(daily_pipeline).to_list(31)
    breakdown_by_day = {d["_id"]: d["tokens"] for d in daily_agg}

    balance_doc = await db.token_balances.find_one({"branch_id": branch_id})
    school_topup_pool = balance_doc.get("school_topup_pool", 0) if balance_doc else 0
    role_limits = balance_doc.get("role_limits", DEFAULT_ROLE_LIMITS) if balance_doc else DEFAULT_ROLE_LIMITS

    return {
        "branch_id": branch_id,
        "month": month,
        "grand_total_used": grand_total,
        "school_topup_pool": school_topup_pool,
        "role_limits": role_limits,
        "breakdown_by_role": breakdown_by_role,
        "breakdown_by_day": breakdown_by_day,
    }


# ─── get_balance ─────────────────────────────────────────────────────────────

async def get_balance(branch_id: str) -> dict:
    """Returns current token balance and configuration for the branch."""
    db = get_db()
    month = _current_month_key()

    balance_doc = await db.token_balances.find_one({"branch_id": branch_id})

    if not balance_doc:
        return {
            "branch_id": branch_id,
            "configured": False,
            "message": "No token budget configured. Running in unlimited mode.",
            "role_limits": DEFAULT_ROLE_LIMITS,
            "school_topup_pool": 0,
            "personal_topups": {},
            "self_recharge_enabled": True,
            "subscription_status": None,
            "subscription_plan": None,
            "subscription_current_period_end": None,
            "razorpay_customer_id": None,
        }

    # Total usage this month across all users
    agg = await db.token_usage.aggregate([
        {"$match": {"branch_id": branch_id, "month": month}},
        {"$group": {"_id": None, "total": {"$sum": "$tokens_used"}}},
    ]).to_list(1)
    total_used_this_month = agg[0]["total"] if agg else 0

    return {
        "branch_id": branch_id,
        "configured": True,
        "month": month,
        "role_limits": balance_doc.get("role_limits", DEFAULT_ROLE_LIMITS),
        "school_topup_pool": balance_doc.get("school_topup_pool", 0),
        "personal_topups": balance_doc.get("personal_topups", {}),
        "self_recharge_enabled": balance_doc.get("self_recharge_enabled", True),
        "total_used_this_month": total_used_this_month,
        "warnings": balance_doc.get("warnings", {}),
        "subscription_status": balance_doc.get("subscription_status"),
        "subscription_plan": balance_doc.get("subscription_plan"),
        "subscription_current_period_end": balance_doc.get("subscription_current_period_end"),
        "razorpay_customer_id": balance_doc.get("razorpay_customer_id"),
    }


# ─── purchase_topup ──────────────────────────────────────────────────────────

async def purchase_topup(
    branch_id: str,
    user_id: str,
    pack_id: str,
    payment_id: str,
) -> dict:
    """
    Record a token purchase after Razorpay payment confirmation.
    Adds tokens to the user's personal top-up balance.
    """
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    pack = PACKS.get(pack_id)
    if not pack:
        return {"success": False, "error": f"Unknown pack: {pack_id}"}

    # Prevent duplicate processing of the same payment
    existing = await db.token_purchases.find_one({"payment_id": payment_id})
    if existing:
        return {"success": False, "error": "Payment already processed."}

    tokens = pack["tokens"]
    price = pack["price_inr"]

    # 1. Record the purchase
    purchase_doc = {
        "branch_id": branch_id,
        "user_id": user_id,
        "pack_id": pack_id,
        "tokens": tokens,
        "price_inr": price,
        "payment_id": payment_id,
        "created_at": now_iso,
    }
    await db.token_purchases.insert_one(purchase_doc)

    # 2. Credit tokens to user's personal top-up balance
    await db.token_balances.update_one(
        {"branch_id": branch_id},
        {
            "$inc": {f"personal_topups.{user_id}": tokens},
            "$setOnInsert": {
                "branch_id": branch_id,
                "role_limits": DEFAULT_ROLE_LIMITS,
                "school_topup_pool": 0,
                "self_recharge_enabled": True,
                "created_at": now_iso,
            },
        },
        upsert=True,
    )

    logger.info(
        f"Token purchase: user={user_id} branch={branch_id} "
        f"pack={pack_id} tokens={tokens} payment={payment_id}"
    )

    return {
        "success": True,
        "pack_id": pack_id,
        "tokens_added": tokens,
        "price_inr": price,
        "payment_id": payment_id,
    }


# ─── update_role_limits ─────────────────────────────────────────────────────

async def update_role_limits(branch_id: str, limits: dict) -> dict:
    """
    Owner updates per-role token limits for the branch.

    limits example: {"owner": -1, "admin": 100000, "teacher": 50000, "student": 20000}
    """
    db = get_db()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Validate limits
    validated = {}
    for role, limit_val in limits.items():
        if role not in ("owner", "admin", "teacher", "student"):
            return {"success": False, "error": f"Invalid role: {role}"}
        try:
            limit_int = int(limit_val)
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid limit for {role}: {limit_val}"}
        validated[role] = limit_int

    # Merge with existing limits so partial updates work
    balance_doc = await db.token_balances.find_one({"branch_id": branch_id})
    if balance_doc:
        existing_limits = balance_doc.get("role_limits", {})
        existing_limits.update(validated)
        merged = existing_limits
    else:
        merged = {**DEFAULT_ROLE_LIMITS, **validated}

    await db.token_balances.update_one(
        {"branch_id": branch_id},
        {
            "$set": {
                "role_limits": merged,
                "updated_at": now_iso,
            },
            "$setOnInsert": {
                "branch_id": branch_id,
                "school_topup_pool": 0,
                "self_recharge_enabled": True,
                "personal_topups": {},
                "created_at": now_iso,
            },
        },
        upsert=True,
    )

    logger.info(f"Role limits updated for branch={branch_id}: {merged}")

    return {"success": True, "role_limits": merged}
