"""RETIRED (2026-07-10) — this script is intentionally disabled.

It previously seeded a demo "Rohit Management" admin account (user +
auth login + staff record, ids user-admin-007 / staff-017). That was dummy
data and has been purged from the live database. Running this script would
re-create the dummy account, so it now refuses to run and exits without
touching the database.

Do NOT restore the old seeding logic. Real staff should be added through the
normal staff-creation flow, not this script.
"""
from __future__ import annotations

import sys


def main() -> None:
    print(
        "add_management_account.py is RETIRED and does nothing.\n"
        "The dummy 'Rohit Management' account was removed from production on "
        "2026-07-10 and must not be re-seeded. No database changes were made."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
