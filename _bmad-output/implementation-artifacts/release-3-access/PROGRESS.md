# Release 3 (access) - PROGRESS

**This file is the only record of what is done. Read it first, update it last, every run.**

The work itself is in
`_bmad-output/planning-artifacts/release-3-access-department-heads-2026-08-14.md`.

**This is the ACCESS ladder step 3, department heads.** It is NOT the table and download
work that shipped under the name "Release 3" on 12 August. Two numbering schemes collided;
see `_bmad-output/planning-artifacts/release-numbering-collision-2026-08-14.md`.

Starting point: `main` at `966edeb`, clean. The table release and the audit release are
both live.

---

## Status

| Part | What it is | State |
|---|---|---|
| R3-0 | Make dormant mean something, at the door | **RETIRED by Abhimanyu's decision, 2026-08-14. Will not be built.** A credential goes out only once the profile is ready, so the lock never fires. The 20 questions it raised are KEPT, named test by test, in `R3-0-retired-and-the-twenty-questions-2026-08-14.md`. Branch `r3-0-dormant-lock` (`033ef40`) stays, not deleted. |
| R3-M | The staff room holds only profiles whose release has landed | **LIVE 2026-08-14** |
| R3-1 | Close the gap between the matrix and the REST API | **Survey DONE 2026-08-14, read only, nothing changed. `R3-1-survey-2026-08-14.md`. The fixing half is not started and needs a decision on order first.** |
| R3-2 | Chaman's profile built properly | **BUILT and green 2026-08-15, NOT DEPLOYED.** Note the title used to read "no money anywhere" and that is now WRONG: Abhimanyu decided on 2026-08-15 that he holds transport money in full. See the log entry at the foot of this file. |
| R3-3 | The tenth profile: drivers and conductors, defined only | **DONE 2026-08-15**, defined only, no screens and no logins. Built alongside R3-2 because the transport head could not otherwise record his own team truthfully. |
| R3-4 | Switch Chaman on and watch him sign in | Not started. **Now waits on the APPROVALS workflow** (`planning-artifacts/approvals-one-workflow-2026-08-15.md`), by Abhimanyu's decision of 2026-08-15: his credentials are not going out for at least two days, and there is nowhere for Aman or Adesh to answer the requests he can raise. **No longer blocked by R3-0** - it was blocked only by R3-0 being parked, and R3-0 is retired. Waits on R3-2 now. |

R3-2 and R3-3 are built and green as of 2026-08-15 and are NOT deployed. No live school
data has been read or changed by this release.

---

## What is already true before a line is written

- **The permission thinking is DONE**, in `profile_matrix.py` and in Abhimanyu's twelve
  answers of 2026-08-11. This release builds the grants that were deliberately held back.
- **The seven office logins already exist in the live database**, created by migration 041
  on 2026-08-12. None has ever been used: all carry `must_change_password` and the
  one-time passwords were never handed out (decision 15).
- **"Dormant" is documentation, not a lock.** Proven, not assumed: a probe against the
  running application showed all three dormant office profiles can `POST /api/transport`
  and read the full student and staff lists. Money is properly refused everywhere tested.
  Full results in Part 2 of the plan.

---

## Log

### 2026-08-14 - plan written

**Did.** Recovered the access ladder from the 2026-08-09 session transcript and found it
had also been sitting in the Release 2 plan since 10 August. Established that the ladder
stopped after step 2 while two unrelated pieces of work took the numbers 3 and 4.

**Decided today (15 to 18).** Passwords were never handed out; assistants get their own
profiles with the specifics still to come from the school; **messaging stops at teachers
and students never get it**, which closes the question that had blocked Release 5 since
10 August; and Release 3 plus as much of Release 4 as possible should land before Sonu's
and Lalit's credentials go out, with doubts left open rather than guessed.

**Found by probing rather than reading.** `profile_matrix` governs menus, Flo tools and
exports. It does **not** gate the REST API, which uses hand-written checks;
`require_role("owner", "admin")` ignores the sub-category, so every office desk passes it.
A support staff account can create a school bus route. What holds the line today is that
nobody has a password, and nothing else.

**Left.** R3-0 is next and should precede any credential handover. R3-1 is a read-only
survey and changes nothing.

### 2026-08-14 (later) - the staff room now holds only the four whose release has landed

**Why.** Abhimanyu saw office staff in the colleague list who cannot sign in. Logins exist
for people whose release has not happened: the seven office accounts from migration 041
and four shared desks. Every one of them was offered as somebody to message. **A colleague
you can see and write to but who can never answer reads as being ignored**, which is worse
than their simply not being there.

**The rule he set:** a profile appears in the staff room when its release lands. Not
before, not after.

**How it is done, and why not a list of names.** `_release_has_landed` in
`routes/messaging.py` asks the permission table the question it already answers: is this
profile marked `live`? So nobody maintains a second list, and **switching a profile on for
its release lights it up in the staff room the same day, with no code change**. There is a
test that proves exactly that, by marking the transport head live and watching him appear.

`STAFF_ROLES` stays underneath as the floor. Both filters apply, so a mistake in the matrix
still cannot put a child in the staff room.

**Teachers are out too, and that is deliberate.** They are step 5 of the ladder. The four
tests written on 12 August that proved a teacher can use messaging were NOT deleted: they
now run with the teacher profile switched on, so they still prove the feature works and
they will pass unchanged when Release 5 lands. Only the date of the answer moved.

**Hiding is not refusing.** A second test proves that a dormant colleague cannot be reached
by typing their id either, not merely that they are absent from the list.

**The button follows the list.** `MessagingContext.js` drew the messaging button from role
alone, so without this the excluded profiles would have opened an empty staff room, which
looks broken rather than not-yet-theirs. It now reads the same `status` field through a new
`releaseHasLanded` helper in the generated mirror, so the button and the list cannot drift.

**Gates:** backend 3,611 passed / 0 failed / 15 deselected. Frontend 777 passed / 0 failed.
Production build clean including lint. **Not deployed.**

### 2026-08-14 (later still) - the teacher question, closed

Abhimanyu confirmed that admin staff and teachers are **counted together**, meaning
governed by the same rule, and asked directly whether that also merged their two steps of
the ladder. It does not. **Steps 4 and 5 stay separate** (decision 20). Both stay out of
the staff room and the menus until their own step lands.

No code change. The behaviour shipped earlier today was already correct under either
reading; only the roadmap was in question, and it is unchanged.

### 2026-08-14 (evening) - the staff room change is LIVE, and R3-0 is parked

**Deployed.** Backend `eduflow-msgrelease-20260814-2619d16`, environment Ready and Green.
Frontend Amplify job 148 SUCCEED. `main` is at `2619d16`, pushed.
Rollback target: `eduflow-release4-20260813-fec72a7`.

Verified against the running system rather than the status page: `/api/health/ready`
answers 200, `/api/messaging/contacts` and `/api/audit-log/retention/plan` answer 401.
The bundle's file list was diffed against the last good deploy first: zero differences.

**R3-0 is built and is NOT on main.** It is on branch `r3-0-dormant-lock`, commit `033ef40`,
pushed. The change itself works and its own 35 tests pass. It turns **20 existing tests
red**, and those failures are a question rather than a chore, so it was parked instead of
being forced through.

The 20, by file:

| File | Count |
|---|---|
| `tests/backend/unit/test_transport_optimisation.py` | 11 |
| `tests/backend/api/test_phase3_capabilities.py` | 3 |
| `tests/backend/unit/test_receptionist_p11.py` | 2 |
| `tests/backend/api/test_campus_operations.py` | 1 |
| `tests/backend/api/test_ui_sweep_epic4_tool_endpoint.py` | 1 |
| `tests/backend/unit/test_maintenance_p12.py` | 1 |
| `tests/backend/unit/test_require_access.py` | 1 |

Every one of them asserts that the receptionist, IT, maintenance or transport head **CAN**
do something. Each needs the same judgement made individually:

- **Is it asserting behaviour that should now wait for that profile's release?** Then run it
  with the profile switched on, exactly as the four teacher messaging tests were handled in
  the staff room change. The coverage is kept and the test will pass unchanged when the
  release lands.
- **Or did that profile genuinely have working access somebody relies on?** Then R3-0 is too
  wide and the gate needs narrowing, not the test.

**Do not resolve these by making the suite green.** Making a red test pass is not the same
as deciding what a person may do, and this is a permission change on a live school platform.

### 2026-08-14 (evening) - R3-0 parked by instruction; next is R3-1

Abhimanyu asked for R3-0 to be paused regardless of what the handoff says. **That is an
instruction, not a failure.** The branch stands as built and the 20 red tests stay an open
question, listed above, for whoever resumes it.

**The consequence, so nobody has to derive it: no new credential may be handed out.** R3-0
was the thing that made a handover safe. Sonu and Lalit are the exception the plan already
allows, since their profiles were built and proven in Release 2 and are live. Chaman (R3-4)
and the four office accounts whose profiles the school has not defined must wait.

**Everything else in this release is safe to do with R3-0 parked**, because none of it
hands anybody a password:

- **R3-1**, the survey. Read-only. This is next.
- **R3-2**, Chaman's profile. Better after R3-1, which tells you which gates it touches.
- **R3-3**, drivers and conductors, defined only. Fully independent.
- **R3-4**, the handover. **BLOCKED while R3-0 is parked.** This is the one that must wait.

Release 4 (access), the whole admin staff, is also unaffected. Its two blockers are the
school's answers, not R3-0.

**Unrelated work closed the same evening**, recorded here only so a cold reader is not left
wondering: all four Release 4 leftovers are done. Ticket email works through Zoho and was
seen in a real inbox, the dead Resend sender is removed and deployed, `stat.layaa.ai` is
live, and rotating `CRON_SECRET` is dropped by decision. Detail lives in
`implementation-artifacts/release-4/PROGRESS.md`, not here.

### 2026-08-14 (evening) - R3-1, the survey. Read only, nothing changed

**Result: `R3-1-survey-2026-08-14.md`, with the raw probe evidence beside it.**

**How big the gap is.** The backend has **484 route handlers**. **153** are gated by role
alone in a way that lets every office desk through; **101** use the narrowest form R3-1 was
asked about. 100 of those were called eight times each, once as every office desk, against
the same authorisation code production runs. **63 let all eight through, 41 of them writes,
and 62 of the 63 are wrong against the table.** One is fine after all, because the service
underneath it refuses. Nothing was widened, nothing was changed, nothing was deployed, and
no live school data was touched.

**Three that matter most.**

1. **Transport, thirteen routes.** The only case found where the table says an explicit NO
   and the server says yes: decision 2 of 10 August named five transport tools and DENIED
   them to the management head, and he passes all thirteen routes anyway.
2. **`POST /api/settings/year-end-transition` and `GET /api/settings/branches`** are
   owner-only in the table and open to every desk, support staff included.
3. **`POST /api/ops/certificates` answered 200 for all eight desks**, proven with a real
   request body. Its sibling ID card route IS correctly narrowed and carries a comment
   saying exactly why. Somebody saw this problem, fixed one route and left the one beside
   it, which is the whole argument for a shared check rather than more hand-edits.

**The structural finding.** About a dozen separate hand-written lists of desk names sit
across the route files. None reads `profile_matrix.py`, none knows about the others, and
none moves when the table moves. It is Release 2's "permission by subtraction" one layer
down. One symptom worth keeping: four library routes are narrowed to
`{"principal", "librarian"}` and **there is no such thing as a librarian on this platform**,
so the word does nothing and a reader would believe otherwise.

**Deliberately NOT done: narrowing 62 gates by hand.** That would leave the thirteenth
list of names in the codebase instead of removing the habit, and sixty-two hand-edits to
permissions on a live school platform is how an access accident happens. The suggested
order is in the survey: the three headline items first, then one shared way of asking the
table, then the rest screen by screen. **That order is a recommendation awaiting
Abhimanyu's decision, not a plan already agreed.**

**A limit of this survey, stated so nobody over-reads it.** It proves who gets past the
door, not what is in the room. A read route that answered 200 against the empty stand-in
database may still filter what it returns on the live system. The places where that matters
are called out in the survey.

**Also unmeasured:** `GET /api/attendance/stream` carries the same gate and was skipped
because it is a live stream that never returns. And a second tier of **52 routes** with a
wider gate was counted but not probed desk by desk; two in it deserve a direct look, the
per-child fee status and discount lookups, and the student attendance bulk write.

**No code changed, so the test suite is untouched.** The two probe files were temporary and
were deleted; only their results were kept, as JSON, beside the survey.

### 2026-08-14 (evening) - Sonu and Lalit now hold passwords, so part of the survey became urgent

Abhimanyu handed out their credentials. Nothing in the survey changed; what changed is that
two of the eight office desks stopped being theoretical.

**Their profiles need NO change. The table describing them is correct.** The server does
not read it, which is a different problem and the one to fix.

**Two corrections to the survey, made by reading rather than assuming, and the false alarm
matters more than the finding.** `GET /api/fees/status/{student_id}` and
`GET /api/fees/discounts/{student_id}` are **fine**: both narrow inside the handler, fee
status returns a paid-or-unpaid flag with no amount to the management head exactly as
decision 1 asks, and every dormant desk is refused. The survey had flagged them as needing
a look; the look was done and somebody had already built them properly.
`POST /api/attendance/student/bulk` IS genuinely open to every admin desk, confirmed.

**Confirmed and worse than first written: `GET /api/sms/logs` hands the management head fee
amounts.** The stored reminder row carries an `amount` field and the full message text, and
the route returns the rows unfiltered to every admin desk. That is a direct breach of
decision 1, live today.

**Also confirmed fine: the certificate route.** Lalit and Sonu pass its gate, but the
approval rule lives in the service, so what they create is marked waiting for approval
exactly as R2-9 intended. Only the owner and the principal issue outright.

**Proposed next, awaiting Abhimanyu's decision: R3-1a.** Five items, about seventeen
routes, every one a narrowing, chosen as the only ones both wrong AND reachable by somebody
who now has a password: the SMS log, transport off the management head, the year-end
transition back to the owner, the two attendance writes off the accountant head, and the
branch records back to the owner. Detail and harm ranking in the survey.

**Carried from R3-0, because it will apply again:** narrowing these may turn existing tests
red. If it does, do not make them green to make the suite green. Decide what the person may
do first.

### 2026-08-14 (evening) - R3-1a BUILT and green. Five gates narrowed, nothing widened

Abhimanyu approved the five on 2026-08-14, with one change to item 4: **marking a register
stays with Aman, Adesh, Sonu AND Lalit.** So item 4 closes the five dormant desks out and
keeps all four of the people who hold or will hold credentials, including the accountant
head, whom the table otherwise holds to attendance read-only. That widening is now written
down in `require_attendance_marker` as a decision of the school's, not a route disagreeing
with the table.

| # | What | Where |
|---|---|---|
| 1 | The message log stops handing the management head fee amounts | `routes/sms.py`, `GET /api/sms/logs` now `require_owner_accountant_or_principal` |
| 2 | Transport refused to the management head | `routes/operations.py`, new `require_transport_access` on all 13 routes |
| 3 | Year-end promotion back to the school's owner alone | `routes/settings.py` |
| 4 | Marking a register: owner, principal, accountant head, management head (plus teachers on the student register only) | new `require_attendance_marker` in `middleware/auth.py`, both bulk routes |
| 5 | Branch records back to the school's owner alone | `routes/settings.py` |

**Every change is a narrowing. Nobody gained anything.** `profile_matrix.py` was not
touched, so the generated mirror is unchanged and the pinned reach counts cannot have moved.

**Two decisions inside the work worth knowing.**

**The transport fix reads the refusal off the table rather than naming a profile.**
Decision 2 denied five transport tools to the management head in `profile_matrix.py` and
the routes never asked. They ask now, so when transport moves to the transport head the
routes follow with no code change. There is a test that proves exactly that, by clearing
the denial and watching the route open.

**It deliberately does NOT close the five dormant desks out of transport.** They can still
reach those routes, which is wrong, and R3-0 is the change that closes it. R3-0 is parked,
and eleven of its twenty red tests are transport tests. Closing them here would have
settled that parked question as a side effect of an unrelated fix. There is a test that
records the gap on purpose, with a comment saying to delete it when R3-0 lands.

**The message log was narrowed rather than filtered.** The only screen that reads it is
Smart Fee Defaulter, which the table gives to the accountant head and not to the management
head, so he could never reach it through the platform and loses nothing he was using.
Filtering rows instead would have left a route that half-answers a screen he cannot open.

**Checked so no dead button appears:** the management head's menu never offered a transport
screen, and no frontend file calls the branch-records route at all. Nobody sees a control
that now refuses.

**Gate: backend 3,680 passed / 0 failed / 15 deselected.** No frontend change, so the
frontend suites were not run.

**Nothing turned red.** Unlike R3-0, these five broke no existing test, which is the
clearest sign that they are narrowings the codebase already believed in.

**NOT DEPLOYED.** Waiting on Abhimanyu. This matters more than usual: Sonu and Lalit already
hold their passwords, so until this ships the fee-amount leak in item 1 is live.

### 2026-08-14 (evening) - three sidebar changes Abhimanyu asked for

**1. The "More" tab is gone, and Staff Tracker moved into People & Attendance.** It was the
only entry in that tab, and a whole tab holding one screen reads as a leftovers drawer.

**The fallback that CREATES a "More" tab stays in the code, deliberately.** Deleting it
would mean the next tool with no hub silently vanishes from the menu, and a menu that
quietly loses an entry is indistinguishable from access being taken away. The tab is gone
because the screen now has a home, not because the net was cut. A new test,
`OneLayoutForEveryProfile::no leftovers tab`, fails on any profile that produces a leftover,
so the next unplaced tool is caught while somebody is writing it.

**An existing test caught a real mistake, and it was right.** The first attempt added Staff
Tracker to the hub's `items` list, which also paints a tile on the People & Attendance
landing page. `ManagementHubs::the merged directory is the only front door to student and
staff records` went red, because that is the exact duplication the school's owner asked to
be removed on 2026-08-07 ("let's just have a single place... rather than 3 places"). The
fix was to place it in the tab map instead, which decides sidebar placement only and is not
read by the landing pages. **The test was not touched.**

`HUB_FOR_CLASSROOM_TOOL` was renamed to `HUB_TAB_FOR_TOOL`: it is no longer classroom-only,
and the distinction it actually draws is "tab placement without a landing-page tile".

**2 and 3. Recent Chats now starts closed and Tools starts open, for every profile.** Both
used to start open, so the two sections split the sidebar and the tool list opened already
scrolled, with the tabs a person came for pushed below the fold. There is no per-person
memory of the setting, on purpose: the same profile opens the same way on every device, and
either section is one click away. Pinned by `SidebarSectionDefaults.test.js`, which renders
the real sidebar and reads the headings rather than checking a variable's starting value.

**Nothing here grants anybody anything.** Tab placement is decided after each profile's own
tool list is resolved, so a layout change cannot widen the permission table.

**Gate: frontend 792 passed / 0 failed, production build clean including lint.** No backend
change. **Not deployed.**

### 2026-08-14 (evening) - R3-1a and the sidebar changes are LIVE

**Deployed on Abhimanyu's go-ahead.** Backend `eduflow-r31a-20260814-d571571`, environment
Ready and Green. Frontend Amplify job **151 SUCCEED** on the same commit. `main` is at
`d571571`, pushed.

**Rollback target: `eduflow-msgrelease-20260814-2619d16`.**

**The bundle was checked before it was uploaded**, as the rule requires: the file list was
compared against the last good deploy and came back **identical, 240 entries either way**.
Nothing was dropped and no stray file was swept in.

**Verified against the running system, not the status page.** `/api/health/ready` answers
200, and all five narrowed routes answer 401: `/api/sms/logs`, `/api/ops/transport`,
`/api/settings/branches`, `POST /api/settings/year-end-transition` and
`POST /api/attendance/staff/bulk`. A 401 proves the new code is live and still guarded; a
404 would have meant it never shipped.

**What that verification does NOT prove, said plainly.** It proves the routes are live and
refuse a stranger. It does **not** prove on the live system that the management head is now
refused transport, or that he is refused the message log, because proving that needs a
signed token for a real profile and the signing secret is not something to go and fetch or
write down. **The narrowings themselves are proven by tests, not by a live probe.** If
somebody wants a live proof, ask Abhimanyu to sign in as Lalit and open Transport.

**The money leak is closed as of this deploy.** Until now the management head could read
every fee reminder ever sent, with the amount and the child's name, and he has held a
password since earlier today.

### 2026-08-14 (evening) - R3-0 is RETIRED, not parked. The twenty questions are kept

**Abhimanyu's decision.** Credentials go out only once a profile is ready, so a lock that
refuses a not-ready profile never fires. That reasoning is sound and it is the deciding
factor. R3-0 will not be built. Full record, including the exact twenty tests and what each
one asks:
`R3-0-retired-and-the-twenty-questions-2026-08-14.md`.

**The twenty were enumerated properly rather than left as a count in a table.** The R3-0
change was applied to today's `main` in the working tree, the whole suite was run, the exact
failures were captured, and the working tree was reverted. **21 failed, and the twenty-first
is our own deliberate marker test.** By profile: transport head 11, front desk 3,
maintenance 2, IT 1, mixed 3, plus one that is really a test of the permission helper using
the front desk as an example and is a one-line change rather than a decision.

**Two of them are worth real attention rather than a rubber stamp.** The transport eleven
are the map of what Chaman can already do and should be the starting point for R3-2 rather
than a set of failures. The procurement one shows a maintenance account raising a purchase
requisition carrying an estimated cost, and Release 4 (access) says maintenance touches no
money, so **that one may be a genuine narrowing rather than a wait.**

**What is being accepted, written down rather than buried.** "Dormant" still means nothing
at runtime. The seven office logins in the live database from migration 041 still reach real
screens if anybody ever signs in. **The remaining risk is a handover mistake at the school,
not a bug**, and the control has moved from the code to the process. If that ever feels too
large, the cheap answer is to change those seven passwords to something nobody holds, which
removes the same risk without touching a permission gate. Not done; nobody asked.

**R3-4 is UNBLOCKED by this.** It was blocked only because R3-0 was parked. It now waits on
R3-2 and nothing else.

**One test corrected in the same commit.**
`test_r3_1a_narrowed_gates::test_transport_still_reaches_the_dormant_desks` said the gap
closes when R3-0 lands. That is no longer true, so it now records an ACCEPTED gap and names
who deletes it. A comment that quietly stops being true is how a decision gets lost.

### 2026-08-14 (evening) - session log: what shipped after R3-1a

Recorded here so the whole evening is in one place. Three pieces of work, all LIVE.

**1. R3-1a, five permission narrowings.** Backend `eduflow-r31a-20260814-d571571`.
Detail earlier in this file.

**2. Sidebar: the More tab retired, and the sections open differently.** Staff Tracker moved
into People & Attendance; Recent Chats now starts closed and Tools open, for every profile.
Detail earlier in this file. Shipped in the same deploy as R3-1a and Amplify job 151.

**3. Campus retail removed, and the screen renamed.** Backend
`eduflow-noshop-20260814-484135d`, frontend Amplify job 155, `main` at `484135d`.
Rollback target `eduflow-r31a-20260814-d571571`. Full record:
`implementation-artifacts/fit-to-the-school/campus-retail-removed-2026-08-14.md`.

**4. R3-0 retired rather than parked.** Detail earlier in this file.

**Nothing in the access ladder itself moved tonight.** R3-2 (Chaman), R3-3 (drivers and
conductors) and R3-4 (his handover) are all still not started, and R3-4 is no longer blocked
now that R3-0 is retired.

### 2026-08-14 (evening) - admissions was surveyed, read only, nothing changed

Abhimanyu asked how the admission funnel works today and whether there is a proper workflow
from a family's enquiry through to enrolment. Read from the code; nothing changed, no live
data read. Full record:
`implementation-artifacts/admissions-how-it-actually-works-2026-08-14.md`.

**The answer is no, not end to end.** Two well-built halves with nothing joining them.

- **The enquiry pipeline** (8 stages, new through enrolled, with a timeline per family)
  works properly.
- **The application lifecycle** (8 statuses, draft through enrolled, with a real state
  machine, an assessment, a dated offer, and student creation in one transaction) works
  properly and carefully.
- **There is no way on ANY screen to turn an enquiry into an application.** The server
  supports it and refuses duplicates; the form on screen has no field for it. That is the
  single break in the chain.

**The finding that matters most: an enquiry can reach "enrolled" without any child being
created.** `fee_paid` to `enrolled` is an ordinary stage move, nothing requires an
application, and the enquiry service never creates a student. So the funnel can show a child
as enrolled while the school has no record of them, and nobody looking can tell that apart
from a real enrolment. **Same shape as the fault Release 4 was written to close.**

Also found: three screens show the same enquiries under three names, the application
workflow has no menu entry of its own (it is a panel at the bottom of two other screens),
and the two tracks use different words for one journey.

**Nothing was fixed.** Four suggestions are in the artifact, smallest first; adding a "start
an application" button to the enquiry screen is the one that turns two halves into a whole.

### 2026-08-15 - R3-2 and R3-3 BUILT and green. NOT DEPLOYED

**Chaman Singh's profile is built, and the tenth profile (drivers and conductors) is
defined.** Approved by Abhimanyu on 2026-08-15; the six answers are in Part 0 of
`R3-2-proposal-chamans-profile-2026-08-15.md` and they OVERRIDE the proposal beneath them.

**The biggest thing to know, because it reverses what the plan said.** The plan and the
first proposal both said the transport head must see **no money anywhere**. Abhimanyu
changed that: **he holds full financial visibility of school TRANSPORT, fares and who owes
what included, amounts and all.** The boundary is transport money, not "no money". Tuition,
concessions, Right to Education places, salaries and every other rupee stay refused, and
that boundary is pinned by `test_only_the_finance_profiles_reach_a_finance_tool` and by
`test_the_transport_head_holds_exactly_one_money_tool_and_it_is_transport_only`.

**Why that made the work SMALLER, not bigger.** The original proposal was going to have to
strip the fare out of the transport screen, the Add Route form, the Flo answers and the
server. None of that is needed.

**The six decisions, and where each one lives:**

| # | Decision | Where it is enforced |
|---|---|---|
| 1 | Transport money in full; no other money | `profile_matrix` names ONE finance tool, `get_transport_fee_status`, purpose-built so it can only return the four transport fields on a child's record |
| 2 | Children on a bus only, not the whole roll | `services/transport_scope.py`, applied to the QUERY in the student list, the single record, the roster and Flo's search |
| 3 | Deleting needs Aman OR Adesh, either one | `TransportApprovalRequired` plus `PENDING_ACTIONS` in `approvals_service.py` |
| 4 | Drivers and conductors on the roll, NO logins | `staff_service.create_staff` takes a separate path that mints no login |
| 5 | Vehicle repair costs yes, building repairs no; cost agreed before it is charged | new `vehicle` category, `_strip_costs_for`, and `POST /api/issues/facility/{id}/propose-cost` |
| 6 | He moves a child between routes himself | `TRANSPORT_HEAD_FIELDS`, which already existed, plus `transport_stop` |

**Five things a later session will trip over.**

**1. There is a FOURTH shape of profile now, and it is the narrowest.** `NAMED_GRANT` in
`ai_action_policy.py`. The other three are DOMAINS: a profile gets a whole surface and the
matrix names exceptions. That cannot express "transport": finance is wrong for a school
bus, and non_finance is the management head's entire surface. So `extra_tools` becomes the
WHOLE grant and everything else is refused. It is derived from the table rather than from a
list of profile names, so the next department head follows with no change to that file.

**2. A named-grant profile inherits `shared` READS and NEVER inherits a write.** The first
version returned `domain == SHARED` outright and the suite caught what that meant:
`import_data_file` and `create_student` are classified shared, so the transport head could
have rewritten fields across the whole roll from a spreadsheet and put new children on it.
The dormant profiles were only ever safe from that because `may_write` is False for them.
**Do not relax this.** `report_platform_problem` is named in his grant precisely because it
is a shared WRITE and would not arrive on its own.

**3. Narrowing him to children on a bus opened a hole, and the fix is deliberately tiny.**
A child's first day on a bus means finding a child who is NOT on one. New tool
`get_student_to_add_to_a_route`: exact admission number only, returns name, class and
whether they already ride. No address, no guardian's number, no fee, and it refuses to
search by name, because a name search is the narrowing undone a letter at a time.

**4. An approval CARRIES OUT the action it asked for.** `PENDING_ACTIONS` in
`approvals_service.py`. The cheap version, raise a request and leave somebody to go and
delete it by hand, was rejected: it produces a card reading APPROVED over a route that is
still there. The action runs BEFORE the request is marked approved, so a failure leaves it
pending rather than showing approved over something that never happened.

**5. His deletes answer 202, not 200 and not 403.** "Sent for agreement" and "deleted" are
different facts and a screen has to be able to tell them apart. In Flo it comes back as
`success: True, awaiting_approval: True` for the same reason: telling him "you cannot"
would send him off to find somebody by hand when the platform has already asked the right
two people.

**Three faults fixed on the way, none caused by R3-2 and all of them in its path.** Pinned
by `test_r3_2_second_source_of_truth_2026_08_15.py`, 17 tests, every one asserting a
refusal. **None of the three broke a single existing test**, which is the clearest sign
they were defaults that leaked rather than decisions anybody made.

- **`_can_view_all` in `routes/issues.py` treated an admin with NO job title as the
  principal.** It governed the maintenance calendar, the contractor list, the whole issue
  register and the request history. The rest of the platform already denies by default when
  `sub_category` is missing, and migration 016 exists to eliminate that state, so this
  helper was the outlier.
- **`GET /api/issues/facility/{id}` was signed-in-only.** Any account could read any repair
  request by its id, `estimated_cost` and `actual_cost` included, while the list route
  beside it refused the same people. Facility requests are where every repair amount lives.
- **`GET /api/ops/certificates` narrowed students and nobody else**, handing every other
  signed-in account the school's whole certificate list, transfer certificates included.

**Counts that moved, all deliberate and all with a written reason beside them.**

| Profile | Before | After | Why |
|---|---|---|---|
| owner, principal | 164/103 | 166/103 | plus 2 reads: the transport fee tool and the add-to-a-route lookup |
| accountant | 59/30 | 60/30 | plus 1 read, the transport fee tool. Not the lookup: it is non_finance |
| management | 104/63 | 105/63 | plus 1 read, the lookup only. **He does NOT get the transport fee tool** by decision 1: he never sees a rupee figure |
| **transport_head** | **30/0** | **23/8** | The 8 writes are the grant. **The tool count went DOWN**, and that is a narrowing: as a dormant profile he FELL THROUGH to about thirty registry reads nobody had granted him. He is now default-deny |
| the four dormant desks | 30/0 or 29/0 | plus 1 | the lookup, which tells them strictly less than the student lookup they already hold |
| transport_staff | did not exist | 30/0 | what the gate WOULD say. Nobody can exercise any of it: no login, no screens |

Screens: transport head 6 to 8, the servicing calendar and the contractor list. Live
profiles 4 to 5. Total profiles 12 to 13, and dormant stays at 8 by coincidence, one out
and one in, which is exactly why the LISTS are asserted and not just the numbers.

**Gate: backend 3,848 passed / 0 failed / 14 deselected. Frontend 824 passed / 0 failed.
Production build clean including lint.** No live school data was read or changed.

**NOT DEPLOYED. Waiting on Abhimanyu.** Pushing to `main` IS a frontend deploy, so the two
halves have to go out together.

**What is left.**

- **R3-4, creating his account and handing over the password.** The last step, and a
  deliberate act rather than a code change. The Add Staff screen is owner and principal
  only and shows the username and one-time password once.
- **Two questions for Abhimanyu**, neither blocking, both recorded rather than guessed:
  1. **Setting the fare on a CHILD is not his**, only on a route. Seeing what a family is
     charged and deciding it are different acts, and the second is billing. If the school
     wants him to set it per child, that is a decision to take rather than a field to add
     quietly.
  2. **The `vehicle` repair category is new and empty.** Any bus repairs logged before
     today sit under the old categories and he will not see them until somebody re-files
     them. Nothing is lost; his screen simply starts empty.
- **No frontend work was done for him.** The screens he holds already exist and are
  server-gated, so nothing shows him what he may not have. But the new controls, proposing
  a repair cost, removing a vehicle and the "sent for agreement" state, have no buttons yet
  and are reachable through Flo and the API only.

### 2026-08-15 (later) - two screen-side faults found by CHECKING rather than assuming

Both were introduced by R3-2 itself and both were found by going and looking at what the
screens actually do, after the backend was already green. Neither would have been caught
by any test that existed, because the fault was the absence of one.

**1. His home page showed five screens while his sidebar offered eight.**
`ToolDashboard.js` builds the landing page for the office desks from `TOOL_SETS`, a
hand-written list of screen ids that nothing keeps in step with the permission table. His
entry named five. R3-2 granted him the servicing calendar and the contractor list, so the
two menus disagreed the moment the grant landed.

Nothing was over-granted: that list is INTERSECTED with the table, so it can only ever
take away. But a menu that quietly loses an entry is indistinguishable to the person
looking from access being withdrawn, which is the standing "nothing is ever dropped" rule.

He is now resolved through `hubsForUser`, the same question the sidebar asks of the same
table, so the two cannot drift again. **The hand-written set stays for the four profiles
that are still dormant**; each leaves it as its own release lands. Pinned by a new block in
`OneLayoutForEveryProfile.test.js`, which also records the ONE screen deliberately in a
sidebar and on no home page: `staff-tracker`, placed that way because the owner asked on
2026-08-07 for a single directory rather than three.

**2. Pressing Delete on a route did nothing visible, and said nothing.**
The Delete button read `if (res.success) load()`. The new 202 answer carries
`success: true` - because a request correctly recorded IS a success - so the list reloaded,
the route was still sitting there, and the person was told nothing at all.

That is precisely the fault the 202 was introduced to prevent, reappearing one layer up.
The screen now says what happened, and the same notice also covers a REFUSED delete
(children still assigned), which was equally silent before and is not new to R3-2.
Pinned by `TransportDeleteNeedsAgreement.test.js`, which renders the real screen and reads
the words a person would see rather than checking a variable.

**Gate after both: backend 3,848 passed / 0 failed. Frontend 831 passed / 0 failed.
Production build clean including lint.**

**What is still NOT built on screen, stated plainly rather than left to be discovered.**
Three things work through Flo and the API and have no button:

- proposing what a vehicle repair will cost (`POST /api/issues/facility/{id}/propose-cost`)
- removing a vehicle from the register (`DELETE /api/ops/transport/vehicles/{id}`)
- the approval queue does not show that a request CARRIES an action, so Aman and Adesh see
  "Delete the bus route Joya Town" as an ordinary request and approving it does the
  deletion. That works, and it is honest, but the card does not say the deed will be done
  on approval. Worth a line of text before it goes to the school.

Verified by search, not assumed: no file under `frontend/src` calls either of the first two
routes or reads `awaiting_approval` anywhere except the transport screen fixed above.

### 2026-08-15 (later still) - the three things Abhimanyu asked for after the build

**1. The transport head prices a vehicle repair ON THE PLATFORM, not only through Flo.**
A "Propose a cost" control on his own screen. The figure does NOT land on the request: it
sits beside it as `cost_awaiting_approval` and is drawn as "proposed, waiting to be
agreed", never as the cost. Writing it straight on and calling it pending would leave a
number every other screen reads as the real one.

**Two gaps this exposed, both found by going and looking rather than reasoning about it:**

- **The control was first built on the wrong screen.** It went on the facility-queue card,
  which the transport head cannot open - he holds "Report a problem", not the queue. It
  would have shipped unreachable. It is now a shared component, `ProposeRepairCost`, used
  by both, because written twice the two would drift and the half he uses would be the half
  nobody noticed was wrong.
- **He could not log a bus repair at all.** The category list on that screen had no
  `vehicle` option, so every repair he raised would have been filed under something the
  platform does not treat as his, and he would then not have seen its cost. There were also
  TWO copies of that list in one file; it is now one exported constant, so a category added
  to one screen cannot be missing from the other.

**2. Removing a vehicle through Flo, behind the same agreement gate.** New tool
`remove_transport_vehicle`. The gate lives in `transport_service.delete_vehicle`, not in
the tool, which is what stops chat and the screen giving different answers about whether
Aman has to agree. Pinned by three parity tests including one that drives both doors as the
transport head and proves both record a request and neither removes anything.

**The pinned reach counts caught a real leak while this was added.** The new tool is
classified non_finance, which is the management head's entire domain, so it reached him by
default. Decision 2 of 2026-08-10 moved transport OFF him. It is now named in his
`denied_tools` beside the original five. **Any future transport tool belongs there**, or
that denial rots one tool at a time as transport grows.

**3. Approvals are their own thing, separately from ordinary notifications.**

One rule, `frontend/src/lib/notifKinds.js`, read by BOTH the bell dropdown and the All
Notifications screen. They fetch separately and render separately, so classifying
separately would let the bell's count and the screen's rows drift and tell a person two
different things about one inbox.

Three notification kinds ask for a decision, taken from the server rather than guessed:
`approval_submitted`, `certificate_approval_requested`, `profile_change_request`. Everything
that merely LOOKS like an approval by name is an OUTCOME - `approval_decision`,
`certificate_approved` and the rest - and stays in ordinary notifications, because telling
somebody their request was approved is news, not a task. An unknown kind defaults to
ordinary, deliberately: a new type in the wrong list is cosmetic, but a receipt counted as
"waiting on you" makes the number overstate, and a number that overstates gets ignored.

**The bell opens on Approvals when there are any**, because that is the half where somebody
is blocked, and the tabs do not appear at all when there is nothing to decide - a permanent
"Approvals (0)" is an invitation to an empty room. The empty state was also fixed: "You're
all caught up" over an empty approvals tab, with unread messages behind the other one, is
simply untrue.

**And the line Abhimanyu asked for.** An approval request that CARRIES an action now says
so, in ordinary words, in its own box on the card: "Agreeing to this DELETES the bus route
straight away", "Agreeing to this COMMITS the school to that amount". Without it the card
reads like every other request and Aman would press Approve believing he was recording an
opinion. A person has to be able to tell "I agree with this" from "carry this out", and the
platform is the only thing that knows which the button is.

**A finding that matters more than any of the three, and it is NOT fixed.**

**There is no screen anywhere for Aman or Adesh to approve or reject anything.**
`getApprovalRequests` and `decideApprovalRequest` exist in `lib/api.js` and NOTHING calls
them. Verified by search, not assumed. Today the only way to decide an approval is through
Flo or a raw API call.

So the notification now reaches them clearly and leads nowhere. **Until an approvals screen
exists, every deletion the transport head asks for and every repair cost he proposes stays
pending unless somebody decides it in chat.** That is a decision for Abhimanyu: it is a real
build, not a line of text, and it was outside what was asked for today.

**Gate: backend 3,851 passed / 0 failed / 14 deselected. Frontend 855 passed / 0 failed
across 72 suites. Production build clean including lint.**

**One thing recorded rather than dismissed:** a single frontend test failed once during
this session and did not reproduce across five subsequent full runs. It was not identified.
If it reappears, it is real.

### 2026-08-15 (end of session) - R3-4 now waits on the APPROVALS workflow, not on R3-2

**R3-2 is built and green and is NOT going out yet, by Abhimanyu's decision of
2026-08-15.** Chaman's credentials are not being handed over for at least two days, and
shipping him into a platform where his requests cannot be answered would be shipping a
button that leads nowhere.

**The reason is the finding at the foot of the previous entry: there is no screen for Aman
or Adesh to approve or reject anything.** That is now its own piece of work, planned and
decided:
`_bmad-output/planning-artifacts/approvals-one-workflow-2026-08-15.md`.

**It is bigger than it sounds and the scope is deliberate.** Abhimanyu chose ALL SIX
approval systems on one workflow rather than the general one first, plus a requirement that
any approval invented later joins automatically. Eleven decisions (21 to 31) are recorded in
Part 1 of that document and are settled.

**Three of them will catch people out, so they are repeated here:**

1. **Flo is NEVER in the shared approval thread.** Each participant gets Flo privately, on
   their own screen, within their own profile, and nothing Flo says enters the transcript.
   Aman's Flo sees far more than Chaman's, so a shared Flo would print an answer built on
   Aman's access in front of somebody who does not hold it. The permission table would be
   right and the platform would leak anyway.
2. **Every kind KEEPS the approvers it has today.** Announcements stay Adesh's alone;
   student leave keeps its teacher-then-principal shape. Cover for absence, which is what
   Abhimanyu actually wants from flattening them, is a separate later item.
3. **Adesh sees Aman's approval decisions**, which is NOT a reversal of the Release 4
   decision that Adesh must not see Aman's changes in the action log. Different surface:
   both men are approvers of the same queue. Keep the two apart.

**The order is now: this work, then R3-4.**

### 2026-08-15 (audit) - every decision checked against the code, and one was half-built

Abhimanyu asked for it to be made certain that every decision he made was properly logged.
Rather than assert it, every message of the session was walked and each decision grepped
for in the files. **Two gaps, and the first was a feature, not a note.**

**GAP 1, and it was real: removing a driver or conductor could not be ASKED for.**

He said, on 2026-08-15, in one breath: "adding a driver, a conductor... and make the
deletion tools have an approval process from Aman and/or Adesh". The half that CARRIES OUT
such a removal on approval was built (`_do_remove_staff_member`). **Nothing anywhere raised
it.** So the transport head could add a driver and could never ask for one to be removed,
and the working half looked complete on its own.

Now built end to end:

- He asks through the screen or through Flo; both answer 202 / `awaiting_approval` and
  remove nobody.
- It is narrowed to HIS OWN transport staff. Without that, the path built so he could
  retire a bus driver would also let him ask for a teacher's removal.
- Aman or Adesh agreeing carries it out, **through the real removal path**
  (`staff_service.delete_staff`), not a hand-written `is_active: False`. The first version
  of the executor did write the flag directly; it looked equivalent and was not. The real
  path also closes the login, revokes any refresh token so an open session cannot outlive
  the decision, records the leaving state so it can be undone, and erases what the
  assistant had learned about the person (R6.4, DPDP §12).
- **`may_delete_people` stays False for him**, which is not a contradiction: he ASKS,
  somebody else carries it out.

Six tests in `test_r3_2_chamans_profile_2026_08_15.py`, including one proving he cannot ask
about a teacher and one proving the owner still removes a colleague outright.

**Reach count moved again, deliberately: transport head 24/9 to 25/10** (`delete_staff`).
Nobody else moves; the owner, principal and management head all already held it.

**GAP 2: three documents still said the transport head sees no money at all.** True when
written, reversed on 2026-08-15, and left standing they would have sent a session to strip
out access he was deliberately given. Corrected in place, never deleted, each with the date
and what survives of the original:

- `planning-artifacts/maps-and-ai-route-planning-2026-08-15.md` - had a whole section
  built on the old rule, offering three ways round a conflict that no longer exists. It now
  says which of the three he chose. Its "order of work" line was also stale.
- `HANDOFF-2026-08-14-access-ladder.md` - corrected inline and given a superseded note.
- `planning-artifacts/staff-profiles-draft-for-aman-2026-08-10.md` - answer 2 now carries
  a warning box saying what was reversed and, just as importantly, **what survives**: no
  other money, and building repairs stay hidden.

Also recorded properly: Abhimanyu's reason for parking the maps work, in his own words. It
is not simply "it costs money" but that **the cost lands in Aman's subscription**, making
it his decision, on a tool the school may never press since its routes already work.

**Gate after the audit: backend 3,857 passed / 0 failed / 14 deselected.**

### 2026-08-15 (later) - the APPROVALS WORKFLOW is BUILT and green. NOT DEPLOYED

**All six approval systems are on one workflow, and a seventh joins by declaring
itself.** The gap this closes: there was no screen anywhere for Aman or Adesh to approve
or reject anything, so every request the transport head can raise led nowhere.

**The one thing to understand about the architecture, because it decides everything
else.** This is NOT a new store that the six were migrated into. It is one shared way of
asking six existing, working systems the same four questions: what is waiting on me,
what have I raised, may this person decide this, and decide it. Each kind's `decide`
calls the SAME service function its own screen calls, and its `may_decide` mirrors the
gate its own route already carries.

**So the worst a mistake in the registry can do is HIDE a row from somebody entitled to
see it.** It can never hand somebody a decision they do not hold, because the service
underneath refuses them regardless. That is why moving six live systems was safe to do
in one piece rather than one at a time. Do not relax it.

`backend/services/approval_registry.py` is the source of truth for the kinds.
`approval_thread_service.py` is the conversation. `routes/approvals.py` names no kind
anywhere, and neither does `frontend/src/components/tools/ApprovalsQueue.js`.

**Two extractions were needed first, and both are behaviour-for-behaviour moves.**
Deciding a colleague's leave and deciding a correction to somebody's staff details both
lived in the body of a route. They are now `leave_service.decide_leave_request` and
`profile_change_service.decide_profile_change`, called by the old route and the new
queue alike. Nothing about who may decide moved.

**Four things a later session will trip over.**

**1. There are TWO decision paths on `leave_requests` and they are not the same.**
`PATCH /api/staff/leaves/{id}` goes to `decide_leave` and writes `approved_by`. The
workflow route goes to `decide_leave_request`, which writes `decided_by` AND marks the
person unavailable in `staff_availability`. The approvals queue uses the second, because
without the availability row a colleague given leave still reads as available on every
screen that asks. **Merging the two is a decision for Abhimanyu, not a side effect of
building a screen**, so `decide_leave` was left exactly as it was. Written up at the
foot of `leave_service.py`.

**2. The plan's table was wrong about announcements, and it matters.** It said they are
Adesh's alone. The code has always let Aman OR Adesh decide one. Decision 22 says every
kind keeps the approvers it has today, so **Abhimanyu confirmed on 2026-08-15 that it
stays as the code has it.** Following the table would have taken a power off the school's
owner as a side effect of building a screen. Pinned by name in
`test_approvals_one_workflow_2026_08_15.py`.

**3. "What you may see from before you joined" is a message NUMBER, not a timestamp.**
The first version compared the moment a person was added against the time each message
was written. Two of those can be identical to the microsecond, and when they tied, the
whole history was handed to somebody who had been added without it. **A clock is not
fine-grained enough to answer a permission question.** Every message carries its position
in its thread instead. Found by a test, not by reading.

**4. Deciding through Flo was NOT showing the confirm card decision 30 requires**, and
the test written for it is what found that. The name has to go in
`EXPLICIT_CONFIRMATION_TOOL_NAMES`; a literal `requires_confirmation: True` in the
registry entry is silently overwritten by the loop at the foot of that module. Same trap
that cost `import_data_file` its confirm card on 2026-08-08.

**Attachments ARE built** (Abhimanyu, 2026-08-15), and nothing about the photo rules of
the same day is worked around. A quote or a bill goes through the ordinary upload route,
so it gets the same allowed types, the same size ceiling for that person, the same check
that the contents match the extension, and the same private bucket behind a short-lived
signed link. **There is no second way to put a file into this school's storage.** One
narrow rule was added to who may OPEN one: a file attached to a message in a conversation
you may read. Without it the accountant head, who is in a repair-cost conversation
precisely because he pays it, could see that a quote existed and could not open it. A
person added without the history cannot open an attachment from before they joined
either, which would have been a hole if the rule had covered words and not files.

**A rejected request stays readable for ever and cannot be re-opened** (Abhimanyu,
2026-08-15). The refusal stands and the raiser puts up a new version, so a no cannot be
quietly turned into a yes on the same record.

**Counts that moved, all deliberate.** Two Flo tools were added, both classified
`shared`: `get_my_approvals` (a read) and `decide_any_approval` (a write).

| Profile | Before | After | Why |
|---|---|---|---|
| owner, principal | 167/104 | 169/105 | both tools |
| accountant | 60/30 | 62/31 | both tools. **Holding the write grants him nothing**: it asks each kind's own service, which refuses him exactly as its screen does |
| management | 105/63 | 107/64 | same |
| transport_head | 25/10 | **26/10** | the READ only. The R3-2 rule held: a named-grant profile inherits `shared` reads and never a `shared` write |
| the five dormant desks | 30 or 31 / 0 | plus 1 read | `may_write` is False, so the write did not arrive |

**The two sub-tabs are now the same in the bell and in the notifications window**
(Abhimanyu, 2026-08-15). They already split by the same rule and labelled it differently,
with three tabs in one place and two in the other, so one inbox read as two different
things depending on where a person stood. They are now **"Waiting on you"** and
**"Already happened"**, from `KIND_TABS` in `notifKinds.js` so they cannot drift again.
The old "Both" tab is gone and nothing is dropped with it: the two halves are exhaustive,
so every row is still reachable under exactly one of them.

**Gate: backend 3,941 passed / 0 failed / 14 deselected. Frontend 868 passed across 73
suites. Production build clean including lint.** Baseline before this work was 3,857 and
855 across 72. No live school data was read or changed.

**NOT DEPLOYED. Waiting on Abhimanyu.** Pushing to `main` IS a frontend deploy, so this,
R3-2 and R3-3 have to go out together.

**What is left.**

- **R3-4, Chaman's handover.** It was waiting on this work and is no longer blocked.
- **Three things still open and NOT guessed at:** cover for absence when one of Aman or
  Adesh is away (decision 22 names it as a later item); whether the "bring somebody in"
  control should offer a list of colleagues rather than an account id, which is what it
  takes today; and no live-system proof, because everything here is proven by tests.
- **A fault found in passing and deliberately NOT fixed:** `_is_owner_or_principal_user`
  in `routes/staff.py` and `_is_owner_or_principal` in `services/staff_service.py` both
  read `(sub_category or "principal") == "principal"`, so **an admin with no job title
  counts as the principal.** That is the same shape as the `_can_view_all` fault fixed in
  `issues.py` during R3-2. It does NOT affect approvals, which go through
  `middleware.auth.is_owner_or_principal` and require the sub-category exactly. Left
  alone because changing it is a permission decision on a live platform, not a tidy-up.

### 2026-08-15 (deploy) - EVERYTHING HELD BACK IS NOW LIVE

**Deployed on Abhimanyu's instruction to ship it all together.** Backend
`eduflow-approvals-20260815-69a2705`, environment Ready and Green. Frontend Amplify job
**166 SUCCEED** on the same commit. `main` is at `69a2705`, pushed.

**Rollback target: `eduflow-photoleak-20260815-36b04c7`.**

**What went out in one release**, all of it previously built, green and deliberately held:
the approvals workflow, R3-2 (Chaman's profile), R3-3 (drivers and conductors), the three
approvals leftovers closed the same day, and the platform-wide searchable drop-downs.

**The reason for holding is gone.** R3-2 was held because the transport head would
otherwise hold buttons whose requests nobody could answer. There is now a screen where
Aman or Adesh answer them, and a form for raising one.

**Verified against the running system, not the status page.** `/api/health/ready` answers
200 with db, ai, s3 and sms all ok. `/api/approvals/kinds`, `/waiting-on-me`,
`/raised-by-me` and `/{kind}/{id}/people` all answer 401, while a made-up path under the
same prefix answers 404 from the same server. A 401 proves the code is live and still
guarded; a 404 would have meant it never shipped.

**The bundle was diffed before upload**, as the rule requires: 242 entries before, 247
after. The five added are exactly this release's new backend files
(`routes/approvals.py`, `services/approval_registry.py`,
`services/approval_thread_service.py`, `services/profile_change_service.py`,
`services/transport_scope.py`) and **nothing was removed**.

**Gate at deploy: backend 4,000 passed / 0 failed / 14 deselected. Frontend 884 passed
across 74 suites. Production build clean including lint.** No live school data was read
or changed.

**What this deploy does NOT prove, said plainly.** Everything is proven by tests plus a
live route check. Nothing was proven by signing in as a real profile, because that needs
a signing secret this session will not go and fetch. If somebody wants live proof, ask
Abhimanyu to sign in and open Approvals.

**R3-4 is the only thing left in this release**, and it is a deliberate act rather than a
code change: create Chaman's account and hand over the password. It is no longer blocked
by anything.
