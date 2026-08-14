# Data Models - Backend

_Generated: 2026-05-15 | Scan: deep | Part: backend_

---

## Database

- **Engine:** MongoDB Atlas (async via Motor 3.3.1)
- **Connection:** `MONGO_URL` env var (mongodb+srv://)
- **Database name:** `DB_NAME` env var
- **Multi-tenancy:** Every operational document carries a `schoolId` field (string). System collections are exempt.

---

## Multi-Tenancy Architecture

EduFlow uses a **dual-axis tenancy model**:

| Axis | Field | Scope | Mechanism |
|------|-------|-------|-----------|
| School | `schoolId` | All operational docs | `ScopedCollection` in `database.py` auto-injects `schoolId` on writes and adds `{$or: [{schoolId: X}, {schoolId: {$exists: false}}]}` on reads |
| Branch | `branch_id` | Per-branch operational docs | `scoped_query()` in `tenant.py` - caller must pass `branch_id` explicitly |

**`ScopedDatabase`** wraps every collection access: `get_db().students` returns a `ScopedCollection` that enforces `schoolId` automatically. System collections bypass scoping.

---

## System Collections (no schoolId scoping)

| Collection | Purpose |
|-----------|---------|
| `_migrations` | Migration run history |
| `auth_users` | User login credentials and profile |
| `login_attempts` | Brute-force lockout tracking |
| `otps` | OTP records (TTL-indexed - auto-deletes on `expires_at`) |
| `refresh_tokens` | JWT refresh token store |

---

## Auth Collections

### `auth_users`
| Field | Type | Notes |
|-------|------|-------|
| `_id` | ObjectId | MongoDB default |
| `user_info.id` | string | Logical user ID (UUID-style) |
| `user_info.role` | string | `owner`, `admin`, `teacher`, `student` |
| `user_info.name` | string | Display name |
| `user_info.sub_category` | string? | `principal`, `accountant`, `receptionist`, `it_tech`, `maintenance` |
| `user_info.branch_id` | string? | Branch assignment |
| `user_info.initials` | string? | Short display name |
| `password_hash` | string | bcrypt hash |
| `phone` | string? | Phone number |
| `email` | string? | Email address |
| `schoolId` | string | Tenant identifier |

Indexes: None defined (uses `user_info.id` / `id` / `user_id` via OR query in `_auth_user_filter`).

### `refresh_tokens`
| Field | Type | Notes |
|-------|------|-------|
| `token_hash` | string | SHA-256 of raw token |
| `user_id` | string | Owner |
| `expires_at` | datetime | TTL-indexed (auto-purge) |
| `created_at` | datetime | Issue time |

Indexes: `token_hash` (unique), `user_id`, `expires_at` (TTL)

### `login_attempts`
| Field | Type | Notes |
|-------|------|-------|
| `user_id` | string | Target account |
| `attempts` | int | Rolling count |
| `locked_until` | datetime? | Lockout expiry |
| `last_attempt` | datetime | Last attempt time |

### `password_reset_tokens`
| Field | Type | Notes |
|-------|------|-------|
| `token` | string | Secure random token |
| `user_id` | string | Target user |
| `expires_at` | datetime | TTL: 15 min |

Indexes: `token` (unique), `user_id`, `expires_at` (TTL)

### `confirm_tokens`
| Field | Type | Notes |
|-------|------|-------|
| `token` | string | Confirmation token |
| `expires_at` | datetime | TTL-indexed |

Indexes: `token` (unique), `expires_at` (TTL)

### `idempotency_keys`
| Field | Type | Notes |
|-------|------|-------|
| `key` | string | `{user_id}:{Idempotency-Key header}` |
| `response_body` | bytes | Cached response body |
| `status_code` | int | Cached status code |
| `expires_at` | datetime | TTL-indexed |

Indexes: `key` (unique), `expires_at` (TTL)

---

## Student / Academic Collections

### `students`
Core student registry.
| Field | Type | Notes |
|-------|------|-------|
| `_id` | ObjectId | |
| `schoolId` | string | Tenant |
| `branch_id` | string | Branch scope |
| `name` | string | Full name |
| `admission_number` | string? | Unique per school (sparse index) |
| `class_id` | string | Class reference |
| `dob` | string? | Date of birth |
| `gender` | string? | |
| `photo_url` | string? | S3 URL |
| `guardians` | array | Guardian contact objects |
| `created_at` | datetime | |

Indexes: `class_id`, `admission_number` (unique, sparse)

### `student_attendance`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | Tenant |
| `student_id` | string | Reference |
| `class_id` | string | |
| `date` | string | ISO date YYYY-MM-DD |
| `status` | string | `present`, `absent`, `late` |
| `corrected` | bool? | Has been corrected |
| `corrections` | array? | Correction history |

Indexes: `(student_id, date)` (unique)

### `assignments`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `class_id` | string | |
| `subject` | string | |
| `title` | string | |
| `due_date` | string | |
| `created_by` | string | Staff ID |

Indexes: `class_id`

### `exams`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `name` | string | Exam name |
| `class_id` | string | |
| `subject` | string | |
| `date` | string | |
| `max_marks` | int | |

### `exam_results`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `exam_id` | string | |
| `student_id` | string | |
| `marks` | number | |
| `class_id` | string | |
| `subject` | string | |

### `lesson_plans`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `class_id` | string | |
| `subject` | string | |
| `teacher_id` | string | |
| `week` | string | ISO week |
| `content` | string | Plan text |

### `question_papers`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `class_id` | string | |
| `subject` | string | |
| `generated_by` | string | Staff ID |
| `questions` | array | AI-generated questions |
| `created_at` | datetime | |

---

## Staff Collections

### `staff`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `branch_id` | string | |
| `name` | string | |
| `role` | string | `teacher`, `admin`, etc. |
| `sub_category` | string? | Admin sub-role |
| `department` | string? | |
| `joining_date` | string? | |
| `photo_url` | string? | S3 URL |

### `staff_attendance`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `staff_id` | string | |
| `date` | string | ISO date |
| `status` | string | `present`, `absent`, `late` |

Indexes: `(staff_id, date)` (unique)

### `leave_requests`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `staff_id` | string | |
| `start_date` | string | |
| `end_date` | string | |
| `reason` | string | |
| `status` | string | `pending`, `approved`, `rejected` |
| `approved_by` | string? | |

Indexes: `staff_id`

---

## Finance Collections

### `fee_transactions`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `student_id` | string | |
| `amount` | number | |
| `fee_type` | string | |
| `status` | string | `paid`, `partial`, `pending` |
| `collected_by` | string | Staff ID |
| `transaction_date` | string | |
| `receipt_number` | string? | |

Indexes: `student_id`, `status`

### `fee_structures`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `class_id` | string | |
| `fee_types` | array | `{name, amount, frequency}` |
| `academic_year` | string | |

### `discount_types`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `name` | string | |
| `percent` | number | |

### `expenses`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `category` | string | |
| `amount` | number | |
| `description` | string | |
| `date` | string | |
| `recorded_by` | string | |

---

## Communication Collections

### `conversations`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `user_id` | string | Owner |
| `title` | string | |
| `created_at` | datetime | |

Indexes: `user_id`

### `messages`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `conversation_id` | string | |
| `role` | string | `user` or `assistant` |
| `content` | string | Message text |
| `created_at` | datetime | |
| `tool_calls` | array? | AI tool invocations |
| `artifacts` | array? | Structured result objects |

Indexes: `conversation_id`

### `notifications`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `user_id` | string | Recipient |
| `title` | string | |
| `body` | string | |
| `read` | bool | |
| `created_at` | datetime | |

### `queries`
Support tickets.
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `branch_id` | string | |
| `raised_by` | string | User ID |
| `subject` | string | |
| `body` | string | |
| `status` | string | `open`, `resolved` |
| `attachment_url` | string? | S3 URL |

---

## Operations Collections

### `visitors`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `name` | string | |
| `purpose` | string | |
| `in_time` | datetime | |
| `out_time` | datetime? | |
| `checked_out` | bool | |

### `complaints`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `category` | string | |
| `description` | string | |
| `status` | string | `pending`, `resolved` |
| `raised_by` | string | |

### `incidents`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `title` | string | |
| `description` | string | |
| `severity` | string | |
| `assigned_to` | string? | |
| `thread` | array | Reply thread |
| `status` | string | |

### `certificates`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `student_id` | string | |
| `type` | string | `bonafide`, `character`, etc. |
| `issued_date` | string | |
| `issued_by` | string | |

### `facility_requests`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `item` | string | |
| `status` | string | `pending`, `approved`, `resolved` |
| `raised_by` | string | |

### `maintenance_schedule`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `task` | string | |
| `scheduled_date` | string | |
| `assigned_to` | string? | |
| `status` | string | |

### `vendors`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `name` | string | |
| `contact` | string | |
| `category` | string | |

---

## AI / Token Budget Collections

### `token_balances`
| Field | Type | Notes |
|-------|------|-------|
| `branch_id` | string | One doc per branch |
| `balance` | int | Remaining tokens |
| `schoolId` | string | |

Indexes: `branch_id` (unique)

### `token_usage`
| Field | Type | Notes |
|-------|------|-------|
| `branch_id` | string | |
| `user_id` | string | |
| `month` | string | YYYY-MM |
| `tokens_used` | int | |
| `created_at` | datetime | |

Indexes: `(branch_id, user_id, month)`, `created_at`

### `token_purchases`
| Field | Type | Notes |
|-------|------|-------|
| `payment_id` | string | External payment reference |
| `branch_id` | string | |
| `pack_id` | string | |
| `tokens` | int | |
| `purchased_at` | datetime | |

Indexes: `payment_id` (unique)

---

## Other Collections

## Admissions Collections

The funnel is two collections joined by `enquiry_id`, plus the two CRM ones. Corrected
and expanded 2026-08-14; the previous version of this section listed a `name` field that
does not exist and a status list that was never right.

### `enquiries`
An admission enquiry, and the same row a CRM lead is stored in. There is one collection,
not two: `create_enquiry` and `create_crm_lead` both write here, and `delete_enquiry`
covers both.

| Field | Type | Notes |
|-------|------|-------|
| `id`, `schoolId`, `branch_id` | string | |
| `student_name` | string | Required. |
| `parent_name` | string? | **The contact the office deals with.** Kept deliberately alongside the two below: it is what messaging and every export read, and 102 live records carry it. |
| `mother_name`, `father_name` | string? | Added 2026-08-14. The school's own form records both, and carrying only `parent_name` onto an application meant one of the two arrived with no way to tell which. |
| `dob`, `gender`, `previous_school` | string? | Added 2026-08-14. All three were collected on paper at enquiry time and then retyped onto the application. |
| `phone` | string? | |
| `class_applying` | string | Free text such as "Class 3". **Not a class on the roll**, and never guessed into one. |
| `status` | string | `new`, `contacted`, `visit_scheduled`, `visited`, `documents_submitted`, `fee_paid`, `enrolled`, `lost`, plus `applied`, `admitted`, `closed` on the CRM path. |
| `source` | string | `walk_in`, `phone`, `referral`, `online`, `ad`. |
| `next_follow_up` | string? | `YYYY-MM-DD`. Written by an activity carrying a date, and read by the follow-up worklist. Refused at write time if it is not a readable date. |
| `application_id`, `student_id` | string? | Set when an application is started, and when the child is created. |
| `entity_id`, `estimated_value_paise`, `probability`, `lead_type`, `campaign`, `lost_reason` | mixed | The CRM half. |
| `timeline` | array | Every stage change with who made it and any note. |
| `assigned_to`, `created_at`, `updated_at` | mixed | |

**`enrolled` is never written by a stage change.** It is set only by
`enroll_application`, in the same transaction that creates the child. Every other path
refuses it with one shared message. Before 2026-08-14 this was an ordinary stage move, so
a row could sit in the last column with no child behind it.

Indexes: `status`

### `admission_applications`
The second half of the funnel. Created from an enquiry or from scratch.

| Field | Type | Notes |
|-------|------|-------|
| `id`, `schoolId`, `branch_id` | string | |
| `enquiry_id` | string? | The family this came from. **One application per enquiry**: a second attempt returns the first. |
| `applicant_name` | string | |
| `guardian_name`, `guardian_phone`, `guardian_email` | string? | Name and phone are required before the application may be submitted. |
| `mother_name`, `father_name`, `dob`, `gender`, `previous_school` | string? | Carried from the enquiry when one is named; anything typed here wins. |
| `class_id`, `class_applying`, `academic_year`, `address` | string? | |
| `status` | string | `draft`, `submitted`, `under_review`, `assessment_scheduled`, `assessed`, `offered`, `accepted`, `rejected`, `withdrawn`, `enrolled`. |
| `status_history` | array | Every move, with who and when. |
| `documents` | array | Attached files with an uploader and a verified flag. |
| `assessment` | object? | Score, maximum, percentage, date. Required before `assessed`. |
| `offer` | object? | Class, valid-until date, admission fee, terms. Required before `accepted`. |
| `student_id`, `enrolled_at`, `enrolled_by` | mixed | Set only by enrolment. |

### `crm_activities`
One call, visit, meeting or note about a family.

| Field | Type | Notes |
|-------|------|-------|
| `id`, `schoolId`, `branch_id`, `entity_id` | string | |
| `enquiry_id` | string | |
| `activity_type` | string | `note`, `call`, `email`, `meeting`, `visit`, `follow_up`. |
| `subject`, `notes`, `occurred_at` | mixed | |
| `next_follow_up` | string? | `YYYY-MM-DD`. Copied onto the enquiry, which is what makes the family appear on the "who to call" worklist. |
| `created_by`, `created_at` | mixed | |

### `crm_opportunities`
A money value against a lead. Stages `qualification`, `visit`, `application`, `offer`,
`won`, `lost`; amounts in integer paise; a lost one needs a reason.

### `admission_tests` (added 2026-08-15)
An entrance test as a record. Before this it was a word: `assessment_scheduled` was a status
on an application with no date, no place and no list behind it.

| Field | Type | Notes |
|-------|------|-------|
| `id`, `schoolId`, `branch_id` | string | |
| `title` | string | Required. |
| `scheduled_for` | string | Required, `YYYY-MM-DD`. |
| `start_time` | string? | `HH:MM`. |
| `place` | string | **Required.** A date with no place is half a summons that reads as a whole one. |
| `class_applying`, `notes` | string? | |
| `maximum_marks` | number | Required, above zero. **The paper's total lives here, not on each child**, and it is frozen once any mark is recorded: changing it would silently rewrite every percentage already on an application. |
| `status` | string | `planned`, `held`, `cancelled`. A cancelled test takes no applicants and no marks, and a test that has been marked cannot be cancelled. |
| `created_by`, `created_at`, `updated_at` | mixed | |

Indexes: `(branch_id, scheduled_for)`.

### `admission_test_seats` (added 2026-08-15)
One applicant on one test. The join between a test and an application.

| Field | Type | Notes |
|-------|------|-------|
| `id`, `schoolId`, `branch_id` | string | |
| `test_id`, `application_id` | string | |
| `attendance` | string? | `present`, `absent`, or **`null`, which is its own state and means nobody has said yet**. It is never drawn as absent, and every count includes `not_yet_marked` separately. |
| `score` | number? | `null` until marked. Refused unless `attendance` is `present`. |
| `attendance_marked_by/_at`, `scored_by/_at`, `created_by`, `created_at` | mixed | |

**The applicant's name is deliberately NOT stored here.** It is read from the application
whenever the list is drawn, so a corrected spelling appears rather than the list keeping the
old one forever. If the application has gone, the row is still returned and flagged
`application_found: false` rather than vanishing from a list somebody printed on Friday.

**A score is not stored here and copied to the application later.** It goes through
`admissions_service.record_assessment` in the same call, and if that refuses nothing is
written at all, including the attendance. The seat and the application can never disagree.

Indexes: `(branch_id, test_id)`, and `(schoolId, test_id, application_id)` unique, so a
double submit cannot seat the same child twice.

### `audit_log`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `actor_id` | string | Who did it |
| `action` | string | Event type |
| `target_id` | string? | Affected record |
| `changes` | object? | Before/after diff |
| `timestamp` | datetime | |

### `uploads`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `file_id` | string | |
| `filename` | string | |
| `s3_key` | string | S3 object key |
| `uploaded_by` | string | |
| `created_at` | datetime | |

### `sms_logs`
| Field | Type | Notes |
|-------|------|-------|
| `schoolId` | string | |
| `recipient` | string | Phone number |
| `message` | string | |
| `status` | string | |
| `sent_at` | datetime | |

---

## Migrations

Migrations are Python scripts in `backend/migrations/`. Production migrations are
reviewed, rehearsed, and executed one at a time; `run_all.py` must never target the live
school database.

| Migration | Description |
|-----------|-------------|
| `001_add_branches` | Adds branch structure |
| `002_add_houses` | Adds school houses |
| `003_add_staff_hierarchy` | Staff org chart |
| `004_add_transport` | Transport routes |
| `005_add_library` | Library module |
| `006_add_inventory_vendors` | Inventory + vendor data |
| `007_add_fees_discounts` | Discount types |
| `008_add_events_sports` | Events and sports |
| `009_add_payroll` | Payroll data |
| `010_add_tokens` | AI token budget system |
| `011_add_support_tickets` | Support ticket module |
| `012_migrate_uploads_to_s3` | S3 upload migration |
| `013_add_school_id` | schoolId backfill |
| `014_ensure_maintenance_user` | Maintenance role user |
| `015_ai_rate_limit_counters` | AI rate limit fields |
| `016_admin_sub_category_default` | Default sub_category for admin users |
| `017_backfill_rate_limit_override_expires_at` | Fix rate limit expiry backfill |

The table is historical and not a production execution plan. Inspect the current
`backend/migrations/` directory and the specific script before any run.
