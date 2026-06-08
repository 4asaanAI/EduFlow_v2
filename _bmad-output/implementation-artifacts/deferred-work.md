# Deferred Work

## Deferred from: code review of 7-42-token-recharge-subscription-billing (2026-05-18)

- **Frontend handleRecharge silently swallows payment errors** — no user feedback when Razorpay payment-link/subscription creation fails (misconfigured key, 500, network error). Token bar stays showing "upgrade" but clicking does nothing. Phase 3 UX hardening. [frontend/src/components/ChatInterface.js]
- **subscription.updated / subscription.paused / subscription.halted not handled** — subscription_status and subscription_current_period_end drift when Razorpay fires plan-change, pause, or delinquency events. Delinquent accounts keep receiving renewal credits. Out of scope per story Scope Exclusions (Phase 3). [backend/routes/tokens.py — razorpay_webhook] _(vendor change 2026-06-08: was the Stripe `customer.subscription.updated` gap.)_
- **conftest.py does not monkeypatch routes.tokens for full-suite tests** — the shared `client` fixture (main app) exercises real DB for token balance endpoints, while all other routes use FakeCollection. Pre-existing test isolation gap; masked by graceful fallback in get_balance. [tests/backend/conftest.py]

## Deferred from: code review of 7-44-school-onboarding-flow (2026-05-18)

- **`deactivate_school` does not invalidate JWT sessions or set `is_active=False`** — deactivation only sets `schools.status="deactivated"`; existing tokens remain valid. Full enforcement (402 on all API calls for deactivated schools) is Story 7-45. [backend/routes/operator.py:deactivate_school]
- **Same owner email across multiple schools — duplicate `username_lower` in `auth_users`** — no unique index on `auth_users.username_lower`; same operator email can own two schools producing ambiguous login results. Cross-school login scope belongs to Story 7-45. [backend/routes/operator.py:create_school]
- **`_make_initials` derives owner initials from school name, not owner's personal name** — display initials will show school acronym (e.g., "SA") rather than owner's name initials (e.g., "RG"). Matches spec Dev Notes intentionally; UX refinement for a future cycle. [backend/routes/operator.py:53]
- **`SMTP_PORT int()` parsing in `send_welcome_email` lacks dev-environment guard** — minor inconsistency with `send_password_reset_email` which skips SMTP in non-production. Maintenance hazard if `SMTP_PORT` is malformed in test env. [backend/services/email_service.py]

## Deferred from: code review of 7-45-multi-tenancy-schema-per-tenant-enforcement (2026-05-19)

- **Compound unique index silent failure on legacy duplicate data** — if Story 1-3 backfill left `(username_lower, schoolId=null)` duplicates in `auth_users`, index creation fails silently at startup. Acceptable fail-open behavior but means the uniqueness guarantee is absent until duplicates are cleaned. [backend/database.py:_create_indexes]
- **`_SKIP_PATHS` exact-match doesn't cover trailing-slash variants** — pre-existing pattern across the codebase; FastAPI normalizes paths so it hasn't caused issues in practice. [backend/middleware/school_context.py:_SKIP_PATHS]
- **`scoped_filter()` bypassed when caller supplies `schoolId` in base query** — the `if "schoolId" in base: return base` short-circuit allows any caller to set their own schoolId. Pre-existing design constraint; fixing requires auditing all callers across 27 route files. [backend/tenant.py:53]
- **Background `asyncio.create_task()` tasks inherit ContextVar and lose school context on `finally` reset** — no current route spawns background tasks that call `get_school_id()`, but this is an architectural footgun for future developers. [backend/middleware/school_context.py]
- **TOCTOU deactivation race** — in-flight requests that passed the middleware deactivation check before `deactivate_school()` completes can write to a now-deactivated school's collections. Inherent to middleware-based enforcement; requires distributed locking or per-handler re-validation to fix. [backend/middleware/school_context.py + backend/routes/operator.py:deactivate_school]

## Deferred from: code review of 7-46-google-maps-transport-optimisation (2026-05-19)

- **O(students×zones) in-memory haversine loop** — cluster_analysis iterates all students × all zones in Python with no pagination or background offload; acceptable today for school fleet size; revisit if analysis times out under load. [backend/routes/operations.py:cluster_analysis]
- **haversine math.asin overflow for near-antipodal points** — floating-point rounding can make `math.sqrt(a)` slightly exceed 1.0; math.asin raises ValueError; unreachable for India-based coordinates with valid data but would cause a 500 with garbage coordinate input. [backend/services/maps_service.py:haversine_km]
- **zone document missing `id` field raises KeyError** — suggest_route uses `z["id"]` directly; `id` is enforced as a data invariant by the insert path; not introduced in this story. [backend/routes/operations.py:suggest_route]

## Deferred from: code review of 7-39-teacher-student-login-activation (2026-05-18)

- **No rate limiting on POST /api/auth/change-password** — an attacker with a stolen JWT can brute-force the current_password field at full API throughput with no lockout. Pre-existing gap: no other JWT-gated endpoint has endpoint-specific rate limiting either. Phase 3 security hardening. [backend/routes/auth.py:change_password]
- **Access token stays valid up to 1h after password change** — `revoke_user_refresh_tokens` revokes the refresh cookie but the current JWT remains valid until expiry. Accepted behavior for short-lived JWTs; worth a token-revocation mechanism in Phase 3. [backend/routes/auth.py:change_password]
