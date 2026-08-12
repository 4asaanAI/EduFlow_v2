# Release 4: the platform can account for itself

**Written 2026-08-12. Branch: `release-4-2026-08-12`. Starting point: `main` at `743be98`.**

Release 3 is live. This is the release agreed alongside it and deliberately kept out of it.

> **Read this first, then `_bmad-output/implementation-artifacts/release-4/PROGRESS.md`.**
> The PROGRESS file is the only record of what is done. This file is what the work is.

---

## Part 0 - The one idea behind the whole release

Release 3's faults were all one shape: **a query that quietly returned less than it
should**. A lookup matching nobody looked like a lookup with nothing to do.

Release 4's faults are the same shape moved one step sideways: **the platform quietly
says less about itself than it should.**

- A change that was never written down looks exactly like a quiet day.
- A record of a change that omits the previous value looks exactly like a change that
  cannot be undone, and the person is told to ask the principal for no real reason.
- A menu offering a button the server will refuse looks exactly like a working feature,
  right up to the moment somebody presses it in front of a parent.
- Storage that grows without limit looks exactly like storage that is fine, until the
  bill arrives.

So the test for every item below is the same: **can a person tell the difference between
"nothing happened" and "we did not record it"?** If not, the item is not done.

---

## Part 1 - Where the decisions came from

All of these are Abhimanyu's, recorded on 12 August 2026. **Settled. Do not reopen.**

| # | Decision |
|---|---|
| 1 | Release 4 is split from Release 3 and ships straight after it. *(Release 3 is live.)* |
| 2 | Record everything happening on the platform, by whichever profile did it. Especially everything on Aman's and Adesh's profiles, and **most especially the remarks and notes they type onto other people's profiles**, plus the school's important data. |
| 3 | Cloud costs will rise as the database grows and that is accepted. Keep it as lean as possible **without losing anything important**. |
| 4 | **Undo only the things that hurt the platform.** For everything else, Flo talks the person through undoing it by hand. |
| 5 | Both Aman and Adesh see the audit trail, but **Adesh must not see Aman's changes.** |
| 6 | Tickets to Layaa AI land in **LayaaStat**. |
| 7 | Flo raises a concern **before** storage fills, works with the office to solve platform problems, and raises a Layaa AI ticket when it is beyond Flo and the staff. |
| 8 | **Full history kept for two years. A monthly summary kept forever.** *(2026-08-12. Two years covers a full school session plus the one before it, which is as far back as a fee or attendance dispute realistically reaches. The summary means nothing is ever truly gone.)* |
| 9 | **A tool a profile may not use does not appear in that profile's tool directory at all.** Only that profile's own tools, and every profile arranged the same way, in one unified layout. *(2026-08-12.)* |

Read-only permission to measure the live database size was granted (question 5,
answered "sure"). **That is permission to READ. Nothing on the live database is written,
migrated or deleted in this release without a fresh, explicit yes.**

---

## Part 2 - What is actually there today, measured not assumed

### Audit

- One shared way to write an audit line exists: `services/audit_service.py`, 100 lines.
  It never throws. If the write fails it logs and carries on, by an earlier decision.
- **Sixteen of the platform's thirty-nine areas write audit lines.** The rest write
  nothing. Those changes leave no trace.
- Entries are **kept forever.** Nothing deletes an old one. This is the direct cause of
  the cost worry in decision 3.
- There is a screen, `AuditLog.js`, 243 lines, and routes for a daily digest, a school
  summary, that summary's history, and a record's own history.

### Undo

- `services/undo_service.py` exists and is honest about its own narrowness. It undoes
  **your own** change, **today**, on a **student or staff record**, and never money,
  enrolment or a login.
- Its own docstring records the real blocker: **there are at least eight different shapes
  in which a change gets written down**, and only one of them carries both the before and
  the after value. The rest cannot be reversed by writing a value back, and an undo
  written against an assumed shape would appear to work and silently do nothing.
- Deleted children and staff go to a recycle bin and can be restored. An ordinary edit, a
  fee correction, a changed salary cannot be put back automatically.

### Tickets to Layaa AI

- A ticket system exists but it stays **inside the school**. Tickets go to the school's
  own IT person or to Aman.
- The LayaaStat link is real and already wired: `services/layaastat/client.py` pushes
  telemetry, `routes/federation.py` lets LayaaStat pull incidents. **It is not a ticket
  inbox.** It pushes health and cost figures one way.
- So a piece is needed on the LayaaStat side too, to show a ticket and let Layaa AI
  reply. Not a problem, but not free, and it is in a different repository.

### Menus

Better than expected, and the gap is precise.

- The eight office desks are already **default deny** off one written-down table,
  `backend/services/profile_matrix.py`, mirrored to the frontend. All three places that
  show tools already filter through it: the sidebar, the tool dashboard, and the command
  palette. `support_staff`, which used to fall through to the whole admin list, is in the
  table now.
- **Teachers, students and guardians are not in that table.** `canUseTool` passes them
  through: anything not on a short office-only list is allowed. Their menus are
  hand-written arrays inside `Sidebar.js` with nothing proving they match what the server
  accepts. **That is where a dead button lives today**, and Release 5 is teachers and
  Release 6 is students, so it is about to matter.
- **The layout is not unified.** Owner and principal get hubs only. The other office desks
  get hubs followed by a flat tail of anything with no hub. Teachers and students get a
  different set of hand-written groups. Three arrangements for one platform.

---

## Part 3 - The work, in six parts

Ordered so each part stands on the one before. **One part per run.** A part is done when
it is built, tested, and written into PROGRESS.md, not when the code compiles.

### R4-1 - One shape for a recorded change

**The problem.** Eight shapes. Only one says what the value was before. Everything below
is limited by this, so it goes first.

**Do.**
- Write down the one shape, with the before value required, and a reason field.
- Move every one of the sixteen areas that already record onto it, keeping the old shapes
  readable so existing history is not orphaned.
- Where a change genuinely has no before value, such as creating a record, say so **in
  the record itself** rather than leaving a field empty. An empty before value and "this
  kind of change has no before value" must not look the same.
- A test that fails if a new write path records in a shape nobody decided on.

**Done when** a single reader can take any audit line, old or new, and say what changed,
who did it, and what it was before, or say plainly that no before value exists and why.

### R4-2 - Everything is recorded

**The problem.** Twenty-three areas of the platform record nothing.

**Do.**
- Cover the rest, prioritised by decision 2: first Aman's and Adesh's profiles including
  **the remarks and notes they type onto other people's profiles**, then the school's
  important data, then the remainder.
- List every write path in the platform and mark each one recorded or not. **Publish the
  list, including the gaps.** A quiet gap is the whole failure this release exists to fix.
- A test that a new write path without recording fails the build.

**Done when** the published list has no unexplained blank, and every blank that remains
carries a written reason.

### R4-3 - Two years in full, a summary forever

**The problem.** Nothing ever deletes an old entry, so the bill only goes one way.

**Do.**
- Full detail kept for two years. Beyond that, a monthly summary per person per kind of
  change, kept forever.
- **Thinning is a scheduled job that says what it did, in its own audit line.** History
  that quietly shrinks is the same failure as history that was never written.
- Measure the current audit and database size first, read only, under the permission
  already given. Report the real number before designing around a guess.
- Never thin anything inside the two year window, whatever the size.

**Done when** the growth curve is bounded, a person can still see any month from any year,
and the thinning itself is on the record.

### R4-4 - Undo what hurts, guide the rest

**The problem.** Undo is narrow because the recording was dishonest. R4-1 fixes that, so
undo can widen truthfully.

**Do.**
- Agree the list of "things that hurt the platform" and write it down. Starting proposal,
  to be confirmed: a fee entry, a salary change, attendance for a day, marks, and a bulk
  spreadsheet import. Money and enrolment stay with Aman and Adesh, as today.
- Widen undo to exactly that list and no further.
- **Everything else: Flo walks the person through undoing it by hand**, using the recorded
  before value to tell them what to type. This is decision 4 and it is the larger half of
  the work, not a consolation prize.
- Every refusal keeps saying why, in a sentence a person can act on. Every undo keeps
  writing its own audit line.

**Done when** the things that hurt can be put back, and everything else produces real
guidance rather than "ask the principal".

### R4-5 - Flo watches the platform and can reach us

**Do.**
- Flo raises a concern **before** storage becomes a problem, not after, with a number
  and a plain sentence.
- Flo helps the office work through a platform problem, using what it can actually see.
- When it is beyond Flo and the staff, Flo raises a **ticket to Layaa AI in LayaaStat**.
  This needs the EduFlow side to send a ticket and the **LayaaStat side to show it and let
  us reply**. The LayaaStat piece is in another repository and is its own task, sized
  separately.
- A ticket must never be raised silently. The person sees it was raised and can see its
  state.

**Done when** a problem the school cannot solve reaches us without anyone needing to
telephone, and the school can see that it did.

### R4-6 - Honest menus, one layout

**Decision 9.** Two rules, and neither may be relaxed.

- **Nothing offered that will be refused.** If a profile may not use a tool, that tool is
  not in that profile's directory at all. Extend the written-down table to teachers,
  students and guardians, who are outside it today, and prove menu and server agree for
  every profile in one sweep.
- **Nothing dropped.** A tool a profile does have must never vanish because a layout
  changed. That is the rule that saved Staff Tracker after Release 3, and it stands. A
  tool with no home is still shown.
- **One layout for everybody.** The same arrangement for the owner, the eight office
  desks, teachers and students, instead of today's three different schemes.

Two items parked here during Release 2 belong to this part: proper profiles for the
transport head, receptionist, IT and maintenance, and clearing the dead buttons currently
offered to `support_staff`.

**Done when** no profile can be shown a button that answers no, no profile has lost a
button it had, and the menus all read the same way.

---

## Part 4 - Rules for whoever picks this up

- **Grouping never grants.** A layout decides which tab a tool sits under. It can never
  widen what a profile may reach. Resolve the tool list exactly as before, then arrange it.
- **The permission table stays the one source of truth.** `profile_matrix.py`, with the
  frontend copy generated from it. Never hand-edit the generated copy. The pinned reach
  counts are the alarm: a count moving without a written reason means somebody's access
  changed and nobody decided to.
- **Never return the dict you just inserted into Mongo.** It stamps an id into your copy
  in place and that is not sendable. This 500'd every staff message send on 12 August.
- **The stand-in database must fail the way the real one fails.** A kinder stand-in
  manufactures a green suite that proves nothing.
- **Never bind a module constant as a default argument.** It freezes at import and every
  test that changes the constant is silently ignored.
- **Never run `backend/migrations/run_all.py` against production.** One migration at a
  time, after reading what that one does.
- Python 3.9. `from __future__ import annotations` on the first line of any file using
  `str | None`. No TypeScript, frontend is `.js` and `.jsx`.
- **The bar is zero failures. Never pin a pass count anywhere.**
- Deploys run as the `claude-hosting` IAM user. Confirm with `aws sts get-caller-identity`
  before deploying. Build the bundle with Python's zipfile, not PowerShell, and compare
  its file list against the last good bundle before uploading.

---

## Part 5 - Open, and who answers

| Item | Who | Note |
|---|---|---|
| The exact list of "things that hurt the platform" for R4-4 | Abhimanyu | Proposal is in R4-4. Confirm or change it before that part starts. |
| The LayaaStat ticket inbox | Layaa AI side | Different repository. Size it before R4-5 starts, do not discover it mid-part. |
| Reading live database and audit size | Granted, read only | Nothing written, migrated or deleted without a fresh yes. |

Three items are still open from 12 August and are not Release 4 scope unless asked:
Aman showing as online with nobody signed in, no warning before the one hour sign-out,
and that sign-out never having been watched in a real browser for an hour.

---

| Date | Change |
|---|---|
| 2026-08-12 | Written. Decisions 1 to 7 recovered from the 12 August session; 8 and 9 given the same day. |
