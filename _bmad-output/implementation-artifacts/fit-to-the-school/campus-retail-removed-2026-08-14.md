# Campus retail is removed, and the rule that decided it

**Abhimanyu, 2026-08-14:** The Aaryans has no shop. The school does have a canteen, but it
is an **outside vendor renting the space** and running its own business, so what the school
has there is a tenant, not a counter of its own to operate.

**The wider instruction, which matters more than this one removal:** EduFlow carries what
The Aaryans actually needs, and nothing extra that a general-purpose school ERP happens to
ship with.

A screen for a business the school does not run is not harmless. It is a menu entry people
have to learn to ignore, a set of Flo tools paid for on every turn, and a surface somebody
may one day type real numbers into.

---

## What was removed

| | Count |
|---|---|
| Server routes | 8 (product catalogue, cashier shifts, sales, returns) |
| Flo tools | 6 (`create_retail_product`, `delete_retail_product`, `open_pos_shift`, `close_pos_shift`, `post_pos_sale`, `post_pos_return`) |
| Screen | The Retail tab of Commercial Operations, and the three shop tiles on its overview |
| Backend code | About 590 lines across the service, routes, tool registry and prompts |

The hub was renamed from **"Finance & Campus Sales" to "Finance"**, since campus sales no
longer exist.

## What was deliberately KEPT, and why

- **The admissions CRM.** Leads, follow-ups, activities and the pipeline. This is admission
  enquiries, which the school genuinely runs. The name "commercial" made it look like sales
  machinery; it is not.
- **The legal entities.** Read by the accounting-period service, so they are load-bearing
  well beyond this screen.

## What was NOT deleted, and this is the important line

**No school data was removed.** The shop's collections are untouched. Removing a feature
must never remove a school's records: if any rows exist from testing or a demo, they are
still there, and `delete_legal_entity` still refuses to delete an entity holding any of
them rather than orphaning them.

**Not verified, and do not assume either way:** whether the live database holds any shop
rows at all. Nothing here reads the live database. If they are ever wanted gone, that is a
separate, deliberate decision with its own backup.

## How the removal was proved to have hit only what it aimed at

The pinned per-profile reach counts are the alarm for accidental access changes, and they
moved. **That is the alarm working, and this time there is a written reason.**

| Profile | Before | After |
|---|---|---|
| Owner | 165 tools, 104 writes | 159, 98 |
| Principal | 165, 104 | 159, 98 |
| Accountant head | 65, 36 | 59, 30 |
| **Management head** | **101, 60** | **101, 60 (unchanged)** |

Exactly six fewer, all six of them writes, on exactly the three profiles that had them. The
six were finance-classified, which is why the management head never held them, **and his
number not moving is the proof the cut did not catch anything else on its way past.**

## Tests: what changed and what was gained

The shop tests are gone with the shop. Two things were done rather than simply deleting
them, and both are the more useful half:

**A test now asserts the routes are GONE, not merely refused.** All eight answer 404 to the
school's owner. A 404 rather than a 403 is the point: a refused route still exists and can
be widened back by a permission change made for another reason, and a route that is not
there cannot. The same is asserted for the six Flo tools and for the Retail tab.

**Two rules the shop tests were proving got moved onto surviving paths rather than lost:**

- **A closed accounting period refuses a posting.** Proven on a till sale before; now proven
  on an expense. The rule belongs to the accounting period, not to the till, and fees,
  expenses and campus operations all still enforce it.
- **A group legal entity cannot be booked to.** Proven on a till shift before; now on a CRM
  lead. Again the rule is the entity's.

**Two lessons were lost with their tests and are recorded here instead**, because neither
has another exercise in the suite today. From the 2026-08-05 audit: a Flo tool must never
let a raw database error escape to the person, and a batch write must not issue one query
per line.

## Gate

Backend **3,676 passed / 0 failed**. Frontend **793 passed / 0 failed**. Production build
clean including lint. **Not deployed.**

## Still open: other candidates for the same rule

Not touched, and each needs a decision rather than a guess. Put in front of Abhimanyu:

- **The legal entities screen itself.** The school is one trust with one active branch. A
  multi-entity structure with group parents and consolidated reporting may be more than it
  needs. Entangled with accounting periods, so removing it is real work rather than a cut.
- **Procurement and requisitions**, purchase orders with approval decisions and goods
  receipt. Genuine ERP machinery. Whether the school buys this way is a question for them.
- **The word "commercial" itself.** With the shop gone, that screen is admission enquiries
  and legal entities. Naming it Commercial Operations now describes nothing it does.

---

## A second sweep found five leftovers, after the first pass looked done

Abhimanyu asked directly whether it had been removed everywhere including the frontend and
Flo's knowledge. **The honest answer was no**, and asking was worth it. The first pass took
out the routes, the service, the tools and the screen, and left five things behind:

1. **The sidebar still advertised it, in words, on two profiles.** Commercial Operations was
   subtitled "CRM, entities & campus sales" in both the owner's and the admin's menus. **The
   only user-visible leftover**, and the sort of thing that survives because the removal
   happened in a different file. Now "Admissions CRM & legal entities".
2. **Flo still carried the six dead tools in its required-parameter map** (`routes/chat.py`).
   Harmless in itself, since the tools were gone from the registry, but it is exactly the
   half-removed state that makes somebody later think a feature still exists.
3. **Flo's own wording on `delete_legal_entity`** told a person an entity is blocked while an
   "enquiry, product or till shift is booked to it". Two thirds of that sentence described
   things the platform no longer has, and Flo would have said it out loud.
4. **Eight database indexes** for the shop collections. Nothing writes to them any more.
5. **The reason the front desk is kept out of Commercial Operations was written in terms of
   the till**, which no longer exists. See below, because this one is not cosmetic.

## The consequence nobody would have derived: Release 4 (access) just lost its largest item

Release 4 (access) lists **"Split Commercial Operations"** as its biggest single piece of
work. The reason was decision 4: the front desk runs the shop counter, so she should get the
till and nothing else, and the screen had to be split first because giving her the whole
thing would hand the front desk the school's legal-entity records.

**There is no till. That work is no longer needed at all.** What is left on the screen is the
admissions CRM and the legal entities, and neither is front-desk work, so she holds none of
it for a simpler reason and no split is required to keep it that way.

This is recorded here and in `profile_matrix.py` rather than left for somebody to trip over,
because the plan still reads as though the largest item in the next release is outstanding.

## Gate after the second sweep

Backend **3,676 passed / 0 failed**. Frontend **793 passed / 0 failed**. Build and lint
clean. The generated permission mirror regenerated to **no change**, which is the proof that
none of this moved anybody's access.

---

## Renamed: "Commercial Operations" is now "Legal Entities & Admissions"

With the shop gone the old name described nothing the screen does. What is left is the
trust's legal entities and admission leads carrying a value.

**The internal id stays `commercial-operations`.** It is what every permission list, deep
link and saved menu entry points at, so renaming it would quietly take the screen away from
whoever holds it. Only the words on screen changed, in four places: both sidebar menus, the
hub tile and the page heading, plus Flo's own description of the tool.

## Found while renaming, and NOT fixed: two screens do the same job

**This screen's admission leads and the Enquiry Register are the same records.** Both read
and write `db.enquiries`. The hub even labels the Enquiry Register "Admissions CRM", which is
what the other screen's main tab is called.

The difference is that this screen adds a layer on top: a follow-up activity log, an
opportunity with a rupee value and a probability, and a weighted pipeline total.

**Not touched, because it is a decision rather than a tidy-up.** The honest options are to
merge the two, or to keep both and name them so a person can tell which to open. What should
not stand is today's position, where two menu entries lead to the same children under two
names, one of them the same name as the other's tab.

This is the same shape as the duplicate student and staff directories the school's owner had
merged on 2026-08-07: "let's just have a single place with all the information rather than
3 places."

---

## LIVE, 2026-08-14

**Backend `eduflow-noshop-20260814-484135d`**, environment Ready and Green.
**Frontend Amplify job 155 SUCCEED** on the same commit. `main` is at `484135d`, pushed.

**Rollback target: `eduflow-r31a-20260814-d571571`.**

The bundle's file list was compared against the last good deploy before upload: **identical,
240 entries either way.** Nothing dropped, nothing stray swept in.

**Verified against the running system, and this deploy could be verified more strongly than
most.** A removal proves itself better than an addition does:

| Probe | Answer | What it proves |
|---|---|---|
| `/api/health/ready` | 200 | The site is up |
| `/api/commercial/products` | **404** | The shop route is GONE, not merely refused |
| `/api/commercial/pos/shifts` | **404** | ditto |
| `/api/commercial/pos/sales` | **404** | ditto |
| `/api/commercial/entities` | 401 | Still there and still guarded |
| `/api/commercial/crm/leads` | 401 | Still there and still guarded |
| `/api/sms/logs` | 401 | The earlier narrowing is undisturbed |

The 404 and 401 answers together are the point: they prove the shop went and the rest
stayed, in one pass, against the live system rather than off a status page.

**What this does NOT prove**, said plainly so nobody reads more into it: nothing here logs
in. The screen's new name and the missing Retail tab are proven by tests and by the build,
not by a person looking at the live platform. Worth one glance from Abhimanyu.

**No school data was touched by this deploy.** No migration was run.
