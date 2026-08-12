"""R2-16 - what the school's records are still missing, as counts.

Abhimanyu approved this read on 2026-08-11. It answers one question for Aman: what does
the school still owe the platform before Sonu and Lalit can do their jobs properly?

STRICTLY READ-ONLY, AND COUNTS ONLY.

    * It never writes. There is no update, insert or delete anywhere in this file.
    * It never prints a child's name, admission number, guardian, phone or address.
      The output is "412 students have no date of birth", never which 412. The school
      holds records on 1,876 children who are minors, and a report that names them is an
      export of children's data wearing a report's clothes.
    * The only names it prints are the school's own class labels, which are not personal.

Run it against the live database, read the numbers, and hand them to Aman:

    backend/.venv/Scripts/python.exe scripts/missing_data_report.py

Add --json to write a machine-readable copy for the follow-up work.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend"))

# The connection details live in backend/.env, which is gitignored and never printed.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, "backend", ".env"))
except ImportError:  # pragma: no cover - the app itself depends on python-dotenv
    pass

# Fields worth asking about, with why each one matters. A gap only counts as a gap if
# somebody would actually be stopped by it, otherwise the report is noise and nobody
# reads the next one.
# Each entry is (what a person calls it, [every field name the platform has used for
# it], why it matters). The list of names is the important part.
#
# The first run of this report, 2026-08-11, said "1,842 of 1,842 have no date of birth"
# and "1,842 have no guardian phone". Both were WRONG in the way that matters: the date
# of birth is stored under `dob` for 1,055 children and the contact number under `phone`
# for 1,833 of them. Reporting per raw field name would have sent the school hunting for
# 1,842 dates of birth it already holds. A gap only counts as a gap when NONE of the
# names carries a value.
STUDENT_FIELDS = [
    ("date of birth", ["date_of_birth", "dob"],
     "needed on a Transfer Certificate and for CBSE registration"),
    ("gender", ["gender"], "needed on official documents"),
    ("class", ["class_id"], "without it the child is on no class list at all"),
    ("admission number", ["admission_number"],
     "how a fee, a certificate and an import all find the child"),
    ("father's name", ["father_name", "fathers_name"], "needed on a Bonafide and a TC"),
    ("mother's name", ["mother_name", "mothers_name"], "needed on official documents"),
    ("a contact number", ["guardian_phone", "phone", "father_phone", "mother_phone",
                          "contact_number", "mobile"],
     "how the school reaches the family"),
    ("address", ["address"], "needed for transport planning and official documents"),
    ("blood group", ["blood_group"], "needed in a medical emergency"),
    ("a fee plan", ["fee_structure_id"], "without it the child is on no fee plan"),
]

STAFF_FIELDS = [
    ("a role", ["staff_type"], "decides what the person can be assigned to do"),
    ("a contact number", ["phone", "mobile", "contact_number"],
     "how the school reaches them"),
    ("an employee number", ["employee_id"], "needed for payroll"),
    ("a joining date", ["date_of_joining", "joining_date", "doj"],
     "needed for leave balances and payroll"),
    ("a salary", ["salary", "monthly_salary", "basic_salary"],
     "needed for payroll. Counts only, never an amount."),
]


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().lower() in {"n/a", "na", "-", "none"}
    return False


def _missing_everywhere(record: dict, names) -> bool:
    """True only when NONE of the names this thing has ever been called carries a value."""
    return all(_is_blank(record.get(name)) for name in names)


def _where_it_is_stored(records, names) -> dict:
    """How many records use each field name. Shows the school where its data actually is.

    Without this the report says "1,842 have no date of birth" when 1,055 of them have
    one under `dob`, and the school goes hunting for data it already holds.
    """
    return {
        name: sum(1 for r in records if not _is_blank(r.get(name)))
        for name in names
        if any(not _is_blank(r.get(name)) for r in records)
    }


async def _report() -> dict:
    from database import connect_db, get_db

    # The app opens its connection on startup; a standalone script has to do it itself.
    await connect_db()
    db = get_db()
    out: dict = {}

    students = await db.students.find({}, {"_id": 0}).to_list(5000)
    active = [s for s in students if s.get("is_active") is not False]
    out["students"] = {
        "on_the_roll": len(students),
        "active": len(active),
        "missing": {},
    }
    for label, names, why in STUDENT_FIELDS:
        missing = sum(1 for s in active if _missing_everywhere(s, names))
        if missing:
            out["students"]["missing"][label] = {
                "count": missing, "why": why,
                "stored_as": _where_it_is_stored(active, names),
            }

    staff = await db.staff.find({}, {"_id": 0}).to_list(2000)
    active_staff = [s for s in staff if s.get("is_active") is not False]
    out["staff"] = {"on_the_roll": len(staff), "active": len(active_staff), "missing": {}}
    for label, names, why in STAFF_FIELDS:
        missing = sum(1 for s in active_staff if _missing_everywhere(s, names))
        if missing:
            out["staff"]["missing"][label] = {
                "count": missing, "why": why,
                "stored_as": _where_it_is_stored(active_staff, names),
            }

    # The collections Sonu and Lalit need to have anything to work with. An empty one is
    # a bigger finding than any number of blank fields.
    for name in ("fee_structures", "classes", "transport_routes", "vendors",
                 "academic_years", "message_templates", "fee_transactions"):
        try:
            rows = await getattr(db, name).find({}, {"_id": 0, "id": 1}).to_list(5000)
            out.setdefault("collections", {})[name] = len(rows)
        except Exception as exc:
            out.setdefault("collections", {})[name] = f"could not read: {exc}"

    # Class labels are the school's own, not personal data, so naming them is safe and
    # is the fastest way for Aman to spot a class that does not exist yet.
    classes = await db.classes.find({}, {"_id": 0, "name": 1, "section": 1, "id": 1}).to_list(500)
    labels = sorted(
        f"{(c.get('name') or '').strip()}-{(c.get('section') or '').strip()}".strip("-")
        for c in classes
    )
    out["class_labels"] = labels
    counted = {}
    for s in active:
        counted[s.get("class_id")] = counted.get(s.get("class_id"), 0) + 1
    by_id = {c.get("id"): f"{(c.get('name') or '').strip()}-{(c.get('section') or '').strip()}".strip("-")
             for c in classes}
    out["students_per_class"] = {
        (by_id.get(cid) or "NO CLASS ON THE RECORD"): n
        for cid, n in sorted(counted.items(), key=lambda kv: -kv[1])
    }
    return out


def _print_where(info: dict) -> None:
    """Where the records that DO have this keep it. Blank when nobody has it at all."""
    stored = info.get("stored_as") or {}
    if stored:
        detail = ", ".join(f"{n} under '{name}'" for name, n in stored.items())
        print(f"        the ones that have it keep it as: {detail}")


def _print(report: dict) -> None:
    s = report["students"]
    print(f"\nSTUDENTS: {s['active']} active of {s['on_the_roll']} on the roll")
    if not s["missing"]:
        print("  nothing missing from the fields we check")
    for field, info in sorted(s["missing"].items(), key=lambda kv: -kv[1]["count"]):
        pct = round(100 * info["count"] / max(1, s["active"]))
        print(f"  {info['count']:5} ({pct:3}%) have no {field:18} {info['why']}")
        _print_where(info)

    st = report["staff"]
    print(f"\nSTAFF: {st['active']} active of {st['on_the_roll']}")
    for field, info in sorted(st["missing"].items(), key=lambda kv: -kv[1]["count"]):
        pct = round(100 * info["count"] / max(1, st["active"]))
        print(f"  {info['count']:5} ({pct:3}%) have no {field:18} {info['why']}")
        _print_where(info)

    print("\nHOW MUCH IS IN EACH LIST:")
    for name, n in report.get("collections", {}).items():
        flag = "  <-- EMPTY" if n == 0 else ""
        print(f"  {name:22} {n}{flag}")

    print(f"\nCLASSES ON RECORD ({len(report['class_labels'])}): "
          f"{', '.join(report['class_labels']) or 'none'}")
    print("\nSTUDENTS PER CLASS:")
    for label, n in report["students_per_class"].items():
        print(f"  {label:16} {n}")


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="also write the report to this path")
    args = parser.parse_args()
    report = await _report()
    _print(report)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"\nalso written to {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
