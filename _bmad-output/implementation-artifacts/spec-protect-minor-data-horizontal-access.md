---
title: 'Protect minor data from horizontal access'
type: 'bugfix'
created: '2026-08-05'
status: 'done'
baseline_commit: 'f82f685c244504d053baa383b77586d1410ea111'
context:
  - '{project-root}/_bmad-output/project-context.md'
  - '{project-root}/_bmad-output/planning-artifacts/research/technical-eduflow-vs-erpnext-and-frappe-education-research-2026-08-05.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Four read paths expose a minor's record to a caller who has the correct broad role but no relationship to that student: global teacher search, teacher direct-student lookup, student guardian lookup, and student fee-discount lookup. The surrounding comments and scoped list endpoints promise narrower access, so these are authorization defects rather than product-policy choices.

**Approach:** Reuse the canonical teacher-scope service and student-to-user relationship checks at each endpoint. Return the existing 403 `Forbidden` contract for a named out-of-scope record and exclude out-of-scope students from search results.

## Boundaries & Constraints

**Always:** Keep owner/admin behavior unchanged; derive teacher classes from `compute_teacher_scope`; derive a student's own record from authenticated `user_id`; preserve school scoping and existing response shapes; add unauthenticated and horizontal-access regression tests; never disclose whether an inaccessible guardian/discount record exists beyond the route's existing semantics.

**Ask First:** Any proposal to add a parent role, change teacher assignment rules, or alter current owner/admin permissions.

**Never:** Change branding/theme, mutate live data, add a branch, add hostel features, trust a caller-supplied user/student relationship, or solve authorization only in the frontend.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Teacher search | Teacher assigned class A searches a student in class B | Student B is absent from results | Successful empty/filtered result |
| Teacher direct read | Teacher assigned class A requests student B | No student data returned | 403 `Forbidden` |
| Student guardian read | Student A requests Student B guardians | No guardian data returned | 403 `Forbidden` |
| Student discount read | Student A requests Student B discount breakdown | No financial data returned | 403 `Forbidden` |
| Authorized paths | Teacher reads assigned student; student reads own guardians/discount | Existing response shape and data remain | N/A |

</frozen-after-approval>

## Code Map

- `backend/routes/search.py` -- global person search; contains the explicit unimplemented teacher-scope placeholder.
- `backend/routes/students.py` -- direct student and guardian read authorization.
- `backend/routes/fees.py` -- student discount breakdown authorization.
- `backend/services/teacher_scope_service.py` -- canonical class scope resolver.
- `tests/backend/api/test_minor_data_horizontal_access.py` -- focused regression coverage using existing API test conventions.

## Tasks & Acceptance

**Execution:**
- [x] `backend/routes/search.py` -- restrict teacher person search to `compute_teacher_scope(...)["all_class_ids"]`; an empty assignment must fail closed.
- [x] `backend/routes/students.py` -- enforce teacher class scope on direct lookup and student ownership on guardian reads.
- [x] `backend/routes/fees.py` -- enforce student ownership before returning a requested student's discounts.
- [x] `tests/backend/api/test_minor_data_horizontal_access.py` -- prove all four denials plus their authorized counterparts.

**Acceptance Criteria:**
- Given any broad-role caller without an entity relationship, when they request a named minor record, then the backend returns no protected data.
- Given a teacher with no assigned classes, when they use person search, then zero students are exposed.
- Given existing owner/admin paths, when the same endpoints are used, then their behavior and response shapes do not change.
- Given an unauthenticated caller, when each protected route is called, then it returns 401.

## Spec Change Log

## Verification

**Commands:**
- `python -m pytest tests/backend/api/test_minor_data_horizontal_access.py -q` -- expected: all focused authorization tests pass.
- `python -m pytest tests/backend/api/test_security_roles.py tests/backend/test_unauthenticated_surface.py -q` -- expected: no security regression.

**Results:**
- Focused horizontal-access suite: 9 passed.
- Existing student and fee-discount API suites: 18 passed.
- Modified Python modules compile successfully.

## Suggested Review Order

**Authorization boundaries**

- Fail-closed teacher search now derives classes from Academic Structure.
  [`search.py:121`](../../backend/routes/search.py#L121)

- Direct student reads now enforce the same teacher scope as list views.
  [`students.py:458`](../../backend/routes/students.py#L458)

- Student guardian reads verify the authenticated student relationship.
  [`students.py:589`](../../backend/routes/students.py#L589)

- Student discount reads verify ownership before financial aggregation.
  [`fees.py:696`](../../backend/routes/fees.py#L696)

**Regression proof**

- Nine tests cover allowed, denied, empty-scope and unauthenticated paths.
  [`test_minor_data_horizontal_access.py:45`](../../tests/backend/api/test_minor_data_horizontal_access.py#L45)
