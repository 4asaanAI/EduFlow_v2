# Release 4 - PROGRESS

**This file is the only record of what is done. Read it first, update it last, every run.**

The work itself is in
`_bmad-output/planning-artifacts/release-4-audit-undo-and-honest-menus-2026-08-12.md`.

Starting point: `main` at `743be98`, clean, matching origin. Release 3 and the four owner
reports after it are live.

---

## Status

| Part | What it is | State |
|---|---|---|
| R4-1 | One shape for a recorded change | **Live** |
| R4-2 | Everything is recorded | **Live** |
| R4-3 | Two years in full, a summary forever | **Live** |
| R4-4 | Undo what hurts, guide the rest | **Live** |
| R4-5 | Flo watches the platform and can reach us | **Live except the final email**, which moves to Zoho Mail (see `ticket-email-via-zoho-2026-08-14.md`) |
| R4-6 | Honest menus, one layout | **Live** |

**All six parts went out on 2026-08-13.** Backend `eduflow-release4-20260813-fec72a7`,
frontend Amplify job 147. Merged as `6daf32f`. No live school data was read or changed.

Backend re-verified from this machine on 2026-08-14 by hitting the new routes through
CloudFront: `/api/audit-log/retention/plan`, `/api/audit-log/my-changes-today`,
`/api/audit-log/school-summary`, `/api/issues/platform` and `/api/operator/platform-health`
all answer **401**, which proves the new code is live and still guarded.
*(`/api/audit-log`, not `/api/audit`. Guessing the shorter one returns a 404 and reads
exactly like a failed deploy. It cost a false alarm on 14 August.)*

Rollback target: `eduflow-msgfix-20260812-6520aed`.

R4-5 is the one that reaches outside this repository. The ticket route works end to end
inside our own systems: the button is live, the school can raise a ticket and it is stored
in LayaaStat under The Aaryans. **The only hop still broken is the final email**, waiting
on that last step being pointed at **Zoho Mail**, decided 2026-08-14. *(It previously said
Gmail; that is dead and must not be carried forward.)* The instruction sheet, including the
two things blocked on Abhimanyu, is `ticket-email-via-zoho-2026-08-14.md` in this folder.
Do not describe the email as working until one real ticket has been watched into the inbox.

---

## Log

### 2026-08-12 - plan written (Claude, Opus 5)

**Did.** Recovered the real Release 4 scope from the 12 August session transcripts. The
project notes carried only the one line "audit and undo, deliberately separate", which is
about a quarter of what was actually agreed. The full set is six decisions from that
session plus two given today, all now in Part 1 of the plan.

**Found, by reading rather than assuming.**

- Audit lines are written by sixteen of thirty-nine areas. The other twenty-three record
  nothing.
- Audit entries are kept forever. Nothing deletes one.
- Undo is narrow because the recording is dishonest: eight different shapes, one of which
  carries a before value.
- The route from the school to Layaa AI does not exist. LayaaStat is wired for telemetry
  one way, not as a ticket inbox.
- Menus are in better shape than expected. The eight office desks are already default
  deny off one table, filtered the same way in all three places tools are shown.
  **Teachers, students and guardians are outside that table** and their menus are
  hand-written, which is where a dead button lives today.
- The layout is not unified: three different arrangements across owner, office desks,
  and teachers/students.

**Decided today.** Two year retention with a monthly summary kept forever (decision 8).
No profile is offered a tool it may not use, and every profile is arranged the same way
(decision 9).

**Left.** R4-1 is next and everything else waits on it. Before R4-4 starts, Abhimanyu
confirms the list of "things that hurt the platform".

### 2026-08-12 (later) - the ticket route is designed, and it is smaller than feared

**Did.** Researched open-source helpdesks as asked, and read LayaaStat properly. Recorded
decisions 10 to 13 and wrote R4-5a through R4-5e.

**Do not clone a helpdesk.** Peppermint was the closest fit and was **archived on 17 July
2026**. Helpin is our exact stack with **six commits in total**. Zammad, FreeScout and
Frappe are whole products in other stacks. Each would be a second application beside
LayaaStat rather than tickets inside it, and Azure Container Apps will not provision in
our subscription anyway.

**Almost nothing needs building for delivery.** LayaaStat already has alert routing with
`slack`, `email`, `webhook` and `ntfy` channels, a delivery cron, a settings screen and
working Resend email. A ticket becomes another thing that fires a route. n8n hangs off the
**existing webhook channel**. Store first, notify second: if n8n is down the ticket is
still safe.

**Abhimanyu's client-versus-product concern was right and LayaaStat already answers it.**
`0002_registry.sql` has `products → tenants → environments`. EduFlow is the product, The
Aaryans is the tenant. The ingest key is **already tenant-bound**, so a ticket sent with
the school's key is already on the school. Two things must be VERIFIED rather than
assumed: that an `eduflow` product and Aaryans tenant exist at all (only `layaa-internal`
is in the seed), and that the **live** key points at that tenant rather than at Layaa's
own internal one, which would look like it was working while filing everything in the
wrong place.

**Web search and crawling cannot take a screenshot.** They fetch public pages and cannot
see a screen behind a login. The page is captured inside the person's own browser instead.

**Raised, needs an answer before R4-5 is built:** a screenshot of an EduFlow screen carries
real children's names, fees and guardians' phone numbers **out of the school's system into
Layaa AI's**. Proposal in R4-5e. This is Abhimanyu's decision, not an implementation
detail.

**Cost is now decision 13 and Part 4a**, a constraint on every part rather than a review at
the end. The rule is the cheapest way to the same result, never a smaller result.

### 2026-08-12 (later still) - screenshots go unblanked, and the Peppermint numbers

**Decision 14.** Screenshots are sent **unblanked**. Abhimanyu's reason is correct: Layaa AI
already holds most of the school's records, so a picture of a screen is not a new category
of exposure. The blanking proposal is dropped and is not to be reopened.

What that decision does **not** settle is where the picture travels, which is a different
question. Email leaves any system we control and stays in inboxes, and LayaaStat's own
`0004_seed.sql` auto-grants every new authenticated user access to the default tenant. So
the full picture is stored in LayaaStat behind its login and **the email carries a link,
not the image**. That is exactly the flow Abhimanyu described, costs him nothing, and keeps
email small for decision 13. Attaching the image to the mail later is one line of config.

**Peppermint, measured rather than described.** Abhimanyu made the fair argument that we
inherit security patches either way, so cloning still puts us ahead. The GitHub API answers
it: **archived and read-only, last code change 21 September 2025** (eleven months before
today, so it was dead long before it was archived), **101 issues open forever**, **licence
reported as "Other", meaning GitHub could not identify the terms**, and **112 MB** of code
for a feature of which we need about a tenth. "Keep it updated" is not available because
there is nothing upstream to update from, so cloning does not move maintenance off us, it
moves 112 MB onto us. It would also fight decision 11, since Peppermint's idea of clients
does not match LayaaStat's product-and-tenant registry.

**Proposal, awaiting a yes, not blocking R4-1:** read Peppermint's code and take its data
model and ticket states, adopt nothing. Free, no licence question, no second login. If
Abhimanyu would rather adopt something maintained, **FreeScout is the honest candidate**
and would be costed properly rather than argued against.

---

### 2026-08-12 - R4-1 and R4-2 built and green (Claude, Opus 5)

Baseline before starting: 3454 passed / 0 failed. After: **3503 passed / 0 failed / 15
credentialed deselected.** Not deployed. No live school data read or changed.

#### The count in the earlier note was wrong, and the real one is better

That note said "16 of 39 areas write audit lines". That was **route files only**. Counting
every module that writes to the database, it was **55 of 75**, and the gap was 20 modules
holding 108 writes. The shortfall was real but smaller than first reported, and it is
recorded here rather than quietly corrected.

#### R4-1 - one shape

`services/audit_changes.py`. Five kinds (`edit`, `create`, `delete`, `bulk`, `none`), each
carrying a `kind` so no reader sniffs keys. `normalise()` translates all eight legacy
shapes; existing rows are NOT rewritten, they are translated on the way out.

**The distinction the whole module exists for:** "the value used to be empty" and "nobody
wrote down what the value was" were byte-identical in every legacy shape. Every canonical
field now carries `previous`, `new` AND `previous_known`.

`undo_service` now asks it instead of hand-checking one shape, which made undo both
**wider** (`before`/`after` and nested `previous_state` rows carry a real previous value
and are now reversible) and **more honest** (new-values-only rows are still refused,
because writing None back would ERASE rather than restore). It also fixed a refusal
message that named the words "before" and "after" back to the user as if they were fields.

`routes/audit.py` adds `changes_normalised` and `changes_summary` beside the untouched
original, so the screen stops rendering an unrecorded previous value as a blank that reads
like "it used to be empty".

#### R4-2 - everything is recorded, and the gaps are published

`services/audit_coverage.py` gives **every** writing module a verdict: RECORDS or EXCUSED
with a written reason. There is no third state, and
`test_audit_coverage_r4_2.py::test_every_writing_module_has_a_verdict` fails on a module in
neither list, so a new gap cannot be added without somebody writing down why.
`test_the_register_is_published` prints the whole picture including gaps. **Counts are
printed, never asserted** - a pinned number goes stale and is then read as a target.

Now: **64 modules record, 15 excused, 0 undecided.**

Closed: campus operations (23 writes, the largest gap: rooms, equipment, stock, purchasing,
library), staff messaging, Razorpay school fees, operator provisioning, payroll, quizzes,
enquiries, file deletions, the AI kill switch.

Excused with reasons: token counters, confirm tokens, refresh tokens, idempotency, AI rate
counters, AI metrics, shadow mode, the plan executor, Flo's four memory stores, notifications,
generated summaries, and SMS.

#### Two things worth knowing

**Payroll was already audited, by its routes, not its service.** Adding a service-level row
would have made every salary change appear twice in the school's history and counted twice
in Aman's digest. The audit moved INTO `payroll_service`, the one shared path REST and Flo
both use, and the five route-level and AI-level copies were removed.

**A parity test caught a real bug.** `test_salary_correction_ai_and_rest_have_same_state`
failed because Flo still wrote its own correction row while the screen did not, so Flo
appeared to correct somebody's pay twice. That test earned its keep.

**Sending a message is deliberately NOT audited**, but **editing one is**. A message row is
already the record of what was said; an edit REPLACES it, so without a record the earlier
wording is gone with no sign anything changed. Same reasoning for uploads: the upload is
its own record, the deletion is not.

**Left.** R4-3 (two-year retention) next. Nothing is deployed.

---

### 2026-08-12 - R4-3, R4-4 and R4-6 built and green (Claude, Opus 5)

Backend **3579 passed / 0 failed / 15 deselected** (baseline was 3454). Frontend **771
passed**. Production build and lint clean. Not deployed. No live school data touched.

#### R4-3 - two years in full, a monthly summary forever

`services/audit_retention.py`. **The rule that decides the whole design: summarise,
verify, THEN delete.** Read the month, write the summary, read the summary back and
confirm it landed, and only then remove the detail. The audit writer elsewhere is
deliberately fail-open, and fail-open plus delete-first is exactly how a year of records
would vanish with nobody noticing until they went looking.

Decisions worth knowing: the cutoff steps back whole calendar years, not 365 days, so the
boundary cannot drift a day per leap year and eventually eat a live month. Dates compare
as text, so an unreadable value only reaches the plan when it sorts BELOW the cutoff; one
sorting above reads as recent and is kept in full, which is the safe direction. Oldest
month first, so an interrupted run leaves a clean boundary. Idempotent. A summary holds
counts, not copies, which is what makes "forever" affordable.

**The thinning writes its own audit row.** History that quietly shrinks is the same
failure as history never written.

Two routes, deliberately separate: `plan` looks, `run` acts and defaults to ONE month.
Owner only, not the principal, because decision 5 keeps Aman's changes out of Adesh's
view and a principal who could thin the trail could remove those very entries. Both
declared ABOVE `/{record_id}`, which matches any single segment and would otherwise have
answered them as a record lookup, 404ing in a way that reads like the feature was never
built.

#### R4-4 - undo what hurts, guide the rest

`services/undo_scope.py`. **Eligibility is always two questions, never one:** is this the
kind of change that hurts, and may THIS person make that kind of change at all. A fee
entry hurts, so it is undoable, but the management head may not touch money - with only
the first question, undo would have become a back door into fees for exactly the person
the Release 2 table keeps out, and it would have looked like a feature. The second
question is answered by that same table.

Seven kinds are on the list, each with a written reason. `guidance()` turns a recorded
change into the exact values to type back, and returns **no steps at all** when it cannot
be specific: a confident instruction built on a value nobody wrote down would send
somebody to overwrite a good value with a blank, and they would trust it because it came
from the platform. Fields with no recorded before value are named out loud beside the
steps that do work.

Fixed a real gap in the R4-1 reader on the way: a row carrying a real before value for
some fields and only a new value for others was rejected whole, so a half-reversible
change became entirely irreversible.

#### R4-6 - honest menus, one layout

Teachers, students and guardians are in the permission table. Lists copied verbatim from
the old hand-written menus; a test asserts screen for screen that **nobody gained or lost
one**, they hold no Flo domains, `may_write` stays False, and all three are dormant.

One layout replaces three. Each hub's own screen leads its own tab, because
`groupToolsIntoHubs` matches a hub's MEMBER screens and not the hub itself, so hub screens
would otherwise have fallen into "More" or vanished.

**Two real bugs, both found by tests, both mine.**

1. The auto-open effect depended on the whole layout object. That was a stable module
   constant for the owner, so it settled; once every layout became derived it was rebuilt
   each render, and the update always allocated a new Set, so state changed identity every
   time. **An endless render loop that hangs the page rather than erroring.** Now keyed on
   the group id string with a no-op update when already open.
2. **Teachers lost their attendance and results downloads.** The export gate fell through
   to an explicit role list precisely because teachers had no profile; giving them a
   dormant one meant the dormant-profile refusal caught them and two working features
   started answering 403. A menu change had quietly removed a feature, which is the exact
   failure this release exists to end. The explicit grant is asked first now.

Pinned profile counts moved nine to twelve and dormant five to eight, in both sweeps, each
with the reason beside the number.

**Left.** R4-5 only. It reaches outside this repository (LayaaStat, and an n8n workflow),
so it needs its own run. Nothing in Release 4 is deployed.

---

### 2026-08-12 - R4-5 built and green (Claude, Opus 5)

Backend **3608 passed / 0 failed / 15 deselected** (was 3579). Frontend **777 passed**,
run three times over because one unrelated chat test failed once under load and then
passed on every subsequent run; it is timing under a heavier suite, not a defect, and it
is written down here rather than left as a number nobody could reproduce. Production
build and lint clean. EduFlow `5474f7e`, LayaaStat `b702c38`. **Nothing is deployed.**
No live school database was read or changed.

#### The two things the plan said to VERIFY. One of them was wrong.

**The ingest key is fine.** It does NOT point at `layaa-internal`. That risk is closed.

**The registry was not the shape the plan assumed, and this is exactly why it said to
check.** The Aaryans existed in LayaaStat as **its own PRODUCT** (`eduflow-the-aaryans`),
sitting BESIDE EduFlow rather than underneath it, and the live key filed everything under
the EduFlow product's own tenant, which was called "EduFlow". So a ticket today would
have landed on the product wearing a client's clothes. One level shallower than feared,
and the same shape of fault.

Abhimanyu chose to make The Aaryans a proper tenant of EduFlow. Done, and done by
**renaming** the existing tenant rather than minting a new one. A new tenant would have
been the obvious move and the wrong one: it would have split the school's history in two.
The rename keeps the live ingest key, 11,342 events, 154 spans, 13 alerts and the email
alert route all attached and correct, and needed **no key rotation and no restart**.

**Not done, and not to be done blind:** the duplicate `eduflow-the-aaryans` product still
exists and **holds 376,220 notification rows** plus 4 incidents and its own ingest key, on
a tenant with no events at all. Deleting the product cascades and takes all of that with
it. That number also looks like something ran away, and is worth understanding before
anything is removed. Waiting on Abhimanyu.

Two other corrections to the plan's facts, found by reading rather than assuming.
**LayaaStat runs on AWS Amplify** (`ddsqdblq9ge74`), not Vercel. And the ingest key prefix
is `lyk_`, matching the real SDK; the `lsk_live_` in the onboarding document and in
EduFlow's own client docstring is the stale one.

#### What was built

**One path, not two.** `services/platform_ticket_service.py`; the button and Flo both go
through it, pinned by `parity/platform_ticket_parity_test.py`. It is a third kind of issue
in the tracker that already exists, not a second tracker beside it.

**Store first, send second, and that ordering is the design.** The ticket is written down
and audited BEFORE anything leaves the school. A delivery that fails is a delivery to
retry, never a report that never existed, and the person is told which of the two happened
in plain words. "Saved here, but it has not reached Layaa AI yet" is a real outcome and
wears an amber mark rather than a tick. This platform has told somebody the opposite of
what happened twice: the bulk messaging route that recorded every recipient as
`not_configured` and returned success, and the staff message send that answered 500 for a
message it had already saved.

**No role gate on raising one, and that is a decision.** Owner down to student. The person
most likely to be first to see a screen that will not load is whoever was using it. Reading
other people's reports IS gated, and a student gets their own empty list rather than a 403,
because refusing the whole screen teaches them the feature is not for them.

**The judgement lives where Flo reads it.** `WHEN_NOT_TO_RAISE` is quoted into the tool
description rather than typed twice, and `tried` is REQUIRED at the chat gate. A report
that does not say what was already attempted makes us start from the beginning, and
requiring it is the cheapest way to stop tickets for things the receptionist could have
fixed in ten seconds.

**The storage watch rides on the heartbeat loop** rather than starting a second one, checks
once a day against figures MongoDB already keeps, and reports at most once per problem
rather than once per check. Two things it deliberately will not do: it will not report
"could not measure" as "fine", and it will not invent a threshold. With no ceiling
configured it gives the number and says it cannot judge it. Set `STORAGE_CEILING_MB` to
the plan's real limit and it starts speaking up at seven tenths.

**Nearly nothing new at the LayaaStat end.** The registry, the login, the alert routes, the
delivery cron, Resend and the storage buckets all existed. A ticket became one more thing a
notification can be about. The email carries a LINK and never the picture.

**n8n is live**, workflow `zGBva8cGLZybDhEh`, webhook
`https://qwe123qwe.app.n8n.cloud/webhook/layaastat-ticket`, emailing Abhimanyu and Shubham
through the Gmail credential that already exists. No new paid service anywhere in R4-5.

#### Guards that fired, each answered rather than silenced

Adding one write tool and one read tool moved five pinned things. `report_platform_problem`
is `shared`, because a broken fees screen is still a fault and the management head must be
able to report it. It joined `EXPLICIT_CONFIRMATION_TOOL_NAMES` for a **fifth reason that
is new in kind**: it is the only tool that sends anything OUT of the school, and somebody
must be able to tell "Flo helped me" from "Flo told my supplier what I was doing". The read
tool was renamed from `check_storage_room` to `get_storage_room` because the verb-prefix
guard was right to object.

**No literal `requires_confirmation` in the registry entry.** The loop at the foot of
`tool_functions_v2.py` assigns it, so a literal `True` would have been overwritten with
`False` while still reading as authoritative. That is precisely how `import_data_file` lost
the confirm card its own description promised.

#### Left, and none of it is code

1. **Run `supabase/migrations/0052_tickets.sql` by hand** in the LayaaStat SQL editor. Every
   migration there is applied that way; the Supabase connector cannot reach that project.
2. **Set `LAYAASTAT_PUBLIC_URL`** on the LayaaStat Amplify app, or the email arrives with no
   link and says so.
3. **Add a `webhook` alert route** for The Aaryans pointing at the n8n address above.
4. **Deploy** both, then **watch one real ticket travel the whole way**. Until that has been
   seen, this is built, not working.

---

### 2026-08-13 - R4-5 proven as far as it can be, and what it cost

**The route works.** A real ticket travels: the school's key is accepted, LayaaStat
stores it, a re-send lands once rather than twice, the alert route fires, and the n8n
workflow receives it with the correct link. The ONLY hop not yet seen working is the
final email, because n8n's Gmail sign-in has expired and only Abhimanyu can renew it.

#### Three faults, none of which any test could have caught

Every one lived outside the code the tests call, which is exactly why the plan insisted
on watching a real ticket rather than trusting a green suite.

1. **The endpoint was behind the login wall.** `/api/tickets` carries its own key, like
   `/api/ingest`, but was not in `PUBLIC_PREFIXES`, so a machine POST got a redirect to
   the sign-in page. The route tests call the handler directly and never touch the
   middleware, so all eight passed while nothing could reach it. **A route test proves
   the handler, not that anything can get to the handler.**
2. **Every insert failed with a bare 500.** The idempotency index was written PARTIAL
   (`where external_ref is not null`) and Postgres will not infer a partial index for
   `on conflict`. It never needed to be partial: NULLs are already distinct in a unique
   index. Migration 0053.
3. **The link in the email was wrong twice before it was right.** First it said "no
   dashboard address is configured" although the variable WAS set, because Amplify hands
   server-only variables to the build and not to the running function. Then the fix for
   that emailed a link to `localhost:3000`, because behind a proxy the function is handed
   the request on an internal address. **The second version was worse than the first: a
   broken link looks like it should work, a missing one does not.** Now resolved from the
   forwarded headers, with a localhost address refused outright rather than sent.

#### The database was rebuilt, and that is on me

The old LayaaStat Supabase project **ran out of disk and stopped answering**. On the free
plan the disk cannot be enlarged and there are no backups, so it could be neither repaired
nor copied, and it was replaced by a fresh project (`jwttleaqpcfsqmblolqw`).

**What tipped it over was mine.** Writing off 405,000 quarantined rows with an UPDATE made
Postgres write a second copy of every one of them, which is how Postgres updates work, and
that duplicated the largest table in a database already at its limit. A DELETE would have
been a fraction of the cost. **Check free space before a bulk write, and never UPDATE where
a DELETE will do.**

**What had already put it near the limit was not mine, and is the more useful finding.**
Two runaways nobody had noticed, roughly 780,000 junk rows between them:
- Four incidents imported from EduFlow in May were never closed, and the notification job
  re-enqueued all four EVERY MINUTE against a tenant with no alert route, each instantly
  skipped and written again. 376,000 rows, still growing after two months. Closing the
  four incidents stopped it in one minute.
- A month of AI spans quarantined by the already-fixed `service_id` bug. 405,000 rows,
  stopped on 7 August, never cleared.

Both are absent from the new project. **The lesson: a job that writes on a timer needs a
stopping condition, and a quarantine table needs something that eventually empties it.**

**Lost:** all telemetry history, deliberately, as the alternative was paying to keep charts
of a period when the reporting was half broken. **Not lost:** anything about the school.
The registry was rebuilt, and the ingest key was recreated from the SAME raw key the live
EduFlow server already holds, so **nothing at The Aaryans changed and nothing restarted.**

EduFlow is sending to the new database and it lands under The Aaryans. Zero rejected
records, where the old one had 405,000.

#### Left

1. ~~**Abhimanyu reconnects the Gmail credential in n8n.**~~ **Superseded 2026-08-14:** the
   email goes through Zoho Mail instead. See `ticket-email-via-zoho-2026-08-14.md`.
2. **Deploy EduFlow's backend**, which is the only way the button inside the school's
   platform starts working. Not done: it touches the live platform and needs his say-so.
3. **Delete the old Supabase project** once 1 is confirmed.
4. **The Resend key is dead** (403, invalid) and has been for a while, so LayaaStat's
   direct alert emails have been failing silently. Not caused by any of this, and worth
   renewing.

---

### 2026-08-13 - shipped, and a credentials leak that is not yet fully closed

**Deployed.** Backend `eduflow-release4-20260813-fec72a7`, environment green, every new
route answering 401. Frontend merged to `main` and built as Amplify job 147.

**The order was deliberate: backend first.** Merging to `main` deploys the frontend by
itself, so doing it the other way round would have put a "Report a problem" button in
front of the school with nothing behind it. That is the exact fault Release 4 exists to
remove, so shipping it during Release 4 would have been the wrong way round.

Gate at the time: 3,608 backend tests and 777 frontend tests passing, build and lint clean.

#### A scratch file holding secrets was committed and pushed to a PUBLIC repository

A small working file holding LayaaStat's database address, its secret key and the shared
secret guarding LayaaStat's scheduled jobs was written **inside the repository**. A blanket
`git add` swept it into a commit and it was pushed. EduFlow_v2 is public, so those values
were briefly readable by anyone.

Done: the file is removed, it is in the ignore list (`59da86b`), the branch history was
rewritten and force-pushed, and the rest of the tree was checked for anything else
sensitive. **None of that is a fix.** The old commit is still reachable on GitHub by its
id, and a public repository can be copied or cached by others, so the only real fix is
changing the values.

Asked of Abhimanyu, and still open at the time of writing:
1. **Rotate `CRON_SECRET` on the LayaaStat Amplify app.** This is the live one and it
   guards the jobs that send notifications. Cannot be done from here.
2. **Delete the old Supabase project.** The other leaked key belongs to it, so deleting
   the project makes the key worthless. This was already on the list as tidy-up; the leak
   moves it to worth doing today.

No school data was in the file, and both values belong to an internal monitoring tool
rather than to anything of the school's. That limits the harm; it does not excuse it.

**The rule, so this cannot recur: never write a secret to a file inside a repository, not
even a scratch one, and never `git add` without looking at what is being added.** Read
credentials fresh from their source each time they are needed.

#### Left after this release

1. **Ticket email moves to ZOHO MAIL, not Gmail** (Abhimanyu, 2026-08-14). "Reconnect
   Gmail" is dead and must not be carried forward. Instruction sheet, including the two
   things blocked on him: `ticket-email-via-zoho-2026-08-14.md` in this folder.
2. **Rotate `CRON_SECRET`** (above). **The old Supabase project is DELETED**, done by
   Abhimanyu on 2026-08-14 and confirmed here: it no longer appears in the account, and
   the live project kept ingesting straight through with zero failed writes. That kills
   the leaked database key. **It does NOT touch `CRON_SECRET`**, which was the third line
   of the leaked file, is not tied to any Supabase project, and is still live.
3. **Delete the Resend route.** No longer a decision: with ticket email going through Zoho,
   nothing needs it, and its key has been dead with a 403 for a while so those alerts were
   failing in silence. A configured but dead sender reads as working, which is worse than
   none.
4. **Give LayaaStat a proper address** such as `stat.layaa.ai`. Can be done without
   Abhimanyu.

### 2026-08-14 - the old LayaaStat database is deleted

Checked before it went, rather than after. The old project was `ojfqroafgxcipjxbzgfi`,
named "Monitor Dashboard", in a different Supabase organisation from the new one.

Four things were confirmed first:

- **Nothing pointed at it.** No reference to the old address survives anywhere in the
  LayaaStat tree. EduFlow never spoke to the database at all, only to LayaaStat's web
  address, so it was unaffected either way.
- **The new project was genuinely doing the job**, not merely existing: events arriving
  the same morning, zero rows in `failed_writes`, and the registry, the school's ingest
  key and the alert routes all present.
- **Nothing was recoverable from the old one.** It refused connections outright
  (`the database system is not accepting connections`), which is the disk-full state it
  died in. The only loss is the old telemetry history, already a recorded decision.
- **The leaked key really did belong to the OLD project.** This was checked by reading the
  leaked blob, which still exists locally, rather than trusting the earlier account. Worth
  the two minutes: the leak happened on 13 August and the rebuild on the 12th, so the
  values could plausibly have been the NEW project's, in which case deleting the old one
  would have fixed nothing while leaving the live database exposed.

**The leaked file had three lines, not two.** The third is `CRON_SECRET`, which guards
LayaaStat's scheduled jobs, belongs to no Supabase project, and is untouched by the
deletion. It is still live and still exposed until rotated.

After deletion the live project was re-checked: still healthy, still ingesting, zero
failed writes, one active ingest key.

**Also still true and easy to misread as fixed:** the commit holding the leaked file is
still in the LOCAL clone, so the values remain readable from this machine despite the
history rewrite. GitHub could not be reached from here to see whether it is still served
publicly, so assume it is.

### 2026-08-14 - ticket email is fixed and the route is unbroken end to end

Item 1 of "Left after this release" is **DONE**. The Gmail step that had been failing
silently is gone; the email now goes out through Zoho Mail from `support@layaa.ai` to
Abhimanyu and Shubham. Full detail, including the credential and what was verified, is in
`ticket-email-via-zoho-2026-08-14.md` in this folder.

The proof is a real send, not a green screen: a POST to the production webhook returned
200 and n8n execution `5` finished `success`. The two attempts on 12 August both ended in
`error`. **What is still outstanding is a human confirming the message reached the inbox
rather than a spam folder.** Until that happens, do not describe ticket email as working.

Items 2 to 4 are unchanged: `CRON_SECRET` on LayaaStat is still exposed and unrotated, the
dead Resend route is still there, and LayaaStat still has no proper address.

**Confirmed the same day:** Abhimanyu received the test email. Ticket email is working.
Shubham's copy is unconfirmed and worth one question, since both addresses ride on the
same send.

### 2026-08-14 - the dead Resend sender is gone from the code

Item 3 of "Left after this release" is **done in code, committed on LayaaStat as
`13fc674`, and NOT yet deployed.** Types, lint and all 165 LayaaStat tests are clean.

The `email` channel in LayaaStat's notification dispatch used to POST to Resend. Its key
had been answering 403 for a long while, so those alerts were failing in silence while
the channel still read as configured. The branch now returns a plain "channel retired"
reason instead of pretending to send, and `RESEND_API_KEY` / `ALERT_EMAIL_FROM` are out
of the environment list because nothing reads them. If they are still set on the host
they are inert and should be deleted there too.

**Two things found while doing it, both worth knowing.**

**LayaaStat runs on AWS Amplify, app `ddsqdblq9ge74`, not on Vercel.** An earlier note in
this session said Vercel because the repository carries a `vercel.json`. It is wrong, and
it matters: **`CRON_SECRET` must be rotated in the Amplify console**, not in Vercel. The
Vercel account holds one unrelated project called `timetable`.

**There is still one enabled `email` alert route in the live LayaaStat database**, id
`41303e25-e227-4a55-9b19-6f0d67a76d48`, pointing at `hello@layaa.ai`. It was left
untouched on purpose. After this change it records an honest skip reason instead of a
silent 403, so nothing is hidden, but it delivers nothing either. **Deciding whether to
switch it off or point it somewhere real is Abhimanyu's.** The `webhook` route beside it
is the one that reaches n8n and now works.

### 2026-08-14 - the proper address for LayaaStat is BLOCKED on permission

Item 4 cannot be done from here. `stat.layaa.ai` does not exist yet, and the deploy
identity (`claude-hosting`) is refused both `amplify:CreateDomainAssociation` and every
Route 53 read. The domain `layaa.ai` is served by AWS name servers, so if its hosted zone
sits in the same AWS account, Amplify will write the DNS records itself and the whole job
is a two minute form in the console. Steps are in the handover message of 2026-08-14.

**Do not widen IAM for this.** A 2026-08-08 session lost a day widening permissions for
what turned out to be the wrong login, and this is a one-off task better done by hand than
by granting a standing power.

### 2026-08-14 (later) - the address is being activated, and the secret rotation is dropped

**`stat.layaa.ai` is set up** on the LayaaStat Amplify app, branch `main`. The certificate
was issued and configured; only the content network propagation was outstanding at the
time of writing, which Amplify gives as up to thirty minutes. Item 4 is effectively done.

Nothing needs changing in the code for it. The route that builds ticket links works out
the site's address from the request it is handed rather than from a setting, so it starts
writing `https://stat.layaa.ai` links by itself once the address answers.

**Rotating `CRON_SECRET` is DROPPED. Abhimanyu's decision, 2026-08-14.** It is off the
list and should not be raised again as an outstanding task.

Recorded once, plainly, so nobody later mistakes it for an oversight: the value was pushed
to a public repository on 13 August and has not been changed, so it must be treated as
known to others. It is the shared secret guarding LayaaStat's scheduled jobs, which means
somebody holding it could trigger those jobs, including the one that sends notifications.
It gives no access to any school data and none to the school's platform. That is the whole
exposure, it was weighed, and the decision is to live with it.

### 2026-08-14 (later still) - Resend removal DEPLOYED, and the dead email route switched off

**Deployed.** LayaaStat Amplify app `ddsqdblq9ge74`, build 40, SUCCEED, on commit
`13fc674`. Checked against the job list rather than assumed from the push.

**The `hello@layaa.ai` route was investigated before being touched, and the investigation
is the reason it could be switched off with confidence.** What was found:

- **Created by the same insert as the working webhook route**, both stamped
  `2026-08-12 21:34:18.178539+00` to the microsecond. It was part of setting the ticket
  feature up, not a later choice by anybody.
- **It fires on exactly the same events.** Same tenant (The Aaryans), no severity limit,
  no product limit. Every ticket produced one of each, so it was always a duplicate and
  never a distinct audience.
- **It sent to `hello@layaa.ai` from `hello@layaa.ai`.** The recipient in the route and
  the sender in the old environment variable were the same address.
- **It has delivered NOTHING, ever.** Three attempts, all on 12 August, all
  `skipped / http 403`, on test tickets 1, 3 and 4. The webhook route delivered all three
  successfully at the same moments. So no message has ever depended on it and nothing was
  lost.

**Switched OFF, not deleted** (`enabled = false`, id
`41303e25-e227-4a55-9b19-6f0d67a76d48`). Off keeps it visible on the alerting screen and
one click from returning if a second destination is ever wanted; deleting would have
removed the evidence along with the route. The school now has exactly one enabled route
and it is the one that works.

**All four Release 4 leftovers are now closed:** ticket email works and was seen in a real
inbox, the dead Resend sender is removed and deployed, `stat.layaa.ai` is live and serving
over a valid certificate, and the secret rotation is dropped by decision.

### 2026-08-14 (evening) - are messages in the audit trail? Asked, checked, two gaps found

Abhimanyu asked whether messages are recorded in the audit trail, both the ones sent to
families and the ones staff send each other. **Nothing was changed. This is a finding.**

**The answer as designed.** Decision 13 says a write that IS the record is not copied into
the audit trail, and what must still be recorded is anything that CHANGES or REMOVES that
record. So:

| | Recorded? |
|---|---|
| A staff message being sent | No, on purpose. The message row is the record. |
| A staff message being EDITED | Yes, `message_edit`. |
| Changing who is in a group | Yes, `message_thread_update`. |
| A parent message batch being sent | Yes, `send_parent_message` in `messaging_service.py`. |
| Creating or changing a message template | Yes. |
| Fee reminders and bulk sends through `routes/sms.py` | No. `routes/sms.py` is on the excused list. |

**Gap 1: deleting a staff message is not recorded, while editing the same message is.**
`DELETE /api/messaging/messages/{id}` blanks the text and stamps `deleted_at`, and writes
nothing to the audit trail. The only two audit actions in the whole file are the edit and
the group-membership change. That contradicts the rule written into
`services/audit_coverage.py`: a removal is exactly the part the existing record cannot tell
you about itself. The message row survives with an empty body, so the fact of a deletion is
not lost, but **who deleted it and when is nowhere in the school's history.**

**Gap 2: "the SMS log IS the record" holds for ninety days, and the audit trail holds two
years.** `routes/sms.py` is excused because every send writes an SMS log row. That row is
on a ninety-day expiry (`database.py`, `sms_logs`, `expireAfterSeconds=7776000`). So a fee
reminder sent to a family stops being answerable after three months, while every other
recorded change is answerable for two years. The excuse is sound in shape and wrong in
duration, and nobody noticed because the two numbers live in different files.

**Not verified, and do not assume either way:** whether that ninety-day expiry is actually
running on the live system. Index creation is deliberately switched off in production
(`CREATE_INDEXES_ON_STARTUP`), so indexes only reach the live database through a migration.
If the expiry never landed, the reminders are still there and the gap is theoretical. If it
did, three months of history is already gone. **Check before deciding anything.**

Neither gap is urgent and neither was fixed. Both are recorded here so the next person does
not have to find them again.

### 2026-08-26 - Gap 1 is FIXED in code, Gap 2 still needs an index decision

Deleting a staff message now writes `message_delete`, with the full pre-deletion message
snapshot under `changes.snapshot`, alongside the existing `message_edit` audit. The test
pins who deleted the message, when, and what its text had been. The messaging API suite
and the R4-2 audit coverage gate pass.

The SMS retention question remains deliberately open because changing expiry is a live
database/index decision. Before deciding anything, check whether the ninety-day TTL index
actually exists on production `sms_logs`; startup index creation is disabled there.
