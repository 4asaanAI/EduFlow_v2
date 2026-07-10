from __future__ import annotations

"""Canonical fee-outstanding math shared across AI tools (R7.1 / M5).

Before R7 there were four subtly different "outstanding" formulas (fee_summary,
defaulters, smart-alerts, context_builder). They disagreed on whether to include
``unpaid`` status and on the ``partial`` remainder, so the numbers the assistant
reported depended on which tool answered. This module is the ONE source of truth.

Definitions
-----------
collected   = SUM(amount WHERE status=paid) + SUM(paid_amount WHERE status=partial)
outstanding = SUM(amount WHERE status in overdue/pending/unpaid)
              + SUM(amount - paid_amount WHERE status=partial)
rate        = collected / (collected + outstanding) * 100
defaulter   = any student carrying an outstanding balance
              (status in overdue/pending/unpaid/partial), NOT only status=overdue.
"""

# Statuses that carry a full outstanding balance (partial handled separately).
OUTSTANDING_STATUSES = ("overdue", "pending", "unpaid")
# A student is a "defaulter" if they hold any transaction in these statuses.
DEFAULTER_STATUSES = ("overdue", "pending", "unpaid", "partial")


async def compute_fee_totals(db, match: dict) -> dict:
    """Canonical collected / outstanding / collection_rate for a fee_transactions filter.

    ``match`` must already be tenant/branch scoped by the caller (each caller has a
    different scoping helper — scoped_query, _tenant_query, _tenant_match).
    """
    pipeline = [
        {"$match": match},
        {
            "$group": {
                "_id": "$status",
                "total_amount": {"$sum": "$amount"},
                "total_paid_amount": {"$sum": {"$ifNull": ["$paid_amount", 0]}},
                "count": {"$sum": 1},
            }
        },
    ]
    rows = await db.fee_transactions.aggregate(pipeline).to_list(20)
    s = {r["_id"]: r for r in rows}

    def _a(status: str) -> float:
        return float(s.get(status, {}).get("total_amount", 0))

    def _p(status: str) -> float:
        return float(s.get(status, {}).get("total_paid_amount", 0))

    collected = _a("paid") + _p("partial")
    partial_remaining = max(0.0, _a("partial") - _p("partial"))
    outstanding = _a("overdue") + _a("pending") + _a("unpaid") + partial_remaining
    total = collected + outstanding
    rate = round(collected / total * 100, 1) if total > 0 else 0.0

    return {
        "collected": collected,
        "outstanding": outstanding,
        "partial_remaining": partial_remaining,
        "collection_rate": rate,
        "by_status_amount": {status: _a(status) for status in s},
    }


def student_outstanding_from_txns(txns: list) -> dict:
    """Per-student owed balance from outstanding transactions.

    Matches the defaulter math in fee_summary: ``partial`` rows owe
    ``amount - paid_amount``; all other outstanding rows owe the full ``amount``.
    Returns ``{student_id: {"owed": float, "oldest_due": str}}``.
    """
    dues: dict = {}
    for txn in txns:
        sid = txn.get("student_id")
        if not sid:
            continue
        status = txn.get("status", "")
        amount = float(txn.get("amount", 0))
        paid_amt = float(txn.get("paid_amount") or 0) if status == "partial" else 0.0
        owed = max(0.0, amount - paid_amt)
        due = txn.get("due_date", "")
        if sid not in dues:
            dues[sid] = {"owed": 0.0, "oldest_due": due}
        dues[sid]["owed"] += owed
        if due and (not dues[sid]["oldest_due"] or due < dues[sid]["oldest_due"]):
            dues[sid]["oldest_due"] = due
    return dues
