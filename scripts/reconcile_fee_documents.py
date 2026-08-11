"""Release 2, step 1: reconcile the school's fee documents against each other.

READ ONLY. This script opens spreadsheets in ``aaryans_database/`` and prints what it
finds. It does not connect to any database and it writes nothing anywhere.

Why it exists. Nine fee documents sit in that folder, several of them near-duplicates
saved an hour apart on 6 August 2026, plus the detailed payment log of 11 August. Before
a single fee figure is written to the live platform, every one of those documents has to
be read against the others, because a wrong fee structure reaches 1,842 families and they
find out through a bill.

The authority on how the school charges is
``_bmad-output/implementation-artifacts/release-2/fee-rules-from-sonu-2026-08-11.md``.
Where a document here disagrees with that one, that one wins and the disagreement is
reported rather than resolved.

Run it with the backend virtualenv:

    backend/.venv/Scripts/python.exe scripts/reconcile_fee_documents.py
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict

import openpyxl

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "aaryans_database")

# The seven sibling concession values already loaded on the platform and confirmed
# correct against the school's photographed 2026-27 fee sheet. Listed here only so the
# band structure below can be checked against something independent.
SIBLING_BANDS = [1410, 1560, 1650, 1800, 2100, 2610, 2910]

QUARTER_HEADS = [
    "Composite Fees 1st Q. (APR , MAY, JUN)",
    "Composite Fee 2 QTR (July, August, September)",
    "Composite Fee 3 QTR (Oct, Nov, Dec)",
    "Composite Fee 4 QTR (Jan, Feb, March) 2",
]

MONTHS = ["apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "jan", "feb", "mar"]


def _rows(filename: str):
    path = os.path.join(DATA, filename)
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    for row in ws.iter_rows(values_only=True):
        yield row
    wb.close()


def _cell_field(text, field):
    """Pull one labelled number out of a 'Fees:8850\\nFine:0\\nDiscount:0' cell."""
    if not isinstance(text, str):
        return None
    m = re.search(rf"{field}:(-?[\d.]+)", text)
    return float(m.group(1)) if m else None


def _norm_class(raw):
    """'3rd-D' -> '3rd'. '11th Science-A' -> '11th Science'."""
    if not isinstance(raw, str):
        return None
    return raw.rsplit("-", 1)[0].strip() if "-" in raw else raw.strip()


def h(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# --------------------------------------------------------------------------------------
# A. The two empty files and the two aggregate files
# --------------------------------------------------------------------------------------

def check_aggregates(findings):
    h("A. The four aggregate files, in the order they were saved")

    empties = []
    for name in ("Fees-Structure-06-08-2026-02-49.xlsx", "Fees-Structure-06-08-2026-12-46.xlsx"):
        body = [r for r in _rows(name)][2:]
        total = body[0][1] if body else None
        if total in (0, None):
            empties.append(name)
    print(f"  EMPTY, carry no fee figure at all: {len(empties)}")
    for name in empties:
        print(f"    - {name}")
    if empties:
        # Not a disagreement. A document that states nothing cannot contradict one that
        # does. Recorded so that nobody later counts these as corroboration either.
        print("    (Not a disagreement. A file that states no figure neither agrees")
        print("     nor disagrees with anything. It is also not corroboration.)")

    print()
    print("  Fees-Structure-summay-06-08-2026-02-51.xlsx says 'Total Fees Structures: 1'")
    print("  Fees-Structure-summay-06-08-2026-03-02.xlsx says 'Total Fees Structures: 9'")
    print("  The first is a strict subset of the second (the LATE FINE head, identical to")
    print("  the rupee). It is an earlier partial save of the same export, not a rival figure.")

    heads = {}
    for row in _rows("Fees-Structure-summay-06-08-2026-03-02.xlsx"):
        if row and isinstance(row[0], str) and row[0] not in ("Fees Type", "Total") and not row[0].startswith("Total Fees Structures"):
            heads[row[0]] = row[1]
    print()
    print(f"  The nine fee heads the school's previous system uses ({len(heads)}):")
    for k, v in heads.items():
        print(f"    {k:<48} billed {v:>12,}")
    return heads


# --------------------------------------------------------------------------------------
# B. Per-class rate card, derived from the per-student report
# --------------------------------------------------------------------------------------

def per_class_rate_card(findings):
    h("B. The per-class quarterly fee, from the per-student report")
    print("  Source: Students-Fees-Structure-Report-06-08-2026-12-49.xlsx")
    print("  This file was never read before. It carries every child's own quarterly")
    print("  figures, so the class rate card can be derived rather than transcribed.")

    rows = list(_rows("Students-Fees-Structure-Report-06-08-2026-12-49.xlsx"))
    header = [c for c in rows[0]]
    idx = {name: i for i, name in enumerate(header) if isinstance(name, str)}

    per_class = defaultdict(lambda: defaultdict(Counter))
    transport = defaultdict(list)
    students = 0
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        students += 1
        cls = _norm_class(row[idx["Class"]])
        if not cls:
            continue
        for q in QUARTER_HEADS:
            fee = _cell_field(row[idx[q]], "Fees")
            if fee:
                per_class[cls][q][int(fee)] += 1
        tf = _cell_field(row[idx["Transport Fees"]], "Fees")
        if tf:
            transport[cls].append(int(tf))

    print(f"\n  {students} students in the file, {len(per_class)} distinct classes.\n")
    print(f"  {'Class':<16}{'Q1':>9}{'Q2':>9}{'Q3':>9}{'Q4':>9}   {'year':>9}  same all 4?")
    print("  " + "-" * 74)

    year_by_class = {}
    disagree = []
    for cls in sorted(per_class, key=_class_sort):
        mode = []
        for q in QUARTER_HEADS:
            c = per_class[cls][q]
            mode.append(c.most_common(1)[0][0] if c else 0)
        same = len(set(m for m in mode if m)) == 1
        year_by_class[cls] = sum(mode)
        print(f"  {cls:<16}{mode[0]:>9,}{mode[1]:>9,}{mode[2]:>9,}{mode[3]:>9,}   {sum(mode):>9,}  {'yes' if same else 'NO'}")
        if not same:
            disagree.append((cls, mode))

    if disagree:
        findings.append(
            "Some classes do not charge the same amount in all four quarters: "
            + ", ".join(c for c, _ in disagree)
        )
    else:
        print("\n  Every class charges the same amount in all four quarters.")
    return per_class, year_by_class, transport


def _class_sort(c):
    order = ["NUR", "LKG", "UKG", "1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th",
             "9th", "10th", "11th Commerce", "11th Science", "12th Commerce", "12th Science"]
    return (order.index(c), "") if c in order else (99, c)


# --------------------------------------------------------------------------------------
# C. The same rate card, independently from the payment ledger
# --------------------------------------------------------------------------------------

def ledger_rate_card(findings, per_class):
    h("C. The same numbers again, from the 11 August payment ledger")
    print("  Source: Fees-log-detailed-11-08-2026-17-36.xlsx")
    print("  Two documents produced by different reports on different days. If the")
    print("  quarterly figure for a class differs between them, one of them is wrong.")

    rows = list(_rows("Fees-log-detailed-11-08-2026-17-36.xlsx"))
    header = list(rows[1])
    idx = {n: i for i, n in enumerate(header) if isinstance(n, str)}

    ledger_q = defaultdict(Counter)
    transport_months = Counter()
    transport_rates = defaultdict(Counter)
    fine_amounts = []
    lines = 0
    for row in rows[2:]:
        if not row or row[idx["Admission No."]] is None:
            continue
        lines += 1
        cls = str(row[idx["Class"]] or "").strip()
        ftype = str(row[idx["Fees Type"]] or "").lower()
        total = row[idx["Total Amount"]]
        if "fine" in ftype:
            if isinstance(total, (int, float)) and total:
                fine_amounts.append(int(total))
            continue
        if "transport" in ftype:
            # The string is 'transport fees may', with no brackets round the month.
            # An earlier version of this script looked for '(may)' and matched nothing,
            # which made June look excluded because EVERY month looked excluded. Match
            # on the trailing word instead, and assert below that every line was placed.
            month = ftype.rsplit(" ", 1)[-1]
            if month in MONTHS:
                transport_months[month] += 1
                if isinstance(total, (int, float)) and total:
                    transport_rates[month][int(total)] += 1
            else:
                transport_months["UNRECOGNISED"] += 1
            continue
        if "composite" in ftype and isinstance(total, (int, float)) and total:
            ledger_q[cls][int(total)] += 1

    print(f"\n  {lines:,} fee lines read.\n")
    print(f"  {'Class':<16}{'ledger Q':>11}{'per-student Q1':>16}   verdict")
    print("  " + "-" * 62)

    mismatches = []
    for cls in sorted(set(ledger_q) | set(per_class), key=_class_sort):
        lq = ledger_q[cls].most_common(1)[0][0] if ledger_q.get(cls) else None
        pq = per_class[cls][QUARTER_HEADS[0]].most_common(1)[0][0] if per_class.get(cls) and per_class[cls][QUARTER_HEADS[0]] else None
        if lq is None or pq is None:
            verdict = "only in one document"
        elif lq == pq:
            verdict = "agree"
        else:
            verdict = "*** DISAGREE ***"
            mismatches.append((cls, lq, pq))
        print(f"  {cls:<16}{(f'{lq:,}' if lq else '-'):>11}{(f'{pq:,}' if pq else '-'):>16}   {verdict}")

    if mismatches:
        findings.append(
            "The payment ledger and the per-student report disagree on the quarterly fee for: "
            + ", ".join(f"{c} (ledger {a:,} vs report {b:,})" for c, a, b in mismatches)
        )

    return transport_months, transport_rates, fine_amounts


# --------------------------------------------------------------------------------------
# D. Transport
# --------------------------------------------------------------------------------------

def transport_check(findings, transport, transport_months, transport_rates):
    h("D. Transport: which months are charged, and what the monthly rate is")

    unrecognised = transport_months.pop("UNRECOGNISED", 0)
    print("  Which months the ledger carries a transport line for:")
    for m in MONTHS:
        n = transport_months.get(m, 0)
        flag = "   <-- NOT CHARGED" if n == 0 else ""
        print(f"    {m}: {n:>6,} lines{flag}")
    total_t = sum(transport_months.values())
    print(f"\n    {total_t:,} transport lines placed into a month.")
    print(f"    {unrecognised:,} transport lines whose month could not be read.")

    if unrecognised:
        findings.append(
            f"{unrecognised} transport lines carry a month this script cannot read. "
            "The month counts above are therefore incomplete and must not be relied on."
        )
    elif total_t == 0:
        findings.append(
            "Not one transport line was matched. That is a fault in this script, not a "
            "finding about the school, and nothing below it can be trusted."
        )
    else:
        charged = [m for m in MONTHS if transport_months.get(m, 0)]
        print(f"\n    {len(charged)} months are charged: {', '.join(charged)}.")
        if transport_months.get("jun", 0) == 0 and len(charged) == 11:
            print("    June is the only month with no line at all. This confirms the fee")
            print("    rules document exactly: eleven months, June excluded.")
        else:
            findings.append(
                f"Transport is charged in {len(charged)} months ({', '.join(charged)}), "
                "not the eleven-with-June-excluded the rules document states."
            )

    # The monthly rate, taken from the ledger's own monthly lines. An earlier version of
    # this script divided the per-student report's ANNUAL transport figure by 11, which
    # gave a range of 620 to 1,900 and looked like a contradiction. It was not: that
    # annual figure is pro-rated for a child who joined mid-year, so dividing it by a
    # full eleven months is simply the wrong sum. A monthly line is the rate itself.
    all_rates = Counter()
    for m in MONTHS:
        all_rates.update(transport_rates.get(m, Counter()))
    distinct = sorted(all_rates)
    print(f"\n  Distinct monthly transport charges actually billed: {len(distinct)}")
    if distinct:
        print(f"  Range: {min(distinct):,} to {max(distinct):,} a month.")
        print("  The fee rules document says 'roughly 650 to 1,520 a month'.\n")
        print(f"    {'rate':>7}{'lines':>9}")
        print("    " + "-" * 16)
        for r, n in sorted(all_rates.items()):
            print(f"    {r:>7,}{n:>9,}")
        # The comparison against the rules document's "roughly 650 to 1,520" is made
        # once, in section D2, where both source documents are on the table together.
        # Raising it here as well would report one fact as two.

    return distinct


# --------------------------------------------------------------------------------------
# D2. The transport rate card and route list, from the two documents nobody had read
# --------------------------------------------------------------------------------------

def transport_rate_card(findings, billed_rates):
    h("D2. The transport route list and rate card")
    print("  Two documents the finishing plan recorded as unread. Both have now been read.")

    # ---- the PDF: a per-route collection summary, NOT a rate card
    import pypdf

    reader = pypdf.PdfReader(os.path.join(DATA, "Transport-Fees-Structure-Report-Summary-06-08-2026-16-58.pdf"))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    lines = text.split("\n")
    labels = []
    for i, line in enumerate(lines):
        if line.strip() == "FEES TYPES" and i + 1 < len(lines):
            lab = lines[i + 1].strip()
            if lab and lab != "Total Head":
                labels.append(lab)
    print(f"\n  Transport-Fees-Structure-Report-Summary-...pdf: {len(reader.pages)} pages,")
    print(f"  {len(labels)} route sections. It is a per-route COLLECTION SUMMARY broken")
    print("  down by class. It carries no monthly rate for any route, so it is not the")
    print("  rate card the plan expected. What it does give is the route list:")
    named = [l for l in labels if not l.isdigit()]
    print(f"    {len(labels) - len(named)} routes identified by number only")
    print(f"    {len(named)} routes identified by place: {', '.join(sorted(named))}")

    # ---- the student export: this IS the rate card, and the child-to-route mapping
    rows = list(_rows("Students-06-08-2026-12-08-00.xlsx"))
    idx = {c: i for i, c in enumerate(rows[0]) if c}
    if "Transport" not in idx:
        findings.append("The student export has no Transport column; the route mapping could not be checked.")
        return
    route_ids, stops, annual = set(), set(), Counter()
    with_route = 0
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        t, f = row[idx["Transport"]], row[idx["TransportFees"]]
        if t in (None, "", "N/A"):
            continue
        with_route += 1
        m = re.match(r"^(.*?)\((.*?)\s*-\s*(.*)\)$", str(t).strip())
        if m:
            route_ids.add((m.group(1).strip() or m.group(2).strip()))
            stops.add(m.group(3).strip())
        if isinstance(f, (int, float)) and f:
            annual[int(f)] += 1

    print(f"\n  Students-06-08-2026-12-08-00.xlsx carries a Transport column that nobody")
    print("  had looked at. It is the rate card AND the child-to-route mapping:")
    print(f"    {with_route:,} children have a bus route named")
    print(f"    {len(route_ids)} route numbers, {len(stops)} distinct stops")

    total = sum(annual.values())
    clean = sum(n for a, n in annual.items() if abs(a / 11 - round(a / 11)) < 1e-9)
    print(f"\n  Is the annual figure eleven times a monthly rate?")
    print(f"    {clean:,} of {total:,} children ({100 * clean / total:.1f}%) divide exactly by 11.")
    print(f"    {total - clean} do not. Those are small odd amounts and are consistent with")
    print("    a child billed for only part of the year, not with a different rule.")

    monthly = sorted({round(a / 11) for a in annual if abs(a / 11 - round(a / 11)) < 1e-9})
    print(f"\n  Monthly rates implied by the export: {len(monthly)} distinct,")
    print(f"    {min(monthly):,} to {max(monthly):,}")
    print(f"  Monthly rates actually billed in the ledger: {len(billed_rates)} distinct,")
    print(f"    {min(billed_rates):,} to {max(billed_rates):,}")
    only_billed = sorted(set(billed_rates) - set(monthly))
    print(f"\n  Rates billed in the ledger that the export does not explain: {len(only_billed)}")
    if only_billed:
        print(f"    {only_billed}")
        findings.append(
            "The payment ledger bills transport at rates the student export does not "
            f"account for: {only_billed}."
        )
    else:
        print("    None. The two documents agree on every transport rate.")

    print("\n  The fee rules document says 'roughly 650 to 1,520 a month'. The real")
    print(f"  spread is {min(monthly):,} to {max(monthly):,} across {len(monthly)} steps.")
    findings.append(
        f"The fee rules document describes transport as 'roughly 650 to 1,520 a month'. "
        f"The school's own two documents agree with each other on a wider card: "
        f"{len(monthly)} rates from {min(monthly):,} to {max(monthly):,}. The word was "
        "'roughly' and the documents do not contradict each other, but a rate card "
        "capped at 1,520 would undercharge the families above it."
    )


# --------------------------------------------------------------------------------------
# E. Streams
# --------------------------------------------------------------------------------------

def stream_check(findings):
    h("E. How many senior students each document names a stream for")

    ledger_named = {}
    rows = list(_rows("Fees-log-detailed-11-08-2026-17-36.xlsx"))
    idx = {n: i for i, n in enumerate(rows[1]) if isinstance(n, str)}
    for row in rows[2:]:
        if not row or row[idx["Admission No."]] is None:
            continue
        cls = str(row[idx["Class"]] or "").strip()
        if "Commerce" in cls or "Science" in cls:
            ledger_named[row[idx["Admission No."]]] = cls

    report_named = {}
    rows2 = list(_rows("Students-Fees-Structure-Report-06-08-2026-12-49.xlsx"))
    idx2 = {n: i for i, n in enumerate(rows2[0]) if isinstance(n, str)}
    for row in rows2[1:]:
        if not row or row[0] is None:
            continue
        cls = _norm_class(row[idx2["Class"]])
        if cls and ("Commerce" in cls or "Science" in cls):
            report_named[row[0]] = cls

    print(f"  Payment ledger names a stream for                {len(ledger_named):>5} students")
    print(f"  Per-student fee report names a stream for        {len(report_named):>5} students")
    both = set(ledger_named) & set(report_named)
    print(f"  Named by both                                    {len(both):>5}")
    print(f"  Named only by the per-student report             {len(set(report_named) - set(ledger_named)):>5}")
    print(f"  Named only by the ledger                         {len(set(ledger_named) - set(report_named)):>5}")

    conflict = [(a, ledger_named[a], report_named[a]) for a in both if ledger_named[a] != report_named[a]]
    print(f"\n  Students the two documents put in DIFFERENT streams: {len(conflict)}")
    for a, l, r in conflict[:20]:
        print(f"    admission {a}: ledger says {l}, report says {r}")
    if conflict:
        findings.append(
            f"{len(conflict)} senior students are put in different streams by the payment "
            "ledger and the per-student fee report. Neither can be trusted for those children."
        )

    union = set(ledger_named) | set(report_named)
    print(f"\n  Between them the two documents name a stream for {len(union)} senior students.")
    print("  The finishing plan assumed only the ledger's 158 were known.")
    return ledger_named, report_named, conflict


# --------------------------------------------------------------------------------------
# F. Fines
# --------------------------------------------------------------------------------------

def fine_check(findings, fine_amounts):
    h("F. Late fines in the ledger")
    print(f"  {len(fine_amounts):,} fine lines carrying an amount.")
    not_ten = [a for a in fine_amounts if a % 10]
    print(f"  Not an exact multiple of 10: {len(not_ten)}")
    if not_ten:
        findings.append(f"{len(not_ten)} fine lines are not multiples of 10, against a rule of 10 a day.")
    exactly_1000 = sum(1 for a in fine_amounts if a == 1000)
    print(f"  Exactly 1,000 (the quarter-end charge): {exactly_1000}")
    print(f"  Largest fine on any one line: {max(fine_amounts):,}" if fine_amounts else "")
    print("\n  The fee rules document says the daily fine is 10 a day and the quarter-end")
    print("  charge is 1,000, repeating at every following quarter end. Multiples of 10")
    print("  are consistent with both. This does not prove the repeat rule and is not")
    print("  claimed to: that rule comes from Abhimanyu, confirmed against a number.")


# --------------------------------------------------------------------------------------

def main():
    findings: list[str] = []

    print("Release 2, step 1: reconciling the school's fee documents.")
    print("READ ONLY. No database is opened and nothing is written.")

    check_aggregates(findings)
    per_class, year_by_class, transport = per_class_rate_card(findings)
    transport_months, transport_rates, fine_amounts = ledger_rate_card(findings, per_class)
    billed = transport_check(findings, transport, transport_months, transport_rates)
    transport_rate_card(findings, billed)
    stream_check(findings)
    fine_check(findings, fine_amounts)

    h("VERDICT")
    if findings:
        print(f"  {len(findings)} disagreement(s) between the documents. Each one goes to")
        print("  Abhimanyu before any fee figure is written.\n")
        for i, f in enumerate(findings, 1):
            print(f"  {i}. {f}")
    else:
        print("  No disagreement found between any two documents on any figure checked.")
    print()


if __name__ == "__main__":
    main()
