# Story 7.44: School Onboarding Flow

Status: done
Epic: 7
Priority: Critical (pre-school #2)
Effort: Large
Created: 2026-05-18

---

## Story

**As** the platform operator (Abhimanyu / Layaa AI),
**I want** a self-service school onboarding flow,
**so that** school #2 can be set up without manual database intervention.

---

## Acceptance Criteria

**AC1. `POST /api/operator/schools` — create a new school (owner-only)**
Accepts `{ school_name, school_id, owner_email, plan_tier }`.
- `school_id` is a slug (lowercase, alphanumeric + hyphens, 3–50 chars). Must be unique across the `schools` collection; duplicate returns 409 with `detail: "school_id already exists"`.
- Creates a document in `db.schools` with `{ id, school_name, school_id, owner_email, plan_tier, status: "onboarding", created_at }`.
- Creates a document in `db.school_settings` scoped to the new `school_id`: `{ id: "main", school_name, schoolId: school_id }`.
- Creates an owner `auth_users` document scoped to the new `school_id` — see AC2.
- Returns `{"success": true, "data": { school_id, owner_username, temporary_password }}`.

**AC2. Owner account creation on school creation**
- Generates a secure temporary password (12 chars, alphanumeric).
- Creates `auth_users` record: `{ id: uuid4, username: owner_email, username_lower: owner_email.lower(), password_hash: bcrypt_hash, role: "owner", schoolId: school_id, user_info: { id: uuid4, name: school_name + " Owner", role: "owner", initials: first-two-initials, schoolId: school_id }, must_change_password: true }`.
- Sends a welcome email to `owner_email` via `send_welcome_email()` (new function in `backend/services/email_service.py`). If SMTP is not configured, logs a warning and continues — do not fail school creation.

**AC3. `GET /api/operator/schools/{school_id}/onboarding-status` — per-step checklist (owner-only)**
Returns the onboarding completion state for the given school. Query each collection with a `schoolId` filter:
```json
{
  "success": true,
  "data": {
    "school_id": "...",
    "school_name": "...",
    "status": "onboarding | active | deactivated",
    "steps": {
      "profile_created": true,
      "first_staff_added": false,
      "first_class_configured": false,
      "first_student_imported": false,
      "first_fee_record_created": false
    },
    "completed": false
  }
}
```
- `profile_created` → `schools` doc with the given `school_id` exists.
- `first_staff_added` → `db.staff` has ≥1 doc with `schoolId == school_id`.
- `first_class_configured` → `db.classes` has ≥1 doc with `schoolId == school_id`.
- `first_student_imported` → `db.students` has ≥1 doc with `schoolId == school_id`.
- `first_fee_record_created` → `db.fee_structures` has ≥1 doc with `schoolId == school_id`.
- `completed: true` only when all five steps are `true`.
- When `completed` transitions to `true` on first poll: send operator notification email and/or Slack webhook (see AC7).

**AC4. `PATCH /api/operator/schools/{school_id}/deactivate` — deactivate a school (owner-only)**
- Sets `status: "deactivated"` on the matching `schools` document.
- Returns `{"success": true, "data": { school_id, status: "deactivated" }}`.
- 404 if the school_id does not exist.
- Note: Full 402-on-all-API-calls enforcement is Story 7-45 (multi-tenancy middleware). This story records the deactivated state; enforcement is applied in Story 7-45.

**AC5. S3 prefix isolation**
New schools automatically get an isolated S3 prefix. No code change needed — the existing Part 6 S3 key convention (`{school_id}/uploads/{file_id}/{safe_filename}`) already isolates files per school. Document in Dev Notes only; no new code.

**AC6. Frontend: `SchoolOnboarding.js` wizard (operator-only)**
`frontend/src/components/tools/SchoolOnboarding.js` renders a three-step wizard:
1. **School Details** — `school_name`, `school_id` (slug, validated client-side: `/^[a-z0-9-]{3,50}$/`), `plan_tier` (select: `"starter" | "pro"`).
2. **Owner Account** — `owner_email`.
3. **Review & Create** — shows entered details + creates school on confirm.

After creation success:
- Displays `owner_username` + `temporary_password` in a copyable panel.
- Shows the onboarding checklist (polls `GET /api/operator/schools/{school_id}/onboarding-status` every 30 seconds; stops polling when `completed: true`).

Component is wired into `Layout.js` for the owner role, same pattern as `PlatformHealthDashboard`.

**AC7. Operator notification on onboarding completion**
When the onboarding-status endpoint first detects `completed: true` (all five steps done), set `status: "active"` on the `schools` document and:
- Send a completion email to `OPERATOR_NOTIFY_EMAIL` env var (if set) via the existing `email_service.py` SMTP helpers.
- `POST` to `OPERATOR_SLACK_WEBHOOK_URL` env var (if set) with a JSON body `{"text": "School <school_name> onboarding complete."}` using `httpx.AsyncClient` with a 5s timeout. If webhook fails, log a warning and continue.

---

## Tasks / Subtasks

- [x] Task 1: `db.schools` collection + model (AC1, AC3)
  - [x] Define Pydantic model `CreateSchoolRequest` with `school_name`, `school_id` (slug-validated), `owner_email`, `plan_tier`
  - [x] Add `schools` as a `FakeCollection` in `tests/backend/conftest.py`
  - [x] Add index `(school_id, unique=True)` in `database.py → _create_indexes()`

- [x] Task 2: `POST /api/operator/schools` endpoint (AC1, AC2)
  - [x] Add to `backend/routes/operator.py` — use `Depends(require_owner)`
  - [x] Check for duplicate `school_id` → 409
  - [x] Insert `schools` doc
  - [x] Insert `school_settings` doc (scoped to new school_id)
  - [x] Generate temp password + bcrypt hash
  - [x] Insert `auth_users` doc with `schoolId` + `must_change_password: True`
  - [x] Call `send_welcome_email(owner_email, owner_username, temp_password)` in try/except (fail-open)

- [x] Task 3: `GET /api/operator/schools/{school_id}/onboarding-status` (AC3, AC7)
  - [x] Add to `backend/routes/operator.py`
  - [x] Five parallel `count_documents` checks (use `asyncio.gather`)
  - [x] On first `completed=True`, update school `status: "active"` and fire notifications (fail-open)

- [x] Task 4: `PATCH /api/operator/schools/{school_id}/deactivate` (AC4)
  - [x] Add to `backend/routes/operator.py`
  - [x] Update `status: "deactivated"` on the `schools` doc
  - [x] 404 if not found

- [x] Task 5: `send_welcome_email` in `email_service.py` (AC2)
  - [x] New function `send_welcome_email(to_email, username, temp_password)` following existing SMTP pattern
  - [x] Fail-open (log and return if `SMTP_HOST` not set)

- [x] Task 6: Operator notification helpers (AC7)
  - [x] `_send_operator_email(school_name)` — uses `OPERATOR_NOTIFY_EMAIL` + existing SMTP (in `email_service.py`)
  - [x] `_send_operator_slack(school_name)` — uses `OPERATOR_SLACK_WEBHOOK_URL` + httpx 5s timeout
  - [x] Both fail-open

- [x] Task 7: Frontend `SchoolOnboarding.js` (AC6)
  - [x] Three-step wizard with form validation
  - [x] `POST /api/operator/schools` on Step 3 confirm
  - [x] Show temp credentials after creation
  - [x] Poll onboarding-status every 30s; render checklist with step completion
  - [x] Wire into `Layout.js` (owner only)

- [x] Task 8: Tests (see Testing section)

---

## Dev Notes

### Critical: Where to Add Endpoints
All new routes go in **`backend/routes/operator.py`** — NOT `settings.py`, NOT a new file. This is the canonical location per project context (Operator Endpoints rule). The router already has `prefix="/api/operator"` and uses `Depends(require_owner)`.

### Critical: Python 3.9 Compat
`backend/routes/operator.py` already has `from __future__ import annotations` as the first line. Do not remove it; keep it first.

### User Creation Pattern
Follow the exact `auth_users` document structure from `backend/seed.py:122-130`:
```python
{
    "id": str(uuid.uuid4()),
    "username": owner_email,
    "username_lower": owner_email.lower(),
    "password_hash": hash_password(temp_password),  # import from middleware.auth
    "role": "owner",
    "schoolId": school_id,  # explicit — NOT via add_school_id()
    "user_info": {
        "id": str(uuid.uuid4()),
        "name": f"{school_name} Owner",
        "role": "owner",
        "initials": _make_initials(school_name),
        "schoolId": school_id,
    },
    "must_change_password": True,
    "is_active": True,
}
```
Import `hash_password` from `middleware.auth` (already there). Do NOT use `bcrypt` directly in the route file.

### Do NOT Use `add_school_id()` for Auth Users
The `auth_users` collection is intentionally NOT scoped via `add_school_id()` in the operator route — `schoolId` is set explicitly in the doc. `add_school_id()` from `tenant.py` uses the env-var `SCHOOL_ID`, which is the running instance's school, not the new school being created.

### `school_settings` Insert Pattern
The `school_settings` insert also cannot use `get_db()` (which scopes to `SCHOOL_ID` env var). Use the raw Motor collection via `db._db.school_settings.insert_one(...)` to bypass `ScopedDatabase`, or pass `schoolId` explicitly. The raw db is accessible as `get_db()._db`.

Actually, the cleanest pattern: import both `get_db` and the raw client. Example from `database.py`:
```python
# get_db() returns ScopedDatabase (scoped to SCHOOL_ID env var)
# For cross-school operator ops, access raw db:
from database import get_db
db = get_db()
raw_db = db._db  # Motor AsyncIOMotorDatabase — no scoping
await raw_db.schools.insert_one({...})
await raw_db.school_settings.insert_one({..., "schoolId": new_school_id})
```

### Slug Validation (Server-Side)
```python
import re
SLUG_RE = re.compile(r'^[a-z0-9-]{3,50}$')
if not SLUG_RE.match(school_id_slug):
    raise HTTPException(status_code=400, detail="school_id must be 3-50 chars, lowercase alphanumeric and hyphens only")
```

### Temp Password Generation
```python
import secrets, string
_ALPHANUM = string.ascii_letters + string.digits
def _generate_temp_password(length: int = 12) -> str:
    return "".join(secrets.choice(_ALPHANUM) for _ in range(length))
```

### Onboarding Status — Five Parallel Checks
Use `asyncio.gather` to avoid serial N+1 I/O:
```python
raw_db = get_db()._db
results = await asyncio.gather(
    raw_db.schools.find_one({"school_id": school_id}, {"_id": 0}),
    raw_db.staff.count_documents({"schoolId": school_id}),
    raw_db.classes.count_documents({"schoolId": school_id}),
    raw_db.students.count_documents({"schoolId": school_id}),
    raw_db.fee_structures.count_documents({"schoolId": school_id}),
)
```
Note: Use `raw_db` (un-scoped) because the operator is querying a potentially different school's data. `get_db()` is scoped to the running instance's `SCHOOL_ID`.

### Notification Fail-Open Pattern
Both `_send_operator_email` and `_send_operator_slack` must be fail-open (log warning, never raise):
```python
try:
    await _send_operator_slack(school_name)
except Exception:
    logger.warning("operator slack notification failed", exc_info=True)
```

### Frontend Patterns
- Use `apiFetch` from `src/lib/api.js` for all API calls — never inline fetch.
- Use `useContext(UserContext)` for auth (`user`, `token`).
- Follow the `PlatformHealthDashboard` pattern already in `OwnerTools.js` for polling (use `setInterval` + `useEffect` cleanup).
- Icons: `Building2`, `CheckCircle`, `Circle`, `RefreshCw` from `lucide-react`.
- Use `var(--bg-card)`, `var(--border)`, `var(--text-primary)` CSS variables — not raw hex.
- The wizard's confirm button must use the existing `ConfirmActionCard` pattern (double-confirm UX) if that component fits, or a simple two-click confirm — creating a school is irreversible.

### `email_service.py` Extension Pattern
Extend with a new function following the existing `send_password_reset_email` shape:
```python
def send_welcome_email(to_email: str, username: str, temp_password: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    if not smtp_host:
        logger.warning("SMTP_HOST missing; welcome email not sent to %s", to_email)
        return
    msg = EmailMessage()
    msg["Subject"] = "Welcome to EduFlow — Your school is ready"
    msg["From"] = os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")
    msg["To"] = to_email
    msg.set_content(
        f"Your EduFlow school has been created.\n\n"
        f"Login URL: {os.environ.get('FRONTEND_URL', '')}/login\n"
        f"Username: {username}\n"
        f"Temporary password: {temp_password}\n\n"
        f"You will be prompted to change your password on first login."
    )
    # ... same SMTP send block as send_password_reset_email
```

### Env Vars (new — add to `.env.example`)
```
OPERATOR_NOTIFY_EMAIL=           # operator receives onboarding completion emails
OPERATOR_SLACK_WEBHOOK_URL=      # Slack incoming webhook for onboarding completion
```

### Project Structure — Files to Modify/Create
| File | Action |
|------|--------|
| `backend/routes/operator.py` | ADD 3 endpoints + helper functions |
| `backend/services/email_service.py` | ADD `send_welcome_email()` |
| `backend/database.py` | ADD `schools` index in `_create_indexes()` |
| `frontend/src/components/tools/SchoolOnboarding.js` | CREATE |
| `frontend/src/components/Layout.js` | ADD wizard wiring for owner role |
| `tests/backend/conftest.py` | ADD `schools` FakeCollection |
| `tests/backend/unit/test_school_onboarding.py` | CREATE |
| `backend/.env.example` | ADD `OPERATOR_NOTIFY_EMAIL`, `OPERATOR_SLACK_WEBHOOK_URL` |

---

### Testing Requirements

**Every new route needs these two tests (MANDATORY — security convention):**
```python
def test_create_school_unauthenticated_returns_401(client):
    resp = client.post("/api/operator/schools", json={...})
    assert resp.status_code == 401

def test_create_school_wrong_role_returns_403(client):
    headers = _bearer({"user_id": "u1", "role": "admin", "name": "T"})
    resp = client.post("/api/operator/schools", json={...}, headers=headers)
    assert resp.status_code == 403
```

Apply the same 401/403 pair for the onboarding-status and deactivate endpoints.

**Functional tests to write (`tests/backend/unit/test_school_onboarding.py`):**
- `test_create_school_success` — creates school doc, school_settings, auth_users; returns temp credentials
- `test_create_school_duplicate_id_returns_409`
- `test_create_school_invalid_slug_returns_400` — e.g., `"My School"` (spaces)
- `test_onboarding_status_all_incomplete` — fresh school, all steps false
- `test_onboarding_status_partial` — seed staff + class; asserts those two steps true
- `test_onboarding_status_complete_sets_active` — seed all five collections; asserts `status: "active"` updated
- `test_deactivate_school_success` — status → "deactivated"
- `test_deactivate_school_not_found_returns_404`
- `test_create_school_email_fail_open` — monkeypatch `send_welcome_email` to raise; assert school still created

**Test fixture setup:**
```python
from __future__ import annotations
import pytest
pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def _clean(fake_db):
    fake_db.schools.docs[:] = []
    fake_db.school_settings.docs[:] = []
    fake_db.auth_users.docs[:] = []
    fake_db.staff.docs[:] = []
    fake_db.classes.docs[:] = []
    fake_db.students.docs[:] = []
    fake_db.fee_structures.docs[:] = []
    yield
    fake_db.schools.docs[:] = []
    # ... repeat
```

**FakeCollection registration:** Add in `conftest.py FakeDb.__init__`:
```python
self.schools = FakeCollection()
```
And patch in the APP_AVAILABLE block:
```python
import backend.routes.operator as operator_mod
operator_mod.get_db = lambda: _fake_db  # already patched — verify it reaches raw_db too
```

**Important:** The operator endpoints use `get_db()._db` to bypass school-scoping. In tests, `_fake_db._db` must return `_fake_db` itself (or a compatible mock). Check `conftest.py` for existing `_db` attribute; add if missing:
```python
class FakeDb:
    def __init__(self):
        ...
        self._db = self  # operator endpoints use raw_db = get_db()._db
```

---

### Previous Story Intelligence

The three most recent stories in Epic 7 (7-42, 7-43, 7-48) established these patterns that apply here:
- **Operator routes always use `Depends(require_owner)`** — no inline role checks.
- **`asyncio.gather` for concurrent I/O** — used in `get_platform_health` (operator.py:228). Follow the same pattern for the five onboarding-status checks.
- **httpx for outbound HTTP** — already imported in `operator.py` for the AI health check. Reuse for Slack webhook.
- **Fail-open service calls** — `_ph_ai_check`, `_ph_s3_check` both catch Exception and log warning. Mirror for notification helpers.
- **`from __future__ import annotations`** is already line 7 of `operator.py`. Keep it first.
- **Test baseline: 699 tests, 0 skipped** — new tests must not cause skips. Ensure `pytestmark = pytest.mark.asyncio` is in the test file.

---

### Scope Boundary: Story 7-44 vs 7-45

**Story 7-44 (this story):**
- Creates the `schools` collection and data model
- Creates owner accounts scoped to new school's `schoolId`
- Deactivation stores `status: "deactivated"` in DB

**Story 7-45 (next):**
- Injects `schoolId` from JWT into every request context (not from `SCHOOL_ID` env var)
- Enforces 402 for deactivated schools at middleware level
- Enforces cross-school isolation in all route handlers

Do NOT implement JWT-based `schoolId` injection in this story — it belongs to 7-45.

---

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Deployment runbook test (`test_deployment_runbook_documents_all_example_env_vars`) failed because the new env vars `OPERATOR_NOTIFY_EMAIL` and `OPERATOR_SLACK_WEBHOOK_URL` were added to `.env.example` but not the runbook. Fixed by adding them to `docs/deployment-runbook.md §5`.
- Used `get_raw_db()` (not `get_db()._db`) for all cross-school operations — `get_raw_db()` is already exported from `database.py` and is the correct bypass for school-scoped ops.

### Completion Notes List

- ✅ AC1: `POST /api/operator/schools` — creates school doc, school_settings, owner auth_users. Validates slug regex server-side. Returns temp credentials.
- ✅ AC2: Owner account created with `must_change_password: True`, welcome email fail-open.
- ✅ AC3: `GET /api/operator/schools/{school_id}/onboarding-status` — five parallel `asyncio.gather` checks. Auto-sets `status: "active"` on first completion.
- ✅ AC4: `PATCH /api/operator/schools/{school_id}/deactivate` — sets `status: "deactivated"`, 404 if missing.
- ✅ AC5: S3 prefix isolation is automatic (existing Part 6 convention) — no code change needed.
- ✅ AC6: `SchoolOnboarding.js` three-step wizard with client-side slug validation, credential copyable panel, 30s polling checklist. Wired into `Layout.js`.
- ✅ AC7: `send_operator_completion_email` + `_send_operator_slack` both fail-open. Called on first `completed=True` poll.
- ✅ 17 new tests (6 security + 11 functional), all passing. Full suite: 751 passed, 0 skipped.

### File List

- `backend/routes/operator.py` — MODIFIED (3 new endpoints + helpers + imports)
- `backend/services/email_service.py` — MODIFIED (`send_welcome_email`, `send_operator_completion_email`)
- `backend/database.py` — MODIFIED (`schools` unique index in `_create_indexes`)
- `frontend/src/lib/api.js` — MODIFIED (`createSchool`, `fetchSchoolOnboardingStatus`, `deactivateSchool`)
- `frontend/src/components/tools/SchoolOnboarding.js` — CREATED
- `frontend/src/components/Layout.js` — MODIFIED (`school-onboarding` tool route)
- `tests/backend/conftest.py` — MODIFIED (`schools` FakeCollection, `get_raw_db` patch)
- `tests/backend/unit/test_school_onboarding.py` — CREATED (17 tests)
- `backend/.env.example` — MODIFIED (`OPERATOR_NOTIFY_EMAIL`, `OPERATOR_SLACK_WEBHOOK_URL`)
- `docs/deployment-runbook.md` — MODIFIED (new env vars documented)

---

### Review Findings

Code review run: 2026-05-18 · Layers: Blind Hunter + Edge Case Hunter + Acceptance Auditor · 0 decision-needed · 17 patch · 4 deferred · 2 dismissed

- [ ] [Review][Patch] Sync smtplib blocks event loop — `send_welcome_email` and `send_operator_completion_email` are blocking sync calls inside async route handlers; wrap with `asyncio.to_thread()` [`backend/routes/operator.py` create_school:156, get_onboarding_status:211]
- [ ] [Review][Patch] `auth_users` and `school_settings` insert failures silently swallowed — exceptions caught and logged but not re-raised; API returns 200 + temp credentials even when owner account was never created [`backend/routes/operator.py:128-167`]
- [ ] [Review][Patch] Duplicate completion notifications when `schools.update_one` fails — email and Slack calls fire unconditionally inside the `if completed and current_status == "onboarding"` block; if DB update raises, status stays "onboarding" and next poll re-sends notifications [`backend/routes/operator.py:199-217`]
- [ ] [Review][Patch] `school_settings.id = "main"` collides across schools — every school writes `{"id": "main"}` with no unique index on `(schoolId)` in school_settings; second school creation produces an ambiguous duplicate [`backend/database.py`, `backend/routes/operator.py:122`]
- [ ] [Review][Patch] `school_id` path param not validated in `get_onboarding_status` / `deactivate_school` — arbitrary strings reach raw MongoDB queries; apply `SLUG_RE.match()` at entry [`backend/routes/operator.py`]
- [ ] [Review][Patch] `DuplicateKeyError` on schools insert returns 500 not 409 — concurrent TOCTOU requests bypass the `find_one` guard; the unique index rejects the second insert but the `except Exception` block raises 500 instead of 409 [`backend/routes/operator.py:create_school`]
- [ ] [Review][Patch] SLUG_RE accepts leading/trailing hyphens — `"---"`, `"-abc"`, `"abc-"` all pass `r"^[a-z0-9-]{3,50}$"`; tighten to require non-hyphen at start/end [`backend/routes/operator.py:41`, `frontend/src/components/tools/SchoolOnboarding.js:5`]
- [ ] [Review][Patch] `_clean` autouse fixture wipes globally seeded `auth_users` — `fake_db.auth_users.docs[:] = []` before every test clobbers the session-scoped `admin-1` seed used by other test modules [`tests/backend/unit/test_school_onboarding.py:56-71`]
- [ ] [Review][Patch] Slack webhook text has extra single quotes around school_name — spec says `"School <school_name> onboarding complete."` but code produces `"School 'Sunrise Academy' onboarding complete."` [`backend/routes/operator.py:61`]
- [ ] [Review][Patch] `school-onboarding` not in OWNERS array — tool is unreachable from the sidebar; `platform-health-dashboard` is listed but `school-onboarding` was omitted [`frontend/src/components/Layout.js:41`]
- [ ] [Review][Patch] `school-onboarding` bypasses OWNERS role filter — early-return on line 39 of `loadTool` loads the component for any authenticated role; any non-owner can load `?tool=school-onboarding` directly [`frontend/src/components/Layout.js:39`]
- [ ] [Review][Patch] React state updates on unmounted component in `pollChecklist` — `setChecklist` / `setChecklistLoading` called after async fetch with no `isMounted` guard or AbortController; component can set state after unmount [`frontend/src/components/tools/SchoolOnboarding.js:138-154`]
- [ ] [Review][Patch] `plan_tier` not server-side enum validated — Pydantic field is `str`; direct API calls can write any string value, silently corrupting billing/feature-flag logic [`backend/routes/operator.py:CreateSchoolRequest`]
- [ ] [Review][Patch] Test: `test_create_school_success` missing `is_active: True` assertion on created `auth_users` doc [`tests/backend/unit/test_school_onboarding.py`]
- [ ] [Review][Patch] Test: `test_onboarding_status_partial` missing `first_fee_record_created: False` assertion (only checks one of the two incomplete steps) [`tests/backend/unit/test_school_onboarding.py`]
- [ ] [Review][Patch] Test: `test_onboarding_status_complete_sets_active` missing `activated_at` field assertion on updated schools doc [`tests/backend/unit/test_school_onboarding.py`]
- [ ] [Review][Patch] No audit log on `deactivate_school` — destructive admin action lacks `write_audit()` call; every other privileged destructive op in the project records to audit_log [`backend/routes/operator.py:deactivate_school`]

- [x] [Review][Defer] `deactivate_school` does not invalidate JWT sessions or set `is_active=False` on owner auth record [`backend/routes/operator.py:deactivate_school`] — deferred, pre-existing; full enforcement is Story 7-45
- [x] [Review][Defer] Same owner email can be used across multiple schools, producing duplicate `username_lower` entries in `auth_users` with no uniqueness constraint [`backend/routes/operator.py:create_school`] — deferred, pre-existing; cross-school login scope is Story 7-45
- [x] [Review][Defer] `_make_initials` derives owner display initials from school name, not owner's personal name [`backend/routes/operator.py:53`] — deferred, pre-existing; matches spec Dev Notes explicitly (`_make_initials(school_name)`)
- [x] [Review][Defer] `SMTP_PORT int()` parsing inconsistency — `send_welcome_email` doesn't guard on `ENVIRONMENT != production` like `send_password_reset_email` does [`backend/services/email_service.py`] — deferred, pre-existing; minor maintenance hazard
