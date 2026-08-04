# The school's spreadsheets compared with what is on the platform

**Read-only. Nothing was changed.** This is the report to read before deciding
whether anything gets written to real student records.

Sources: `aaryans_database/Students-22-06-2026-02-35-08.xlsx` (the current export,
22 June 2026) and `aaryans_database/DETAINEES LIST 2025-26.xlsx` (last year's).
Students were matched on **admission number only** — never on name.

## The short version

The platform is essentially already up to date. **1802 of the
1804 students** in the June export are already on it, and **nothing on the
platform is missing from the export.** Only **two** students would be added, and
both of those need a decision first (see below) because they are not really in a class.

What the folder genuinely adds is **detail that is currently blank**: dates of birth,
admission dates, house and gender for roughly 1,200 to 1,550 students each.

## The numbers

| | Count |
|---|---|
| Students on the platform right now | 1802 |
| ...with no admission number recorded (cannot be matched at all) | 0 |
| ...sharing an admission number with another record | 0 |
| Students in the June 2026 export | 1804 |
| Students in the 2025-26 workbook | 1743 |

| Matching on admission number | Count | What it means |
|---|---|---|
| Already on the platform | 1802 | Only their details would change. |
| In the June export, not on the platform | 2 | Would be added. |
| On the platform, not in the June export | 0 | **Nothing would be deleted.** |
| In last year's workbook, gone from the June export | 190 | Presumed left or passed out. **Would NOT be created.** |

## Two things that need your decision before anything is written

### 1. The senior classes have no stream on the platform

178 students in classes 11 and 12 sit in a class the platform
calls just "11th" or "12th", while the school's own export calls the same class
"11th Science" or "12th Commerce". **The section letter matches every single time**, so
no student is in the wrong room. It is purely that the platform does not record the
stream and the school does.

| Platform calls it | The school calls it | Students |
|---|---|---|
| 11th A | 11th Science A | 58 |
| 12th A | 12th Science A | 58 |
| 11th B | 11th Commerce B | 27 |
| 12th B | 12th Commerce B | 21 |
| 12th C | 12th Commerce C | 8 |
| 11th C | 11th Commerce C | 6 |

Three ways to go, and this is your call, not ours:

1. Leave it. The platform keeps saying 11th and 12th. Nothing breaks; the stream
   simply is not recorded anywhere.
2. Rename the six classes to include the stream. Simplest, but it mixes two facts
   into one name, and section A of 11th would become 11th Science A permanently.
3. Record the stream as its own detail on the class. Cleanest, but it is a change to
   how classes are stored, not a data load, and belongs in its own piece of work.

### 2. The two students who would be added are not in a real class

Both sit in a class that does not exist on the platform, and reading its name
explains why:

| Class in the export | Section | Students |
|---|---|---|
| 12TH PASS OUT OLD DUE 25-26 | A | 2 |

That is not a class, it is a **fee-recovery bucket for students who have already
left owing money**. Creating them as current students would put two people who are
no longer at the school onto class lists, attendance registers and head counts.

| Admission no | Name | Father | Mobile |
|---|---|---|---|
| 19968 | VAIBHAV GUPTA | RAVINDRA GUPTA | 8958624013 |
| 211309 | ANMOL | MUKUL TYAGI | 7817953242 |

**Our recommendation: do not add these two.** If their dues need chasing, that is a
fees job, not a student-record job. Say the word either way.

## What would change on the students already there

| Change | Students affected |
|---|---|
| gender: blank on platform, available from the 2025-26 workbook | 1551 |
| dob: blank on platform, available from the 2025-26 workbook | 1375 |
| admission_date: blank on platform, available from the 2025-26 workbook | 1342 |
| house: blank on platform, available from the 2025-26 workbook | 1199 |
| class name gains a stream (Science / Commerce) | 178 |

**No student would move class or section.** Every difference found was the stream
naming described above.

### The blanks last year's workbook could fill

These are the real prize in the folder. Samples:

**dob** — 1375 students
  - 15001 ABHIJOT SINGH RAHAL: 2010-11-13
  - 15006 DEVANK SIROHI: 2009-10-03
  - 15007 ANANT AULAKH (D%): 2011-07-20
  - 15009 LAKSHAY SAINI: 2009-04-25
  - 15014 NUMIT SINGH: 2013-01-19

**admission_date** — 1342 students
  - 15001 ABHIJOT SINGH RAHAL: 2015-03-20
  - 15006 DEVANK SIROHI: 2015-03-28
  - 15007 ANANT AULAKH (D%): 2015-04-20
  - 15009 LAKSHAY SAINI: 2015-04-08
  - 15014 NUMIT SINGH: 2015-04-08

**house** — 1199 students
  - 15001 ABHIJOT SINGH RAHAL: ATULYA
  - 15006 DEVANK SIROHI: AGAMYA
  - 15007 ANANT AULAKH (D%): ATULYA
  - 15009 LAKSHAY SAINI: ATULYA
  - 15014 NUMIT SINGH: ATULYA

**gender** — 1551 students
  - 15001 ABHIJOT SINGH RAHAL: male
  - 15006 DEVANK SIROHI: male
  - 15007 ANANT AULAKH (D%): male
  - 15009 LAKSHAY SAINI: male
  - 15014 NUMIT SINGH: male

### Where the platform and the workbook disagree

Anywhere a student already has a value on the platform and the workbook says something
different, **the platform's value would be kept**. Last year's workbook is not more
trustworthy than what staff have since entered.

## A warning about the dates in last year's workbook

The dates in that workbook are not all real dates. Some are typed text, and some of
that text does not say what it means.

| Column | Real Excel dates | Blank | Day/month order unknowable | Not a date at all |
|---|---|---|---|---|
| dob | 1524 | 134 | 82 | 3 |
| admission_date | 1478 | 1 | 235 | 29 |

The "unknowable" ones are entries like `09.03.2019`, where 3 September and 9 March are
both possible and the spreadsheet does not say which. A wrong birthday is worse than a
blank one — it follows a child through certificates and records. **Those are counted
here and would be left blank, not guessed.** The handful that are not dates at all
(a year typed as "224") would also be skipped.

## Everything that would NOT happen

- No student would be deleted or archived.
- No class or section would be taken from last year's workbook.
- The 190 students in last year's workbook who are gone from the June
  export would NOT be created. A sample is listed below so you can confirm they really
  have left.
- No value already on the platform would be overwritten by the workbook.

| Admission no | Name | Class last year |
|---|---|---|
| 15016 | VINAY CHOUDHARY | 12-B |
| 15025 | SACHI CHOUDHARY | 12-C |
| 15038 | SHUBH CHAUDHARY | 12-A |
| 15039 | NIMI CHAUDHARY | 12-A |
| 15041 | JAYANT CHOUDHARY | 12-B |
| 15051 | RANDEEP SINGH | 12-A |
| 15070 | MOKSH DHARIWAL | 8-A |
| 15071 | DEVANSH CHAUDHARY | 12-B |
| 15073 | HANSHIKA CHAUDHARY | 12-A |
| 15084 | RAJAT CHOUDHARY | 12-A |
| 15105 | HAPPY SINGH | 12-A |
| 15142 | ANSH DHARIWAL | 12-B |
| 16152 | MUKUL PAL | 12-B |
| 16182 | MOHAMMAD HAROON MALIK | 12-B |
| 16233 | NAKSH SINGH | 7-A |
| 16243 | PUSHKAR CHOUDHARY | 12-B |
| 16247 | AKSHI SINGH | 12-C |
| 16258 | PAVNI CHOUDHARY | 12-B |
| 16277 | BHAVANA CHAUDHARY | 12-A |
| 16303 | MOHD. RAYYAN | 10-B |

...and 170 more.

## What we would like from you

1. The stream question above — leave it, rename, or record it properly.
2. Whether the two fee-recovery entries should be added as students. We suggest not.
3. A yes to filling in the blank dates of birth, admission dates, houses and genders
   for the students already on the platform, on the terms above: blanks only, nothing
   overwritten, ambiguous dates skipped.

Nothing will be written until you answer. When you do, it goes in batches, each one
reversible on its own.