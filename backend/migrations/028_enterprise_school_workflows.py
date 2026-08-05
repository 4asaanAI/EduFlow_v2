"""Migration 028: indexes for additive enterprise school workflows.

This migration creates indexes only. It does not seed, rewrite, backfill, or delete
school data. Legacy library/inventory collections from migrations 005/006 remain
untouched and readable.
"""

from __future__ import annotations


async def migrate(db=None):
    if db is None:
        raise RuntimeError("Run migration 028 through migrations/run_all.py")

    await db.fee_transactions.create_index("charge_key", unique=True, sparse=True)
    await db.fee_structure_revisions.create_index([("structure_id", 1), ("version", -1)])
    await db.school_fee_checkouts.create_index("razorpay_reference_id", unique=True, sparse=True)
    await db.admission_applications.create_index([("branch_id", 1), ("status", 1), ("created_at", -1)])
    await db.admission_applications.create_index(
        [("schoolId", 1), ("enquiry_id", 1)], unique=True, sparse=True
    )
    await db.student_leave_requests.create_index(
        [("student_id", 1), ("start_date", 1), ("end_date", 1), ("status", 1)]
    )
    await db.student_leave_days.create_index([("student_id", 1), ("date", 1)], unique=True)
    await db.resources.create_index([("branch_id", 1), ("is_active", 1), ("name", 1)])
    await db.resource_bookings.create_index(
        [("resource_id", 1), ("start_at", 1), ("end_at", 1), ("status", 1)]
    )
    await db.asset_custody.create_index([("asset_id", 1), ("status", 1)])
    await db.inventory_items.create_index(
        [("schoolId", 1), ("branch_id", 1), ("sku", 1)], unique=True, sparse=True
    )
    await db.stock_movements.create_index([("item_id", 1), ("posted_at", -1)])
    await db.purchase_requisitions.create_index([("branch_id", 1), ("status", 1), ("created_at", -1)])
    await db.purchase_orders.create_index(
        [("schoolId", 1), ("requisition_id", 1)], unique=True, sparse=True
    )
    await db.library_titles.create_index(
        [("schoolId", 1), ("branch_id", 1), ("accession_number", 1)], unique=True
    )
    await db.library_loans.create_index(
        [("borrower_type", 1), ("borrower_id", 1), ("status", 1), ("due_at", 1)]
    )
    await db.accounting_periods.create_index(
        [("branch_id", 1), ("start_date", 1), ("end_date", 1), ("status", 1)]
    )
    await db.salary_disbursement_corrections.create_index(
        [("disbursement_id", 1), ("revision", 1)], unique=True
    )
    await db.guardians.create_index([("user_id", 1), ("student_id", 1)])
    await db.quizzes.create_index([("class_id", 1), ("status", 1), ("created_at", -1)])
    await db.quiz_attempts.create_index(
        [("quiz_id", 1), ("student_id", 1), ("attempt_number", 1)], unique=True
    )
    await db.razorpay_webhook_inbox.create_index("id", unique=True)
    await db.razorpay_webhook_inbox.create_index([("status", 1), ("updated_at", 1)])


if __name__ == "__main__":
    raise SystemExit("Run through: python backend/migrations/run_all.py")
