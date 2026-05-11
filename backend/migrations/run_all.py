"""
Migration Runner: Executes all migrations in order.
Run: python backend/migrations/run_all.py

Each migration is idempotent and tracked in a `_migrations` collection.
Safe to run multiple times - already-applied migrations are skipped.

Usage:
    python backend/migrations/run_all.py            # Run all pending migrations
    python backend/migrations/run_all.py --status    # Show migration status
    python backend/migrations/run_all.py --reset     # Clear migration tracking (re-run all)
"""
import asyncio
import os
import sys
import importlib
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Add parent directory to path so we can import migration modules
sys.path.insert(0, str(Path(__file__).parent))

# Ordered list of migrations
MIGRATIONS = [
    ("001_add_branches", "Add branches collection and branch_id to existing data"),
    ("002_add_houses", "Add houses, house_points, assign houses to students"),
    ("003_add_staff_hierarchy", "Add staff hierarchy fields (sub_category, designation, wing, etc.)"),
    ("004_add_transport", "Add vehicles, transport_routes, student_transport"),
    ("005_add_library", "Add library_books, library_transactions with sample data"),
    ("006_add_inventory_vendors", "Add inventory_items, vendors, purchase_orders"),
    ("007_add_fees_discounts", "Add fee_discounts, student_fee_profiles"),
    ("008_add_events_sports", "Add school_events, sports_teams, clubs"),
    ("009_add_payroll", "Add salary_structures, salary_disbursements, expenses"),
    ("010_add_tokens", "Add token_usage, token_balance, token_recharges"),
    ("011_add_support_tickets", "Add support_tickets collection"),
    ("012_migrate_uploads_to_s3", "Migrate legacy uploads to private S3 storage"),
]


async def is_applied(db, migration_name):
    """Check if a migration has already been applied."""
    record = await db._migrations.find_one({"name": migration_name})
    return record is not None


async def mark_applied(db, migration_name, description):
    """Mark a migration as applied."""
    await db._migrations.insert_one({
        "name": migration_name,
        "description": description,
        "applied_at": datetime.now().isoformat(),
    })


async def show_status(db):
    """Display the status of all migrations."""
    print("\n" + "=" * 70)
    print("  MIGRATION STATUS")
    print("=" * 70)
    print(f"  {'Migration':<30} {'Status':<12} {'Applied At'}")
    print("-" * 70)

    for name, description in MIGRATIONS:
        record = await db._migrations.find_one({"name": name})
        if record:
            applied_at = record.get("applied_at", "unknown")
            status = "APPLIED"
            print(f"  {name:<30} {status:<12} {applied_at}")
        else:
            status = "PENDING"
            print(f"  {name:<30} {status:<12} -")

    total_applied = await db._migrations.count_documents({})
    total = len(MIGRATIONS)
    print("-" * 70)
    print(f"  {total_applied}/{total} migrations applied")
    print("=" * 70 + "\n")


async def reset_tracking(db):
    """Clear migration tracking so all migrations can be re-run."""
    result = await db._migrations.delete_many({})
    print(f"\nCleared migration tracking ({result.deleted_count} records removed).")
    print("Run again without --reset to re-apply all migrations.\n")


async def run_all():
    client = AsyncIOMotorClient(MONGO_URL, tlsInsecure=True, retryWrites=True)
    db = client[DB_NAME]

    try:
        # Test connection
        await db.command("ping")
        print(f"Connected to MongoDB: {DB_NAME}")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        client.close()
        return

    # Handle CLI arguments
    if "--status" in sys.argv:
        await show_status(db)
        client.close()
        return

    if "--reset" in sys.argv:
        await reset_tracking(db)
        client.close()
        return

    # Ensure _migrations index
    mi_indexes = await db._migrations.index_information()
    if "name_1" not in mi_indexes:
        await db._migrations.create_index("name", unique=True)

    print("\n" + "=" * 70)
    print("  EDUFLOW MIGRATION RUNNER")
    print("=" * 70)
    print(f"  Database: {DB_NAME}")
    print(f"  Migrations: {len(MIGRATIONS)}")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    applied_count = 0
    skipped_count = 0
    failed_count = 0

    for name, description in MIGRATIONS:
        # Check if already applied
        if await is_applied(db, name):
            print(f"  SKIP  {name} (already applied)")
            skipped_count += 1
            continue

        # Import and run the migration
        print(f"\n  RUN   {name}: {description}")
        print("-" * 60)

        try:
            module = importlib.import_module(name)
            await module.migrate(db=db)
            await mark_applied(db, name, description)
            applied_count += 1
            print(f"  OK    {name}")
        except Exception as e:
            print(f"\n  FAIL  {name}: {e}")
            failed_count += 1
            import traceback
            traceback.print_exc()
            print(f"\n  Stopping due to failure in {name}.")
            print(f"  Fix the issue and re-run. Already-applied migrations will be skipped.\n")
            break

    # Summary
    print("\n" + "=" * 70)
    print("  MIGRATION SUMMARY")
    print("=" * 70)
    print(f"  Applied:  {applied_count}")
    print(f"  Skipped:  {skipped_count}")
    print(f"  Failed:   {failed_count}")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    client.close()


if __name__ == "__main__":
    asyncio.run(run_all())
