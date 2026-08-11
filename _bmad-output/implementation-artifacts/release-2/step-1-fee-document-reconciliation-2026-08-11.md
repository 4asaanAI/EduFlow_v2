# Step 1: the school's fee documents, read against each other

**Written 2026-08-11. Nothing was written to any database. No approval was needed and
none was used.**

**What this is.** Release 2 step 1, from `FINISHING-PLAN-2026-08-11.md`. Nine fee
documents sit in `aaryans_database/`. Three of them had been reconciled and agreed. The
other six had not been read against anything, and the transport file had not been read at
all. This is the result of reading all of them.

**Re-run it any time:**

```
backend/.venv/Scripts/python.exe scripts/reconcile_fee_documents.py
```

That script opens spreadsheets and prints. It touches no database.

**The authority remains `fee-rules-from-sonu-2026-08-11.md`.** Where a document here
disagrees with that one, the disagreement is reported below rather than resolved.

---

## The headline

**The school's fee figures agree with each other everywhere it matters.** Three
independent documents, produced by different reports on different days, give the same
quarterly fee for every one of the seventeen classes, to the rupee. Nothing in the fee
structure is in doubt, and step 3 can be loaded with confidence.

**Two things need a person, and neither one blocks the fee structure.** Both are about
transport, and both are written out at the bottom.

**Three things the finishing plan says are now known to be wrong**, and they make the
work easier rather than harder. They are corrected below.

---

## What the nine documents actually are

| Document | What it really is | Useful? |
|---|---|---|
| `Fees-Structure-06-08-2026-02-49.xlsx` | Empty. One total row reading zero. | No |
| `Fees-Structure-06-08-2026-12-46.xlsx` | Empty. Identical to the above. | No |
| `Fees-Structure-summay-06-08-2026-02-51.xlsx` | One fee head (late fine). A partial save. | No |
| `Fees-Structure-summay-06-08-2026-03-02.xlsx` | The same export finished: nine fee heads, school totals. | Yes, for the head names |
| `Fees-Structure-Report-Summary-06-08-2026-15-02.xlsx` | Class totals for those nine heads. | Yes, for the class list |
| `Students-Fees-Structure-Report-06-08-2026-12-49.xlsx` | **Every child's own quarterly figures.** Never read before. | Yes, this is the rate card |
| `Fees-log-detailed-11-08-2026-17-36.xlsx` | The real payment ledger. | Yes, already trusted |
| `Transport-Fees-Structure-Report-Summary-...pdf` | **Not a rate card.** A per-route collection summary. | Yes, for the route list |
| `Students-06-08-2026-12-08-00.xlsx` | The student export. **Carries the transport rate card in two columns nobody had opened.** | Yes, and this is the find |

The two empty files are worth one sentence so nobody counts them later. **A document that
states no figure neither agrees nor disagrees with anything, and it is not corroboration
either.** Two of the "nine documents to reconcile" were never going to say anything.

---

## 1. The fee structure. Confirmed a third time, class by class

The photographed fee sheet and the payment ledger already agreed on seven bands. The
per-student report is a **third** independent source, and it agrees with the ledger on
every class:

| Class | Per quarter | Per year | Same all four quarters? |
|---|---|---|---|
| NUR, LKG, UKG | 7,050 | 28,200 | yes |
| 1st, 2nd | 8,250 | 33,000 | yes |
| 3rd, 4th, 5th | 8,850 | 35,400 | yes |
| 6th, 7th, 8th | 9,750 | 39,000 | yes |
| 9th, 10th | 12,000 | 48,000 | yes |
| 11th Commerce, 12th Commerce | 16,500 | 66,000 | yes |
| 11th Science, 12th Science | 17,700 | 70,800 | yes |

**Seventeen classes checked. Seventeen agreements. Not one disagreement.**

Two facts fall out of this that step 3 needs:

- **Every class charges the same amount in all four quarters.** There is no heavier
  quarter and no lighter one. The year is simply four equal instalments.
- **The Commerce and Science gap is 1,200 a quarter, so 4,800 a year**, in both 11th and
  12th. That is exactly the figure the finishing plan quotes, now confirmed from the
  school's own per-child figures rather than from the photograph alone.

**The nine charge headings the school's previous system used**, which is the vocabulary
step 3 has to be able to speak:

Composite Fees 1st Q (April to June) · Registration Fee · Admission Fee · Composite Fee
2nd Quarter · Composite Fee 3rd Quarter · Composite Fee 4th Quarter · 2025-26 dues
carried forward · Cheque bounce charges · Late fine.

Registration and admission are charged to new students only, which the per-student report
shows plainly: most children carry "N/A" against both.

---

## 2. Transport: eleven months confirmed, properly this time

**June is not charged. This is now proved rather than assumed.**

| Month | Transport lines in the ledger |
|---|---|
| April | 1,259 |
| May | 1,277 |
| **June** | **0** |
| July | 884 |
| August | 882 |
| September | 892 |
| October | 72 |
| November | 68 |
| December | 68 |
| January | 61 |
| February | 62 |
| March | 62 |
| **Total** | **5,587** |

Eleven months carry lines. June is the only month in the year with none at all. That
matches the fee rules document exactly.

**Worth recording, because it nearly went the other way.** The first version of the
checking script looked for the month in brackets, as `(may)`. The ledger writes it plainly,
as `transport fees may`. So the script matched **nothing** and reported that every month
including June was uncharged, which it then read as "June confirmed excluded". It would
have confirmed the right answer for a completely wrong reason, and the same bug would have
confirmed any answer at all. The script now counts how many lines it failed to place and
says so out loud, and it refuses to draw a conclusion if that number is not zero.

**1,235 children pay for the bus**, confirmed exactly against the ledger. The platform
says none of its 1,876 students uses the bus. That contradiction is step 4's first job.

---

## 3. The transport rate card was in a different file from the one everybody expected

**The transport PDF is not a rate card.** The finishing plan calls it "exactly the missing
transport rate card". It is not. It is 22 pages of per-route collection totals broken down
by class: how much each route billed and collected. **It carries no monthly rate for any
route.**

What it does give is **the route list**, which is one of the four lists on the platform
that is entirely empty: 48 routes, 36 known only by number and 12 by place name (Joya,
Asmoli, Badoniya, Naraini, Ikonda, Gulariya, Devipura, Racheta, Sahaspur Ali Nagar,
Shanti Nagar Amroha, SBI Amroha, WTM Nursing College).

**The actual rate card is in the student export, in two columns nobody had opened:
`Transport` and `TransportFees`.** This is the find of the whole step.

- **1,378 children have a bus route named** against them
- **49 route numbers and 181 distinct stops**, written as `8( - JOYA)`, so a route number
  plus the stop the child is picked up from
- The transport figure is an **annual** one, and for **1,336 of the 1,378 children, 97%,
  it divides exactly by eleven**. Eleven months, June excluded, arrived at from a
  completely different document than the ledger did.
- The 42 children whose figure does not divide by eleven carry small odd amounts. That is
  what a child billed for only part of the year looks like. It is not a second rule.

So the platform can be given the route list, the stop list, the monthly rate and which
child is on which route, all from documents already in hand. **Step 4 does not need to ask
the school for anything.**

---

## 4. Streams: more seniors are already known than the plan thought

| | Senior students with a stream named |
|---|---|
| Payment ledger | 157 |
| Per-student fee report | 189 |
| **Named by at least one** | **189** |
| Named by both | 157 |
| **Put in different streams by the two** | **0** |

**Nothing to resolve.** Where both documents name a child's stream they name the same one,
every single time.

The finishing plan says 158 children are known and that number came from the ledger. The
ledger's own count is 157, and a second document raises the total to 189. **32 more senior
students can be placed without asking the school.** The rest still need the school, and
guessing still overcharges a family by 4,800 a year.

---

## 5. Late fines: consistent with the rule, and not proof of it

1,217 fine lines in the ledger. **Every one is an exact multiple of ten.** None is not.
Eight are exactly 1,000.

That is consistent with "10 a day plus 1,000 at quarter end" and it is **not proof of it**,
which matters. It cannot show whether the 1,000 repeats at each following quarter end,
because the ledger only runs to 7 August and the session's second quarter-end has not
happened. **The repeat rule rests on Abhimanyu's confirmation, given twice and the second
time against a specific number, and on nothing in these documents.** Step 9 should be built
on that and should not claim ledger support it does not have.

---

## 6. The ledger's own headline numbers

The fee rules document describes the ledger as 10,720 fee lines, 3,177 receipts, 1,723
children, 3.56 crore. Counting it again gives 1,708 children who paid something, 3,136
receipts and **3,55,91,948 collected**.

**This is not a disagreement.** It is the same file counted with a slightly different
filter for what counts as a line and what counts as a child. The money agrees: 3.559 crore
against 3.56 crore. Recorded only so that a later reader who counts it a third time and
gets 1,708 does not think something has changed.

---

## What needs a person

Both are transport. **Neither blocks steps 2, 3 or 5**, and neither blocks loading the
transport route list.

### A. The rate card is wider than the rules document describes

The fee rules document says transport runs "roughly 650 to 1,520 a month". The word is
"roughly", so this is not a contradiction, and **the school's two documents agree with each
other**. But the real card is wider:

- **35 distinct monthly rates, from 620 to 1,900**, per the student export
- **22 of those rates were actually billed** in the ledger between January and August
- The bulk sits where the rules document says: 650 alone covers 1,447 lines, and
  everything from 650 to 1,520 covers all but 18 of the 5,587 transport lines

**Why it needs saying rather than just building.** A rate card capped at 1,520 would
undercharge the families above it, and a card starting at 650 would miss the one child at
620. The safe thing is to load all 35 rates from the school's own data, which is what step
4 will do unless told otherwise. **The question for Sonu is only whether 1,900 and 620 are
real rates or old typing**, because five lines were billed at 1,900 and one child sits at
620.

### B. Four ledger lines are billed at a rate no child's record explains

Two rates, **1,170 and 1,680 a month**, appear in the payment ledger but match no child in
the 6 August student export.

Four lines in total, so this is small. The likely explanation is dull: the export is dated
6 August and the ledger runs to 11 August, so a rate could have been corrected in between.
**But it is money, and it was not assumed.** Sonu can settle it in a sentence.

---

## Three corrections to the finishing plan

Each of these makes the remaining work smaller.

1. **The transport PDF is not the rate card** (plan step 4, and the session entry of
   2026-08-10 which called it "exactly the missing transport rate card"). It is the route
   list. The rate card is in the student export.
2. **189 senior students have a known stream, not 158** (plan step 2). The ledger alone
   gives 157; the per-student fee report adds 32 more, and the two never disagree.
3. **Step 4 needs nothing from the school to load routes and rates.** The plan treats the
   rate card as something to be read out of a PDF. It is already in a spreadsheet, keyed
   to individual children.

---

## Verdict

**Nothing found here stops step 2 or step 3.** The fee structure is confirmed by three
independent documents on all seventeen classes, and the two open items are both about
transport rates at the edges of the card, affecting at most a couple of dozen families.

**Step 3 can be loaded as planned. Step 4 should load all 35 transport rates from the
school's own data and flag the two questions above to Sonu rather than wait on them.**
