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
| 10 | **Do not clone an open-source helpdesk.** Tickets are built inside LayaaStat, reusing its registry, dashboard, login and alert routing. Reasoning and the rejected candidates are in R4-5a. *(2026-08-12.)* |
| 11 | **A ticket attaches to the CLIENT, not the product.** The Aaryans, not EduFlow. EduFlow will have more schools. *(2026-08-12.)* |
| 12 | **Delivery is LayaaStat first, then n8n, then email** to `abhimanyu.singh@layaa.ai` and `shubham.sharma@layaa.ai`. Store before notify, always. *(2026-08-12.)* |
| 13 | **Keep costs as low as possible without giving up any feature.** *(2026-08-12.)* Cost is a design constraint on every part of this release, not a review at the end. It is not a reason to drop something Abhimanyu asked for; it is a reason to reach the same result the cheaper way. Rules in Part 4a. |
| 14 | **Screenshots are sent unblanked.** *(2026-08-12.)* Layaa AI already holds most of the school's records, so a picture of a screen is not a new category of exposure. The blanking proposal is dropped. See R4-5e for the one thing this does not settle, which is where the picture travels. |

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
- When it is beyond Flo and the staff, a **ticket goes to Layaa AI in LayaaStat**.
- A ticket must never be raised silently. The person sees it was raised and can see its
  state.

**Done when** a problem the school cannot solve reaches us without anyone needing to
telephone, and the school can see that it did.

#### R4-5a - The decision not to clone a helpdesk

*Researched 2026-08-12 at Abhimanyu's request, and he agreed with the outcome.*

Cloning an existing open-source helpdesk was the right question to ask and the wrong
answer for us:

- **Peppermint** was the closest fit on paper (Next.js, Postgres, webhooks on ticket
  creation, 3,081 stars). **Archived 17 July 2026, read-only.** Adopting it means owning
  every future security patch.
- **Helpin** is our exact stack (Next.js, Supabase, Vercel) with 159 stars and **six
  commits in total**, described by its author as a weekend project. A template, not a
  product.
- **Zammad** wants 4 to 8 GB plus Postgres, Redis and Elasticsearch. **FreeScout** is PHP
  and Laravel and genuinely light. **Frappe Helpdesk** is Python and Frappe. All three are
  whole products in a different stack.

The cost is not the cloning. Every one of them is a **second application** with its own
database, login, hosting, updates and bill, sitting *beside* LayaaStat rather than inside
it, which contradicts decision 6. Two dashboards to answer one question. Note also that
**Azure Container Apps will not provision in our subscription**, so "just run the Docker
image" is not available to us.

#### R4-5b - The ticket lands on the CLIENT, never on the product

**Abhimanyu, 2026-08-12, and he is right to have raised it.** EduFlow will have more
schools. A ticket from The Aaryans must attach to *The Aaryans*, not to *EduFlow*.

**LayaaStat's registry already has exactly this shape**, so nothing needs inventing:

```
products  →  tenants  →  environments  →  monitored_services
(EduFlow)    (The Aaryans)  (prod)
```

`0002_registry.sql`. A ticket therefore carries `tenant_id`, never `product_id` alone.
Rolling up to "all EduFlow tickets" is then a question you ask of the data, not a shape
baked into it, which is the way round that survives the second school.

**The identity is already carried correctly.** The EduFlow client sends a **tenant-bound
ingest key**: `client.py` says in as many words that the key identifies the tenant. So a
ticket sent with the school's key is already on the school.

**Two things to VERIFY before building, not assume:**
1. That an `eduflow` product and an Aaryans tenant actually exist in LayaaStat. The seed
   file creates only `layaa-internal`, so the rest were made at runtime and cannot be read
   from the repository.
2. That the ingest key configured on the **live** EduFlow server points at that tenant. A
   key pointing at `layaa-internal` would file every school's ticket under Layaa's own
   internal tenant, and it would look like it was working.

#### R4-5c - Delivery: LayaaStat, then n8n, then email

*Abhimanyu, 2026-08-12.* Ticket raised → LayaaStat stores it → webhook to n8n → n8n emails
`abhimanyu.singh@layaa.ai` and `shubham.sharma@layaa.ai` → we open LayaaStat to read and
resolve it.

**Almost none of this needs building.** LayaaStat already has alert routing with four
delivery channels: `slack`, `email`, `webhook`, `ntfy` (`0047_ntfy_channel.sql`,
`alerting/actions.ts`), a delivery cron (`api/cron/notify`), a settings screen, and working
email through Resend. A ticket becomes another thing that fires an alert route.

n8n is reached through the **existing `webhook` channel**. It buys the freedom to add
Slack or WhatsApp later without a code change, at the cost of one more moving part between
a raised ticket and our inbox. **If n8n is down, the ticket is still safely in LayaaStat.**
That ordering is deliberate: store first, notify second. A notification that fails must
never lose the ticket.

#### R4-5d - Raising a ticket from EduFlow

- **A button on the screen, for every profile**, owner down to student. Everyone who can
  hit a problem can report one.
- **Flo can raise one too**, when asked and when it judges the problem is ours. Written in
  plain human language, with what the person was doing, what happened, and what was
  expected.
- **Flo must know WHEN not to.** A ticket for something the receptionist could have fixed
  in ten seconds trains everybody to ignore tickets. Flo tries the school's own remedies
  first and says what it tried.
- Every ticket is recorded in the audit trail like any other action.

#### R4-5e - Screenshots, and the privacy problem in them

**Web search and web crawling do not take screenshots.** They fetch pages from the public
internet. They cannot see the screen the person is looking at, and behind a login there is
nothing for them to fetch. They solve a different problem and are not the answer here.

The right answer is to **capture the page inside the person's own browser** and attach the
image to the ticket, which is a solved, ordinary thing to do.

**Screenshots go UNBLANKED. Decision 14, Abhimanyu, 2026-08-12.** The concern raised was
that a screenshot of an EduFlow screen carries real children's names, fee amounts and
guardians' phone numbers out of the school's system and into Layaa AI's. **Abhimanyu's
answer: Layaa AI already holds most of the school's records, so a screenshot is not a new
category of exposure.** That is factually correct and the blanking proposal is dropped.
Do not reopen it.

**One thing that decision does NOT settle, and it is a different question.** Decision 14 is
about *Layaa AI* seeing the data. It is not about *where the picture travels*. Two places
are looser than LayaaStat:

* **Email.** An attached picture lands in mail servers and inboxes, outside any system we
  control, and stays there.
* **LayaaStat's own sign-up.** `0004_seed.sql` auto-grants **every new authenticated user**
  access to the default tenant. Whoever signs up can see what is there.

**So: the full picture is stored in LayaaStat, behind its login, and the email carries a
LINK rather than the image.** This costs Abhimanyu nothing, because it is exactly the flow
he described ("whenever we receive an email we can directly open LayaaStat to check the
details"). It also keeps email small, which serves decision 13. If he later wants the
image attached to the mail itself, that is one line of configuration.

The screenshot is still **shown to the sender before it goes**, not to protect the data but
because a person should know what they just sent.

**Done when** a ticket reaches us with enough to act on, and the picture lives in one place
we control rather than in everybody's inbox.

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

## Part 4a - Cost is a constraint on every part, not a review at the end

**Decision 13.** The rule is *cheapest way to the same result*, never *a smaller result*.
If a saving would cost a feature Abhimanyu asked for, it is not a saving, and the trade is
brought to him rather than taken quietly.

Where the money in this release actually goes, and what to do about it:

- **Storage is the big one, and it is exactly what R4-3 exists for.** Recording everything
  is what fills the disk. Two years in full plus a monthly summary forever is already the
  cost control. Do not soften it into "keep everything and see".
- **Record once, not twice.** An audit line, a notification and a ticket about the same
  event are three copies of one fact if written carelessly. Point at the audit line.
- **Store what changed, not the whole record.** A copy of an entire student row on every
  edit is the most expensive possible way to record a single changed phone number.
- **Reuse what is already paid for.** LayaaStat's registry, login, dashboard, alert routes
  and Resend email all exist and are already funded. Every one of them used is a service
  not bought. This is the single largest saving in the release and it is why decision 10
  went the way it did.
- **No new paid service.** Nothing in this release should add a subscription. If something
  seems to need one, stop and ask.
- **Screenshots are the quiet cost.** Images are far larger than text. Compress them, cap
  the size, and let them age out sooner than the ticket text does.
- **Flo's watching costs tokens.** Have it check on a schedule against figures already
  collected, not by thinking about the platform continuously.
- **Measure before optimising.** The live audit and database sizes are readable under the
  permission already given. Get the real number before designing around a guess.

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
| ~~Screenshots and children's data~~ | Closed 2026-08-12 | Decision 14. Sent unblanked. Not to be reopened. |
| Borrowing Peppermint's design | Abhimanyu | Peppermint is archived, last code change 21 Sep 2025, 101 issues open forever, licence unidentified by GitHub, 112 MB for a tenth of which we need. Proposal: **read its code and take its data model and ticket states**, adopt nothing. Costs no licence, no hosting, no second login. Awaiting a yes. Does not block R4-1. |
| Does an `eduflow` product and an Aaryans tenant exist in LayaaStat? | Verify | Only `layaa-internal` is in the seed file, so the rest were made at runtime and cannot be read from the repository. Check, do not assume. |
| Does the LIVE EduFlow ingest key point at that tenant? | Verify | A key pointing at `layaa-internal` files every school's ticket under Layaa's own tenant and looks like it is working. |
| Reading live database and audit size | Granted, read only | Nothing written, migrated or deleted without a fresh yes. |
| LayaaStat and n8n changes | Different repositories | The LayaaStat work is real work in `E:\Github\Aasaan AI\LayaaStat`, and the n8n workflow lives outside both. Neither is covered by EduFlow's test suite, so each needs its own proof that it works. |

Three items are still open from 12 August and are not Release 4 scope unless asked:
Aman showing as online with nobody signed in, no warning before the one hour sign-out,
and that sign-out never having been watched in a real browser for an hour.

---

| Date | Change |
|---|---|
| 2026-08-12 | Written. Decisions 1 to 7 recovered from the 12 August session; 8 and 9 given the same day. |
