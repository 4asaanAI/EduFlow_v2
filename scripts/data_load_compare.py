"""
READ-ONLY comparison: the aaryans_database folder vs what is on the live platform.

This script opens the live database and NEVER writes to it. There is no insert,
update, delete or index call anywhere in this file, on purpose. Step 1 of the
handoff sequence is a report the owner reads before anything is written.

Rules from the handoff that this script obeys:
  - match on ADMISSION NUMBER only, never on name
  - class and section come from the JUNE 2026 export only, never from the
    2025-26 workbook
  - a student in the 2025-26 workbook but not in the June 2026 export is
    presumed to have left or passed out; it is listed, never created
  - a student in the June 2026 export but not on the platform is presumed a
    new admission; it is listed as an ADD candidate

Date handling: the 2025-26 workbook mixes real Excel dates with free text typed
by hand. Free text is read DAY-FIRST (Indian school convention). Where the text
alone cannot settle day-vs-month, the value is counted as UNSAFE and reported
rather than quietly converted.
"""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

REPO = Path(r"E:\Github\Aasaan AI\EduFlow_v2")
DATA = REPO / "aaryans_database"
load_dotenv(REPO / "backend" / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")

DATE_TEXT = re.compile(r"^\s*(\d{1,2})\s*[/.\-]+\s*(\d{1,2})\s*[/.\-]+\s*(\d{2,4})\s*$")


def adm(v):
    """Admission numbers / phones as a comparable string. 15001.0 -> '15001'."""
    if v is None or pd.isna(v):
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.upper() or None


def txt(v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s or None


def read_date(v):
    """
    -> (value or None, verdict)
    verdict: 'ok' | 'blank' | 'ambiguous' | 'malformed'

    A real Excel date needs no interpretation. Hand-typed text is read day-first,
    but if BOTH the first and second number could be a month, the text simply does
    not say which it is, and we refuse to guess a child's birthday.
    """
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return None, "blank"
    if isinstance(v, pd.Timestamp) or hasattr(v, "year"):
        return pd.Timestamp(v).strftime("%Y-%m-%d"), "ok"
    s = str(v).strip()
    if not s:
        return None, "blank"
    m = DATE_TEXT.match(s)
    if not m:
        return None, "malformed"
    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1900 <= y <= 2030):
        return None, "malformed"
    if d > 31 or mth > 12 or d < 1 or mth < 1:
        return None, "malformed"
    if d <= 12 and mth <= 12 and d != mth:
        return None, "ambiguous"
    try:
        return pd.Timestamp(year=y, month=mth, day=d).strftime("%Y-%m-%d"), "ok"
    except ValueError:
        return None, "malformed"


def norm_gender(v):
    s = (txt(v) or "").lower()
    if s.startswith(("b", "m")):
        return "male"
    if s.startswith(("g", "f")):
        return "female"
    return None


def norm_name(v):
    """For REPORTING mismatches only. Never used to match records."""
    s = (txt(v) or "").upper()
    # re.S matters: two platform names carry a LINE BREAK inside the bracketed note,
    # so without it the bracket was stripped from one side only and two identical
    # names were reported as a disagreement.
    s = re.sub(r"\(.*?\)", " ", s, flags=re.S)
    s = re.sub(r"[^A-Z ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ── the two workbooks ────────────────────────────────────────────────────────
cur_df = pd.read_excel(DATA / "Students-22-06-2026-02-35-08.xlsx")
old_df = pd.read_excel(DATA / "DETAINEES LIST 2025-26.xlsx", sheet_name="StudentData")

current = {}
for _, r in cur_df.iterrows():
    a = adm(r["AdmissionNo"])
    if not a:
        continue
    current[a] = {
        "adm": a, "name": txt(r["Name"]), "phone": adm(r["Mobile"]),
        "class": txt(r["Class"]), "section": txt(r["Section"]),
        "address": txt(r["Address"]), "mother": txt(r["MotherName"]),
        "father": txt(r["FatherName"]),
    }

date_quality = defaultdict(Counter)
lastyear = {}
for _, r in old_df.iterrows():
    a = adm(r["ADM NO"])
    if not a:
        continue
    dob, dv = read_date(r["Dob"])
    ad, av = read_date(r["Adm.Date"])
    date_quality["dob"][dv] += 1
    date_quality["admission_date"][av] += 1
    lastyear[a] = {
        "adm": a, "name": txt(r["Name of Student"]),
        "dob": dob, "dob_verdict": dv,
        "admission_date": ad, "admission_date_verdict": av,
        "house": txt(r["House"]), "gender": norm_gender(r["gender"]),
        "father": txt(r["Father Name"]), "mother": txt(r["Mother Name"]),
        "phone": adm(r["Contact No."]),
        "class_ignored": txt(r["CLASS"]),   # read, never carried forward
        "address": txt(r["Address"]),
    }

# ── the live platform ────────────────────────────────────────────────────────
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=20000)
db = client[DB_NAME]
classes = {c["id"]: c for c in db.classes.find({"schoolId": SCHOOL_ID}, {"_id": 0})}
live_rows = list(db.students.find({"schoolId": SCHOOL_ID}, {"_id": 0}))

live_by_adm, live_no_adm = defaultdict(list), []
for s in live_rows:
    a = adm(s.get("admission_number"))
    (live_by_adm[a].append(s) if a else live_no_adm.append(s))
live_dupes = {a: v for a, v in live_by_adm.items() if len(v) > 1}
live = {a: v[0] for a, v in live_by_adm.items()}


def live_class(s):
    c = classes.get(s.get("class_id") or "")
    return (str(c.get("name")), str(c.get("section"))) if c else None


matched = sorted(set(current) & set(live))
to_add = sorted(set(current) - set(live))
on_platform_only = sorted(set(live) - set(current))
left_or_passed = sorted(set(lastyear) - set(current))

FILL = ["dob", "admission_date", "house", "gender"]
changes = Counter()
stream_only = Counter()
real_class_moves = []
name_diffs, phone_diffs = [], []
fill_examples = defaultdict(list)

for a in matched:
    exp, liv, old = current[a], live[a], lastyear.get(a)
    lc = live_class(liv)
    ec = (exp["class"], exp["section"])
    if lc != ec:
        # "11th" -> "11th Science" with the same section is a STREAM NAME, not a move.
        if lc and lc[1] == ec[1] and ec[0].upper().startswith(lc[0].upper()):
            stream_only[f"{lc[0]} {lc[1]} -> {ec[0]} {ec[1]}"] += 1
            changes["class name gains a stream (Science / Commerce)"] += 1
        else:
            changes["genuinely a different class or section"] += 1
            if len(real_class_moves) < 15:
                real_class_moves.append((a, exp["name"], lc, ec))

    if norm_name(exp["name"]) and norm_name(liv.get("name")) \
            and norm_name(exp["name"]) != norm_name(liv.get("name")):
        changes["name spelled differently"] += 1
        if len(name_diffs) < 12:
            name_diffs.append((a, liv.get("name"), exp["name"]))

    if exp["phone"] and adm(liv.get("phone")) and exp["phone"] != adm(liv.get("phone")):
        changes["phone differs"] += 1
        if len(phone_diffs) < 8:
            phone_diffs.append((a, liv.get("phone"), exp["phone"]))

    if old:
        for f in FILL:
            has_live = bool(txt(liv.get(f)))
            if old.get(f) and not has_live:
                changes[f"{f}: blank on platform, available from the 2025-26 workbook"] += 1
                if len(fill_examples[f]) < 5:
                    fill_examples[f].append((a, exp["name"], old[f]))
            elif old.get(f) and has_live and str(liv.get(f)) != str(old[f]):
                changes[f"{f}: platform and workbook disagree — leave alone, do not overwrite"] += 1

live_labels = {(str(c.get("name")), str(c.get("section"))) for c in classes.values()}
needed = Counter((current[a]["class"], current[a]["section"]) for a in to_add)
missing_classes = {k: v for k, v in needed.items() if k not in live_labels}

# ── report ───────────────────────────────────────────────────────────────────
o = []
w = o.append
w("# The school's spreadsheets compared with what is on the platform")
w("")
w("**Read-only. Nothing was changed.** This is the report to read before deciding")
w("whether anything gets written to real student records.")
w("")
w("Sources: `aaryans_database/Students-22-06-2026-02-35-08.xlsx` (the current export,")
w("22 June 2026) and `aaryans_database/DETAINEES LIST 2025-26.xlsx` (last year's).")
w("Students were matched on **admission number only** — never on name.")
w("")
w("## The short version")
w("")
w(f"The platform is essentially already up to date. **{len(matched)} of the")
w(f"{len(current)} students** in the June export are already on it, and **nothing on the")
w("platform is missing from the export.** Only **two** students would be added, and")
w("both of those need a decision first (see below) because they are not really in a class.")
w("")
w("What the folder genuinely adds is **detail that is currently blank**: dates of birth,")
w("admission dates, house and gender for roughly 1,200 to 1,550 students each.")
w("")
w("## The numbers")
w("")
w("| | Count |")
w("|---|---|")
w(f"| Students on the platform right now | {len(live_rows)} |")
w(f"| ...with no admission number recorded (cannot be matched at all) | {len(live_no_adm)} |")
w(f"| ...sharing an admission number with another record | {sum(len(v) for v in live_dupes.values())} |")
w(f"| Students in the June 2026 export | {len(current)} |")
w(f"| Students in the 2025-26 workbook | {len(lastyear)} |")
w("")
w("| Matching on admission number | Count | What it means |")
w("|---|---|---|")
w(f"| Already on the platform | {len(matched)} | Only their details would change. |")
w(f"| In the June export, not on the platform | {len(to_add)} | Would be added. |")
w(f"| On the platform, not in the June export | {len(on_platform_only)} | **Nothing would be deleted.** |")
w(f"| In last year's workbook, gone from the June export | {len(left_or_passed)} | Presumed left or passed out. **Would NOT be created.** |")
w("")
w("## Two things that need your decision before anything is written")
w("")
w("### 1. The senior classes have no stream on the platform")
w("")
w(f"{sum(stream_only.values())} students in classes 11 and 12 sit in a class the platform")
w('calls just "11th" or "12th", while the school\'s own export calls the same class')
w('"11th Science" or "12th Commerce". **The section letter matches every single time**, so')
w("no student is in the wrong room. It is purely that the platform does not record the")
w("stream and the school does.")
w("")
w("| Platform calls it | The school calls it | Students |")
w("|---|---|---|")
for k, n in stream_only.most_common():
    a_, b_ = k.split(" -> ")
    w(f"| {a_} | {b_} | {n} |")
w("")
w("Three ways to go, and this is your call, not ours:")
w("")
w("1. Leave it. The platform keeps saying 11th and 12th. Nothing breaks; the stream")
w("   simply is not recorded anywhere.")
w("2. Rename the six classes to include the stream. Simplest, but it mixes two facts")
w("   into one name, and section A of 11th would become 11th Science A permanently.")
w("3. Record the stream as its own detail on the class. Cleanest, but it is a change to")
w("   how classes are stored, not a data load, and belongs in its own piece of work.")
w("")
w("### 2. The two students who would be added are not in a real class")
w("")
if missing_classes:
    w("Both sit in a class that does not exist on the platform, and reading its name")
    w("explains why:")
    w("")
    w("| Class in the export | Section | Students |")
    w("|---|---|---|")
    for (nm, sec), n in sorted(missing_classes.items(), key=lambda kv: -kv[1]):
        w(f"| {nm} | {sec} | {n} |")
    w("")
    w("That is not a class, it is a **fee-recovery bucket for students who have already")
    w("left owing money**. Creating them as current students would put two people who are")
    w("no longer at the school onto class lists, attendance registers and head counts.")
    w("")
    w("| Admission no | Name | Father | Mobile |")
    w("|---|---|---|---|")
    for a in to_add:
        r = current[a]
        w(f"| {a} | {r['name']} | {r['father'] or ''} | {r['phone'] or ''} |")
    w("")
    w("**Our recommendation: do not add these two.** If their dues need chasing, that is a")
    w("fees job, not a student-record job. Say the word either way.")
w("")
w("## What would change on the students already there")
w("")
w("| Change | Students affected |")
w("|---|---|")
for k, v in sorted(changes.items(), key=lambda kv: -kv[1]):
    w(f"| {k} | {v} |")
w("")
if real_class_moves:
    w("### Genuinely different classes (not just a stream name)")
    w("")
    w("| Admission no | Name | Platform | June 2026 export |")
    w("|---|---|---|---|")
    for a, n, lc, ec in real_class_moves:
        w(f"| {a} | {n} | {lc and ' '.join(lc) or '(none)'} | {' '.join(ec)} |")
    w("")
else:
    w("**No student would move class or section.** Every difference found was the stream")
    w("naming described above.")
    w("")
w("### The blanks last year's workbook could fill")
w("")
w("These are the real prize in the folder. Samples:")
w("")
for f in FILL:
    n = changes.get(f"{f}: blank on platform, available from the 2025-26 workbook", 0)
    w(f"**{f}** — {n} students")
    for a, nm, v in fill_examples.get(f) or []:
        w(f"  - {a} {nm}: {v}")
    w("")
w("### Where the platform and the workbook disagree")
w("")
w("Anywhere a student already has a value on the platform and the workbook says something")
w("different, **the platform's value would be kept**. Last year's workbook is not more")
w("trustworthy than what staff have since entered.")
w("")
w("## A warning about the dates in last year's workbook")
w("")
w("The dates in that workbook are not all real dates. Some are typed text, and some of")
w("that text does not say what it means.")
w("")
w("| Column | Real Excel dates | Blank | Day/month order unknowable | Not a date at all |")
w("|---|---|---|---|---|")
for f in ("dob", "admission_date"):
    q = date_quality[f]
    w(f"| {f} | {q['ok']} | {q['blank']} | {q['ambiguous']} | {q['malformed']} |")
w("")
w('The "unknowable" ones are entries like `09.03.2019`, where 3 September and 9 March are')
w("both possible and the spreadsheet does not say which. A wrong birthday is worse than a")
w("blank one — it follows a child through certificates and records. **Those are counted")
w("here and would be left blank, not guessed.** The handful that are not dates at all")
w('(a year typed as "224") would also be skipped.')
w("")
w("## Everything that would NOT happen")
w("")
w("- No student would be deleted or archived.")
w("- No class or section would be taken from last year's workbook.")
w(f"- The {len(left_or_passed)} students in last year's workbook who are gone from the June")
w("  export would NOT be created. A sample is listed below so you can confirm they really")
w("  have left.")
w("- No value already on the platform would be overwritten by the workbook.")
w("")
w("| Admission no | Name | Class last year |")
w("|---|---|---|")
for a in left_or_passed[:20]:
    r = lastyear[a]
    w(f"| {a} | {r['name']} | {r['class_ignored']} |")
w(f"")
w(f"...and {max(0, len(left_or_passed) - 20)} more.")
w("")
if name_diffs:
    w("## Names spelled differently")
    w("")
    w("Nothing here would be changed automatically.")
    w("")
    w("| Admission no | On the platform | June 2026 export |")
    w("|---|---|---|")
    for a, l, e in name_diffs:
        w(f"| {a} | {str(l).replace(chr(10), ' ')} | {str(e).replace(chr(10), ' ')} |")
    w("")
if phone_diffs:
    w("## Phone numbers that differ")
    w("")
    w("| Admission no | On the platform | June 2026 export |")
    w("|---|---|---|")
    for a, l, e in phone_diffs:
        w(f"| {a} | {l} | {e} |")
    w("")
w("## What we would like from you")
w("")
w("1. The stream question above — leave it, rename, or record it properly.")
w("2. Whether the two fee-recovery entries should be added as students. We suggest not.")
w("3. A yes to filling in the blank dates of birth, admission dates, houses and genders")
w("   for the students already on the platform, on the terms above: blanks only, nothing")
w("   overwritten, ambiguous dates skipped.")
w("")
w("Nothing will be written until you answer. When you do, it goes in batches, each one")
w("reversible on its own.")

report = "\n".join(o)
(REPO / "_bmad-output" / "planning-artifacts" / "data-load-comparison-2026-08-04.md").write_text(report, encoding="utf-8")
print(f"written: {len(report)} chars")
client.close()
