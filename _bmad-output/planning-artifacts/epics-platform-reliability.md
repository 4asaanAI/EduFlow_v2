# Epics & Stories — Platform Reliability (Non-AI Layer)

**Date:** 2026-07-08 · **Source:** `audit-platform-reliability-2026-07-08.md` · **Architecture:** `architecture.md`
**Numbering:** Continues the AI-layer initiative (R1–R11). This document is **R12–R15**. Same conventions: written for any executing agent/model, every story carries exact `file:line` + acceptance criteria (AC), baseline `python -m pytest tests/backend/ -x -q` before and after each epic, one epic per run per `EPIC-EXECUTION-PROTOCOL-AI-RELIABILITY.md` (the 7 standing rules and handoff prompt apply unchanged). Audit finding IDs (P-C/P-H/P-M/P-L) refer to `audit-platform-reliability-2026-07-08.md`.
**Build order:** R12 → R13 → R14 → R15. R12 (onboarding + billing) is the highest-severity and unblocks the SaaS multi-school direction; R15 (residual sweep) is last, mirroring R11.6.
**Total: 4 epics / 21 stories.**

> **Prime directive (inherited):** every story FIXES the underlying defect; a nicer error message is never the fix. Every new/changed endpoint gets the standard security test pair (401 unauthenticated, 403 wrong-role) and, for any tenant-touching change, a cross-tenant fixture test proving isolation.

---

## EPIC R12 — Onboarding, Billing & Payroll Integrity
*Goal: a provisioned school can log in, a paid rupee always credits the right tenant exactly once, and a salary is disbursed through one correct path. Fixes P-C1, P-C2, P-H1, P-H2, P-H6, P-M4.*

**R12.1 — Provisioned owner can log in (P-C1)**
Files: `backend/routes/operator.py:280-290`, `backend/routes/auth.py:118-149`
- AC1: `create_school` writes the owner `auth_users` row with `username_lower` (lowercased email) AND a `user_info` sub-document (`id`, `role: "owner"`, `name`, `initials`) matching what `_jwt_payload_from_auth` reads.
- AC2: Integration test: provision a school via `POST /api/operator/schools`, then `POST /api/auth/login` with the returned username + temp password succeeds and returns a JWT with `role=owner` and the correct `school_id`.
- AC3: The provisioned row satisfies the `(username_lower, schoolId)` unique index (no null `username_lower`); provisioning two schools with the same owner email succeeds (different `schoolId`).

**R12.2 — Webhooks credit the correct tenant (P-C2)**
Files: `backend/services/razorpay_service.py:143-374`, `backend/routes/tokens.py:242-281`
- AC1: Each webhook handler resolves `school_id` from a durable source tied to the payment — derived from the `branch_id`/`user_id` in `notes` (look up the branch's or user's `schoolId`), NOT from the ambient env-default `get_school_id()`.
- AC2: All `token_purchases`/`token_balances` reads and writes in the handlers are scoped to that resolved `school_id` (pass it explicitly, e.g. `get_db()` with the context set, or scoped helpers).
- AC3: Cross-tenant test: a webhook whose `notes.branch_id` belongs to school B credits school B's balance, never the env-default school A.
- AC4: A webhook whose branch/user cannot be resolved to a school is logged and rejected (no silent credit to the default tenant).

**R12.3 — Atomic, conflict-free credit (P-H1, P-H2)**
Files: `backend/services/razorpay_service.py:278-287, 349-364`
- AC1: The `personal_topups.{user_id}` `$inc` + `personal_topups: {}` `$setOnInsert` path conflict is removed — either drop the redundant `$setOnInsert` of the parent path, or pre-create the balance doc, so the **first** top-up for a brand-new branch succeeds. Regression test: top-up against a branch with no `token_balances` doc credits correctly.
- AC2: The `token_purchases` idempotency-claim insert and the `token_balances` increment happen atomically (single transaction via `get_txn_session`) OR the increment is idempotent and the claim is written only after it succeeds — so a crash between them cannot leave "paid but not credited."
- AC3: Failure-injection test: simulate a crash/exception after the purchase insert and before the balance update; assert the customer is either fully credited on redelivery or the purchase row is not left blocking retry.
- AC4: Webhook handler still returns 200 on handled events, but a credit *failure* is logged at `error` with enough context to reconcile manually (reference_id, branch_id, resolved school_id).

**R12.5 — One canonical payroll disbursement path (P-H6)**
Files: `backend/routes/payroll.py:47-149`, `backend/routes/fees.py:706-775`, new/shared `backend/services/payroll_service.py` (mirror `fees_service.record_payment`)
- AC1: A single service records a disbursement with one schema (pick canonical field names, migrate any existing docs); both REST routes (or one, with the other deleted) delegate to it.
- AC2: Idempotency is enforced by the `(schoolId, staff_id, month)` unique index and `DuplicateKeyError` is caught on every path → returns the existing row with `idempotent: true`, never a 500.
- AC3: One auth policy for the money action (owner + admin/accountant, canonical `"accountant"` only — no legacy `"accounts"`).
- AC4: Salary-*structure* upsert likewise consolidated to one route/schema. Test: a disbursement created via the surviving route is read back with all expected fields populated; concurrent double-submit yields exactly one row.

**R12.4 — Atomic provisioning (P-M4)**
Files: `backend/routes/operator.py:257-305`
- AC1: `schools` + `school_settings` + owner `auth_users` are created transactionally (or with explicit compensation): a failure leaves no half-provisioned school.
- AC2: Re-invoking provisioning after a failure is not blocked by a stale partial `schools` row (either the row wasn't committed, or the duplicate check distinguishes "onboarding-incomplete" and allows resume).

---

## EPIC R13 — Tenancy & RBAC Fail-Closed (non-AI surfaces)
*Goal: no un-scoped tenant path, no PII surface open to the wrong sub-role. Fixes P-H3, P-H4, P-M1, P-M2.*

**R13.1 — Close the `ScopedCollection` method gap (P-M1)**
Files: `backend/database.py:60-112`
- AC1: `find_one_and_update`, `find_one_and_delete`, `find_one_and_replace`, `replace_one`, `bulk_write`, and `distinct` either inject `schoolId` like the other overrides, or raise `NotImplementedError` with a message pointing to the scoped alternative.
- AC2: The existing `fees.py:884` receipt-counter and `ai_rate_limiter.py` call sites are migrated to the new behavior and still pass.
- AC3: Unit test: calling an un-scoped method on a `ScopedCollection` for a two-school fixture cannot return/modify the other school's document.

**R13.2 — File-serve & file-list least-exposure (P-H3)**
Files: `backend/routes/upload.py:197-255`
- AC1: `serve_file` and `list_uploads` restrict cross-user access to owner + principal (`require_owner_or_principal` semantics), not every `admin` sub_category; a user can always access their own uploads.
- AC2: Cross-role test: an accountant/receptionist cannot serve or enumerate another user's upload; a principal can.
- AC3: Preserve the existing path-traversal guard and branch/school scoping.

**R13.3 — Export RBAC + scoping (P-H4)**
Files: `backend/routes/exports.py:16-173`
- AC1: PII exports (`students`, `staff`, `enquiries`) are gated to owner/principal (and accountant only where financially appropriate, e.g. fee/expense exports) — not any admin sub_category.
- AC2: `export_attendance` is branch-scoped for branch-bound users and, for `teacher`, limited to the teacher's own classes/scope (reuse the scope helpers), never the whole school.
- AC3: `_require_owner_or_accountant` drops the legacy `"accounts"` key; uses canonical `"accountant"` only (aligns with AI-audit C4 / R3.1).
- AC4: Standard 401/403 pair on each export endpoint.

**R13.4 — Login lockout & lookup are tenant-aware (P-M2)**
Files: `backend/routes/auth.py:162-198`
- AC1: The lockout key includes `schoolId` (or the resolved tenant) so one tenant's failed attempts don't lock the same username in another tenant.
- AC2: Multi-school login behavior is documented and tested: when `school_id` is omitted and the username exists in multiple schools, the response is deterministic and safe (either requires disambiguation or is scoped explicitly — not silently the env-default only).

**R13.5 — Operations lists branch-scoped (P-H5)**
Files: `backend/routes/operations.py` — leave-requests (`:219-220`), approval-requests (`:327`), complaints (`:1240`), expenses/visitors/assets/transport list endpoints
- AC1: Each list/count migrated to `scoped_query(branch_id=user.get("branch_id"))` OR carries a `# branch-scope: intentional — <reason>` comment; `grep -n "scoped_filter(" backend/routes/operations.py` audit passes per CLAUDE.md.
- AC2: Cross-branch fixture test per endpoint: a branch-A admin sees no branch-B rows unless intentional-commented. (Completes the CLAUDE.md Wave-3 branch-isolation item.)

**R13.7 — Staff deactivation revokes sessions (P-H7)**
Files: `backend/routes/staff.py:166-182`
- AC1: `delete_staff` calls `revoke_user_refresh_tokens(db, staff["user_id"])` (the existing helper keyed on `revoked_at: None`) instead of the hand-rolled `{"revoked": False}` query against a non-existent field.
- AC2: Test: deactivate a staff member with an active refresh token, then assert `POST /api/auth/refresh` with that token returns 401.
- AC3: Sweep for other hand-rolled refresh-token revocations using a `revoked` boolean and migrate them to the helper.

**R13.8 — Bulk SMS/WhatsApp ownership, scoping & cost cap (P-M7)**
Files: `backend/routes/sms.py:123-193, 196-284, 287-291, 423-564`
- AC1: Recipients are validated to be students/guardians of the caller's school (and branch, for branch-bound users) — no sending to arbitrary client-supplied numbers or cross-branch student IDs.
- AC2: A per-school daily send cap (config-driven) bounds Twilio cost; exceeding it returns a clear error.
- AC3: `get_sms_logs` is branch-scoped for branch-bound users.
- AC4: Standard 401/403 pair + a cross-branch fixture test on `send_parent_message`.

**R13.9 — Bulk import: branch tag + atomic writes (P-M8)**
Files: `backend/routes/import_data.py:164-198, 226-300`
- AC1: `_student_doc` sets `branch_id` (from the importer's branch or an explicit per-row/request branch) so imported students are visible to branch-scoped reads.
- AC2: Student + guardian writes for a row are atomic (transaction) — no student left without a guardian on partial failure.
- AC3: Class lookup and duplicate detection are branch-scoped; re-running the same import is idempotent (no silent duplicate students).

**R13.6 — Escape all user-supplied regex operands (P-M6)**
Files: `backend/routes/audit.py:78-81`, `backend/routes/operations.py:492-494`, `backend/routes/fees.py:1010`, `backend/routes/academics.py:631,638`, `backend/routes/attendance.py:347`
- AC1: All raw user input interpolated into `$regex` is wrapped in `re.escape` (match the correct `students.py:181` / `search.py:98` pattern).
- AC2: Period/month/week params are validated against a strict `^\d{4}-\d{2}` (or week) pattern before use; an invalid value returns 400, never a malformed-regex 500.
- AC3: Test: `q=(a+)+$` and `q=[` on the audit/incident search return promptly with a normal (possibly empty) result, not a hang or 500.

---

## EPIC R14 — Multi-Worker Correctness
*Goal: the runtime is correct under `WEB_CONCURRENCY > 1` (the EB reality), or refuses to run misconfigured. Fixes P-M3, P-M5.*

**R14.1 — Shared or guarded SSE / notification fan-out (P-M3)**
Files: `backend/services/sse.py`, `backend/services/ai_kill_switch.py:61-79`, `backend/services/layaastat.py:55, 79`
- AC1: Decide and implement one: (a) move the SSE channel registry + kill-switch cache to a shared broker (Redis pub/sub) so events reach clients on any worker; or (b) enforce single-worker for the API tier (startup guard mirroring `auth.py:37-43`, plus runbook note) and document it as a hard constraint.
- AC2: `layaastat` fire-and-forget tasks are held in a task set so they can't be GC'd mid-flight; emit failures logged at `warning` not `debug`.
- AC3: Test proving the chosen posture: either a cross-worker delivery test (broker path) or a startup-refuses-multi-worker test (guard path).

**R14.2 — Deactivated-school gate: cached + deliberate failure posture (P-M5)**
Files: `backend/middleware/school_context.py:60-78`
- AC1: The `schools.status` lookup is cached with a short TTL (per-process is acceptable if bounded and documented) so it isn't a per-request DB round-trip on the hot path.
- AC2: The fail-open-on-exception behavior is made a deliberate, documented choice (keep fail-open for availability, or fail-closed for security) — with a test asserting the chosen behavior.

---

## EPIC R15 — Residual Confirmatory Sweep
*Goal: final confirmatory line-level pass over the remaining lower-risk route/service files (the high/medium-risk surface was line-audited in the audit doc's R15 pass — see §7 Coverage). Mirrors R11.6. Findings fixed in-story if small, else appended as new R15.x stories.*

**R15.1 — Financial & operational routes deep audit**
Files: `backend/routes/fees.py`, `backend/routes/operations.py` (expenses/incidents/transport branch-isolation — the CLAUDE.md Wave-3 item), `backend/routes/issues.py`, `backend/routes/payroll.py`, `backend/services/{fees_service,expense_service,incident_service,token_service}.py`
- AC1: Each file audited with the Critical→Low rubric; branch-scope grep audit (per CLAUDE.md) clean or intentional-commented.
- AC2: `token_service.record_usage` debit path (`token_service.py:208-243`, P-L6) made atomic with (or ordered after) the usage-log write, and `personal_topups` floored at 0 (no negative balances) — mirror R12.3 on the spend side.
- AC3: New findings either fixed here or appended to `audit-platform-reliability-2026-07-08.md` as tracked stories.

**R15.2 — Student/staff/academic routes deep audit**
Files: `backend/routes/{students,staff,academics,attendance,activities,search}.py`, `backend/services/{student_service,staff_service,academic_structure_service}.py`
- AC1: Audited with the rubric; DPDP-sensitive fields (guardian PII, consent) verified least-exposure and tenant-scoped.
- AC2: Standard 401/403 + cross-tenant fixture pairs exist for the mutating endpoints.

**R15.3 — Messaging, settings & import routes deep audit**
Files: `backend/routes/{sms,settings,notifications,import_data,reports,queries,assistant}.py`, `backend/services/{sms/twilio path,org_config_service,announcement_service}.py`
- AC1: Audited with the rubric; `sms.py` provider credentials/rate-limit path and `import_data.py` (bulk write, injection surface) get particular attention.
- AC2: `assistant.py` false-success on `ai_unavailable` (AI-audit XM7) confirmed fixed by R1.7 or flagged if it regressed.

**R15.4 — Datetime & config hygiene sweep (P-L1–P-L5)**
Files: repo-wide (routes + services)
- AC1: Naive `datetime.now()`/`datetime.utcnow()` writes standardized to tz-aware UTC where persisted/compared (P-L1).
- AC2: Idempotency response-buffer size cap added (P-L2); `seed_status` endpoint gated or confirmed-intentional (P-L5); duplicated readiness `_check_ai` key-blind-spot noted against R9.1 (P-L3).

**R15.5 — Confirmatory-pass Low fixes (P-L7, P-L8, P-L9)**
Files: `backend/routes/attendance.py:106`, `backend/routes/activities.py:63-79`, `backend/routes/assistant.py:208-241`
- AC1: Manual attendance entry catches `DuplicateKeyError` on `(student_id, date)` and returns a 409/idempotent update instead of a 500 (P-L7).
- AC2: House seeding moved out of the GET handler (explicit idempotent seed or unique index on `(schoolId, name)`); concurrent first-load cannot create duplicate houses (P-L8).
- AC3: `POST /api/assistant` gets rate limiting + token accounting so it can't drive uncapped Azure spend; its `ok=False` false-success is confirmed fixed by AI epic R1.7 (P-L9).

---

## Story-count summary
| Epic | Stories | Theme |
|---|---|---|
| R12 | 5 | Onboarding, billing & payroll integrity (Critical) |
| R13 | 9 | Tenancy & RBAC fail-closed (non-AI) |
| R14 | 2 | Multi-worker correctness |
| R15 | 5 | Residual confirmatory sweep |
| **Total** | **21** | |

## Finding → fix traceability
| Audit finding | Fixed by |
|---|---|
| P-C1 provisioned owner can't log in | R12.1 |
| P-C2 webhook wrong-tenant credit | R12.2 |
| P-H1 personal_topups path conflict | R12.3 |
| P-H2 non-atomic credit (paid-not-credited) | R12.3 |
| P-H3 file-serve/list over-exposure | R13.2 |
| P-H4 export RBAC + attendance scoping | R13.3 |
| P-M1 ScopedCollection method gap | R13.1 |
| P-M2 global login lockout / multi-school lookup | R13.4 |
| P-H5 operations branch-scope leak | R13.5 |
| P-H6 divergent payroll implementations | R12.5 |
| P-H7 staff deactivation doesn't revoke sessions | R13.7 |
| P-M6 unescaped regex injection | R13.6 |
| P-M7 bulk SMS ownership/scope/cost | R13.8 |
| P-M8 bulk import branch tag + atomicity | R13.9 |
| P-L6 non-atomic token debit / negative balance | R15.1 |
| P-L7/P-L8/P-L9 attendance re-mark / house seed / assistant cap | R15.5 |
| P-M3 single-process assumptions | R14.1 |
| P-M4 non-atomic provisioning | R12.4 |
| P-M5 deactivation gate perf/fail-open | R14.2 |
| P-L1–P-L5 hygiene | R15.4 |
| Residual un-audited routes/services | R15.1–R15.3 |

## Definition of done (this initiative)
1. A provisioned school's owner can log in (R12.1 integration test green).
2. Billing credit path has an atomicity + correct-tenant test suite green; no `personal_topups` first-insert failure.
3. `ScopedCollection` has no silently-unscoped method; branch-scope grep audit clean over the touched routes.
4. PII export and file-serve surfaces gated to the correct sub-roles (cross-role tests green).
5. Multi-worker posture chosen, enforced, and tested.
6. Full backend suite green (modulo the pinned deferred failures — fix those LAST per standing directive).
