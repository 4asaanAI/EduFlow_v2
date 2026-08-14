# Release 3 (access): the department heads get in

**Written 2026-08-14.** This is the third step of the access ladder Abhimanyu gave on
2026-08-09: 1 Aman and Adesh, 2 Sonu and Lalit, **3 department heads**, 4 whole admin
staff, 5 teachers, 6 students, 7 parents.

**Do not confuse this with the work that shipped as "Release 3" on 12 August**, which was
tables, downloads and phone sizing. Two numbering schemes collided. See
`release-numbering-collision-2026-08-14.md`. In this document, "Release 3" always means
the access step. The shipped work is called "the table release".

Progress will be recorded in
`_bmad-output/implementation-artifacts/release-3-access/PROGRESS.md`, which becomes the
only record of what is done once work starts.

---

## Part 1: the decisions. Settled, do not reopen.

Numbered from 15 to continue the Release 4 (audit) list rather than restart and collide.

| # | Decision | Given |
|---|---|---|
| 15 | **The seven office passwords were never handed out.** Aman and Adesh have theirs. Sonu's and Lalit's are being handed over today. Nobody else has ever signed in. | Abhimanyu 2026-08-14 |
| 16 | **Assistants get their own profiles, not the head's.** Roughly what the head has, minus some visibility, plus approval by the head for actions. The specifics come from the school. | Abhimanyu 2026-08-14 |
| 17 | **Messaging stops at teachers.** Students never get it, and it is therefore not part of the students release. Staff only. | Abhimanyu 2026-08-14 |
| 18 | **Release 3 and as much of Release 4 as possible should be finished before Sonu's and Lalit's credentials go out**, with the doubtful parts left open rather than guessed. | Abhimanyu 2026-08-14 |
| 19 | Carried from 2026-08-11, answers 1 to 12 of `staff-profiles-draft-for-aman-2026-08-10.md`. All twelve stand. | Abhimanyu 2026-08-11 |

**Decision 17 closes the question that had blocked Release 5 since 10 August.** Teachers
are already inside the staff messaging group (`STAFF_ROLES` in `routes/messaging.py`
covers owner, admin and teacher), so no work is needed to include them. Students must
stay out, which is the current behaviour, so no work is needed there either. **The only
remaining work is a test that pins it**, so that a later change cannot quietly let a
child into the staff chat.

---

## Part 2: what was found by probing the running code, not by reading it

A throwaway test was run against the application with three dormant office profiles. The
authorisation code exercised is the same code production runs. Results:

### Money is genuinely protected. This part is sound.

| Probe, as transport head / front desk / support staff | Result |
|---|---|
| `GET /api/fees/transactions` | **403** all three |
| `GET /api/issues/facility/cost-summary` | **403** all three |
| `GET /api/issues/maintenance/vendors` | **403** all three |
| Cost fields in the facility list | **not present** |

### Writes are NOT protected, and this is the finding that matters

| Probe | Result |
|---|---|
| `POST /api/transport` (create a school bus route) | **200 for all three**, including support staff |
| `PATCH /api/transport/{id}` and `DELETE /api/transport/{id}` | reached the handler and returned 404 only because the id was invented. **The gate passed.** |
| `GET /api/students` | **200 for all three**, including support staff, who has no student screen at all |
| `GET /api/staff` | **200 for all three** |

### Why

`profile_matrix.py` is the source of truth for **three things**: which screens the menu
offers, which tools Flo will use, and who may export. It is **not** consulted by the REST
API. Searching the backend, `may_open_screen` appears only in `routes/exports.py`, and
`granted_domains` only in the Flo tool gates and the undo scope.

The REST routes carry their own hand-written gates. `require_role("owner", "admin")`
checks the role and **ignores the sub-category entirely**, so every office desk passes it.
That is how a support staff account can create a bus route.

**So "dormant" is not a lock.** Nothing at runtime reads the `status` field; it appears
only in tests and the mirror generator. A dormant profile is hidden from the menus and
starved of Flo tools, and that is all.

**What holds the line today is decision 15, and only that.** None of the seven has a
usable password. The moment one is issued, the gaps above are live. That is why this is
ordered first.

---

## Part 3: the work

### R3-0 — Make dormant mean something. **Do this first, before any credential goes out.**

The cheapest honest fix, and the one that matches what everyone already believes is true.

- A single dependency that reads `profile_matrix` and refuses a profile marked `dormant`
  at the door, applied centrally rather than route by route. A dormant account signing in
  gets a plain message saying their profile is not switched on yet, **not** a half-working
  platform.
- **Fail closed and say so.** A profile the matrix does not recognise is refused.
- Tests: every dormant profile refused on the transport write path, the student list and
  the staff list. Every live profile unaffected, proven by the existing pinned reach
  counts not moving.

*Why first:* it is small, it removes the whole class of problem rather than four
instances, and it makes every later step safe to do in any order.

### R3-1 — Close the gap between the matrix and the REST API

R3-0 stops dormant profiles. It does not fix the deeper issue: **a live profile's REST
access is still decided by hand-written role checks rather than the written-down table.**
Sonu and Lalit are correct today only because somebody checked each route by hand.

- Survey every route whose gate is `require_role("owner", "admin")` and record, per route,
  whether every admin desk should really pass it. `POST /api/transport` is the proven
  example and there will be others.
- Where the answer is no, move the route onto the matrix.
- **Nothing is widened.** Any change that would give a live profile more than it has today
  stops and asks.

*This is the same fault as Release 2's "permission by subtraction", one layer down. It is
sized as its own part because a blind rewrite of every gate is how access accidents
happen.*

### R3-2 — Chaman's profile, built properly

Answers 1 and 2 of the staff profiles draft.

- **Route changes without an approval step.** He moves a child between routes himself,
  recorded in the action log like any other change. The audit release already records it.
- **A maintenance view carrying no money.** Good news from the survey: the maintenance
  schedule and the contractor records **hold no money fields at all**, so this is far
  smaller than feared. Every amount lives on facility requests
  (`estimated_cost`, `actual_cost`) and in the cost summary, which are already refused to
  him. The work is to let him reach the calendar and the contractors' phone numbers,
  which today return 403, without opening the request costs.
- **Give him actual tools.** His `tool_domains` is empty, so Flo can do nothing for him.
  Deciding which tools is part of this step, and it is a grant, so it is written down
  before it is built.
- Note for whoever does it: the maintenance gates in `routes/issues.py` are hand-written
  helpers (`_can_view_all`, `_is_maint`) and are a second source of truth. `_can_view_all`
  also admits an admin with **no** sub-category at all, which is worth a second look.

### R3-3 — The tenth profile: drivers and conductors

Answer 10 took them out of support staff and gave them their own profile, which **does not
exist**. The platform recognises eight admin desks plus the owner. Building it belongs
here because it is transport.

Defined only. No logins, following the same rule as support staff.

### R3-4 — Switch Chaman on

- Confirm his account (`chaman.singh`, created by migration 041 on 12 August, never used).
- Hand over his one-time password through the school, the same way Sonu's and Lalit's go
  out today.
- Watch him sign in once and check what he sees matches what was designed.

---

## Part 4: Release 4 (access), as far as it can go today

The whole admin staff. Recorded here so the thinking is not lost; it becomes its own
document when Release 3 is done.

**Ready to build, decided:**

- **Split Commercial Operations.** Answer 4. Asniya runs the shop counter, so she gets the
  till and nothing else: no legal entities, no reporting, no totals. One screen today, so
  it has to be split before she can hold half. This is the largest single item.
- **The paid-or-unpaid flag for the front desk.** Answer 5. Cleared or outstanding, never
  a figure. The same flag Lalit already has, so there is an existing shape to copy.
- **Maintenance can add contractors, touching no money.** Answer 8. Made easier by the
  survey finding above: contractor records carry no amounts.
- **Repair approval reuses the certificate approval built in R2-9.** Answer 9. Either
  Adesh or Aman, not both. It must not become a second approval system.

**Decided as a hard stop, no work:**

- **No IT login while the role is held by a Vedmarg employee.** Answer 6. A standing login
  into the records of 1,876 children, held by an employee of the school's previous ERP
  supplier, is not a question the platform can answer. It switches on when a school
  employee takes the role.
- **No support staff logins.** Answer 11 and 12. What matters is their data being right:
  their record, their attendance, their salary. Carry that into the data work.

**Blocked on the school, per decision 16:**

- **Profiles for the two assistant accountants and the two admin office staff.** The shape
  Abhimanyu expects is: close to the head's, a little less visible, with the head
  approving actions. The specifics come from the school. **Until then those four accounts
  hold the head's full access**, which is safe only while decision 15 holds and no
  password has been issued. **If any of the four is ever given a password before their
  profile exists, they get the accountant head's or management head's access in full,
  including every teacher's salary.**

**One thing to check rather than assume:** Vipin Kumar, the social media executive, was
given a `support_staff` login by migration 041 on 12 August, one day after answer 12 said
those people get no logins. He is not an office helper, so this is probably a mapping
choice rather than a contradiction. Confirm which profile he should hold.

---

## Part 5: order, and why

1. **R3-0**, before any credential leaves the building. Small, and it removes a class of
   problem rather than instances of it.
2. **R3-1**, the survey. Read-only, changes nothing, and tells us how big the real gap is.
3. **R3-2**, Chaman's profile.
4. **R3-3**, drivers and conductors, defined.
5. **R3-4**, switch him on and watch it.
6. Then Release 4 (access), starting with the Commercial Operations split, which is the
   long pole.

**Sonu's and Lalit's credentials do not need to wait for all of this.** Their profiles
were built and proven in Release 2 and are live. What should land before any credential
goes out is **R3-0 alone**, so that a school that starts distributing logins cannot
accidentally hand somebody a half-open door.

---

## Part 6: notes for whoever picks this up cold

- The permission table is `backend/services/profile_matrix.py`. Its JavaScript twin is
  **generated**: never hand-edit `frontend/src/lib/toolPermissions.js`, run
  `scripts/generate_profile_matrix.py`.
- The pinned per-profile reach counts in
  `tests/backend/unit/test_all_nine_profiles_sweep_r2_13.py` are the alarm. A count moving
  without a written reason means somebody's access changed and nobody decided to.
- Twelve answers from Abhimanyu sit at the foot of
  `staff-profiles-draft-for-aman-2026-08-10.md`. **Read that section before the draft
  above it**; where they disagree, the answers win.
- The rule from Release 2 that still governs: **grouping never grants, and nothing is ever
  dropped.**
- Do not run `backend/migrations/run_all.py` against the live database, ever.

---

| Date | Change |
|---|---|
| 2026-08-14 | Written. Decisions 15 to 18 recorded, the access gaps proven by probe rather than assumed, R3-0 identified as the thing that must precede any credential handover. |
