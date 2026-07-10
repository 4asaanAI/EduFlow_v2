# Epic R13 — Tenancy & RBAC Fail-Closed — Review

**Date:** 2026-07-10
**Reviewer:** executing agent (post-implementation adversarial review)

---

## What went well

- **All 9 stories fully shipped** with 38 new tests covering the specific failure modes (not just happy-path assertions).
- **ScopedCollection method gap (R13.1)** is now structurally closed: any route that acquires `db = get_db()` and calls any Mongo method will inject `schoolId` automatically. `bulk_write` raises loudly rather than silently escaping scoping.
- **Canonical revocation (R13.7):** swapping the hand-rolled `{"revoked": False}` query (for a field that doesn't exist) for `revoke_user_refresh_tokens()` fixed a silent no-op bug that had been there since staff deactivation was introduced. The test would previously pass because the assertion checked nothing meaningful.
- **`sub_category: "accountant"` canonicalization (R13.3, R13.8):** the canonical name is now enforced on the export and SMS paths. The legacy `"accounts"` alias in `fees.py::_is_accounts` is the only remaining use (tracked in DEFERRED-AND-DISCOVERIES.md; requires a data migration).
- **Regex injection sweep (R13.6):** all four routes affected by P-M6 now use `re.escape()` + format-validation; a crafted `period=2026-01$` can no longer construct arbitrary regex patterns.
- **Daily SMS cap (R13.8):** protects against runaway Azure/Twilio spend in a single school per day; the cap is env-configurable so it can be adjusted per-tenant without a deploy.
- **Atomic bulk import (R13.9):** `get_txn_session()` returns a real Motor session in production and a `_NoopSession` in dev — the import path is now production-safe without complicating the local dev loop.

## Issues found and fixed during implementation

### test_sms_bulk_logs_each_recipient_when_not_configured — 400 instead of expected
New student-ownership validation filtered out all recipients because `_sms_db` fixture had no student docs. Fixed by seeding the fixture with `stu-1` and `stu-2`.

### test_delete_staff_soft_deactivates_and_revokes_sessions — assertion failure + KeyError
Two root causes:
1. The new `revoke_user_refresh_tokens` helper sets `revoked_at` (canonical schema), not a `revoked: bool` field. The old fixture used `{"revoked": False}` and the assertion checked `["revoked"] is True` — both now canonical.
2. The token created by `issue_refresh_token` (from the login step in the test) doesn't have an `"id"` key, causing `KeyError` when iterating. Fixed with `doc.get("id")`.

### test_expense_export_accessible_to_accountant — 403
R13.3 intentionally dropped the legacy `"accounts"` sub_category from the export gate. The test had been using `"accounts"`. Fixed to use canonical `"accountant"`.

### test_validate_import_reports_errors_and_duplicates — valid_count == 0
`scoped_query` adds a `schoolId` filter; the local FakeDb docs lacked `schoolId`. Added `schoolId: "aaryans-joya"` to FakeDb and added `$and`/`$or` handling to the local `_matches` function.

### test_commit_import_skips_duplicates_without_overwrite — TypeError
The local FakeCollection's `insert_one`/`update_one` didn't accept `**kwargs`; Motor session is passed as a kwarg. Fixed by adding `**kwargs` to both.

### test_scoped_collection_distinct_scopes_to_school — AttributeError
`FakeCollection` in `conftest.py` didn't have a `distinct` method. Added it with correct school-scoped set comprehension.

## Risk areas and mitigations

| Risk | Mitigation |
|------|-----------|
| `find_one_and_update` with `upsert=True` — must inject `schoolId` into `$setOnInsert` | Handled explicitly in the implementation; test `test_find_one_and_update_upsert_injects_school_id` covers the upsert path |
| `replace_one` / `find_one_and_replace` — replacement doc could overwrite `schoolId` | Implementation checks `if "schoolId" not in replacement` and injects; the test verifies the final doc retains the correct `schoolId` |
| SMS cap per-school vs per-branch | Cap is per-school for now (simpler, less risk of wrong-branch attribution); can be tightened per-branch later via config |
| Motor session in bulk import | `get_txn_session()` returns `_NoopSession` in dev to avoid requiring a replica set; production uses real txn; this is pre-existing design from R12 |

## Architectural notes

- **`can_cross_user` pattern (R13.2):** the file-serve least-exposure check is now `role == "owner" or (role == "admin" and sub_category == "principal")`. This is identical to `require_owner_or_principal`'s logic — a future refactor could extract it into a helper, but it's small enough to be readable inline.
- **Branch-scoping in exports (R13.3):** teacher attendance and results exports scope by teacher's classes (not by branch directly) because teachers span classes, not branches. This is correct: a teacher in branch A who has two classes both in branch A will see only those classes.
- **Login lockout key (R13.4):** using `school_id` from the request body (falling back to `get_school_id()`) means a single-tenant deployment has the same lockout behavior as before; a multi-tenant deployment now correctly isolates lockouts per school.

## Recommendation for Abhimanyu/Shubham

The high-severity security findings (P-H3 file exposure, P-H4 export RBAC, P-H5 branch scope leak, P-H7 session revocation) are all fixed and tested. The medium-severity findings (P-M1 through P-M8) are similarly closed.

**The one item needing a data migration before it can be fully closed:** legacy `sub_category: "accounts"` in production `auth_users` documents. Users with the old sub_category can still access fees routes (the `_is_accounts` check in `fees.py` still accepts `"accounts"` for backwards compat). Once you run a migration updating `sub_category: accounts → accountant` in all user documents, that compat shim can be removed.
