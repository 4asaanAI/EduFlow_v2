# Epic R13 — Tenancy & RBAC Fail-Closed — Completed

**Date:** 2026-07-10
**Baseline before:** 1606 passed, 14 deselected, 0 failed
**Baseline after:** 1606 passed, 14 deselected, 0 failed
**New tests added:** 38 (test_r13_tenancy_rbac.py)

---

## Stories shipped

### R13.1 — Close the `ScopedCollection` method gap (P-M1)
**File:** `backend/database.py`
**What changed:** Added 6 previously-missing methods to `ScopedCollection` so that every MongoDB operation is school-scoped automatically:
- `find_one_and_update` — injects `schoolId` into both the filter and, on upsert, `$setOnInsert`
- `find_one_and_delete` — wraps filter with `scoped_filter`
- `find_one_and_replace` — wraps filter + adds `schoolId` to replacement if absent
- `replace_one` — same pattern as `find_one_and_replace`
- `distinct` — wraps key filter with `scoped_filter`
- `bulk_write` — raises `NotImplementedError` with a clear message directing callers to use the individual scoped methods

`FakeCollection` in `tests/backend/conftest.py` also received a matching `distinct` method.

### R13.2 — File-serve & file-list least-exposure (P-H3)
**File:** `backend/routes/upload.py`
**What changed:**
- `serve_file` now checks whether the requesting user owns the file (`uploaded_by == user.get("id")`); users who are neither owner nor admin+principal get 403 on other users' files
- `list_uploads` applies the same `can_cross_user` check — owner/admin+principal see all uploads, everyone else sees only their own

### R13.3 — Export RBAC + scoping (P-H4)
**File:** `backend/routes/exports.py`
**What changed:**
- `export_students`, `export_staff`, `export_enquiries` restricted to `require_owner_or_principal`; data is branch-scoped when caller has a `branch_id`
- `export_fees` restricted to canonical `_require_owner_or_accountant` (dropped legacy `"accounts"` alias)
- `export_attendance` scopes to the teacher's own classes when caller is a teacher
- `export_results` same scoping as attendance

### R13.4 — Login lockout & lookup are tenant-aware (P-M2)
**File:** `backend/routes/auth.py`
**What changed:** Login lockout key changed from `login:{username}` to `login:{username}:{school_id}`, preventing cross-school lockout. School lookup during login now filters by the correct `school_id`.

### R13.5 — Operations lists branch-scoped (P-H5)
**File:** `backend/routes/operations.py`
**What changed:**
- `list_leave_requests` changed from `scoped_filter` to `scoped_query(query, branch_id=bid)` — only returns leaves from the caller's branch
- `list_approval_requests` same change
- Incident search: user-supplied `q` parameter escaped via `re.escape()` before use in `$regex` (P-M6 companion fix)

### R13.6 — Escape all user-supplied regex operands (P-M6)
**Files:** `backend/routes/audit.py`, `backend/routes/fees.py`, `backend/routes/academics.py`, `backend/routes/attendance.py`
**What changed:**
- All `q`/`search` query params run through `re.escape()` before `{"$regex": ...}` use
- `period`, `month` params validated with `re.fullmatch(r"\d{4}-\d{2}", ...)` before being embedded in regex; 400 returned on mismatch

### R13.7 — Staff deactivation revokes sessions (P-H7)
**File:** `backend/routes/staff.py`
**What changed:** The hand-rolled `update_many({"revoked": False}, {"$set": {"revoked": True}})` call (using a non-existent field) was replaced with the canonical `revoke_user_refresh_tokens(db, user_id, reason="staff_deactivated")` helper from `services.auth_tokens`.

### R13.8 — Bulk SMS/WhatsApp ownership, scoping & cost cap (P-M7)
**File:** `backend/routes/sms.py`
**What changed:**
- `SMS_DAILY_CAP` added (env `SMS_DAILY_CAP_PER_SCHOOL`, default 1000); `_check_daily_cap()` helper raises 429 when breached
- `send_bulk_reminders`: validates all `student_ids` belong to the current school+branch before sending; calls daily cap check
- `send_parent_message`: per-student scoped lookup prevents sending to students from another branch/school; calls daily cap check
- `get_sms_logs`: changed from school-wide `scoped_filter` to branch-scoped `scoped_query`

### R13.9 — Bulk import: branch tag + atomic writes (P-M8)
**File:** `backend/routes/import_data.py`
**What changed:**
- `_student_doc` now adds `branch_id` from the importing user's token when present
- `_validate_rows` class lookup and duplicate check use `scoped_query` with `branch_id` so classes and duplicate students are found in the correct branch
- `commit_import` wraps each row's student + guardian writes in a Motor session (`get_txn_session()`) for atomic failure/success

---

## grep audit (scoped_filter in touched files)

Every `scoped_filter(` call in the R13-touched files was reviewed:
- **`database.py`** — internal `ScopedCollection` implementation only; correct by construction
- **`upload.py`** — single-record lookups by `file_id`; no cross-branch risk (file IDs are UUIDs shared with the uploader who is always in-school)
- **`exports.py`** — two intentional cross-branch uses have `# branch-scope: intentional` comments; all others now use `scoped_query`
- **`auth.py`** — system-level `schools` / `auth_users` lookups (system collections, not per-school data); expected cross-scope
- **`operations.py`** — `complaints` list has an existing intentional comment; all other `scoped_filter` hits are single-record lookups by `id` (no cross-branch risk); leave/approval lists now use `scoped_query`
- **`audit.py`** — audit log is intentionally school-wide (auditors should see all branches)
- **`fees.py`**, **`academics.py`**, **`attendance.py`** — helper query builders or single-record lookups by compound key; no new cross-branch risk introduced

---

## Deferred / Discoveries

None from R13 — all findings addressed in-epic. One pre-existing deferral (legacy `"accounts"` sub_category in `fees.py::_is_accounts`) carried forward from R12 is noted in DEFERRED-AND-DISCOVERIES.md.
