# What is still missing on the platform, and what is still sitting in the folder

**Date:** 12 August 2026. Prepared by reading every file in `aaryans_database/` and reading
the live school database (read only, nothing was changed).

> ## ⚠️ MUCH OF THIS WAS LOADED LATER THE SAME DAY
>
> This document is the **survey that came first**. Acting on it, migrations 037 to 043 were
> applied to the live database on 12 August: the whole payment ledger, sibling links, Right
> to Education children, office logins, staff subjects and addresses, student genders, the
> school logo, and the 21 staff departures.
>
> **For what is still outstanding, read
> `implementation-artifacts/release-2/QUESTIONS-FOR-THE-SCHOOL-2026-08-11.md` (revised 12
> August) and the 12 August section of `implementation-artifacts/release-2/PROGRESS.md`.**
> Keep this file for the reasoning behind each decision, not for the current state.

---

## Part A. Data sitting in the folder that is NOT on the platform yet

### A1. The payment ledger. This is the big one.

`Fees-log-detailed-11-08-2026-17-36.xlsx` arrived on 11 August and **has not been loaded**.
The platform holds exactly **one** fee payment today.

This file is the thing the school was asked for in question 10 of the 6 August list and was
said not to exist. It does exist now:

| | |
|---|---|
| Payment lines | 10,720 |
| Receipts | 3,177 |
| Children covered | 1,722 |
| Money collected | 3,56,23,748 |
| Discount given | 52,69,692 |
| Still outstanding on those lines | 10,75,327 |
| Dates covered | 23 January 2026 to 7 August 2026 |
| Payment methods | Cash 5,796 lines, IMPS 4,780, Cheque 144 |

It carries admission number, child name, father name, mobile, class, section, fee head,
amount, discount, balance, payment method, bank reference, receipt number, date, time and
who entered it. A second table at the bottom lists every cheque and bank transfer reference
against an admission number.

**Nothing else in this document matters as much.** Until this is loaded, every fee screen,
every dues list and every parent reminder on the platform is empty or wrong.

### A2. The 136 children who owe fees and do not exist on the platform

Roughly 69.8 lakh of outstanding balance between them. They appear only in the fee reports.
Four of them (the class 12 pass-outs) were added. The other 132 were deliberately held back
until the fee figures settled. The ledger above may now settle them.

### A3. Staff attendance stops on 1 August

7,729 records are loaded, covering 1 April to 1 August 2026. Nothing after that. The four
`Staff attendance` PDFs in the folder are the source and they end there too. Eleven days of
staff attendance are simply not recorded anywhere.

### A4. The SMS history, 10,199 rows

`SMS-Report.xlsx` holds the old system's message history: fee collection alerts (4,158),
general messages (4,104), absence alerts (1,385), present alerts (550). None of it is on
the platform. Honest note: the report has no recipient name or number, only counts and a
type, so it is history rather than usable data. Most rows show 0 sent and 0 failed.

### A5. The timetable, and the honest news about it

`Student-Timetable.pdf` covers 60 class sections. **Only one of them, UKG-A, actually has a
timetable in it.** The other 59 are blank grids with period times and nothing in them. So
the platform's empty timetable is not a loading failure, it is the true state of the old
system.

What does exist is `more staff info.txt`, a subject-and-class allocation by teacher, typed
from the school's notes. That could seed who teaches what, but not when.

### A6. Bus drivers and vehicles

48 routes and 185 stops are loaded with fares. **Every route has a blank driver name, blank
driver phone, blank vehicle number and blank capacity**, and the vehicle list is empty. That
information is in no file in the folder. It has to come from the school.

### A7. Detention list

`DETAINEES LIST 2025-26.xlsx` has 64 sheets. The house column was used and the houses are
loaded. Who was actually detained, and the marks behind it, was not, and there is no exam or
result record on the platform to attach it to.

### A8. Admission form template

`Admission-form-06-08-2026-12-59.pdf` is the school's blank admission form. The platform's
custom-forms area is empty. Low priority.

### A9. Office photographs

`adminstaff.jpg` and the WhatsApp images were used to identify office staff. The photograph
is cut off at the bottom, and it is still not known whether anyone sits below the cut.

---

## Part B. Questions the school has not answered, so data cannot be written

Carried forward from the 6 August list and the 11 August list. None of these are software
faults.

| # | Waiting on | What it blocks |
|---|---|---|
| 1 | Does Class 1 have houses? | 1,204 children have a house, Class 1 has none |
| 2 | The 8 test records under the principal's name in Nursery D | They are still counted in the Nursery roll |
| 3 | Eight real differences: six phone numbers, one roll number, one address | Contact details may be wrong |
| 4 | Which 5 enquiries are the rejected applicants | 5 leads are live that may not be |
| 5 | Are the heavy-pending staff on the fingerprint scanner? | 11 people, affects leave and salary |
| 6 | Contact details for the Accountant and the Receptionist | Two staff records cannot be created |
| 7 | Logins for 21 staff | 22 staff records have no login at all today |
| 8 | Have the 22 missing staff left? | They are still active on the roll |
| 9 | Admission 263105: Commerce or Science? | A live overcharge of 4,800 a year on one family |
| 10 | Stream for four senior students (211309, 19968, 211511, 17566) | Cannot work out their fee |
| 11 | The sibling for 58 discounted children | Concession withheld until stated |
| 12 | 33 families where the fee breaks the youngest-pays-full rule | Somebody's money either way |
| 13 | Are 1,900 and 620 a month real bus rates? | Bus billing |
| 14 | Route for three bus children (201153, 242305, 242439) | No route on their record |
| 15 | Late fine: paying on the 20th is five days or four? | Every late payment |
| 16 | What happens to the 1,844 unvouched fee figures (Abhimanyu's call) | Two sets of numbers on screen |
| 17 | Parent photographs for the other 93% of children | Only 129 of 1,876 exist |

---

## Part C. What is empty on the platform right now

Counted live on 12 August 2026.

### C1. Completely empty, and never used

Daily student attendance (**zero records, ever**), exams, exam results, question paper
results, announcements, notifications, complaints and queries, leave requests, student leave,
assets and asset custody, library titles and loans, inventory and stock movements, purchase
requisitions and orders, expenses and expense budgets, incidents, visitor log, vehicles,
maintenance schedule and vendors, resources and bookings, facility requests, sports teams,
student positions, house points, admission applications, custom forms and responses,
salary structures and salary payments, accounting periods, legal entities, retail and
point-of-sale, CRM activities and opportunities, message templates, platform messages,
approval requests, quizzes and attempts, token balances.

**Zero student attendance is the one to notice.** The school takes a register, and the
platform has no record of a single day of it.

### C2. Barely started

| Area | On the platform |
|---|---|
| Fee payments | **1 record** |
| SMS log | 2 records |
| Assignments | 1 |
| Lesson plans | 2 |
| Certificates issued | 5 |
| Uploaded files | 5 |

### C3. Loaded, but with blank fields inside

**Students (1,876):** blood group blank for every child. Bank details on 21. Aadhaar on 146.
Date of birth missing for 816. Gender missing for 201. House missing for 672. Photograph
missing for 453. Parent photographs on 128.
**Fair warning: nearly all of these are blank in the school's own export too.** Blood group
is blank for all 1,878 rows at source. This is not a transfer failure, it is data the school
never captured.

**Staff (110):** subject, salary, address and qualification are blank for **every single
person**. Joining date on 1. Department on 10. Email on 21. Photograph on 13. The teacher
export does carry qualification, address, joining date and bank details, so some of this
**can** be filled and has not been.

**Guardians (3,725):** no email and no occupation for anyone.

**Classes (48):** no room number on any of them.

**Enquiries (101):** nobody assigned, no parent mobile numbers, no remarks.

**School settings:** no logo on the platform, even though `aaryans_logo.jpg` sits in the
repository root.

**Academic year:** the current session is stored under the code `ay-2025-26` but is *named*
`2026-27`. Harmless today, wrong the moment anything reads the name.

---

## The short version

1. **Load the payment ledger.** It is the one file that unblocks the whole fee side, and it
   has been sitting unloaded since 11 August.
2. **Ask the school the 17 questions.** Most are one-line answers.
3. **Fill in the staff details that the teacher export already carries** (qualification,
   address, joining date, bank).
4. **Get bus drivers and vehicle numbers**, which exist in no file we hold.
5. **Decide about the daily register.** The platform has never recorded a single day of
   student attendance, and that is the biggest empty screen in the product.
