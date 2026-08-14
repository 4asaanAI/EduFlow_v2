# What the school's own admission form asks, against what the platform stores

**Read 2026-08-14 from `aaryans_database/`.** Two sources, both the school's own:
the blank admission form they hand to parents (`Admission-form-06-08-2026-12-59.pdf`)
and an export of 102 real enquiries from their previous system
(`Leads-06-08-2026-16-55.xlsx`).

**No family's details are reproduced here.** The counts below are totals only. Those two
files hold real children's names, dates of birth and parents' mobile numbers, and this
repository is public. Do not paste rows from them into any file here, a commit message,
or a prompt.

## The paper form

Header: THE AARYANS, Prem Nagar Joya, Dist Amroha, UP. CBSE, school code 81936,
affiliation 2133014.

It asks for:

- **The application:** class applying for, source, **referred by**, date, signature.
- **The child:** first name, last name, email, mobile, gender, date of birth.
- **The parents, in three columns side by side, mother and father and guardian**, each
  with: name, qualification, occupation, residential address, official address, annual
  income, email, mobile, Aadhaar number.
- **Background:** nationality, religion, category, the child's Aadhaar number.
- **Last school:** name and address, class attended, what that school was affiliated to.
- **Address:** address, city, state, country, pincode.

## What actually gets filled in, across 102 real enquiries

Always or nearly always: name, mobile, father's name (102 of 102), mother's name (101),
class applying for (101), gender (98), date of birth (89).
Often: pincode (82), last name (78), city and state (77), country (75), previous school
(59), the class they were in (46).
Almost never: qualification (2), occupation (0), income (0), Aadhaar (0), religion (0),
category (1), email (0).

Two more things that matter:

- **Source and "referred by" are empty on all 102 records.** The columns exist and are
  never used. Our enquiry screen makes source a required-looking dropdown of five
  options, which produces a number nobody at the school has ever recorded.
- **Every one of the 102 is status "ACTIVE".** Their old system had no funnel at all, one
  status and nothing else. Our eight stages are new to them, which is the point, but it
  also means nobody there has the habit yet.

## The gap that matters most

**The platform's enquiry holds one `parent_name`. The school records the mother and the
father separately, and does so on essentially every record.** So when "Start application"
carries the family across, it carries one of two parents and there is no way to tell
which. Everything else on the paper form is either already on the application record
(date of birth, gender, address, previous school) or is something the school never fills.

The second gap is that the enquiry does not hold the child's date of birth, gender,
previous school or address, even though the school captures all four at enquiry time. So
those get retyped onto the application when they were already known.

## What this does NOT change

The child's Aadhaar number, religion, category and family income appear on the paper
form and are never filled. They are also exactly the kind of detail that carries a duty
of care once stored. Nothing here recommends adding them. If they are ever wanted, that
is a decision on its own, not a form-matching exercise.

## Placed: this goes into A3 (Abhimanyu, 2026-08-14)

Mother and father as separate fields on an enquiry, plus the child's date of birth,
gender and previous school, are **part of A3**. It lands before the screens are merged in
A4, so the merged screen is built once against the finished record rather than twice.

A3 therefore carries two things, not one: the shared vocabulary between the enquiry and
application halves, and this widening of the enquiry record. Both touch the enquiry
service, the enquiry screen, the spreadsheet import, the downloads and Flo's enquiry
tools, so they are cheaper together than apart.

Deliberately still excluded: Aadhaar, religion, category and family income. Never filled
in practice, and adding them is its own decision.
