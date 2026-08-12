"""
Load STAFF ATTENDANCE for The Aaryans from the school's four PDF reports
(`aaryans_database/Staff attendance*.pdf`), covering 01 Apr 2026 -> 01 Aug 2026.

WHY A PDF PARSER AND NOT A SPREADSHEET
--------------------------------------
The school only exported these as PDF. Three properties of that export had to be handled
or the load would have been silently wrong, and all three are worth knowing about:

 1. **A day's block spans several pages and the `Date :` header appears only once**, at
    the start of the block, sometimes half-way down a page. The date must therefore be
    carried forward across pages, not read per page. Reading per page dropped ~90% of
    the rows.
 2. **The exporter wraps text INSIDE a cell, mid-word** ("Abse\\nnt", "admin_offic\\ne").
    Cell fragments must be joined with NO separator; joining with a space corrupts every
    status and role value. But that also means a date can arrive as "Date : 02 Apr,2026"
    with the space eaten, so the date regex must not require the space.
 3. **Consecutive files overlap by one day** (…To: 01 May and 01 May To:…), so 01 May,
    01 Jun and 01 Jul each appear twice. The duplicate copies were verified to agree
    exactly on status and both punch times before being de-duplicated.

The parse is self-checked: every row carries a running S.No. that restarts at 1 for each
new day, so a day boundary missed by the date regex would show up as a restart with no
new date. The loader refuses to run unless that count is zero.

MATCHING - WHY NOT BY PHONE
---------------------------
Several staff share the school's own switchboard number (8126965555 appears against many
different people), so a phone match is NOT identifying. Matching is therefore by
normalised NAME, and the phone is used only to CONFIRM. A name that matches two staff
records, or no staff record, is reported and skipped -- never guessed.

RULES OBSERVED
  * fill blanks only: a date+staff already recorded is left exactly as it is, which also
    makes this script resumable if it is interrupted
  * never delete; never overwrite
  * dry-run by default; --apply writes and first writes a rollback manifest
  * counts to the transcript, names only to the gitignored aaryans_database/

Usage:
    python scripts/import_aaryans_staff_attendance_2026_08_06.py           # dry run
    python scripts/import_aaryans_staff_attendance_2026_08_06.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import collections
import glob
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import certifi
import pdfplumber
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

SCHOOL_ID = os.environ.get("SCHOOL_ID", "aaryans-joya")
BRANCH_ID = "branch-joya"
SOURCE_TAG = "staff-attendance-pdf-2026-08-06"

HDR4 = ["S.No.", "Name", "Role", "Mobile"]
COLS = ["S.No.", "Name", "Role", "Mobile", "Present", "Absent", "Pending", "PunchIn",
        "PunchOut", "Work Hrs", "Late/HalfDay", "Mode", "Leave/Holiday", "Remark"]
DATE_RE = re.compile(r"Date\s*:\s*(\d{1,2}\s*[A-Za-z]{3}\s*,\s*\d{4})")

# Statuses the platform records. "pending" means the school had not finalised that
# person's mark for that day -- it is NOT an absence and must not be stored as one.
STORED_STATUSES = {"present", "absent"}

# Rows in the report that are not a person. "THE AARYANS JOYA" is the school's own ERP
# login (its Role column literally reads `user`), and it punches in like a member of
# staff. Storing it would invent a 111-day attendance record for an account.
NOT_A_PERSON = {nk_ for nk_ in ("theaaryansjoya",)}

# The attendance report writes one person's name with his DESIGNATION appended, so the
# plain name match misses him. Identification is certain rather than guessed: there is
# exactly one SHIVAM KUMAR on the platform and his sub_category is already `accountant`,
# which is the very word appended. Left as an explicit, named exception rather than a
# fuzzy-matching rule -- fuzzy matching on staff names is how one person's attendance
# ends up on another person's record.
NAME_ALIASES = {"shivamkumaraccountant": "shivamkumar"}


def clean(c) -> str:
    return (c or "").replace("\n", "").strip()


def nk(s) -> str:
    return re.sub(r"[^a-z]", "", (s or "").lower())


def phone10(s) -> str:
    d = re.sub(r"\D", "", str(s or ""))
    return d[-10:] if len(d) >= 10 else ""


def to_24h(t: str) -> str | None:
    """'07:58:am' / '01:45:pm' -> '07:58' / '13:45'. Returns None for blanks."""
    t = (t or "").strip().lower()
    m = re.fullmatch(r"(\d{1,2}):(\d{2}):?(am|pm)", t)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap == "pm" and h != 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mi}"


def parse_pdfs() -> tuple[list[dict], int]:
    rows: list[dict] = []
    restarts = 0
    for p in sorted(glob.glob(str(ROOT / "aaryans_database" / "Staff attendance*.pdf"))):
        cur_date, last_sno = None, 0
        with pdfplumber.open(p) as pdf:
            for pg in pdf.pages:
                for tb in pg.extract_tables():
                    for r in tb:
                        cells = [clean(c) for c in r]
                        m = DATE_RE.search(" ".join(cells))
                        if m:
                            cur_date = datetime.strptime(
                                re.sub(r"\s+", "", m.group(1)), "%d%b,%Y").date().isoformat()
                            last_sno = 0
                            continue
                        if cells[:4] == HDR4:
                            continue
                        if not cells or not re.fullmatch(r"\d+", cells[0] or ""):
                            continue
                        sno = int(cells[0])
                        if sno <= last_sno:
                            restarts += 1
                        last_sno = sno
                        if cur_date is None:
                            restarts += 1
                            continue
                        d = dict(zip(COLS, cells + [""] * (len(COLS) - len(cells))))
                        status = ("present" if d["Present"].lower() == "present" else
                                  "absent" if d["Absent"].lower() == "absent" else
                                  "pending" if d["Pending"].lower() == "pending" else "")
                        rows.append({
                            "date": cur_date, "name": d["Name"], "role": d["Role"],
                            "mobile": phone10(d["Mobile"]), "status": status,
                            "check_in": to_24h(d["PunchIn"]), "check_out": to_24h(d["PunchOut"]),
                            "work_hrs": d["Work Hrs"] or None, "mode": d["Mode"] or None,
                            "remark": d["Remark"] or None, "src": Path(p).name,
                        })
    return rows, restarts


async def main(apply: bool) -> int:
    rows, restarts = parse_pdfs()
    if not rows:
        print("ERROR: no attendance rows parsed - check the PDFs are present.")
        return 1

    print("=" * 68)
    print("STAFF ATTENDANCE - source: 4 x 'Staff attendance*.pdf'")
    print("=" * 68)
    print(f"rows parsed                        : {len(rows)}")
    print(f"day-boundary anomalies (must be 0) : {restarts}")
    if restarts:
        print("ABORT: the parse lost a day boundary; refusing to load a partial month.")
        return 1

    # de-duplicate the file-overlap days, after proving the copies agree
    seen: dict[tuple, dict] = {}
    conflicting = 0
    for r in rows:
        k = (nk(r["name"]), r["date"])
        if k in seen:
            a, b = seen[k], r
            if (a["status"], a["check_in"], a["check_out"]) != (b["status"], b["check_in"], b["check_out"]):
                conflicting += 1
            continue
        seen[k] = r
    dedup = list(seen.values())
    dates = collections.Counter(r["date"] for r in dedup)
    print(f"after de-duplicating overlap days  : {len(dedup)}  (removed {len(rows) - len(dedup)})")
    print(f"  duplicate copies that DISAGREED  : {conflicting}  <- must be 0")
    if conflicting:
        print("ABORT: the school's own files disagree about a day. Not guessing on attendance.")
        return 1
    print(f"distinct dates                     : {len(dates)}  ({min(dates)} -> {max(dates)})")
    print(f"distinct staff in the reports      : {len({nk(r['name']) for r in dedup})}")
    mix = collections.Counter(r["status"] for r in dedup)
    print(f"status mix                         : {dict(mix)}")
    print(f"  'pending' is NOT stored          : {mix.get('pending', 0)} rows skipped by design")

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tlsCAFile=certifi.where(), retryWrites=True)
    db = client[os.environ["DB_NAME"]]
    try:
        staff = [s async for s in db.staff.find(
            {"schoolId": SCHOOL_ID}, {"_id": 0, "id": 1, "name": 1, "phone": 1})]
        name_map: dict[str, list] = collections.defaultdict(list)
        for s in staff:
            name_map[nk(s.get("name"))].append(s)

        resolved: dict[str, str] = {}       # nk(name) -> staff id
        ambiguous, unmatched, phone_disagree = [], [], 0
        skipped_not_person = 0
        for name in {r["name"] for r in dedup}:
            key = nk(name)
            if key in NOT_A_PERSON:
                skipped_not_person += 1
                continue
            hits = name_map.get(NAME_ALIASES.get(key, key), [])
            if len(hits) == 1:
                resolved[key] = hits[0]["id"]
            elif len(hits) > 1:
                ambiguous.append(name)
            else:
                unmatched.append(name)
        # phone is a CONFIRMATION only, never the identifier: many staff share the
        # school switchboard number, so a phone match on its own is not identifying.
        for r in dedup:
            sid = resolved.get(nk(r["name"]))
            if not sid or not r["mobile"]:
                continue
            rec = next((s for s in staff if s["id"] == sid), None)
            if rec and phone10(rec.get("phone")) and phone10(rec.get("phone")) != r["mobile"]:
                phone_disagree += 1

        print(f"\nstaff on the platform              : {len(staff)}")
        print(f"  names resolved to exactly one    : {len(resolved)}")
        print(f"  AMBIGUOUS (2+ staff, skipped)    : {len(ambiguous)}")
        print(f"  UNMATCHED (no staff, skipped)    : {len(unmatched)}")
        print(f"  non-person ERP accounts skipped  : {skipped_not_person}")
        print(f"  rows where the phone disagreed   : {phone_disagree} (kept; phone is not the key)")
        if ambiguous or unmatched:
            (ROOT / "aaryans_database" / "_attendance_unresolved.txt").write_text(
                "AMBIGUOUS (more than one staff record with this name):\n"
                + "\n".join(sorted(ambiguous))
                + "\n\nUNMATCHED (nobody on the platform with this name):\n"
                + "\n".join(sorted(unmatched)))
            print("  (names -> aaryans_database/_attendance_unresolved.txt)")

        # what would actually be written
        candidates = [r for r in dedup
                      if r["status"] in STORED_STATUSES and nk(r["name"]) in resolved]
        existing = set()
        async for a in db.staff_attendance.find(
                {"schoolId": SCHOOL_ID}, {"_id": 0, "staff_id": 1, "date": 1}):
            existing.add((a["staff_id"], a["date"]))
        to_write = [r for r in candidates
                    if (resolved[nk(r["name"])], r["date"]) not in existing]

        print(f"\nrows eligible to store             : {len(candidates)}")
        print(f"  already on the platform (kept)   : {len(candidates) - len(to_write)}")
        print(f"  WOULD WRITE                      : {len(to_write)}")
        wi = sum(1 for r in to_write if r["check_in"])
        wo = sum(1 for r in to_write if r["check_out"])
        print(f"  of those, with a punch-in        : {wi}")
        print(f"  of those, with a punch-out       : {wo}")

        if not apply:
            print("\nDRY RUN - nothing written. Re-run with --apply to write.")
            return 0

        docs = []
        now = datetime.now(timezone.utc).isoformat()
        for r in to_write:
            docs.append({
                "id": str(uuid.uuid4()),
                "schoolId": SCHOOL_ID,
                "branch_id": BRANCH_ID,
                "staff_id": resolved[nk(r["name"])],
                "date": r["date"],
                "status": r["status"],
                "check_in": r["check_in"],
                "check_out": r["check_out"],
                "work_hours": r["work_hrs"],
                "marking_mode": r["mode"],      # 'Finger Print' or 'ERP' - the school's own device record
                "remark": r["remark"],
                "marked_by": SOURCE_TAG,
                "created_at": now,
                "source": SOURCE_TAG,
            })

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        manifest = ROOT / "aaryans_database" / f"_rollback_staff_attendance_{stamp}.json"
        manifest.write_text(json.dumps({
            "script": Path(__file__).name, "written_at": stamp,
            "note": "To roll back, delete staff_attendance documents with exactly these ids.",
            "source_tag": SOURCE_TAG, "created_ids": [d["id"] for d in docs],
        }, indent=1))
        print(f"\nrollback manifest -> {manifest.name}")

        written = 0
        for i in range(0, len(docs), 500):
            batch = docs[i:i + 500]
            if batch:
                res = await db.staff_attendance.insert_many(batch)
                written += len(res.inserted_ids)
        print(f"attendance rows written            : {written}")

        total = await db.staff_attendance.count_documents({"schoolId": SCHOOL_ID})
        print(f"staff_attendance rows on platform  : {total}")
        by_status = await db.staff_attendance.aggregate([
            {"$match": {"schoolId": SCHOOL_ID}},
            {"$group": {"_id": "$status", "n": {"$sum": 1}}}, {"$sort": {"_id": 1}}]).to_list(10)
        print("  " + ", ".join(f"{r['_id']}={r['n']}" for r in by_status))
        dr = await db.staff_attendance.aggregate([
            {"$match": {"schoolId": SCHOOL_ID}},
            {"$group": {"_id": None, "lo": {"$min": "$date"}, "hi": {"$max": "$date"}}}]).to_list(1)
        if dr:
            print(f"  date range: {dr[0]['lo']} -> {dr[0]['hi']}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    sys.exit(asyncio.run(main(ap.parse_args().apply)))
