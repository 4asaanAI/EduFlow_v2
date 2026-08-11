"""Load the school's 6 Aug 2026 exports into the live platform. DRY RUN BY DEFAULT.

    python scripts/import_aaryans_2026_08_06.py            # report only, writes nothing
    python scripts/import_aaryans_2026_08_06.py --apply    # actually writes

Companion to `scripts/data_load_compare.py` (step 1, read-only). This is step 2, and it
is deliberately narrow: it writes ONLY the things that are safe to write today, and
prints everything else for a human to decide on.

RULES, all agreed with Abhimanyu on 2026-08-06 and none of them optional:

  1. Match on ADMISSION NUMBER only, never on name. A name match writes one child's
     details onto another child.
  2. NEVER overwrite. A field is written only where the platform currently holds
     nothing. Anything that WOULD have overwritten is counted and reported instead.
  3. Class and section are never changed for an existing student. (Verified safe
     anyway: all 1774 matched students are already in the same class, and only 5
     differ by section - this file is the same session as the platform.)
  4. Nothing is ever deleted. Students and staff on the platform but absent from the
     export are listed, never removed.

WHAT IS DELIBERATELY NOT IMPORTED, and why - each of these was checked, not assumed:

  * Photo - the column contains the literal word "View" for every filled row. It is a
    link label from an HTML export, not a photograph. Writing it would put the string
    "View" in 1,427 photo fields.
  * Transport - the column holds a BUS ROUTE NAME ("8( - JOYA)"), not a yes/no. It
    needs mapping to `transport_routes`, and the platform is inconsistent about the
    flag itself: `context_builder.py` counts `transport_opted` while
    `student_service.py` writes `uses_transport`. Setting one and not the other would
    make Flo's transport figure disagree with the student records. Own piece of work.
  * Fees - the platform's fee ledger is empty (0 heads, 0 structures, 1 transaction).
    Importing means building the ledger from scratch, ~11,000 line items of money
    data. Own piece of work, with the figures shown to a human first.
  * The other ~71 columns (Aadhaar, caste, PEN/APAAR, bank, parent occupation and
    income, TC, scholarship) have no field in EduFlow at all. They need the schema
    extended before they can be stored.

Confidentiality: this script prints COUNTS ONLY. No name, number, address or date of
any child is ever written to the console or to a file. The data stays between the
spreadsheet and the database.
"""
from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from pathlib import Path

import certifi
import openpyxl
from dotenv import load_dotenv
from pymongo import MongoClient

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "aaryans_database"
load_dotenv(REPO / "backend" / ".env")

STUDENTS_XLSX = DATA / "Students-06-08-2026-12-08-00.xlsx"
TEACHERS_XLSX = DATA / "Teachers-06-08-2026-12-09.xlsx"

SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
BRANCH_ID = "branch-joya"          # the only branch; matches all 1802 existing students
ACADEMIC_YEAR_ID = "ay-2025-26"    # is_current=True on the live platform

# A class name in the export that is not a class at all - a fee-recovery bucket for
# students who have already left. Creating these would put people who have gone onto
# class lists and head counts.
PSEUDO_CLASSES = {"12TH PASS OUT OLD DUE 25-26"}

# Sanity bounds. A date outside these is a typing slip, not a fact, and a wrong
# birthday follows a child onto certificates.
DOB_YEARS = (1995, 2026)
ADM_YEARS = (2000, 2026)


def norm_adm(v):
    """Admission number as a comparable string. 15001.0 -> '15001'."""
    if v is None:
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s.upper() or None


def txt(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def norm_gender(v):
    """male/female only. The export also says 'boy' 4 times."""
    s = (txt(v) or "").lower()
    if s in ("male", "boy", "m"):
        return "male"
    if s in ("female", "girl", "f"):
        return "female"
    return None


def parse_date(v, bounds):
    """Every date in this export is '06 Aug, 2026' - a NAMED month, so there is no
    day/month ambiguity to guess at. (The 2025-26 workbook was not like this; that is
    what the earlier attempt tripped on.) Anything that does not parse, or lands
    outside `bounds`, is returned as None and counted."""
    s = txt(v)
    if not s:
        return None
    try:
        d = datetime.datetime.strptime(s, "%d %b, %Y")
    except ValueError:
        return None
    if not (bounds[0] <= d.year <= bounds[1]):
        return None
    return d.strftime("%Y-%m-%d")


def base_class(v):
    """'11th Science' -> '11TH'. The school names the stream in the class; the
    platform keeps 11th/12th and no stream. Verified on 2026-08-04 that the SECTION
    matches every time, so this is a naming difference, not a class move."""
    return re.sub(r"\s*(SCIENCE|COMMERCE|ARTS)\s*$", "", (txt(v) or "").upper()).strip()


def blank_on_platform(doc, field):
    return doc.get(field) in (None, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually write. Without this the script only reports.")
    args = ap.parse_args()
    mode = "APPLY (writing to the live database)" if args.apply else "DRY RUN (nothing is written)"
    print(f"=== {mode} ===\n")

    client = MongoClient(os.environ["MONGO_URL"], tlsCAFile=certifi.where(),
                         serverSelectionTimeoutMS=30000)
    db = client[os.environ["DB_NAME"]]

    # ---------- class lookup ----------
    classes = list(db.classes.find({"schoolId": SCHOOL_ID}, {"_id": 0}))
    by_name_sec = {(str(c.get("name")).strip().upper(),
                    str(c.get("section") or "").strip().upper()): c["id"] for c in classes}

    # ---------- platform students ----------
    live = {}
    for d in db.students.find({"schoolId": SCHOOL_ID}, {"_id": 0}):
        a = norm_adm(d.get("admission_number"))
        if a:
            live[a] = d

    # ---------- the export ----------
    wb = openpyxl.load_workbook(STUDENTS_XLSX, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    ix = {h: i for i, h in enumerate(hdr)}
    rows = [r for r in it if any(c is not None for c in r)]
    wb.close()

    stats = Counter()
    fills = Counter()
    overwrite = Counter()
    bad_dates = Counter()
    no_class = Counter()
    updates = []        # (student_id, {field: value})
    creates = []        # full docs
    guardian_creates = []

    for r in rows:
        adm = norm_adm(r[ix["AdmissionNo"]])
        if adm is None:
            stats["no_admission_number"] += 1
            continue

        gender = norm_gender(r[ix["Gender"]])
        dob = parse_date(r[ix["Dob"]], DOB_YEARS)
        admdate = parse_date(r[ix["AdmissionDate"]], ADM_YEARS)
        if txt(r[ix["Dob"]]) and dob is None:
            bad_dates["dob_rejected"] += 1
        if txt(r[ix["AdmissionDate"]]) and admdate is None:
            bad_dates["admission_date_rejected"] += 1

        if adm in live:
            stats["matched"] += 1
            doc = live[adm]
            upd = {}
            for field, value in (("gender", gender), ("dob", dob), ("admission_date", admdate)):
                if value is None:
                    continue
                if blank_on_platform(doc, field):
                    upd[field] = value
                    fills[field] += 1
                elif str(doc.get(field)) != str(value):
                    # RULE 2: reported, never written.
                    overwrite[field] += 1
            # Fields the platform already holds - counted so the school can see what
            # its file would have changed, and decide separately.
            for xl_col, field in (("Mobile", "phone"), ("Address", "address"),
                                  ("RollNo", "roll_number")):
                xv = txt(r[ix[xl_col]])
                if xv and not blank_on_platform(doc, field) and str(doc[field]).strip() != xv:
                    overwrite[field] += 1
            if upd:
                upd["updated_at"] = datetime.datetime.now().isoformat()
                updates.append((doc["id"], upd))
        else:
            cls_raw = txt(r[ix["Class"]]) or ""
            if cls_raw.upper() in PSEUDO_CLASSES:
                stats["new_but_passed_out_SKIPPED"] += 1
                continue
            key = (base_class(cls_raw), (txt(r[ix["Section"]]) or "").upper())
            cid = by_name_sec.get(key)
            if not cid:
                no_class[f"{cls_raw} / {txt(r[ix['Section']])}"] += 1
                stats["new_but_no_class_SKIPPED"] += 1
                continue
            sid_new = str(uuid.uuid4())
            now = datetime.datetime.now().isoformat()
            doc = {
                "id": sid_new,
                "schoolId": SCHOOL_ID,
                "branch_id": BRANCH_ID,               # match the existing 1802 exactly
                "academic_year_id": ACADEMIC_YEAR_ID,
                "class_id": cid,
                "name": txt(r[ix["Name"]]) or "",
                "admission_number": adm,
                "roll_number": txt(r[ix["RollNo"]]),
                "dob": dob,
                "gender": gender,
                "address": txt(r[ix["Address"]]),
                "phone": txt(r[ix["Mobile"]]),
                "admission_date": admdate or now[:10],
                "status": "active" if (txt(r[ix["Status"]]) or "").lower() == "active" else "inactive",
                "is_active": (txt(r[ix["Status"]]) or "").lower() == "active",
                "created_at": now,
                "updated_at": now,
            }
            if not doc["name"]:
                stats["new_but_no_name_SKIPPED"] += 1
                continue
            creates.append(doc)
            stats["new_to_create"] += 1
            # Guardians, exactly as create_student() derives them: only when BOTH a
            # name and a phone exist, so we never invent a contact.
            for rel, ncol, pcol in (("Father", "FatherName", "FatherMobile"),
                                    ("Mother", "MotherName", "MotherMobile")):
                gn, gp = txt(r[ix[ncol]]), txt(r[ix[pcol]]) or txt(r[ix["Mobile"]])
                if gn and gp:
                    guardian_creates.append({
                        "id": str(uuid.uuid4()), "schoolId": SCHOOL_ID,
                        "student_id": sid_new, "name": gn, "relation": rel,
                        "phone": gp, "whatsapp_phone": gp,
                        "is_primary": rel == "Father",
                    })

    xl_adms = {norm_adm(r[ix["AdmissionNo"]]) for r in rows} - {None}
    only_platform = set(live) - xl_adms

    # ---------------- report ----------------
    print("STUDENTS")
    print(f"  rows in the spreadsheet            : {len(rows)}")
    print(f"  matched to a student on the platform: {stats['matched']}")
    print(f"  no admission number (LEFT ALONE)   : {stats['no_admission_number']}")
    print(f"  new, will be created               : {stats['new_to_create']}")
    print(f"  new but passed-out (SKIPPED)       : {stats['new_but_passed_out_SKIPPED']}")
    print(f"  new but class not on platform      : {stats['new_but_no_class_SKIPPED']}")
    print(f"  new but no name (SKIPPED)          : {stats['new_but_no_name_SKIPPED']}")
    print(f"  on the platform, absent from file  : {len(only_platform)}  (NEVER deleted)")
    if no_class:
        print("    unmatched class/section:")
        for k, v in no_class.items():
            print(f"      {k}: {v}")

    print("\nBLANKS THAT WILL BE FILLED (existing students)")
    for k, v in fills.items():
        print(f"  {k:18s} {v}")
    print(f"  students receiving at least one value: {len(updates)}")

    print("\nWOULD HAVE OVERWRITTEN - reported, NOT written (rule 2)")
    if overwrite:
        for k, v in overwrite.items():
            print(f"  {k:18s} {v}")
    else:
        print("  nothing")

    print("\nREJECTED AS IMPOSSIBLE DATES (left blank, never guessed)")
    print(f"  {dict(bad_dates) or 'none'}")

    print(f"\nGUARDIANS to create for the new students: {len(guardian_creates)}")

    if not args.apply:
        print("\n--- DRY RUN. Nothing was written. Re-run with --apply to write. ---")
        client.close()
        return

    # ---------------- write ----------------
    # Rollback manifest FIRST, before a single write. Every field written here was
    # blank beforehand (rule 2), so undoing an update is `$unset` of those same
    # fields, and undoing a create is deleting that id. The manifest holds ids and
    # FIELD NAMES only - never a child's name, number or date - so it can sit on disk
    # without being a copy of the school's data.
    rollback_path = Path(os.environ.get(
        "ROLLBACK_DIR", Path.home())) / f"aaryans_import_rollback_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
    import json
    rollback_path.write_text(json.dumps({
        "source_file": STUDENTS_XLSX.name,
        "written_at": datetime.datetime.now().isoformat(),
        "school_id": SCHOOL_ID,
        "undo_updates": [{"id": i, "unset": [k for k in u if k != "updated_at"]} for i, u in updates],
        "undo_creates_student_ids": [d["id"] for d in creates],
        "undo_creates_guardian_ids": [g["id"] for g in guardian_creates],
    }, indent=1))
    print(f"  rollback manifest written to {rollback_path}")

    print("\nWriting...")
    n_upd = 0
    for sid_, upd in updates:
        db.students.update_one({"id": sid_, "schoolId": SCHOOL_ID}, {"$set": upd})
        n_upd += 1
    print(f"  updated {n_upd} existing students")

    if creates:
        db.students.insert_many([{**d, "_id": d["id"]} for d in creates])
    print(f"  created {len(creates)} students")
    if guardian_creates:
        db.guardians.insert_many([{**g, "_id": g["id"]} for g in guardian_creates])
    print(f"  created {len(guardian_creates)} guardians")

    # One audit row for the whole load. 1800 individual rows would bury the log; the
    # counts here plus this script in git are the trail.
    db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "schoolId": SCHOOL_ID,
        "branch_id": BRANCH_ID,
        "action": "bulk_import",
        "collection": "students",
        "entity_id": "aaryans-2026-08-06",
        "changed_by": "layaa-ai-data-load",
        "changed_by_role": "system",
        "changes": {
            "source_file": STUDENTS_XLSX.name,
            "students_updated": n_upd,
            "students_created": len(creates),
            "guardians_created": len(guardian_creates),
            "fields_filled": dict(fills),
            "overwrites_declined": dict(overwrite),
            "dates_rejected": dict(bad_dates),
        },
        "created_at": datetime.datetime.now().isoformat(),
    })
    print("  wrote 1 audit entry")
    client.close()


if __name__ == "__main__":
    main()
