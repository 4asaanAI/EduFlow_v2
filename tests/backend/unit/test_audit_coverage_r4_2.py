"""R4-2 - every module that writes to the database has a verdict, and no gap is quiet.

This is the guard that stops the twenty unrecorded modules happening again. It scans the
backend for database writes and fails when a writing module is neither in `RECORDS` nor
in `EXCUSED`. A new gap therefore cannot be introduced without somebody writing down why
it is acceptable.

`test_the_register_is_published` prints the whole picture including the gaps, so the
state of coverage is a thing you can read rather than a thing you have to trust. A silent
gap is the exact failure this release exists to end, and a register that only listed the
good news would be one.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from services import audit_coverage

BACKEND = Path(__file__).resolve().parents[3] / "backend"

WRITE_CALL = re.compile(
    r"\.(insert_one|insert_many|update_one|update_many|replace_one"
    r"|delete_one|delete_many|find_one_and_update|bulk_write)\("
)

#: Files that are infrastructure rather than a write path, so they are not in scope.
NOT_A_WRITE_PATH = {
    "services/audit_service.py",   # the audit writer itself
    "services/audit_coverage.py",  # this register
    "services/txn_context.py",
}


def _scanned_modules():
    """Every backend module under routes/, services/ and ai/ that writes to the DB."""
    found = {}
    for folder in ("routes", "services", "ai"):
        for path in sorted((BACKEND / folder).rglob("*.py")):
            rel = f"{folder}/{path.relative_to(BACKEND / folder).as_posix()}"
            if rel in NOT_A_WRITE_PATH or "__pycache__" in rel:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            writes = len(WRITE_CALL.findall(text))
            if writes:
                found[rel] = writes
    return found


def test_the_scan_finds_write_paths_at_all():
    """A scanner that silently matches nothing would pass every test below."""
    modules = _scanned_modules()
    assert len(modules) > 50, f"only found {len(modules)} writing modules, scanner is broken"


def test_every_writing_module_has_a_verdict():
    """RECORDS or EXCUSED. There is no third state, and no quiet gap."""
    undecided = {
        module: writes
        for module, writes in _scanned_modules().items()
        if audit_coverage.verdict(module) == "UNDECIDED"
    }
    assert not undecided, (
        "These modules write to the school's database and neither record what they did "
        "nor carry a written reason for not recording:\n  "
        + "\n  ".join(f"{m} ({w} writes)" for m, w in sorted(undecided.items()))
        + "\n\nAdd each to RECORDS (after making it audit) or to EXCUSED (with a reason "
          "a person at the school would accept) in backend/services/audit_coverage.py."
    )


def test_no_module_is_listed_in_both():
    both = set(audit_coverage.RECORDS) & set(audit_coverage.EXCUSED)
    assert not both, f"listed as both recording and excused: {sorted(both)}"


def test_the_register_does_not_list_modules_that_no_longer_write():
    """A stale entry is a claim about code that is not there any more."""
    scanned = set(_scanned_modules())
    listed = set(audit_coverage.RECORDS) | set(audit_coverage.EXCUSED)
    stale = {m for m in listed - scanned if not (BACKEND / m).exists()}
    assert not stale, f"register names modules that do not exist: {sorted(stale)}"


def test_every_excuse_is_a_real_sentence():
    """"n/a" and "not needed" are not reasons. Somebody has to have thought about it."""
    for module, reason in audit_coverage.EXCUSED.items():
        assert len(reason) > 40, f"{module}: the reason is too short to be a decision"
        assert reason.strip().endswith("."), f"{module}: reason should read as a sentence"


def test_modules_that_record_actually_call_the_audit_writer():
    """Guards against a module being marked RECORDS to silence this test."""
    missing = []
    for module in sorted(audit_coverage.RECORDS):
        path = BACKEND / module
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"write_audit|audit_logs\.insert|_write_audit", text):
            missing.append(module)
    assert not missing, (
        "listed as recording but never call the audit writer: " + ", ".join(missing)
    )


def test_the_register_is_published(capsys):
    """Print the whole picture, gaps included. Coverage you can read, not trust."""
    modules = _scanned_modules()
    records = {m: w for m, w in modules.items() if audit_coverage.verdict(m) == "RECORDS"}
    excused = {m: w for m, w in modules.items() if audit_coverage.verdict(m) == "EXCUSED"}
    undecided = {m: w for m, w in modules.items() if audit_coverage.verdict(m) == "UNDECIDED"}

    with capsys.disabled():
        print("\n--- R4-2 audit coverage ---")
        print(f"  records : {len(records):3} modules, {sum(records.values()):4} writes")
        print(f"  excused : {len(excused):3} modules, {sum(excused.values()):4} writes")
        print(f"  UNDECIDED:{len(undecided):3} modules, {sum(undecided.values()):4} writes")
        for module in sorted(undecided):
            print(f"      gap: {module} ({undecided[module]} writes)")

    # The counts are printed, never asserted. A pinned number goes stale the day
    # somebody adds a route and is then read as a target rather than a measurement.
    assert modules
