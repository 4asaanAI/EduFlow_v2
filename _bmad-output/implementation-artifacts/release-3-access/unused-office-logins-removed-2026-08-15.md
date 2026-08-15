# The seven unused office logins are gone (2026-08-15)

**Abhimanyu's decision, 2026-08-15.** The one-time passwords migration 041 issued were
never handed out. Only four handovers ever went out, and they stop at Lalit. Each of those
seven people will be given their proper profile in their own release, so the accounts were
removed rather than left sitting there.

This closes the exposure recorded in `CLAUDE.md` under the release-numbering collision:
two assistant accountants held exactly what the accountant head holds, salaries included,
and two admin staff held exactly what the management head holds. Nobody designed that, and
"dormant" was documentation rather than a lock.

## Proven before anything was deleted

Read-only, against the live database:

| Login | Still on its one-time password | Sessions ever |
|---|---|---|
| sachin.yadav, shivam.kumar, sakshi.gupta, sameer, vipin.kumar, asniya, chaman.singh | yes, all seven | 0, all seven |

Never signed into, not one session created. That is what made the removal safe rather than
a judgement call.

## What was removed

- **7 logins** from `auth_users`.
- **7 profile rows** from `users`, created by migration 047. These had to go with them.
  `users` is the list the platform reads when it decides **who to tell**, so a profile with
  no login behind it keeps being addressed by notifications and digests that can never
  reach anybody. Leaving them is the same fault 047 was written to close, pointing the
  other way.
- **7 staff links cleared.** The staff records themselves are untouched and still on the
  roll. Those seven people still work at the school; only the account was removed.

Backups of everything removed were written OUTSIDE the repository, alongside the other
041 files. No plaintext password was in them and none is in this repo.

## Do NOT use `041_office_staff_logins.py --rollback` for this

It is broader than the job and it does real damage. The saved rollback file also clears the
staff link for **Adesh Singh and Lalit Thomas**, who both sign in for real, which would
split those two people from their own staff records. The removal was done with a targeted
script touching only the seven.

## Verified afterwards

- The seven logins remaining: **0**.
- Their staff records still present: **7**, none pointing at a login.
- Adesh, Lalit and Sonu: all present, all still linked to their staff records.
- `auth_users` and `users` both **1,897**, one profile per login exactly.

**One trap for whoever checks this next.** `users.id` is NOT `auth_users.id`. It is the id
inside `auth_users.user_info`, which for the older accounts is a readable string like
`user-admin-001-adesh`. A check that joins on `auth_users.id` finds nothing and reads
exactly like every profile being orphaned. That happened during this verification and was
a wrong query, not a wrong database.

## What this does not do

The seven people have no way to sign in until their release builds their profile. That is
the intended state, not an outage: they never had a working account, because they were
never given the password.

The **four shared desk accounts** (`transport`, `reception`, `ittech`, `maintenance`) were
untouched by this removal. They are desks rather than people and were never part of the 041
handover. *(They were deleted later the same day on Abhimanyu's instruction. See
`shared-desk-logins-removed-2026-08-15.md`. This paragraph was true when written.)*
