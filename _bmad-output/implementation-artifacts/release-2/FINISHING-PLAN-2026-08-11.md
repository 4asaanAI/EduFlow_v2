# Release 2: everything still left, in the order to do it

Written 2026-08-11, after the permission work finished and the fee rules were settled.

**What this document is.** The permission half of Release 2 is done, green and largely
live. What remains is the school's fee ledger, and it is a bigger piece of work than the
one-line entry in PROGRESS.md suggested. This breaks it into steps that can each be
finished, checked and stopped at.

**Read alongside:**
- `fee-rules-from-sonu-2026-08-11.md` for how the school actually charges. That document
  is the authority; this one is the order of work.
- `PROGRESS.md` for what is already done. Still the only record of progress.

**The standing rules do not change.** One step per run. Suite green before the next.
Every number that moves gets explained. Nothing is written to the live database without
a rollback file saved first.

---

## Where Release 2 stands

| | |
|---|---|
| **Done, green, and on the branch** | R2-1 to R2-13, R2-15 to R2-18. Every permission sub-part. |
| **Done and LIVE on the school's database** | R2-11, the two office logins renamed. That is the only thing that has touched production. |
| **Not done** | The fee ledger, R2-19, the deploy, R2-14 handover. |
| **Not shipped** | Everything else. 34 commits on the branch, nothing deployed. The live platform still behaves as it did before this work began. |

---

## The eleven steps

Steps 1 to 8 are the fee ledger. They are ordered so that each one is useful on its own
and nothing depends on a step that has not happened.

### Step 1. Reconcile the nine fee documents

**No approval needed. Writes nothing. Do this first.**

Nine fee documents sit in `aaryans_database/`, several of them near-duplicates saved an
hour apart on 6 August, plus the detailed payment log of 11 August and the photograph of
the school's official 2026-27 fee sheet.

Three are already reconciled and agree: the photographed sheet, the payment log's own
per-class amounts, and the seven sibling concession values already on the platform. The
remaining six have not been read against them, and the transport rate card
(`Transport-Fees-Structure-Report-Summary-06-08-2026-16-58.pdf`) has not been read at all.

**Output:** one short note saying which documents agree, which disagree, and about what.
Any disagreement goes to Abhimanyu before step 2 begins.

**Size:** half a day.

---

### Step 2. Split 11th and 12th into Commerce and Science

**Writes to the live database. Small, and easy to undo.**

The school charges the two streams 4,800 a year apart. The platform has one 11th and one
12th and no stream field on a class.

Create the four class records, add `stream` to the class record, and put every child on
the right one.

**What is known and what is not.** The payment ledger names the stream for **158 senior
students** who have paid something, which is evidence from the school's own records. The
rest are not known and must not be guessed: putting a Commerce child on the Science band
overcharges the family by 4,800 a year.

**Needs from the school:** the stream for every 11th and 12th student not in that 158.

**Size:** half a day once the list arrives. Do the 158 first; they are not blocked.

---

### Step 3. Load the fee structures

**Writes to the live database. Approved by Abhimanyu already.**

Seven bands, quarterly instalments, plus registration and admission charges for new
students only. Every figure confirmed twice over, by the photographed sheet and by what
the school actually charged in the ledger.

`fee_structures` is completely empty today, so the rollback is deleting exactly what was
inserted. That makes this the safest large write in the whole release.

**Depends on:** step 2, because Commerce and Science need separate structures.

**Size:** one day.

---

### Step 4. Transport

**Writes to the live database.**

Three things, and the first is a contradiction that has been sitting there since August:

1. **Every one of the 1,876 students is marked as not using the bus**, while 1,235 of
   them are demonstrably paying for it. Fix the flag from the ledger.
2. **Load the routes and the rate card.** Charges run 650 to 1,520 a month by distance,
   and the route list is one of the four lists on the platform that is entirely empty.
3. **Eleven months, not twelve. June is excluded**, confirmed exactly: the ledger holds
   5,587 transport lines and not one of them is June.

**Depends on:** step 1, for the rate card.

**Size:** one day.

---

### Step 5. The concessions

**Writes to the live database.**

Four kinds, all settled in the rules document:

- **Sibling.** Flat per quarter by the discounted child's class band. The seven values
  are already loaded and correct. **Needs step 6 to know who is a sibling.**
- **Employee's child.** 50%. Does not stack with the sibling discount: the employee one
  wins.
- **Paying the whole year by 30 April.** 5%.
- **One-time at admission.** Not a rule but a decision by Aman or Adesh. Must record who
  authorised it and must never repeat in a later quarter.

**The one to be careful with.** The platform has a general discount mechanism already.
These four are not four rows in it: three are rules that must recompute themselves, and
one is a single authorised amount. Building all four as plain discounts would mean
somebody re-typing the sibling discount for 500 children every quarter.

**Size:** two days.

---

### Step 6. Sibling links, and the tag Sonu asked for

**Writes to the live database.**

Sonu asked for a child with a brother or sister in the school to be tagged, with the
other children's admission numbers on the record and on the fee screen.

**The school has already done most of the work by hand.** The remarks column of the
payment ledger carries **414 explicit sibling links across 441 children**, written in the
form `SIB NO - 221858`. That is a stated fact, not an inference.

Beyond those, grouping by father's name and mobile finds 764 children in a family of two
or more. **Those are candidates and must be confirmed by a person**, for two reasons: 111
children who receive the discount today are not found that way, and 787 children have no
date of birth, so which sibling is youngest is often unknown. The youngest pays full, so
that ordering decides who is charged what.

**Shape:** the platform proposes the groups, Sonu confirms them. The confirming is the
useful work, not an obstacle to it.

**Size:** two days.

---

### Step 7. Right to Education

**Writes to the live database. Small.**

**21 children are already marked** in the school's 6 August export, in a column nobody
had looked at, and the school marks them a second time inside the child's own name.
Cross-checked against the ledger and it holds: of the 13 who appear there, not one was
charged a school fee.

They pay **no school fee at all**. If they use the bus they pay transport, and that is
fined normally. This must be its own mark on the child, **not a 100% discount**, or it
starts interacting with the concession rules and becomes reversible by anyone who can
edit a discount.

**Needs from the school:** confirm the 21 are current and complete, and settle admission
number **15067**, whose name says RTE while the flag says no.

**Size:** half a day.

---

### Step 8. Load what has actually been paid

**Writes to the live database. The biggest write in the release.**

The platform records **one payment for the entire school**. The ledger holds **3,177
receipts covering 3.56 crore collected from 1,723 children**, from 23 January to 7 August.

Load the receipts so that every family's balance is real.

**Two things to handle honestly.**

- **The ledger's own summary disagrees with its own rows** on total billed and total
  outstanding. **Money collected agrees to the rupee**, and that is the half being
  loaded, which is why Abhimanyu's instruction to load collections first also disposes of
  this problem.
- **1,844 children already carry fee figures whose own label says they are not the
  ledger.** Once the real numbers land, those two sets will either agree or they will
  not. Where they do not, the school has been looking at figures nobody stands behind.
  Decide what happens to them: most likely clear them, having reported the differences.

**Size:** two days.

---

### Step 9. Late fines. LAST, on Abhimanyu's instruction

**The rule, settled 2026-08-11:** 10 rupees a day from the 16th of the quarter until the
quarter ends, then 1,000 when the next quarter begins. **The daily fine stops there for
that quarter, but the 1,000 repeats at every following quarter end** — four times over a
full year of arrears. Only one daily fine ever runs at a time.

**This is where the previous system is wrong** and must not be copied: it keeps the old
quarter's daily fine running alongside the new one, so two accrue at once and families
are overcharged.

The fine is worked out on the **whole outstanding bill, transport included**. Right to
Education children have no school fee, so theirs is on transport alone.

**Nothing about fines is loaded before this step**, deliberately, so that a wrong fine
never reaches a family while the rest of the ledger is being settled.

**Size:** two days.

---

### Step 10. R2-19: Flo does the same work

Abhimanyu's standing rule: anything done by hand, Flo must do on request, through the
same services, proved by parity tests. Everything in steps 2 to 9 needs that.

**Size:** two days.

---

### Step 11. Deploy, then R2-14 handover

**The deploy.** Runs as the `claude-hosting` IAM user, never the other two. Needs
Abhimanyu's explicit go-ahead. Verify with a brand-new route: 401 proves the new code is
live and still guarded, 404 means it did not ship.

**R2-14, the handover.** Sonu and Lalit are walked through their one-page guides, which
are written and waiting. **And the password decision is raised again**, as recorded:
guessable passwords were an accepted risk while only Abhimanyu held them, and the moment
two more people do, that is worth deciding again on purpose.

---

## What is blocked, and on whom

| Waiting on | What | Blocks |
|---|---|---|
| **The school** | Stream for the senior students not among the 158 the ledger names | Step 2 finishing |
| **The school, via Sonu** | Confirm the 21 Right to Education children, and settle admission 15067 | Step 7 |
| **Sonu** | Confirm the proposed sibling groups | Step 6 finishing |
| **Abhimanyu** | Go-ahead to deploy | Step 11 |
| **Abhimanyu** | What happens to the 1,844 unvouched fee figures | Step 8 finishing |

**Nothing else is blocked.** Steps 1, 3, 4, 5, 9 and 10 can be done with what is in hand.

---

## Honest sizing

About **fourteen working days** of build, plus whatever the school takes to answer the
five items above. Two of those days are the deploy and handover.

**The single biggest risk is not technical.** A wrong fee structure reaches 1,842
families and they find out through a bill. That is why step 1 reconciles before anything
is written, why every write saves a rollback first, and why the fines are held to last.
