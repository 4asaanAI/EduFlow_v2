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
| R4-1 | One shape for a recorded change | **Done** (not deployed) |
| R4-2 | Everything is recorded | **Done** (not deployed) |
| R4-3 | Two years in full, a summary forever | **Done** (not deployed) |
| R4-4 | Undo what hurts, guide the rest | **Done** (not deployed) |
| R4-5 | Flo watches the platform and can reach us | Not started |
| R4-6 | Honest menus, one layout | **Done** (not deployed) |

Five of six parts built and green. **Nothing deployed. No live school data has been
read or changed.** R4-5 (Flo watching storage, and the ticket route to Layaa AI) is the
only part not started, and it is the one that reaches outside this repository.

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
