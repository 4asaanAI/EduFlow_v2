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
| R3-0 | Make dormant mean something, at the door | **Built, PARKED on branch `r3-0-dormant-lock`. Parked by Abhimanyu's instruction on 2026-08-14 evening, NOT because it failed. Do not start it. Turns 20 existing tests red; see below.** |
| R3-M | The staff room holds only profiles whose release has landed | **LIVE 2026-08-14** |
| R3-1 | Close the gap between the matrix and the REST API | **Survey DONE 2026-08-14, read only, nothing changed. `R3-1-survey-2026-08-14.md`. The fixing half is not started and needs a decision on order first.** |
| R3-2 | Chaman's profile built properly, no money anywhere | Not started |
| R3-3 | The tenth profile: drivers and conductors, defined only | Not started |
| R3-4 | Switch Chaman on and watch him sign in | Not started |

Nothing beyond R3-M is built. No live school data has been read or changed by this release.

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
