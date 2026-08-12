# The Aaryans on EduFlow: what is done, and what is yours to finish

**For:** Aman Litt, Adesh Singh, Sonu Ruhal and Lalit Thomas
**Date:** 12 August 2026
**Hand this over with the logins.**

---

## The transfer is finished

Everything the school gave us is on the platform. Every record that could be checked has
been checked and loaded. What remains is a short list of things only the school can enter,
because the information has never existed in any file, or because the file that held it
was wrong often enough that copying it would have put a wrong figure on a real person's
record.

**Nothing on the list below is waiting on us, and none of it needs to come back to us.**
Each one is something your office can do on the platform itself, and Flo will point at
most of them as you work.

---

## What is on the platform now

| | |
|---|---|
| Children on the roll | 1,842 active, 1,876 records in all |
| Payments recorded | 10,686 lines, 3,146 receipts, 1,718 children |
| Money collected | 3,55,49,158 |
| Discounts given | 52,43,192 |
| Period the payments cover | 23 January to 7 August 2026 |
| Fee structures | all 48 classes, four quarterly instalments each |
| Brothers and sisters linked | 824 children in 377 families |
| Right to Education children | 21, who are never billed a school fee |
| Bus riders | 1,376 children, 48 routes, 185 stops with fares |
| Staff | 88 active, 21 recorded as departed |
| Staff attendance | 7,729 days, 1 April to 1 August 2026 |
| Dates of birth | 1,561 of 1,876 |
| Houses | 1,204 children |
| Logins | the owner, the principal, the accounts head, seven office staff, 88 teachers |

The old fee figures that came from a student export rather than the fee ledger have been
taken off. The platform now shows one set of numbers, and they come from the school's own
receipts.

---

## Your list

### 1. Money, and do these before the next bills go out

**1.1 Admission number 263105 is being overcharged 4,800 a year.** The child's record says
Commerce and their section is a Science section. Open the child's record, set the correct
stream, and move them to a Commerce section if that is what they study.

**1.2 Four senior students have no stream: 211309, 19968, 211511, 17566.** Set each to
Commerce or Science on their record. Until then the platform cannot work out their fee.

**1.3 58 children hold a sibling concession with no brother or sister named.** Your office
gave them the discount in the old system and never wrote down who the sibling was, so the
platform has not carried the concession over. Open each child, add the sibling's admission
number, and the concession returns by itself. The list is in
`_sibling_links.json` under `discounted_with_no_stated_family`.

**1.4 33 families do not follow your own youngest-pays-full rule.** In 17 of them every
child was discounted and nobody paid full; in 16, two or more paid full. One is a group of
eight children, which is more likely two families than one. They are recorded exactly as
your office had them. Correct the ones that are wrong.

**1.5 Three bus points to settle in the fee screens.** Five payments are at 1,900 a month
and one child at 620, against a normal range of 650 to 1,520. Four payments sit at 1,170
and 1,680, which match no child's record. And three children have a stop but no route:
**201153 (SINORA), 242305 (JAMA PUR), 242439 (MOHANPUR)**. Set their route on the
transport screen.

**1.6 132 children owe fees and are on the platform nowhere.** Roughly 69 lakh between
them. They exist only in the old fee report. If you want them chased, add them as students
first, then their balance.

### 2. The buses

**Every one of the 48 routes has a blank driver, telephone number, vehicle number and seat
count.** That was in no file handed over. Fill it in on the transport screen. This is the
one thing a parent asks for when a child is late home, and it is the largest single gap
left on the platform.

### 3. Staff

**3.1 No salary is recorded for anybody.** Not one of the 110 staff records has one, and no
file handed over contained a salary column. Until they are entered, the platform cannot
produce a payslip or a salary report.

**3.2 Qualifications and joining dates.** Nobody has a qualification recorded and only one
person has a joining date. We loaded every address the teacher export carried, which was
twenty. These are quickest to add on each person's own record.

**3.3 29 subjects are still shown against a teacher who has left.** The 21 departed staff
between them hold 29 slots. Reassign them on the subjects screen. We did not guess,
because the only record of who teaches what now is a typed summary of a wall chart that
still lists people who have gone.

**3.4 Put the eleven unrecorded staff on the fingerprint scanner.** Eleven people have no
attendance on more than 80% of days and four have no punch at all across four months, which
almost certainly means they were never enrolled on the device. Until they are, their
attendance is not being recorded, and that feeds leave and salary.

**3.5 Twelve teachers and the care taker still have no login.** That was deliberate. When
you want them to sign in, the office can create their logins on the staff screen.

### 4. Children's records

**4.1 315 children still have no date of birth.** We loaded 501 from your detainees
workbook, but only after testing each one against the age that child's class actually is.
**11 were thrown out because they were impossible** (a fifth-class child who would have
been seven, a sixth-class child who would have been sixteen) and 66 more were left alone
because the workbook and the platform disagree about them. Those figures are why the rest
of the workbook was not copied in blindly. Enter the remaining ones from the admission
files as families come through the office.

**4.2 90 children have no gender recorded**, and **no child has a blood group**. Blood
group was blank for all 1,876 in your own records too.

**4.3 453 children have no photograph and 1,748 have no parent photograph.** Every
photograph that existed anywhere in the handover is already on the platform. No software
change can produce pictures that were never taken.

**4.4 Eight records under the principal's name sit in Nursery D** (263167 to 263174) and
are counted in your Nursery head count. They came through your own export with real
admission numbers, so we did not remove them. Take them off the roll when you are ready;
the platform moves rather than destroys them.

**4.5 Eight details differ between your file and the platform:** six telephone numbers, one
roll number and one address, for 221549, 221617, 242462, 252678, 252701, 252822, 263018 and
263102. We kept what the platform had. Correct any that are wrong on the child's record.

**4.6 Five admission enquiries share a name with a rejected applicant.** They are live and
marked active. Close the ones that are the rejected applicants. The names are in
`_leads_overlap_with_rejected.txt`.

**4.7 Class 1 has no houses.** Every class from 2 upward does, because your detainees
workbook records them. It records none for Class 1. If Class 1 is assigned houses, set them
on the children's records.

### 5. Two settings

**5.1 The current academic year is named wrongly.** It is stored under a code that says
2025-26 and is named 2026-27. It is harmless while only one session is in use, and wrong
the moment anything reads the name. Renaming a live academic year is the school's decision,
so it has been left for you.

**5.2 The timetable is empty, and it was empty in the old system too.** The timetable
export covers 60 class sections and only UKG A has anything in it. Building the timetable
on the platform is a job for the school.

---

## Things you may notice, which are correct

**Staff attendance stops on 1 August.** That is where your four attendance reports ended.
From here the platform records it itself.

**No student attendance exists at all.** The old system never gave us a single day of the
daily register. The platform starts recording from the first day someone takes it.

**Some staff show no subject.** 45 of them do, taken from the platform's own subject
assignments. The rest teach more than one subject or none, so nothing could be filled in
without choosing for them.

**1,807 days of staff attendance are marked neither present nor absent.** Those are days
when the scanner has no record and nobody entered anything. They were deliberately not
stored as absences, because 1,807 unexplained absences against real staff would flow
straight into leave balances and salary.

---

## Where the old figures went

The fee figures that were on the platform before today came from a student export, not from
the fee ledger, and they disagreed with what the school actually collected. They have been
taken off, and a complete copy of all 1,844 of them is kept outside the platform. If anyone
ever needs to know where a number on an old printout came from, it can be produced.

---

*Prepared by Layaa AI, 12 August 2026.*
