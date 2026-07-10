# Epic R12 Review — Onboarding, Billing & Payroll Integrity

**For:** Abhimanyu / Shubham  
**Date:** 2026-07-10  
**Status:** COMPLETE — 1568 tests passing

---

## What we fixed and why it mattered

**R12.1 — New schools couldn't log in reliably.**  
When a school was provisioned, the owner account was missing two fields: `username_lower` (needed for case-insensitive login) and `user_info` (needed for the AI to know who it's talking to). A school owner who typed their email in a different case would see a login failure with no explanation. Fixed: provisioning now derives name and initials from the email and stores both fields.

**R12.2 — Razorpay webhook could credit the wrong school.**  
The billing service had a shared database handle that could get confused when webhooks arrive in quick succession. A payment made by School B could theoretically have credited School A's token balance. Fixed: each webhook now resolves the correct school from the branch ID in the webhook payload before any money operation, with full cross-tenant isolation proven by test.

**R12.3 — First top-up for a new school always failed.**  
MongoDB rejected the very first payment for any new school branch because of a field naming conflict in the upsert operation (`personal_topups: {}` conflicted with `personal_topups.user_id`). This was silently swallowed. Also: the purchase insert and balance update were not atomic — a crash between them left credit uncredited. Fixed: conflict removed; both ops now run in a transaction. Replayed webhooks are idempotent.

**R12.4 — A crashed provisioning left the school permanently stuck.**  
If the server crashed between writing the school record and creating the owner account, the school was in a "zombie" state — exists in the DB but has no owner. Re-trying provisioning returned 409 (already exists) with no way to recover without manual DB intervention. Fixed: retry now detects the partial state, cleans up the stub, and re-provisions cleanly.

**R12.5 — Salary could be paid twice; wrong staff could approve it.**  
Submitting the disbursement form twice (e.g. double-click or network retry) created two salary rows, doubling the reported payroll. Also, the payroll API accepted `"accounts"` sub-category which was a fee-domain concept, not payroll — an accountant in the fee context could have approved payroll they shouldn't touch. Fixed: disbursement is now idempotent; payroll routes require the canonical `"accountant"` role.

---

## What needs human verification

- [ ] **Provision a new school end-to-end and log in as the owner immediately.** The owner email-as-username login should work on the first try, in any case (UPPERCASE, lowercase, mixed). *(R12.1 — the most user-visible fix)*
- [ ] **Check the Razorpay dashboard after a real payment** — confirm the token balance in the correct school's branch was credited. *(R12.2 — can only be confirmed with a live Razorpay test payment)*
- [ ] **Make a top-up for a brand-new school** (one that has never had a token balance doc). It should succeed. Previously this always silently failed. *(R12.3)*
- [ ] **Confirm payroll: duplicate form submit.** Submit a salary disbursement, then immediately submit the same form again. The second submit should return "already paid" with the original record, not create a new row. *(R12.5 AC2)*
- [ ] **Confirm payroll auth:** Log in as an admin with `sub_category: accounts` (the old fee accountant role) and try to disburse a salary. It should be rejected with 403. *(R12.5 AC3)*

---

## Decisions made

1. **`fees.py` keeps accepting `"accounts"` for now.** Fee routes predated the canonical rename. Changing them immediately would break live fee-accountant workflows. Only payroll routes enforce `"accountant"`. The right fix is a one-time data migration of `sub_category: accounts → accountant` in `auth_users`, which is a separate story.

2. **ContextVar for webhook tenant isolation, not a per-call ScopedDatabase.** We set `_school_id_var` before calling `get_db()` so production code uses the standard `ScopedDatabase` path (same as every other request). Tests patch `get_db` to return a fake — the ContextVar set is a no-op in tests, which is correct.

3. **`personal_topups: {}` removed from `$setOnInsert`.** MongoDB's `$inc` on a dotted path (`personal_topups.user_id`) auto-creates the parent object. Adding an explicit empty-object init in `$setOnInsert` triggered a path conflict. Removal is safe and is the documented MongoDB pattern.
