# R3-0 is retired, and the twenty questions it raised are kept

**Decided by Abhimanyu, 2026-08-14.** R3-0 moves from PARKED to RETIRED. It will not be
built. **The twenty questions it exposed are kept and are listed below**, because they are
about the platform, not about R3-0, and most of them need answering anyway.

---

## The decision, in his words

Credentials are only handed to somebody once their profile is ready. If that holds, a lock
that refuses a not-yet-ready profile never fires, because nobody in that state ever has a
password to sign in with.

**That reasoning is sound and it is the deciding factor.** R3-0 was written to make a
credential handover safe. If the handover is already sequenced behind the profile being
finished, the lock is a second belt on the same trousers.

## What is being given up, stated plainly rather than buried

R3-0 was not only about credentials. It was also the one place where **the word "dormant"
would have meant something at runtime.** Today it means nothing: nothing in the running
code reads the `status` field, so a profile marked dormant is hidden from the menus and
starved of Flo tools and nothing more. If somebody ever does sign in on one of those
accounts, they reach real screens and can make real writes.

Two things stand between that and harm, and neither is code:

1. **Nobody has a password.** Seven office logins exist in the live database from
   migration 041 on 12 August, and their one-time passwords went to a handover file
   outside this repository. Abhimanyu confirmed on 14 August that they were never
   distributed.
2. **The process rule just set:** a credential goes out only when the profile is ready.

**The risk that remains is a handover mistake at the school, not a bug.** If one of those
seven one-time passwords is ever passed on before that profile is built, the person gets a
half-open platform, and for four of the seven that means the accountant head's or the
management head's full access, every teacher's salary included.

**That is a real risk and it is now accepted rather than closed.** It is written here so
that nobody later reads "R3-0 retired" and assumes the problem it named went away. It did
not; the control moved from the code to the process.

**A cheap partial answer, if the risk ever feels too large:** rather than rebuilding R3-0,
change those seven passwords to something nobody holds. That removes the same risk without
touching a single permission gate, and it is minutes of work. Not done, because nobody
asked for it.

## One thing this UNBLOCKS

**R3-4, handing Chaman his password, is no longer blocked.** It was blocked only because
R3-0 was parked and R3-0 was the thing that made a handover safe. With the process rule in
its place, R3-4 waits on Chaman's profile being built (R3-2) and nothing else.

---

## The twenty questions, kept

These were produced by running the R3-0 change against the current suite on 2026-08-14.
Every one of them is a test asserting that a **dormant** profile CAN do something. The R3-0
change made them fail, which is what raised the question in the first place.

**The question each one asks is the same, and it does not need R3-0 to be worth answering:**

> Is this a real, working ability that somebody at the school relies on today? Or is it
> coverage for a feature that was built for a profile whose release has not happened, and
> which nobody is using?

They are worth answering because they are the map of **what each dormant profile can
actually do right now**, which is exactly what R3-2, R3-3 and Release 4 (access) each need
before they can grant anything on purpose.

### Transport head, 11 tests

`tests/backend/unit/test_transport_optimisation.py`

- `test_geocode_503_when_no_api_key`
- `test_geocode_returns_coordinates`
- `test_geocode_502_on_geocoding_failure`
- `test_geocode_422_on_empty_address`
- `test_geocode_422_on_missing_address_field`
- `test_suggest_route_422_when_student_has_no_coordinates`
- `test_suggest_route_happy_path`
- `test_set_student_coordinates_success`
- `test_set_zone_centroid_success`
- `test_suggest_route_404_when_student_not_found`
- `test_suggest_route_does_not_return_other_school_zones`

**Directly relevant to R3-2.** These prove the transport head can already geocode
addresses, suggest routes and move a child's pin on the map. Chaman's profile grants him
transport on purpose, so the answer here is almost certainly "keep the ability, it is
his". Confirm rather than assume, then this list becomes the starting point for what R3-2
grants rather than a set of failures to fix.

### Front desk, 3 tests

- `tests/backend/unit/test_receptionist_p11.py::test_receptionist_sees_all_school_queries`
- `tests/backend/unit/test_receptionist_p11.py::test_complaint_stores_on_behalf_of_phone`
- `tests/backend/api/test_ui_sweep_epic4_tool_endpoint.py::test_sub_category_is_honoured_like_the_chat_path`

**Relevant to Release 4 (access).** The front desk can see every support ticket in the
school and log a complaint on a parent's behalf. Both are plainly front-desk work, so the
question is when she is switched on, not whether she should have them.

### Maintenance, 2 tests

- `tests/backend/unit/test_maintenance_p12.py::test_it_tech_can_view_tech_issues`
- `tests/backend/api/test_campus_operations.py::test_procurement_receipt_updates_inventory_once`

**The procurement one deserves a proper look.** It proves a maintenance account can raise a
purchase requisition and receive stock against it. Release 4 (access) says maintenance may
add contractors while touching no money, and a requisition carries an estimated unit cost.
**So this test may be showing an ability that the agreed design does not want.** It is the
one on this list most likely to be a genuine narrowing rather than a wait.

### IT, 1 test

- `tests/backend/unit/test_maintenance_p12.py::test_it_tech_can_view_tech_issues` (above)

Note the hard stop already recorded: **no IT login at all while that role is held by a
Vedmarg employee.** So whatever this test proves, nobody is exercising it.

### Mixed, 3 tests

- `tests/backend/api/test_phase3_capabilities.py::TestIssueNamespaces::test_maintenance_and_it_namespaces_are_isolated`
- `tests/backend/api/test_phase3_capabilities.py::TestIssueNamespaces::test_owner_confirmation_closes_facility_request_and_notifies_submitter`
- `tests/backend/api/test_phase3_capabilities.py::TestTransportAndSubstitutions::test_transport_aliases_and_transport_head_student_assignment_scope`
- `tests/backend/unit/test_require_access.py::test_require_access_tuple_sub_category`

The last one is different from the rest and worth flagging: it is a test **of the
permission helper itself**, using the front desk as its example. It is not a statement
about what the front desk may do, so if this list is ever worked through, that one is a
one-line change of example and not a decision.

---

## Two notes for whoever picks this up

**A twenty-first test failed, and it is mine and deliberate.**
`test_r3_1a_narrowed_gates::test_transport_still_reaches_the_dormant_desks_because_r3_0_is_parked`
records, on purpose, that the dormant desks can still reach transport. With R3-0 retired
rather than parked, **that test's comment is now wrong**: it says the gap closes when R3-0
lands, and R3-0 is not going to land. It is corrected in the same commit as this file.

**Do not resolve any of the twenty by making a red test green.** That rule was written when
R3-0 was parked and it still holds. Making a test pass is not the same as deciding what a
person may do, and this is a live school platform.

**The R3-0 branch is not deleted.** `r3-0-dormant-lock` at `033ef40` stays, pushed, so the
work and its reasoning are recoverable if the decision is ever revisited.
