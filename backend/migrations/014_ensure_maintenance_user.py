"""
Migration 014: RETIRED (2026-07-10).

This migration previously upserted a demo "Arvind Maintenance" admin account
(auth login + user profile + staff record, ids user-admin-006 / staff-015).
That was dummy seed data. It has been purged from the live database and must
never be re-created — so this migration is now a no-op.

It is intentionally kept in the ordered list (and importable with the same
`migrate(db=None)` signature) so the migration ledger and numbering stay
intact. On databases where 014 was already marked applied, nothing changes.
On a fresh database it simply records as applied without seeding anything.

Do NOT restore the old seeding body. If a real maintenance staff member is
needed, add them through the normal staff-creation flow, not a migration.
"""
import asyncio


async def migrate(db=None):
    print("  Migration 014 is RETIRED — no-op (dummy maintenance account is not seeded).")


if __name__ == "__main__":
    asyncio.run(migrate())
