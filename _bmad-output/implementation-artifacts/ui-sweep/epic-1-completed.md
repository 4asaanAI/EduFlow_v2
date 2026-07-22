# Epic 1 — Access That Cannot Be Talked Around · COMPLETED

**Branch:** `ui-sweep-2026-07-22` · **Date:** 2026-07-22
**Requirements covered:** FR2, FR3, FR4, FR5, FR78, NFR-S1, UX-DR1, UX-DR4, UX-DR9
**Closes:** D-02 (the owner-role hole reported as fixed when it was not), D-11, D-12, D-13, D-14

---

## What the school gets

Someone who can add or edit staff can no longer make themselves — or anyone
else — the owner of the school. Before this epic, the only thing stopping them
was that the option had been taken out of a dropdown; the server still accepted
the instruction if it was sent directly. Now the server refuses it, records who
tried, and refuses it for everybody including the owner. A job title the
permission system does not recognise is refused too, instead of being saved and
quietly granting the person nothing. And nobody — at any level — can change
their own name, phone or email; they ask, and the Owner or the Principal decides
(Epic 8).

---

## Story 1.1 — Reject privileged role assignment at the API, not the dropdown

**Files:** `backend/services/staff_service.py`, `backend/routes/staff.py`,
`backend/middleware/auth.py`, `backend/ai/prompts.py`

| AC | Met | How |
|---|---|---|
| Any caller, Owner included, is refused `role: "owner"` on create | ✅ | `_assert_no_owner_authority_change()` runs for every caller; no `_is_owner` bypass |
| Refused before any record is written | ✅ | The gate precedes `_create_or_link_user()`; `auth_users.user_info.role` is what login reads to mint the JWT, so a gate placed after it would leave a privileged login behind on a 403 |
| No `staff` **and** no `auth_users` document created | ✅ | `test_denied_create_writes_neither_a_staff_record_nor_a_login` |
| Attempt audited with the caller's user id | ✅ | `action="privilege_escalation_denied"`, `changed_by` = caller |
| Audit failure does not become a 500 | ✅ | `_audit_denial()` swallows and logs (ADR-002 fail-open) |
| PATCH granting owner → 403, stored value unchanged | ✅ | Same guard, evaluated against the stored record |
| PATCH **removing** owner → 403 | ✅ | Owner cannot be re-granted here, so demotion could strand the school with no owner |
| Owner resending an unchanged `role: "owner"` succeeds | ✅ | The rule is about a *change*, not about the string appearing in a body — the staff form posts every field back |
| A staff record cannot claim an owner's login | ✅ | `_assert_login_is_linkable()` (D-12) |
| AI tool description matches what the server accepts | ✅ | `TOOL_CREATE_STAFF` no longer offers `owner` (D-13) |
| 401 unauthenticated + 403 wrong-role, create and update | ✅ | Four tests, per the standing convention |
| Denial holds for every casing/whitespace spelling | ✅ | Values are normalised before comparison; parametrised over 5 spellings |

**Deliberate design choice:** an escalation attempt is a hard 403, *not* the
silent strip used for salary. Stripping salary says "that field isn't yours";
silently stripping an escalation leaves the caller believing it worked and
leaves no record that they tried.

## Story 1.2 — Refuse job categories the permission system does not recognise

**Files:** `backend/middleware/auth.py`, `backend/services/staff_service.py`,
`backend/routes/staff.py`

| AC | Met | How |
|---|---|---|
| `sub_category` outside the recognised set → 422 naming the field | ✅ | `StaffFieldValidationError` → 422; caught **before** its parent or the 400 handler would swallow it |
| No record written on rejection | ✅ | Validation precedes every write |
| A sub-category not belonging to the submitted role → rejected | ✅ | New `SUB_CATEGORIES_BY_ROLE` map; `VALID_SUB_CATEGORIES` is now derived from it so the two cannot drift |
| An unrecognised **role** → 422 | ✅ | `ASSIGNABLE_STAFF_ROLES`, derived by subtraction from `VALID_ROLES` |
| The 88 live records are not modified, and a legacy stored value does not block an unrelated edit | ✅ | Validation applies only to values being *written*; a field resent unchanged counts as stored |
| Changing only the role cannot strand a mismatched sub-category | ✅ | **Found by the adversarial pass, not by the original ACs** — see the review doc |
| Tool description lists only canonical values | ✅ | The legacy `accounts` spelling is gone from the prompt |

**Authority is checked before validation**, deliberately: a caller who may not
set these fields at all should not receive an error message enumerating the
values that would have been accepted.

## Story 1.3 — Nobody edits their own record (REVISED by the owner mid-run)

**Files:** `backend/routes/staff.py`, `frontend/src/lib/api.js`,
`frontend/src/contexts/UserContext.js`, `frontend/src/components/ProfileModal.js`

> **The first version of this story was wrong and was removed.** It let a person
> edit their own name, phone and email directly. Abhimanyu reversed it: *"no one
> changes their name, phone, email to misuse the power — only after admin
> approval should be able to do that."* The self-service write path was **taken
> out**, not hidden: the endpoint that applied the change is gone, the client
> function that called it is gone, and the context helper that merged the result
> into the session is gone. The ask-and-approve flow he asked for is **Epic 8**.

| AC (revised) | Met | How |
|---|---|---|
| Own details visible, none editable | ✅ | `SELF_SERVICE_FIELDS` is now the **empty set** |
| Any self-edit refused with 403 — contact details, authority fields, mixed, or empty body | ✅ | Parametrised over 12 bodies; "refused" must not depend on what was asked for |
| The Owner cannot self-edit either | ✅ | The rule is "nobody edits themselves", not "staff are restricted" |
| Nothing written to the staff record **or** the login record | ✅ | Asserted on every refusal |
| The refusal says who *can* make the change | ✅ | A dead-end refusal is useless to a teacher whose number really changed |
| The empty allow-list is itself asserted | ✅ | So a field cannot be quietly added back and silently restore self-editing |
| Someone with no staff record has none conjured for them | ✅ | tested |
| `GET /api/staff/me` still serves the person their own record, without salary | ✅ | Read-only |
| `data-testid`, CSS variables, visible focus at ≥3:1 | ✅ | Every control; reuses `.focus-ring` |
| The dialog no longer prints a hard-coded wrong city | ✅ | D-11 |

**Scope decision:** there is now exactly **one** place in the platform where a
person's record changes — the staff screen, operated by the Owner or Principal.

---

## Tests

New file `tests/backend/api/test_ui_sweep_epic1_access.py` — 48 tests.
Rewritten (not deleted) to the stronger contract: 3 tests in
`test_staff_routes.py` and `test_epic_j_crud_guardrails.py` (D-14).
Epic 8 adds `test_ui_sweep_epic8_change_requests.py` — 34 tests.

**Full suite: 1720 passed, 2 failed, 14 deselected.** The 2 are the pinned,
pre-existing, order-dependent failures in `test_r13_tenancy_rbac.py` (D-03) —
unchanged in count and identity. Baseline before this epic was 1636 passed / 2
failed; +84 passing tests, all accounted for.

## Also in this run — the city

"Lucknow" was wrong in five places in the code, including
`ai/prompts.py`, which told the assistant itself that the school is in Lucknow.
All corrected to Joya, Amroha. **No database write** — the value the sidebar
shows comes from a code default when no school record is stored, so this may fix
production on deploy without touching data. If it does not, the wrong city is
also stored, and correcting that needs separate approval (D-15).

Run with the connection pinned away from production, per D-04:
`$env:MONGO_URL="mongodb://127.0.0.1:27099/eduflow_test"; $env:DB_NAME="eduflow_test"`

## Live data

**No writes to the production database.** 1,802 students, 88 staff and 1,892
users were untouched. The frontend was exercised read-only against the live
backend; nothing was saved.
