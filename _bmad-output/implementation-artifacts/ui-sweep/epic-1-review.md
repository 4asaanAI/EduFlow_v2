# Epic 1 — Quality Gate Output

**Branch:** `ui-sweep-2026-07-22` · **Date:** 2026-07-22
Run over the whole epic's combined diff, per STEP 4 of the execution protocol.

---

> **Amended after the owner's mid-run reversal of Story 1.3 and the addition of
> Epic 8.** The findings below stand as recorded; F-5 and F-7 relate to a
> self-service write path that was subsequently removed entirely, and are kept
> because the reasoning carried over into the request route that replaced it.

## a. Test suite

| | Passed | Failed | Deselected |
|---|---|---|---|
| Pinned baseline (D-03) | 1636 | 2 | 14 |
| After Epic 1 | 1682 | 2 | 14 |
| After the Story 1.3 reversal + Epic 8 | **1720** | **2** | 14 |

The 2 failures are the same two pre-existing order-dependent tests
(`test_r13_tenancy_rbac.py::test_scoped_collection_find_one_and_update_injects_school_id`
and `::test_scoped_collection_distinct_scopes_to_school`) — neither fixed nor
worsened, as required. +46 passing tests, exactly matching what was added
(44 new + 2 net new in rewritten files).

Frontend: `craco build` compiles. None of the three changed frontend files
produces a lint warning. (The repo has many pre-existing `react-hooks/
exhaustive-deps` warnings in other files; `CI=true` therefore fails the build
repo-wide, both before and after this epic. Logged as D-16.)

## b–c. Review lenses, findings, and what was done about each

Lenses run: code-review, adversarial-general, edge-case-hunter,
testarch-test-review, testarch-trace, testarch-nfr. Two of these ran *before*
implementation as well (advanced-elicitation + party-mode, per STEP 3), and
their findings E-1…E-9 were folded into the ACs before any code was written —
those are recorded in the epic document itself, not repeated here.

| # | Sev | File | Issue | Fix | Regression test |
|---|---|---|---|---|---|
| F-1 | **High** | `staff_service.py` | Changing only the `role` left the stored `sub_category` attached — a `class_teacher` promoted to `admin` ended up with a pairing that matches no permission rule. The exact defect Story 1.2 exists to prevent, reached by changing the *other* half of the pair. Not covered by the original ACs. | Validate the record **as it will end up**, not the shape of the request: compute the effective role and sub-category and check the pair | `test_changing_only_the_role_cannot_strand_a_mismatched_sub_category` (fails before, passes after) + `test_changing_role_and_sub_category_together_is_accepted` |
| F-2 | **High** | `staff_service.py` | Blanket "role owner ⇒ 403" broke two legitimate flows: the staff form posts every field back, so an Owner editing the Owner's own record would be refused; and an Owner could demote the last owner, leaving the school with no owner and no in-app way to appoint one | Evaluate against the **stored** value — an unchanged resend is a no-op, and removal is refused as well as granting | `test_owner_editing_their_own_record_may_resend_the_unchanged_role`, `test_the_last_owner_cannot_be_demoted_through_the_api` |
| F-3 | **High** | `staff_service.py` | Authority gate originally ran *after* field validation, so an unauthorised caller got a 422 enumerating the values that would have been accepted | Authority first, validation second | Existing `test_principal_cannot_create_privileged_staff` (which this reordering restored to green) |
| F-4 | **High** | `staff_service.py` | `create_staff` accepted a caller-supplied `user_id`, and silently re-used any login whose derived username collided. Either path attached a staff record to the **owner's** login — and `DELETE /api/staff/{id}` deactivates the linked login and revokes its sessions, so any admin could lock the owner out | `_assert_login_is_linkable()` refuses a login holding owner authority or already claimed | `test_a_staff_record_cannot_be_linked_to_an_owner_login`, `test_a_login_already_claimed_by_another_staff_record_is_refused` |
| F-5 | Medium | `routes/staff.py` | `GET /api/staff/me` relied on a query projection to hide salary — a privacy guarantee resting on a database option a later caller could change without noticing what it protected | Strip it explicitly in `_own_profile()` | `test_self_profile_never_exposes_salary` |
| F-6 | Medium | `routes/staff.py` | `/me` would be shadowed by `/{staff_id}` if ever declared after it, silently turning a profile edit into a lookup of the staff member whose id is literally "me" | Declared before, with a comment saying why | `test_self_profile_endpoints_are_not_shadowed_by_the_id_route` |
| F-7 | Medium | `routes/staff.py` | A mixed body `{name, role}` would have saved the name and dropped the role, telling the caller exactly where the boundary sits | Refuse the whole request | `test_a_mixed_request_is_refused_whole_not_partly_applied` |
| F-8 | Medium | `staff_service.py` | Refusing a claimed login is reachable without malice — two staff with the same name and no email or phone derive the same username. The old behaviour silently gave them **one shared login** | Kept the refusal (the shared login was the worse bug) but the message now names the conflict and says what to do | covered by F-4's tests |
| F-9 | Low | `staff_service.py` | `ASSIGNABLE_STAFF_ROLES` was a hand-typed literal that could drift from the platform's role list | Derived by subtraction from `VALID_ROLES` | `test_every_valid_sub_category_belongs_to_exactly_one_role` |
| F-10 | Low | `ProfileModal.js` | The profile form could be submitted before the record loaded, writing blanks over a real phone number | Inputs and the save button are disabled until loaded | — (UI state; on the human checklist) |

### Dismissed, with reasons

| Finding | Reason |
|---|---|
| `_is_accounts()` still honours the legacy `"accounts"` spelling, which can no longer be written | Deliberate. It **reads** stored values, and some of the 88 live records may hold it. Removing it would strip permissions from a real person. Correcting stored data is a write and needs approval. |
| Pre-existing `scoped_filter(` hits in `staff.py` lack the `# branch-scope: intentional` comment | Pre-existing, not introduced here. Annotating them is unrelated churn in a security diff. Logged as D-17. |
| The new test file carries a module-level `pytestmark = pytest.mark.asyncio` over mostly-sync tests, producing warnings | Matches the existing convention in `test_staff_routes.py` and CLAUDE.md's standing rule. Changing the convention is a repo-wide decision, not an Epic 1 one. |
| `"unassigned"` as the audit `entity_id` for a denied create | A denied create has no id to record. The sentinel is documented at the call site. |
| The profile dialog still prints the school name as a literal `"The Aaryans"` | The *wrong* part (Lucknow) is gone. The stored school record is still placeholder data; correcting it is a write and is Epic 4 / Track 2. |

## d. Scoped filter / query audit

Every `scoped_filter(` / `scoped_query(` hit in the two touched backend route
and service files was re-checked. The epic introduces exactly **one** new hit:

- `staff_service.py` `_assert_login_is_linkable()` — carries
  `# branch-scope: intentional`, because a login already claimed by a staff
  record in another branch is still claimed. Branch-filtering here would allow
  the same login to be claimed once per branch, which is the hole being closed.

The `/me` routes reach the database through the pre-existing `_staff_query()`
helper and add no new call site. No hit was migrated or altered.

## e. Hands-on verification — PARTIALLY DONE, and honestly so

The dev server runs against the **live production backend** (`setupProxy.js`),
and the browser session on this machine is signed in as the school owner's real
account. Confirmed read-only: the app builds, starts, and renders with these
changes.

**Not done, and deliberately not attempted:**
1. Saving a profile change end-to-end. That is a write to the live database,
   which this run is not authorised to make.
2. The phone-width pass on the profile dialog. Chrome would not shrink the
   window below roughly 1400 CSS px on this machine, so the check could not be
   made honestly at 390px.

Both are on `HUMAN-VERIFICATION-CHECKLIST.md` for Abhimanyu, marked as not
verified by this run rather than quietly assumed.

## Live data

No writes to the production database at any point. Tests ran with `MONGO_URL`
pinned to a local test database throughout (D-04).
