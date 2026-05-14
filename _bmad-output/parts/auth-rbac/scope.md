# Part 1: Auth + RBAC — Scope Document

**Part:** 1 of 16 (platform quality sweep)
**Status:** 🟢 in-progress (scoping)
**Created:** 2026-05-15
**Goal:** Audit and harden the authentication and authorization substrate to enterprise quality before all other parts depend on it.

---

## 1. Surface Inventory

### Backend Authentication
| File | Role |
|---|---|
| `backend/middleware/auth.py` | JWT encode/decode, password hashing, `get_current_user`, `require_role` (defined but unused) |
| `backend/routes/auth.py` | Login, logout, refresh, forgot-password, reset-password endpoints |
| `backend/services/auth_tokens.py` | Refresh token lifecycle: issue, consume, revoke, rotate |
| `backend/services/email_service.py` | Password-reset email delivery |

**JWT shape:**
- Algorithm: `HS256`
- TTL: 60 minutes (`JWT_EXPIRY_MINUTES`)
- Claims: `user_id`, `role`, `name`, `initials` + conditional `sub_category`, `branch_id`, `phone`
- Secret: env `JWT_SECRET`; dev fallback raises on `ENVIRONMENT=production`

**Refresh token shape:**
- TTL: 7 days (`REFRESH_TOKEN_TTL_DAYS`)
- Stored as `sha256(token)` in `db.refresh_tokens`
- Rotated on every refresh (`revoked_reason="rotated"`)
- Mass-revoked on password reset (`revoked_reason="password_reset"`)
- Cookie: HttpOnly, Secure, SameSite=Strict, Path=`/api/auth`

**Password reset:**
- Token: UUID, 15-min TTL, stored in `db.password_reset_tokens`
- Rate limit: tracked in `db.password_reset_requests` (per-email)
- Mass-revokes refresh tokens on successful reset

### Backend RBAC
| File | Role |
|---|---|
| `backend/ai/scope_resolver.py` | The single source of truth — 855 lines |
| `backend/tenant.py` | `get_school_id()`, `scoped_filter()`, `add_school_id()` |
| Per-route helpers | `_can_decide` (operations), `_can_manage` (staff), `_require_owner` (operator), `_is_maint`/`_is_it` (issues) |

**Roles enumerated:**
- `owner` — unrestricted
- `admin` (with `sub_category`):
  - `principal` — type="all"
  - `accountant` — domain="financial"
  - `transport_head` — domain="transport"
  - `receptionist` — domain="enquiries"
  - `it_tech` — type="self_only"
  - `maintenance` — type="self_only"
  - `support_staff` — type="self_only"
- `teacher` (with `sub_category`):
  - `hod` — type="subject"
  - `coordinator` — type="class_list" (regex range)
  - `class_teacher` — type="class_list"
  - `subject_teacher` — type="class_list"
  - `kg_incharge` — type="class_list"
- `student` — type="self_only"

**Scope object:**
- Fields: `type`, `role`, `sub_category`, `user_id`, `branch_id`, `class_ids`, `student_id`, `subject`, `domain`, `staff_record`
- Methods: `filter(collection)`, `can_see_personal_info(target)`, `can_see_financial_data()`, `allowed_collections()`, `is_restricted_to_self()`

**Two tenancy axes** (both must be enforced):
- `branch_id` — legacy, enforced via `_apply_branch_filter` in `ai/tool_functions_v2.py`
- `schoolId` — Story 1-3 forward-compat, enforced via `tenant.scoped_filter`

### Frontend Authentication
| File | Role |
|---|---|
| `frontend/src/contexts/UserContext.js` | Provider, in-memory token, `authFetch` 401-intercept |
| `frontend/src/lib/authSession.js` | `getAuthHeaders`, `refreshAccessToken`, dedup'd refresh promise |
| `frontend/src/components/Login.js` | Login UI + forgot-password flow |

**Storage discipline:**
- Access token: in-memory only (lost on hard refresh; restored via refresh endpoint on app boot)
- User object: `localStorage["eduflow_user"]`
- No persistent access token by design

**401 handling:** `authFetch` wrapper attempts ONE refresh; on failure clears session and redirects to `/login`. Refresh promise is deduped to prevent concurrent refresh races.

### Frontend RBAC (role-aware UI)
- `InputBar.js` — `TOOLS_BY_ROLE[role]` filters available AI tools
- `Header.js` — route visibility per role
- `Sidebar.js` — admin tool list filtered for non-admin roles
- `ToolDashboard.js` — owner/admin see grid; teachers/students see chat
- `ChatInterface.js` — system prompts vary by `role` + `sub_category`

### Data Model
| Collection | Purpose | Key indexes |
|---|---|---|
| `auth_users` | Identity, password hash, user_info | `username_lower` (unique) |
| `refresh_tokens` | Active refresh tokens (hashed) | `token_hash` (unique), `expires_at` (TTL=7d) |
| `password_reset_tokens` | One-time reset tokens | `token` (unique), `expires_at` (TTL=15m) |
| `password_reset_requests` | Reset rate-limit tracking | `email`, `created_at` |
| `login_attempts` | Failed login counter | `key` (login:username_lower) |
| `otps` | OTP records (separate from password reset?) | `expires_at` (TTL=0), `phone` |

### Tests (existing coverage)
| File | Covers |
|---|---|
| `tests/backend/api/test_auth.py` | Login (valid/invalid/injection/empty), `GET /me` |
| `tests/backend/api/test_phase5_auth_matrix.py` | Role × endpoint matrix (attendance, fees) |
| `tests/backend/unit/test_auth_tokens.py` | Refresh token lifecycle |
| `tests/backend/unit/test_auth_password_reset.py` | Password reset flow |
| `tests/e2e/auth.spec.js` | Login UI flow |

---

## 2. Quality Concerns Identified (from surface scan)

### High severity
1. **`require_role` dependency exists but is never used.** All ~30+ role gates in the codebase are inline `if user["role"] not in [...]`. This means:
   - Inconsistent gates (drift across endpoints)
   - No single audit point for role enforcement
   - Already-known mistakes (operator endpoint owner check was inline; we wrote a helper `_require_owner` only after creating `operator.py`)
2. **`scope_resolver.py` has zero direct unit-test coverage.** Story 5-24 exists in `sprint-status.yaml` as "done" — must verify what was actually covered. The scope resolver is the SINGLE source of truth for RBAC; lack of unit tests is the highest risk in the auth layer.
3. **Legacy admin permissiveness:** an admin row with no `sub_category` defaults to type="all" (full access). This is intentional for legacy data but undocumented and dangerous post-migration.
4. **JWT vs auth_users drift:** JWT contains `sub_category` from issuance time. If a staff record's sub_category changes (e.g., promotion to principal), the active session retains stale privileges until refresh (up to 7 days if user never logs out and access token cycles).

### Medium severity
5. **Inconsistent role-check patterns:**
   - Inline `if user["role"] not in [...]` (most routes)
   - Helper functions per-domain (`_can_decide`, `_can_manage`, `_require_owner`, `_is_maint`)
   - Direct `scope_resolver` usage (rare — only new code)
   This makes audit hard and refactoring brittle.
6. **`branch_id` vs `schoolId` coexistence:** 179 references to `branch_id`, 51 to `schoolId`. Both must be applied; missing either leaks cross-tenant data. No single helper enforces both.
7. **Refresh cookie path `/api/auth` is narrow.** If new auth-related endpoints are added outside `/api/auth/*` (e.g., a future `/api/account/*`), they won't receive the refresh token.
8. **No concurrent-refresh race tests.** Frontend dedups refresh via `refreshPromise`, but backend has no protection against two simultaneous refreshes consuming the same token. The token-hash uniqueness + atomic update probably saves us, but it's untested.

### Low severity
9. **`require_role` rejection message leaks the allowed list** (`"Required: owner, admin"`). Minor info disclosure.
10. **No explicit access-token revocation.** Access tokens are valid for their full 60-min TTL even after logout (refresh is revoked, but access still works). Acceptable for short TTL, but enterprise-grade would maintain a revocation list.
11. **`otps` and `password_reset_tokens` are separate collections.** Unclear why — may be legacy. Worth consolidating or documenting the distinction.
12. **Dev JWT secret fallback** is acceptable, but committing the dev secret to git makes it harder to roll. Should be `os.urandom`-derived per-process and only used when `ENVIRONMENT=development`.

---

## 3. Out of Scope for Part 1

- Multi-tenancy logic deeper than `scope_resolver` integration (deferred to Part 4)
- AI rate limiting / confirm-token flow (deferred to Part 2, AI Layer)
- Frontend foundation (ChatInterface, ToolPage primitives) — Part 8
- DPDP parental consent for student logins — gated on Story 7-39

---

## 4. Quality Goals for Part 1

By the end of Part 1, the following must be true:

1. **Single canonical role-check path.** All route handlers either use `require_role(...)` or `Depends(resolve_scope)` — no more inline `if user["role"] not in [...]`. Auditable via a single grep.
2. **`scope_resolver` has direct unit-test coverage** for every role × sub_category × scope-type combination. At least 30 tests.
3. **JWT freshness contract documented.** Either we accept stale claims (and document the staleness window explicitly) or we re-fetch the user on every request (with a session cache).
4. **Legacy permissiveness fix.** A migration enforces `sub_category` presence on all admin rows; legacy admin without sub_category is migrated to `support_staff` explicitly.
5. **Concurrent-refresh race tested.** Two simultaneous refresh attempts on the same token: exactly one succeeds, the other gets 401.
6. **`branch_id` + `schoolId` enforcement helper.** A single `scoped_query(scope)` returns a query that satisfies BOTH axes; all new code uses it.
7. **No bypass paths.** Adversarial review confirms: no endpoint, no AI tool, no frontend route bypasses the canonical auth path.

---

## 5. Anticipated Stories (preview for `create-epics-and-stories`)

These are working titles for the next step:

1. **PT1-S01 — `require_role` adoption + role-check audit.** Migrate every route's role gate to `Depends(require_role(...))` or a scope-aware equivalent. Inline checks become a lint failure.
2. **PT1-S02 — `scope_resolver` unit-test coverage.** Direct tests for every role × sub_category × collection. 30+ tests.
3. **PT1-S03 — Legacy admin sub_category migration.** Migration `016_admin_sub_category_default.py` backfills `sub_category="support_staff"` for any admin row without one. Resolver's `type="all"` fallback for "no sub_category" path is removed.
4. **PT1-S04 — Concurrent refresh race + invalidation tests.** Adversarial integration tests.
5. **PT1-S05 — `scoped_query` helper for combined `branch_id` + `schoolId`.** Helper in `tenant.py`; one call replaces both filter applications.
6. **PT1-S06 — JWT staleness policy.** Either implement session-cache re-fetch OR document the staleness window and add it to project-context.md as a known limitation.
7. **PT1-S07 — Auth surface adversarial review.** Final review pass — explicit attempt to bypass each canonical check.

**Estimated 6–7 stories**, none individually large.

---

## 6. References

- `_bmad-output/project-context.md` — Multi-tenancy, RBAC, and AI sections
- `_bmad-output/platform-quality-sweep.md` — Master tracker
- `backend/ai/scope_resolver.py` — The thing being hardened
- `backend/middleware/auth.py` — JWT + role helpers
- Existing tests: `tests/backend/api/test_auth.py`, `test_phase5_auth_matrix.py`, `unit/test_auth_tokens.py`, `unit/test_auth_password_reset.py`
