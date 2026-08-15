# The four shared desk logins are gone (2026-08-15)

**Abhimanyu's instruction, 2026-08-15:** delete every account that stands for a whole
department rather than a person, because they clash with the per-person profiles the
releases are building.

Four existed, and they were the last of that kind:

| Login | Displayed as | Profile it held |
|---|---|---|
| `transport` | Transport Desk | `transport_head` |
| `reception` | Reception Desk | `receptionist` |
| `ittech` | IT Desk | `it_tech` |
| `maintenance` | Maintenance Desk | `maintenance` |

`accountant` and `management` were the same idea and were turned into Sonu and Lalit by
migration 033 back on 2026-08-11. The seven unused 041 office logins went earlier the same
day as this. So **every remaining login on the platform now belongs to one named person**:
Aman Litt, Adesh Singh, Sonu Ruhal, Lalit Thomas and Chaman Singh, plus the teachers and
students.

## Why it mattered, beyond tidiness

`Transport Desk` carried `transport_head` - **the very same profile Chaman Singh was given
hours earlier**. Two accounts answering to one profile is exactly the confusion this
removes: a decision recorded by "the transport desk" can never be traced back to the person
who took it.

## Proven read-only before anything was deleted

- **Zero sessions ever** and zero refresh tokens, for all four.
- **Zero documents anywhere in the database** referenced any of the eight ids (four
  `auth_users.id` plus four `user_info.id`) through any authorship, actor, approval,
  assignment or messaging field. Every collection was checked, not a sample.
- **No staff records** exist for these desks, so no staff link had to be cleared.
- Nothing in the running backend or frontend reads these usernames or ids. The only hits
  in the repository are test fixtures carrying their own made-up ids.

The removal script refuses to delete if that check finds anything, so the proof is not a
one-off: it re-runs every time.

## What was removed, and how to undo it

`backend/migrations/050_remove_shared_desk_logins.py`, run on its own, never through
`run_all.py`. Four rows from `auth_users` and their four matching rows from `users`.
Afterwards both collections stand at **1,894**, one profile per login exactly.

The rollback file is `rollback-050-20260815T090001Z.json` under
`~/eduflow-migration-backups/`, **outside this public repository**. Unlike the 041 backups
it deliberately keeps the bcrypt hash, so a rollback restores a login that actually works
rather than a row nobody can sign into. Never copy that file into the repo.

## Two traps

`users.id` is NOT `auth_users.id`. It is the id inside `auth_users.user_info`, a readable
string like `user-admin-003`. A check joining on `auth_users.id` finds nothing and reads
exactly like every profile being orphaned.

`db._migrations` raises on Motor, which reads the leading underscore as an attribute rather
than a collection name. Use `db["_migrations"]`. The deletion had already completed when
this fired, so the run looked like a crash while every record it printed was true.

## What this does not do

The four `sub_category` values stay in the code and in the permission table. This deleted
accounts, not profiles. When the school needs a receptionist or an IT person on the
platform, they get a named login of their own in their own release.
