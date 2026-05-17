# Story 7-39: Teacher/Student Login Activation

**Status:** review
**Epic:** 7 — Growth Features
**Priority:** High — gates Parts 14 & 15 going live in production
**Effort:** Medium (backend + frontend, no new routes except one)
**Created:** 2026-05-18
**Baseline tests:** 699 passing, 0 skipped

---

## Story

**As** the operator (Abhimanyu),
**I want** teacher and student accounts to be activatable with a mandatory first-login password change,
**so that** teachers and students can log into EduFlow in production without using the shared default seed password.

---

## Acceptance Criteria

### AC1 — Teacher login produces correct JWT
Given a teacher auth_user exists with `role=teacher` and `sub_category=class_teacher` (seeded as `user-teacher-001`),
when `POST /api/auth/login` is called with `{"username": "Rajesh Kumar", "password": "teacher@123"}`,
then the response contains an `access_token`, and decoding the JWT reveals `role=teacher`, `sub_category=class_teacher`, and `user_id=user-teacher-001`.

### AC2 — Student login produces correct JWT
Given a student auth_user exists with `role=student` (seeded with `username=ADM20250001`),
when `POST /api/auth/login` is called with `{"username": "ADM20250001", "password": "student@123"}`,
then the response contains an `access_token` and decoding the JWT reveals `role=student` and the correct `user_id`.

### AC3 — Login response includes `must_change_password` flag
Given a seeded teacher or student auth_user has `must_change_password: True` in their DB document,
when they log in successfully,
then the login response includes `"must_change_password": true` alongside the token.

### AC4 — `POST /api/auth/change-password` clears the flag
Given an authenticated user whose `auth_users` document has `must_change_password: True`,
when they call `POST /api/auth/change-password` with `{"current_password": "...", "new_password": "..."}` and the current password is correct,
then the password is updated, `must_change_password` is cleared (set to False/removed), all existing refresh tokens for that user are revoked, and the response is `{"success": true}`.

### AC5 — Wrong current password returns 400
Given `POST /api/auth/change-password` is called with an incorrect `current_password`,
then the response is HTTP 400 with `detail: "Current password is incorrect"`.

### AC6 — Frontend routes to password-change screen on first login
Given a teacher or student logs in and the response contains `"must_change_password": true`,
when the frontend processes the login response,
then the user is routed to `/change-password` before the tool panel is shown, and cannot access any tool until the password is changed.

### AC7 — After password change, user lands on the normal tool panel
Given a user on `/change-password` successfully changes their password via `POST /api/auth/change-password`,
then they are redirected to the main app (`/`) with their existing session token still valid.

### AC8 — Seed documents have `must_change_password: True`
Given `seed.py` is run on a fresh DB,
all teacher and student `auth_users` documents have `"must_change_password": True` in the inserted records.

---

## Tasks / Subtasks

- [x] **T1 — Backend: expose `must_change_password` in login response** (AC3)
  - [x] In `_jwt_payload_from_auth()` or the login route, do NOT put `must_change_password` in the JWT (it's a session-level UX flag, not an auth claim)
  - [x] In `login()` at `auth.py:232`, after building the response, check `auth.get("must_change_password")` and if True add `"must_change_password": True` to the response dict
  - No schema model change needed — response is a plain dict

- [x] **T2 — Backend: `POST /api/auth/change-password` endpoint** (AC4, AC5)
  - [x] Add Pydantic model `ChangePasswordRequest(current_password: str, new_password: str)`
  - [x] Add `@router.post("/change-password")` (requires `Depends(get_current_user)`)
  - [x] Fetch `auth_users` doc for `current_user["user_id"]`
  - [x] Verify `current_password` against `password_hash` using `verify_password()` — if wrong, raise `HTTPException(400, "Current password is incorrect")`
  - [x] Update `password_hash` with `hash_password(new_password)` and set `must_change_password: False`
  - [x] Call `await revoke_user_refresh_tokens(db, user_id, reason="password_changed")` to invalidate all existing refresh tokens
  - [x] Return `{"success": True}`

- [x] **T3 — Seed: add `must_change_password: True` to teacher and student auth documents** (AC8)
  - [x] In `seed.py` around line 293, add `"must_change_password": True` to each dict in `teacher_auth_docs`
  - [x] In `seed.py` around line 352, add `"must_change_password": True` to each dict in `student_auth_docs`

- [x] **T4 — Frontend: `ChangePassword.js` component** (AC6, AC7)
  - [x] Create `frontend/src/components/ChangePassword.js`
  - [x] Simple form: current password + new password + confirm new password
  - [x] On submit: call `POST /api/auth/change-password` via `api.js` (add the helper there too)
  - [x] On success: clear the `must_change_password` flag from session state and navigate to `/`
  - [x] On error: show error message in the form
  - [x] Lucide icons only, inline styles consistent with `Login.js`

- [x] **T5 — Frontend: wire the force-change gate in `UserContext.js` and routing** (AC6)
  - [x] In `loginPassword()` in `UserContext.js`: after a successful login, check `data.must_change_password`
  - [x] If True: store a `mustChangePassword` boolean in context state; navigate to `/change-password`
  - [x] In `App.js`: add `/change-password` route pointing to `ChangePassword.js`
  - [x] In the auth guard (currently at `App.js:36`): if `mustChangePassword` is True and path is not `/change-password`, redirect to `/change-password` — block all other routes

- [x] **T6 — Tests: integration tests for teacher and student login** (AC1, AC2, AC3)
  - [x] Create `tests/backend/unit/test_teacher_student_login.py`
  - [x] `test_teacher_login_jwt_contains_correct_role_and_sub_category` — seed a teacher auth_user with role/sub_category, POST to `/api/auth/login`, decode JWT, assert `role=teacher`, `sub_category=class_teacher`, `user_id` matches
  - [x] `test_student_login_jwt_contains_correct_role` — same pattern for student
  - [x] `test_login_returns_must_change_password_flag_when_set` — seed auth_user with `must_change_password: True`, login, assert response contains `"must_change_password": true`
  - [x] `test_login_does_not_return_flag_when_not_set` — seed auth_user WITHOUT the flag, login, assert `must_change_password` is absent or False
  - [x] `test_change_password_clears_flag` — seed auth_user with flag, login, POST change-password with correct current password, then assert `must_change_password` is False/absent in the DB
  - [x] `test_change_password_wrong_current_password_returns_400` — wrong current_password → 400
  - [x] `test_change_password_requires_auth` — no auth header → 401

---

## Dev Notes

### What already works — do not reinvent

- **Login route is role-agnostic**: `POST /api/auth/login` in `auth.py` already handles ALL roles. There is no code gating teacher/student login — the accounts simply never had integration tests or `must_change_password` enforcement.
- **`_jwt_payload_from_auth()` at `auth.py:131`** already correctly propagates `sub_category` and `branch_id` into the JWT for all roles. No changes needed to JWT generation.
- **`scope_resolver.py`** already has full teacher and student scope implementations (`_build_class_teacher_context`, `_build_student_context` in `context_builder.py`). These paths are already exercised by mock-JWT tests in Parts 14 and 15.
- **`content_filter.py`** already applies student-specific safety filtering when `role=student`. No changes needed.
- **`revoke_user_refresh_tokens()`** already exists in auth.py — import and call it in T2.
- **`must_change_password` field** already exists as a concept — `admin_reset_password` at `auth.py:400` sets it. The login route just doesn't read/return it yet. T1 is additive only.

### What does NOT exist yet

- `POST /api/auth/change-password` endpoint (T2)
- `must_change_password` in the login response (T1)
- `must_change_password: True` in seed documents (T3)
- Frontend `ChangePassword.js` component and gate (T4, T5)
- Integration tests for teacher/student login (T6)

### Seed file locations

```
backend/seed.py:282-301  — teacher auth_users (teacher_auth_docs list)
backend/seed.py:348-359  — student auth_users (student_auth_docs list)
```

Add `"must_change_password": True` inside the dict appended to both lists.

### Login response — current shape (auth.py:232-238)

```python
return {
    "success": True,
    "access_token": token,
    "token": token,
    "token_type": "bearer",
    "expires_in": 3600,
    "user": user_info,
}
```

T1 addition — add AFTER this dict is built, before the return:
```python
if auth.get("must_change_password"):
    response_dict["must_change_password"] = True
```

Do NOT put `must_change_password` in the JWT payload — it is a first-login UX flag, not an access claim.

### Change-password endpoint pattern

```python
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    db = get_db()
    auth = await db.auth_users.find_one(_auth_user_filter(current_user["user_id"]))
    if not auth:
        raise HTTPException(404, "Auth record not found")
    if not verify_password(body.current_password, auth.get("password_hash", "")):
        raise HTTPException(400, "Current password is incorrect")
    await db.auth_users.update_one(
        _auth_user_filter(current_user["user_id"]),
        {"$set": {"password_hash": hash_password(body.new_password), "must_change_password": False}},
    )
    await revoke_user_refresh_tokens(db, current_user["user_id"], reason="password_changed")
    return {"success": True}
```

### Frontend: `UserContext.js` change

`loginPassword()` already returns `data` (line 102). In `App.js` or the `Login.js` handler, check `data.must_change_password` after `await loginPassword(...)` and use React Router to navigate to `/change-password`.

Add `mustChangePassword` state to `UserContext` and expose it via the context value.

In `App.js` auth guard (currently line 36), add:
```js
if (isAuthenticated && mustChangePassword && path !== '/change-password') {
    window.history.replaceState(null, '', '/change-password');
}
```

### Test file conventions

```python
from __future__ import annotations
import pytest
from middleware.auth import create_jwt, verify_password
from tests.backend.conftest import FakeCollection

pytestmark = pytest.mark.asyncio
```

Use `FakeCollection` for `auth_users` — seed the doc directly in `fake_db.auth_users.docs`.

For the `must_change_password` DB assertion in T6, check `fake_db.auth_users.docs[0].get("must_change_password")` after calling the endpoint.

### Do NOT implement

- DPDP parental consent for student login — that is Story P15.2, already marked done
- Student content filter hardening — already done in `content_filter.py`
- Teacher scope resolver changes — already done in `scope_resolver.py`
- Any change to the JWT secret, expiry, or token format

---

## Dev Agent Record

### Agent Model Used
claude-sonnet-4-6

### Completion Notes List

- **T1**: Added `must_change_password: True` to login response dict when flag is set in `auth_users`. Flag is NOT in the JWT (session-level UX concern, not an auth claim).
- **T2**: Added `ChangePasswordRequest` Pydantic model and `POST /api/auth/change-password` endpoint to `auth.py`. Verifies current password, updates hash, clears flag, revokes all refresh tokens.
- **T3**: Added `"must_change_password": True` to both `teacher_auth_docs` and `student_auth_docs` in `seed.py`.
- **T4**: Created `frontend/src/components/ChangePassword.js` with current/new/confirm-password fields, inline styles matching `Login.js`, Lucide icons, error display, and calls `clearMustChangePassword()` + navigates to `/` on success.
- **T5**: Updated `UserContext.js` — added `mustChangePassword` state, set on login when flag is returned, exposed `clearMustChangePassword` callback. Updated `App.js` — added import + auth gate (redirects to `/change-password` when `mustChangePassword` is true) + route rendering `ChangePassword` when on `/change-password`. Added `changePassword()` helper to `api.js`.
- **T6**: Created `tests/backend/unit/test_teacher_student_login.py` with 7 tests covering AC1–AC5: teacher/student JWT correctness, `must_change_password` flag in login response, change-password clearing the flag, wrong-password 400, and unauthenticated 401.
- **Test result**: 706 passed (699 baseline + 7 new), 0 regressions.

### File List

**Modified:**
- `backend/routes/auth.py` — T1 (login response), T2 (new endpoint)
- `backend/seed.py` — T3 (must_change_password flag)
- `frontend/src/contexts/UserContext.js` — T5 (mustChangePassword state)
- `frontend/src/App.js` — T5 (route + gate)
- `frontend/src/lib/api.js` — T4 (change-password API helper)

**Added:**
- `frontend/src/components/ChangePassword.js` — T4
- `tests/backend/unit/test_teacher_student_login.py` — T6

### Change Log
- 2026-05-18 — Story file created by bmad-create-story
- 2026-05-18 — All tasks implemented by claude-sonnet-4-6: backend endpoint + login flag (T1/T2), seed.py update (T3), ChangePassword.js + api.js helper (T4), UserContext.js + App.js gate (T5), 7 unit tests (T6). 706 tests passing.
