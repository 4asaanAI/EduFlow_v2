# Questions for The Aaryans — from the data transfer

*First issued 6 August 2026. **Revised 6 August 2026 (evening)** after the school's replies.*

We have moved the school's records from the old system onto EduFlow. Almost everything went
across cleanly, and most of the original questions have now been answered — thank you. This
revision removes what is settled and lists **only what is still open**.

Nothing below is broken, and nothing has been deleted. Each item is waiting for someone at
the school to confirm what is true, so that we do not guess.

**Please reply against the numbers.**

**The exact records are in a companion file:** `QUESTIONS-DETAIL-with-names-2026-08-06.md`,
which lists every child, teacher and admission number behind each question so your office can
look them up directly. It is kept **separate from this document and out of our code
repository on purpose**, because it contains pupil names — please handle it as you would any
pupil list. This document stays name-free so it can be forwarded freely.

---

## Settled since the first version — no action needed

| Question | Outcome |
|---|---|
| The 30 names with no admission number | Confirmed: they failed the admission test and were rejected. Removed from the list. |
| 28 children on EduFlow but not in the new export | Moved to the **NSO list** — off the roll, still on the daily register, exactly as the school does it. |
| 23 staff missing from the teacher list | 22 remain on the query list; the 23rd was a new joiner and has been added as a teacher. |
| 12 teachers not on EduFlow | **All 12 added.** |
| Three impossible dates | Set to 2021, as instructed. |
| The 4 who passed class 12 and still owe | **Kept**, with a remark and financial year 2025-26, deliberately off the roll and off the register. |
| Who is the Transport Head | Already recorded correctly. Verified, nothing changed. |
| The empty fee-structure export | Closed by decision — the per-student report is used instead. |
| Houses for Nursery, LKG and UKG | Confirmed: the school does not assign houses at that age. Correct as it stands. |
| **Student houses showing as "not recorded"** | **Fixed — 1,204 children now have their house back.** One part still open, item 1. |
| **Children's photographs being publicly viewable** | **Closed.** See the note at the end. |

---

## 1. Houses for Class 1

**Settled:** Nursery, LKG and UKG have **no houses** — the school does not assign them at that
age. Nothing further is needed, and those children will correctly show no house.

**Still open:** whether **Class 1** is assigned a house.

**Where this came from:** the house for every child from Class 2 upward was found in the
school's own `DETAINEES LIST 2025-26` workbook, which carries a HOUSE column on 64 of its
sheets. The sheets for Nursery, LKG, UKG **and Class 1** carry no house at all. For the
younger three that is now confirmed correct; Class 1 is the one we cannot tell.

**What we need:** does Class 1 have houses? If yes, the list. We will not guess, and we will
not spread children evenly across the four houses to make the screen look finished.

*(1,204 children now have their house. The four are almost perfectly even — Atulya 316,
Agamya 299, Aprajit 298, Agrim 291 — which is what told us this was a real allocation rather
than something invented.)*

---

## 2. Eight records under the principal's name are counted in the Nursery roll

**The situation:** eight student records in **Nursery D** all carry the principal's name. The
school has told us these were entered as **test accounts by mistake**.

We have taken them off our question list as asked. But **the records themselves are still on
EduFlow and are still counted in your Nursery head count**, because they arrived through the
school's own student export with real admission numbers — and our standing rule is that we
never delete a person's record on our own judgement.

**What we need:** confirm, and we will take them off the roll. They will be **moved, not
destroyed**, so the record survives if it is ever needed.

---

## 3. Eight records where your file and EduFlow genuinely differ

**You were right to push back on this.** The previous version listed 24 differences. Sixteen
were **not differences at all**: many addresses are stored with a line break inside them, and
the comparison was reading "…IKONDA⏎ROAD NARAN" and "…IKONDA ROAD NARAN" as two different
addresses. They are the same address. That fault is now fixed in our code so it cannot recur.

**Eight are real:** six telephone numbers, one roll number, one address. We have changed
nothing and kept what EduFlow already had.

**What we need:** for each of the eight, which is correct — your file or EduFlow? The list is
in the companion file.

---

## 4. Five admission enquiries share a name with a rejected applicant

We have loaded your **102 admission-form enquiries** onto the platform. Five have the same
name as one of the thirty applicants you told us had failed the admission test.

**What we did:** loaded all five exactly as your own file has them, marked ACTIVE. A matching
name is not proof of a matching person, and overriding a live record on the strength of a name
is the one mistake this transfer has been most careful to avoid.

**What we need:** tell us which of the five are the rejected applicants and we will close
those enquiries.

---

## 5. Two office staff still have no contact details

Unchanged: an **Accountant** and a **Receptionist** appear in your office photograph but not in
the employee list, so we have no telephone number or email and have not created their records.

Also: **that office photograph appears to be cut off at the bottom.** One member of transport
staff was missing from it but did appear in the employee list, so at least one row was lost
below the crop. Please check whether anyone else sits below the cut.

---

## 6. Twenty-one people cannot sign in yet

The nine office staff and the twelve teachers just added have a staff record but **no login**.

They appear in staff lists, can be assigned duties, and their attendance is recorded. They
simply cannot log in, because none of the exports carried a password — and **we will not
invent passwords for real people**.

**What we need:** say the word and we will set up their logins.

---

## 7. Some staff have no attendance being recorded at all

We have loaded **7,729 staff attendance records covering 1 April to 1 August 2026**, with
punch-in and punch-out times, from your four attendance reports.

While doing that we found something the school should know. Every row is in one of three
states, and the third is easy to misread:

| State | What it actually means |
|---|---|
| **Present** | The person's finger was on the scanner. Every single one has a punch time. |
| **Absent** | Somebody went into the software and marked them absent. No punch — a human decision. |
| **Pending** | **Nothing happened at all.** No scanner record, and nobody marked them either way. |

**There are 1,807 "pending" days — about 19% of all rows.**

**We deliberately did NOT store these as absences.** Pending is not an absence; it is a day
that was never completed. Recording it as absence would put 1,807 unexplained absences against
real staff, and those would flow into leave balances and salary.

**The part needing attention:** eleven people are "pending" on **more than 80% of their days**,
and **ten of those eleven are the twelve teachers just added**. Four members of staff have
**no fingerprint punch at all** across the whole four months. The most likely explanation is
that they were **never enrolled on the fingerprint scanner**.

**What we need:** please check whether those staff are registered on the attendance device.
Until they are, their attendance is effectively not being recorded — and that matters for
leave and for salary.

---

## 8. The fee figures — the school's own reports still disagree

**This is the one thing blocking the fee ledger, and it has got broader, not narrower.**

The original question stands: three of your own reports disagree about how much has been
billed, by up to **₹81 lakh** (₹8.69 crore vs ₹7.88 crore vs your class summary's ₹8.02 crore).

We hoped the two new **transport** reports would explain the gap. They do not — and they
disagree with each other as well:

| Source | Transport billed |
|---|---|
| Your per-student fee report (1,468 children charged) | **₹1,61,23,170** |
| Your own transport summary | **₹1,52,20,280** |
| **Difference** | **₹9,02,890** |

So there are now **two separate disagreements**, not one. That points at something in the old
system's reporting rather than a single missing piece.

**The `Ledger-Report` file has also arrived, and it is not what we hoped.** It holds 69,572
transactions — amount, date and who entered them — but **no student name or number anywhere in
it, and no payment method**. It cannot tell us which child paid what, which is exactly what a
fee ledger has to know.

**What we need, and nothing about fees can be written until we have it:**
1. Which children should EduFlow bill — currently enrolled only, or everyone who owes,
   including those who have left?
2. Where does your ₹8.02 crore come from — which children are counted in it?
3. Is there an export listing **payments against individual children**, with the date and the
   method? That is the file the ledger has to be built from.

> **Why we are being this careful.** A fee ledger is not a report that can be quietly
> corrected later. Once it exists, every receipt, every dues list and every parent reminder is
> calculated from it. Loading a figure that three of your own reports disagree about would put
> a number on a parent's receipt that your books do not recognise.

---

## 9. What was NOT a problem after all — parent photographs

The school reported that parent photographs were not appearing on a child's profile. **We
checked carefully and there is no fault in the software.** The screen displays them correctly,
and the photographs that exist do load.

**The real position is that very few exist.** Only **129 children out of 1,876 — about 7% —
have a parent photograph anywhere in the records handed over.** Anyone opening a handful of
profiles would almost certainly see none, because 93% genuinely have none.

**What we need, only if the school wants them shown:** parent photographs for the remaining
children. No change to the software can produce pictures that were never supplied.

---

## 10. Small things, only if convenient

**(a) Which source wins for contact details?** Where EduFlow already had a value and the new
file had a different one, we kept what was already there. Worth knowing: the addresses already
on EduFlow look filled in from a template — 1,802 children share only 489 different addresses
between them — so the school's file may well be more accurate.

**(b) Some class sections exist in the school's system but hold no students** — LKG E and F,
UKG E and F, 1st D, E and F, 4th C, and 12th Science B. Harmless, but should EduFlow show them
as empty sections, or leave them out?

**(c) Science and Commerce students look identical on EduFlow.** The school's system calls the
class "11th Science" and "11th Commerce"; EduFlow calls it "11th" and records the section
separately. Every child is in the right class and section — but the platform cannot currently
tell you which stream a student is in. Should we add that?

**(d) One of your academic-year records is named inconsistently.** The current session is
stored under a code that says 2025-26 but is *named* 2026-27. Harmless today because only one
session is in use, but anything reading the name would report the wrong year. We have not
changed it — renaming a live academic year is the school's call, not ours.

---

## About the children's photographs — now closed

Every photograph brought over from the previous software vendor was stored as a public web
link on that vendor's system. **Anyone with the link could open a photograph of a child — no
login of any kind.** That affected 1,423 children, 13 staff and 256 parents.

**This is now closed.** The school holds its own copy of all 1,692 images, and EduFlow now
issues a **fresh, short-lived, private link** each time a page is opened. Photographs appear
exactly as before, and the platform never gives out the old public address again.

One honest caveat: those images **still sit on the previous vendor's system**, which is outside
our control. If the school wants them taken down there, that is a request to make to the old
vendor. What has changed is that EduFlow no longer points anyone at them.

---

*Prepared by Layaa AI, 6 August 2026. Children's names, phone numbers, addresses and
photographs have been deliberately left out of this document. Ask us and we will send any list
you need through a private channel.*
