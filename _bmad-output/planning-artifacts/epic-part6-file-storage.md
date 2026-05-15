---
workflowType: 'epics'
project_name: 'EduFlow Platform Quality Sweep — Part 6'
user_name: 'Abhimanyu'
date: '2026-05-15'
status: 'ready-for-implementation'
part: 6
part_name: 'File Storage + Uploads'
source_parts: ['Part 1 Auth+RBAC', 'Part 2 AI Layer', 'Part 3 Owner role', 'Part 4 Multi-tenancy', 'Part 5 Notifications+SSE']
test_baseline: '387 backend tests passing, 0 skipped'
---

# EduFlow Quality Sweep — Part 6: File Storage + Uploads

## Context

Part 6 addresses correctness, security, and data lifecycle gaps in the file upload and storage layer. Items were identified by auditing `backend/services/s3_storage.py`, `backend/routes/upload.py`, `backend/routes/chat_upload.py`, `backend/routes/image_gen.py`, and `backend/routes/students.py`.

Key discoveries from the code audit:

1. **`GET /api/uploads/serve/{filename}` — unauthenticated access**: The `serve_file` endpoint at line 107 of `upload.py` does NOT call `get_current_user(request)`. Any person with the URL `https://api.example.com/api/uploads/serve/somefile.pdf` can fetch the file's presigned S3 redirect without being authenticated. The `file_url` stored in records is `/api/uploads/serve/<safe_filename>` — a path that any browser can directly access.

2. **S3 key namespace has no school/branch prefix**: `build_upload_key(file_id, original_filename)` returns `uploads/{file_id}/{filename}`. There is no `schoolId` or `branch_id` prefix. If the same S3 bucket is ever shared across schools (e.g. during a future multi-tenant migration), or if bucket ACLs are accidentally made public, files from different schools are stored in the same flat namespace with no isolation boundary. The key format `uploads/<uuid>/<filename>` provides no context about which school owns the file.

3. **`file_uploads` collection has no `schoolId` field**: `upload.py` `upload_file()` stores the record with `uploaded_by`, `file_url`, `file_name` etc. — but does NOT call `add_school_id()`. The record has no `schoolId`. This means `GET /api/uploads` for an admin/owner returns all uploads across all users — there is no school-level isolation in the DB query (though in a single-school deployment this is not a visible bug yet).

4. **MIME type validated by extension only**: `upload.py` checks `ext not in allowed` where `ext` is extracted from `file.filename`. There is no server-side MIME type sniffing (e.g. `python-magic` or file header inspection). A user can rename `evil.exe` to `evil.pdf` and it will pass the extension check. The `content_type` stored is `infer_content_type(file.filename, file.content_type)` which trusts the client-supplied `content_type` header.

5. **`chat_upload.py` has no file-type allowlist**: `upload_chat_file()` accepts any file extension — `_extract_text()` handles known types and returns placeholder text for unknown ones. But there is no size check per MIME class, no rejection of potentially dangerous files (e.g. `.exe`, `.bat`, `.sh`), and no restriction by user role. A student can upload a 20 MB zip containing 10 text files.

6. **Orphan cleanup gap — `chat_upload.py` files never stored**: Files uploaded via `POST /api/chat/upload` (chat context) have their text extracted in-memory and are NEVER stored in S3 or `file_uploads`. This is correct by design (ephemeral). But there is no documentation of this intentional difference from `POST /api/uploads`, leading to confusion.

7. **Image generation outputs are never persisted**: `POST /api/image-gen/certificate` and `POST /api/image-gen/id-cards` return PDF bytes directly in the HTTP response. The generated PDFs are not stored in S3 or `file_uploads`. If the user does not download them, they are lost. There is no retry path. The Gemini background call (`_gemini_image`) is not retried on transient failure; it silently falls back to a plain background.

8. **`DELETE /api/uploads/{file_id}` does not check `schoolId`**: The delete endpoint queries `db.file_uploads.find_one({"id": file_id})` without a `schoolId` filter. An admin from a different school (if the DB were ever shared) could delete another school's files. In the current single-school deployment this is dormant but is a latent cross-tenant bug.

9. **`GET /api/uploads` admin/owner case removes ALL filters**: When `user["role"] in ["owner", "admin"]`, the query is reset to `{}` (with optional entity_type/entity_id filters). This means an owner/admin can see all uploads from all users. There is no `schoolId` scope in the admin query.

10. **Minimal file storage tests**: `tests/backend/unit/test_s3_storage.py` covers only `s3_storage.py` helpers (upload_bytes, presigned URL, checksum). There are no tests for `upload.py` route behavior (auth, file type checks, admin scope, delete authorization).

**Entering baseline:** 387 backend tests, 0 skipped.

---

## Functional Requirements

**FR6.1 — Authenticated file serving**: `GET /api/uploads/serve/{filename}` MUST require authentication via `get_current_user(request)`. Unauthenticated requests must return 401. The presigned redirect must only be issued after the user's identity is verified.

**FR6.2 — School-scoped S3 key namespace**: `build_upload_key()` MUST accept a `school_id` parameter and produce keys in the format `{school_id}/uploads/{file_id}/{filename}`. All existing call sites in `upload.py` must pass `get_school_id()`. This ensures files from different schools occupy distinct key prefixes even in a shared bucket.

**FR6.3 — schoolId in file_uploads documents**: `upload_file()` MUST call `add_school_id()` when constructing the upload record. All queries against `db.file_uploads` MUST include `schoolId` via `scoped_filter()`.

**FR6.4 — Server-side MIME type validation**: `upload.py` MUST validate file content type by inspecting the file's magic bytes (first 8–512 bytes), not only the extension. If the detected MIME type does not match the declared extension's expected content type, return 415. Use `python-magic` or manual header inspection.

**FR6.5 — chat_upload.py file type blocklist**: `upload_chat_file()` MUST reject files with extensions in a defined blocklist: `{".exe", ".bat", ".sh", ".cmd", ".com", ".ps1", ".vbs", ".jar", ".msi", ".dll"}`. Return 415 for blocked types with a clear error message.

**FR6.6 — Image generation optional persistence**: `POST /api/image-gen/certificate` and `POST /api/image-gen/id-cards` MUST accept an optional `persist: true` body flag. When `persist` is true, the generated PDF bytes MUST be stored in S3 using `upload_bytes()` and a record inserted in `file_uploads`. The response must include the `file_url` in addition to (or instead of) streaming the bytes.

**FR6.7 — Delete endpoint schoolId guard**: `DELETE /api/uploads/{file_id}` MUST scope the lookup to `scoped_filter({"id": file_id}, get_school_id())`. A file belonging to a different school (by schoolId) must return 404.

**FR6.8 — Admin GET /api/uploads schoolId scope**: When `user["role"] in ["owner", "admin"]`, `GET /api/uploads` MUST still apply `schoolId` scoping via `scoped_filter(query, get_school_id())` before executing the MongoDB query.

---

## Non-Functional Requirements

**NFR6.1 — Presigned URL expiry**: Presigned GET URLs generated by `create_presigned_get_url()` MUST expire within 3600 seconds (1 hour). This is already enforced — ensure the constraint is tested. A future endpoint for short-lived document previews must use `expires_in ≤ 300`.

**NFR6.2 — Upload size limits by role**: The per-role allowed type table in `upload.py` MUST be accompanied by per-role size limits. Currently all roles share the 10 MB cap. Define: owner/admin 50 MB, teacher 20 MB, student 10 MB. Add to `MAX_SIZE_BY_ROLE` dict.

**NFR6.3 — Large file streaming**: `upload_bytes()` reads the entire file content into memory (`content=await file.read()`). For files approaching 50 MB this means 50 MB allocated per concurrent upload. The `upload_fileobj()` helper exists but is not used. Files > 10 MB SHOULD use multipart upload. For Part 6, add a comment and a log warning at > 20 MB.

**NFR6.4 — S3 error observability**: S3 errors in `upload_bytes()`, `create_presigned_get_url()`, and `delete_object()` are converted to `HTTPException(502)`. The original `BotoCoreError` / `ClientError` must be logged at `logger.error` level with `exc_info=True` before re-raising. Currently only the `HTTPException` is raised.

---

## Architecture Requirements

**AR6.1 — File access control model**: The current model is: owner of file or owner/admin role can delete; anyone authenticated can serve. This is too permissive for serve. Define the access model:
- Any authenticated user can serve their own uploads (`uploaded_by == user["id"]`)
- Owner/admin can serve any upload in their school
- Students can only serve their own uploads
Document in `upload.py` as a comment block above `serve_file`.

**AR6.2 — chat_upload intentional ephemerality**: Add a module-level comment in `chat_upload.py` documenting that files uploaded here are processed in-memory and never stored. This prevents future developers from "fixing" the missing persistence.

**AR6.3 — S3 bucket policy**: Document in `_bmad-output/parts/file-storage/` that the S3 bucket must have:
- Block all public access enabled
- No bucket policy granting cross-account or public read
- Server-side encryption enabled (AES-256 or KMS)
These are infrastructure requirements outside the application code but must be verified before production.

---

## FR Coverage Map

| FR | Story | Notes |
|----|-------|-------|
| FR6.1 | P6.1 | auth on serve_file |
| FR6.2 | P6.2 | S3 key namespacing |
| FR6.3 | P6.2 | schoolId in records |
| FR6.4 | P6.3 | MIME validation |
| FR6.5 | P6.4 | chat upload blocklist |
| FR6.6 | P6.5 | image gen persistence |
| FR6.7 | P6.6 | delete schoolId guard |
| FR6.8 | P6.6 | list admin scope |
| NFR6.2 | P6.3 | role-based size limits |
| NFR6.4 | P6.7 | S3 error logging |
| AR6.1 | P6.1 | access control model |

---

## Epic P6: File Storage + Upload Hardening

### Story P6.1: Add authentication to serve_file endpoint + define access model

**Problem:** `GET /api/uploads/serve/{filename}` (line 107, `upload.py`) does not call `get_current_user(request)`. The endpoint queries `db.file_uploads.find_one({"safe_filename": filename})` and returns a presigned S3 redirect. No authentication check is made. Any person who knows a `safe_filename` (which is `{uuid}.{ext}` — not guessable but also not secret once leaked in a URL) can fetch a school's uploaded documents without logging in. This exposes student records, fee documents, and imported spreadsheets to unauthenticated access.

**Scope:**
- Add `user = get_current_user(request)` at the top of `serve_file()`
- Add access control check:
  - If `record["uploaded_by"] == user["id"]`: allow
  - If `user["role"] in ["owner", "admin"]` AND `record["schoolId"] == get_school_id()`: allow
  - Otherwise: raise `HTTPException(403, "Forbidden")`
- Add `schoolId` check to `db.file_uploads.find_one()` query: `{"safe_filename": filename, "schoolId": get_school_id()}`
- Add a comment block above `serve_file` documenting the access model
- Add unit tests:
  - Unauthenticated request → 401
  - Authenticated owner → 307 redirect
  - Authenticated student requesting another student's file → 403
  - File not found → 404

**Acceptance Criteria:**

Given an unauthenticated GET request to `/api/uploads/serve/abc.pdf`,
When the request is processed,
Then the response is 401 Unauthorized with `{"detail": "Not authenticated"}`.

Given a student user requests a file uploaded by a different student,
When `serve_file` runs,
Then the response is 403 Forbidden.

Given an admin user requests any file in their school,
When `serve_file` runs,
Then the admin receives the 307 redirect to the presigned URL.

Given a valid authenticated request to an existing file,
When the redirect is followed,
Then the presigned URL is served and the original S3 key is not exposed in the response.

- `serve_file` requires authentication
- Access model comment block added
- 4+ unit tests in `tests/backend/unit/test_upload_routes.py`
- All 387 existing tests still pass

---

### Story P6.2: School-scoped S3 key namespace + schoolId in file_uploads

**Problem:** `build_upload_key(file_id, original_filename)` returns `uploads/{file_id}/{filename}` with no school prefix. If the same S3 bucket is shared across deployments (e.g. staging, dev, or a future multi-school setup), files are commingled in the same namespace. Additionally, `upload.py` `upload_file()` does not call `add_school_id()`, so `file_uploads` documents lack `schoolId`. This means all `db.file_uploads` queries run without tenant scoping — the collection is not multi-tenant-safe.

**Scope:**
- Modify `build_upload_key(file_id, original_filename, school_id: str = "")`:
  - If `school_id` is provided: key becomes `{school_id}/uploads/{file_id}/{filename}`
  - If not: falls back to current `uploads/{file_id}/{filename}` (backward compat for existing records)
- In `upload_file()`, pass `school_id=get_school_id()` to `build_upload_key()`
- Add `add_school_id()` wrap in the `record` dict construction in `upload_file()`
- Update `list_uploads()` to use `scoped_filter(query, get_school_id())`
- Update `delete_file()` to query `scoped_filter({"id": file_id}, get_school_id())`
- Update `serve_file()` to query `{"safe_filename": filename, "schoolId": get_school_id()}`
- Add migration `020_file_uploads_add_school_id.py` to backfill `schoolId` on existing records from `SCHOOL_ID` env var
- Add unit tests:
  - `build_upload_key` with school_id produces `school_abc/uploads/{id}/{name}`
  - `build_upload_key` without school_id produces `uploads/{id}/{name}` (backward compat)
  - Uploaded file record has `schoolId` field

**Acceptance Criteria:**

Given `build_upload_key("uuid123", "report.pdf", school_id="school-a")`,
When called,
Then it returns `"school-a/uploads/uuid123/uuid123.pdf"`.

Given `build_upload_key("uuid123", "report.pdf")` with no school_id,
When called,
Then it returns `"uploads/uuid123/uuid123.pdf"` (backward compatible).

Given `POST /api/uploads` with an authenticated user,
When the file is stored,
Then `db.file_uploads.find_one({"id": file_id})["schoolId"]` equals `get_school_id()`.

Given an owner/admin calls `GET /api/uploads`,
When the query runs,
Then only records with the current `schoolId` are returned.

- Migration 020 created and added to `run_all.py`
- `build_upload_key` signature updated
- All upload/list/delete endpoints scoped
- Unit tests pass
- All 387 existing tests still pass

---

### Story P6.3: Server-side MIME type validation + per-role size limits

**Problem:** `upload.py` validates file type by checking `file.filename.rsplit(".", 1)[-1].lower()` against `ALLOWED_TYPES`. This trusts the filename extension entirely. An attacker can rename `malware.exe` to `malware.pdf` and it will pass. The uploaded bytes will be stored in S3 labeled as `application/pdf` but contain an executable. Additionally, all roles share the same 10 MB limit — there is no differentiation between owner (who might legitimately upload large spreadsheets) and students.

**Scope:**
- Add `detect_mime_from_bytes(content: bytes) -> str` helper in `s3_storage.py` or `upload.py`:
  - Inspect the first 512 bytes of the file content
  - Check against known magic byte signatures for common formats: PDF (`%PDF`), PNG (`\x89PNG`), JPEG (`\xff\xd8\xff`), ZIP (`PK\x03\x04`), DOCX/XLSX (also ZIP-based)
  - If detected MIME does not match the extension's expected MIME family, raise `HTTPException(415, "File content does not match declared extension")`
- Add `MAX_SIZE_BY_ROLE: dict[str, int]` in `upload.py`:
  ```python
  MAX_SIZE_BY_ROLE = {
      "owner": 50 * 1024 * 1024,
      "admin": 50 * 1024 * 1024,
      "teacher": 20 * 1024 * 1024,
      "student": 10 * 1024 * 1024,
  }
  ```
- Replace `if len(content) > MAX_SIZE_BYTES` check with role-based lookup
- Add unit tests:
  - PDF magic bytes on a `.pdf` file → accepted
  - PNG magic bytes on a `.pdf` file → 415
  - EXE renamed to `.docx` → 415
  - 15 MB file from teacher → rejected
  - 15 MB file from admin → accepted

**Acceptance Criteria:**

Given a file named `invoice.pdf` whose bytes start with `\x89PNG` (PNG magic bytes),
When uploaded via `POST /api/uploads`,
Then the response is 415 Unsupported Media Type.

Given a valid 12 MB PDF uploaded by a teacher (20 MB limit),
When `upload_file` checks the size,
Then the file is accepted.

Given a valid 12 MB PDF uploaded by a student (10 MB limit),
When `upload_file` checks the size,
Then the response is 400 with a message indicating the student's size limit.

Given a file with correct PDF magic bytes and `.pdf` extension,
When uploaded by any allowed role,
Then it is stored successfully.

- `detect_mime_from_bytes` implemented without external dependency (magic byte inspection only)
- `MAX_SIZE_BY_ROLE` replaces `MAX_SIZE_BYTES`
- At least 5 unit tests in `tests/backend/unit/test_upload_routes.py`
- All 387 existing tests still pass

---

### Story P6.4: chat_upload.py file type blocklist + documentation

**Problem:** `POST /api/chat/upload` accepts any file extension. `_extract_text()` returns a placeholder for unknown types rather than rejecting them. This means a student can upload a `.exe`, `.sh`, or `.bat` file — it will receive a `[File: evil.exe — unsupported format '.exe']` placeholder and be added to AI context. While harmless for the AI context itself, it normalizes dangerous file uploads and could be a vector if the extraction path is ever modified to execute files. Additionally, there is no documentation that files here are ephemeral (not stored in S3).

**Scope:**
- Define `BLOCKED_EXTENSIONS = {".exe", ".bat", ".sh", ".cmd", ".com", ".ps1", ".vbs", ".jar", ".msi", ".dll", ".bin", ".scr"}` at module level
- In `upload_chat_file()`, check `suffix in BLOCKED_EXTENSIONS` before extraction; return `HTTPException(415, f"File type {suffix} is not permitted")`
- Add module-level docstring clarifying ephemeral nature: "Files uploaded here are processed in-memory and never stored to S3 or the database. This is intentional."
- Add unit tests:
  - `.exe` file → 415
  - `.sh` file → 415
  - `.txt` file → 200 with extracted text
  - `.pdf` file → 200 with extracted placeholder or text

**Acceptance Criteria:**

Given a file named `payload.exe` uploaded to `POST /api/chat/upload`,
When the handler checks the extension,
Then the response is 415 with "File type .exe is not permitted".

Given a file named `data.txt` with text content,
When uploaded to `POST /api/chat/upload`,
Then the response is 200 with `extracted_text` containing the file content.

Given the `chat_upload.py` module,
When read by a developer,
Then the module docstring clearly states files are not persisted.

- `BLOCKED_EXTENSIONS` defined at module level
- Blocklist check is the first operation after reading file bytes
- Module docstring updated
- 4+ unit tests in `tests/backend/unit/test_chat_upload.py`
- All 387 existing tests still pass

---

### Story P6.5: Optional persistence for image-generated documents

**Problem:** `POST /api/image-gen/certificate` and `POST /api/image-gen/id-cards` return PDF bytes directly in the HTTP response with `Content-Disposition: attachment`. The generated PDF is never stored. If the user does not receive the download (network failure, accidental close), there is no way to retrieve the document. Additionally, there is no audit trail for certificate generation — a teacher could generate a fraudulent certificate and there would be no record in `audit_logs`. The Gemini image API call has no retry on transient failure; a 500 from Gemini silently falls back to a plain background without logging the failure level.

**Scope:**
- Add optional `persist: bool = False` field to the request body for both endpoints
- When `persist=True`:
  - Store the generated PDF bytes in S3 using `upload_bytes()` with `school_id` prefix
  - Insert a record in `db.file_uploads` linked to the student (`linked_table="certificate"` or `"id_card"`, `linked_id=<student_id>`)
  - Return response with `file_url` in addition to (or instead of) the binary response
  - Write an audit log entry: action `certificate_generated` or `id_card_generated`
- When Gemini call fails, log at `logger.warning` level (not silent fallback at debug/info)
- Add unit tests:
  - `persist=False` returns binary PDF (no DB write)
  - `persist=True` returns `file_url` and writes to `file_uploads`
  - Gemini failure → warning logged, fallback used, response still valid

**Acceptance Criteria:**

Given `POST /api/image-gen/certificate` with `persist=true` and valid student data,
When the endpoint runs,
Then a `file_uploads` record is created and `response["file_url"]` is present.

Given `POST /api/image-gen/certificate` with `persist=false` (default),
When the endpoint runs,
Then no `file_uploads` record is created and the response is a binary PDF.

Given the Gemini API returns a 500 error,
When `_gemini_image()` catches it,
Then `logger.warning(...)` is called with the exception, and a plain-background PDF is returned.

Given `persist=true` certificate generation,
When the audit log is checked,
Then a `certificate_generated` record exists with `changed_by`, `entity_id` (student id), and `schoolId`.

- `persist` flag implemented for both endpoints
- Audit log written for persisted generations
- Gemini failure logs at warning level
- 4+ unit tests
- All 387 existing tests still pass

---

### Story P6.6: Delete and list endpoints full schoolId scoping

**Problem:** `DELETE /api/uploads/{file_id}` queries `db.file_uploads.find_one({"id": file_id})` with no `schoolId` filter. An admin from a future secondary school in the same MongoDB instance could delete another school's files if they guess or obtain a file UUID. Similarly, `GET /api/uploads` for admin/owner resets the query to `{}` with optional entity filters — no `schoolId` scope is applied. The `file_uploads` collection is currently scoped only by `uploaded_by` for non-admin users, but completely unscoped for admin queries.

**Scope:**
- Update `delete_file()`:
  - Query: `scoped_filter({"id": file_id}, get_school_id())`
  - If record not found with scoped query: 404 (same as before, but now school-safe)
- Update `list_uploads()` admin/owner branch:
  - Apply `scoped_filter(query, get_school_id())` before executing the find
- Add unit tests:
  - Delete file belonging to same school → 200
  - Delete file with mismatched schoolId → 404
  - Admin list returns only same-school files
  - Student list returns only own files

**Acceptance Criteria:**

Given a file record with `schoolId = "school-a"` and current deployment `SCHOOL_ID = "school-b"`,
When `DELETE /api/uploads/{file_id}` is called by a school-b admin,
Then the response is 404 Not Found (cross-school file is invisible).

Given an admin calls `GET /api/uploads` in school-a,
When the query executes,
Then only records with `schoolId = "school-a"` are returned.

Given a student calls `GET /api/uploads`,
When the query executes,
Then only records with `uploaded_by = student["id"]` are returned.

- All three upload endpoints have `schoolId` scope
- Unit tests cover cross-school isolation
- 4+ unit tests in `tests/backend/unit/test_upload_routes.py`
- All 387 existing tests still pass

---

### Story P6.7: S3 error logging + storage layer observability

**Problem:** `s3_storage.py` wraps S3 errors in `raise HTTPException(502, "...")` but does not log the underlying `BotoCoreError` / `ClientError` before raising. When S3 issues occur in production, the only signal is the 502 response — there is no log line with the original exception, the S3 operation type, the bucket name, or the key. This makes S3 incidents extremely difficult to diagnose. `upload_bytes()`, `create_presigned_get_url()`, and `delete_object()` all have this gap.

**Scope:**
- In each S3 operation's `except (BotoCoreError, ClientError) as exc:` block, add `logger.error("s3_operation_failed", operation=<op_name>, bucket=<bucket>, key=<key>, exc_info=True)` before `raise HTTPException(...)`
- Add `logger = logging.getLogger(__name__)` to `s3_storage.py`
- Ensure the log call uses structured fields (not f-string interpolation), consistent with `logging_config.py`'s JSON formatter
- Add unit tests using the `FakeS3Client` that raises `ClientError`:
  - `upload_bytes` failure → logger.error called, HTTPException 502 raised
  - `create_presigned_get_url` failure → logger.error called, HTTPException 502 raised
  - `delete_object` failure → logger.error called, HTTPException 502 raised

**Acceptance Criteria:**

Given an S3 `put_object` call that raises `ClientError`,
When `upload_bytes()` catches it,
Then `logger.error` is called with `exc_info=True` BEFORE the `HTTPException(502)` is raised.

Given an S3 `generate_presigned_url` call that raises `BotoCoreError`,
When `create_presigned_get_url()` catches it,
Then `logger.error` is called with operation name and key.

Given `delete_object()` raises a `ClientError`,
When the exception is caught,
Then `logger.error` is called and `HTTPException(502)` is raised.

- `logger` added to `s3_storage.py`
- All 3 S3 operations log before raising
- 3+ unit tests verifying log calls
- All 387 existing tests still pass (including existing `test_s3_storage.py`)

---

### Story P6.8: File upload test coverage baseline

**Problem:** `tests/backend/unit/test_s3_storage.py` covers only the S3 helper layer (4 tests). There are no tests for `upload.py` route behavior: authentication guards, file type validation, admin scoping, delete authorization, or the serve endpoint. The `chat_upload.py` route has zero tests. This is the largest test gap in the backend after notifications.

**Scope:**
- Create `tests/backend/unit/test_upload_routes.py` with at least 10 tests:
  1. `POST /api/uploads` with disallowed extension → 400
  2. `POST /api/uploads` with file exceeding role size limit → 400
  3. `POST /api/uploads` happy path → 200, record in DB with schoolId
  4. `GET /api/uploads/serve/{filename}` unauthenticated → 401 (after P6.1)
  5. `GET /api/uploads/serve/{filename}` student serves own file → 307
  6. `GET /api/uploads/serve/{filename}` student serves other's file → 403
  7. `GET /api/uploads` as student → only own uploads
  8. `GET /api/uploads` as admin → all uploads in school (scoped)
  9. `DELETE /api/uploads/{id}` by owner of file → 200
  10. `DELETE /api/uploads/{id}` by different user without admin role → 403
- Create `tests/backend/unit/test_chat_upload.py` with at least 5 tests:
  1. `.txt` upload → extracted text returned
  2. `.exe` upload → 415 (after P6.4)
  3. File > 20 MB → 413
  4. `.pdf` upload → extracted text or placeholder
  5. Unauthenticated request → 401

**Acceptance Criteria:**

Given all 15 tests in the new test files,
When the test suite runs,
Then all 15 pass.

Given `test_upload_routes.py` is added to the test suite,
When combined with existing tests,
Then total passing tests is 387 + ≥15.

- `test_upload_routes.py` created with 10+ tests
- `test_chat_upload.py` created with 5+ tests
- All tests pass
- All 387 existing tests still pass

---

## Implementation Order Recommendation

1. **P6.1** — Add auth to `serve_file` (critical security fix, 2-line change with tests)
2. **P6.2** — School-scoped S3 keys + schoolId in records (foundational, unblocks P6.6)
3. **P6.6** — schoolId scoping for delete/list (depends on P6.2 to have the field)
4. **P6.3** — MIME type validation + role size limits (security hardening)
5. **P6.4** — Chat upload blocklist + documentation (low risk)
6. **P6.7** — S3 error logging (observability, zero functional risk)
7. **P6.8** — Test coverage baseline (can run in parallel with P6.7)
8. **P6.5** — Image gen persistence (new feature, last since it requires P6.2)

---

## Epic P6: Retrospective

A retrospective entry for Part 6 to be completed after all P6.1–P6.8 stories are done.
