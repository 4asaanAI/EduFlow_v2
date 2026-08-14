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
