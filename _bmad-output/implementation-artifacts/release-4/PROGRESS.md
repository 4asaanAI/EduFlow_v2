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
| R4-1 | One shape for a recorded change | Not started |
| R4-2 | Everything is recorded | Not started |
| R4-3 | Two years in full, a summary forever | Not started |
| R4-4 | Undo what hurts, guide the rest | Not started |
| R4-5 | Flo watches the platform and can reach us | Not started |
| R4-6 | Honest menus, one layout | Not started |

Nothing built. Nothing deployed. No live school data has been read or changed.

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
