"""Release 2, step 6 - who the school itself says is a brother or sister.

Reads the school's payment ledger and nothing else. **Touches no database.**

    backend/.venv/Scripts/python.exe scripts/sibling_links.py

--------------------------------------------------------------------------------
Why only the ledger, and only the remarks column
--------------------------------------------------------------------------------

Abhimanyu, 2026-08-11: **use only the siblings the school has itself defined**, and put
everything else in a file the school can read, to be handed over with the credentials.

The office has been writing the link by hand for years, in the remark on a payment, in
the form ``SIB NO - 221858``. That is the school stating a fact about a family. Grouping
children by father's name and mobile number would find more families, and every one of
them would be a guess: a wrong guess either overcharges a family or gives away money.

--------------------------------------------------------------------------------
Two traps in the remarks, both real
--------------------------------------------------------------------------------

1. **``SBI`` is a bank, ``SIB`` is a sibling**, and both appear in the same column, often
   in the same sentence. A pattern that is not anchored on the whole word ``sib`` picks up
   bank reference numbers and invents families.
2. **The office spells it eleven different ways**: ``SIB NO``, ``SIB N0`` with a zero,
   ``SIB.``, ``SIB NBO``, ``SIB NI``, and sometimes the admission number comes first.

So every number this finds must ALSO be a real admission number in the ledger and must not
be the child's own. A number that fails either check is discarded and the line is reported
as unreadable rather than being made to fit.

--------------------------------------------------------------------------------
What comes out
--------------------------------------------------------------------------------

* **the stated families**, built by joining up the links, so that a link written on one
  child's line puts both of them in the same family
* **who the school actually discounted**, which is a separate and stronger fact: the
  concession is copied from what the office did, never inferred from who looks youngest
* **everything a person still has to settle**, which becomes the handover file
"""

from __future__ import annotations

import collections
import json
import os
import re
import sys

LEDGER = "aaryans_database/Fees-log-detailed-11-08-2026-17-36.xlsx"

# The seven sibling concession values, from the school's 2026-27 fee sheet. A discount
# line at exactly one of these is the office applying the sibling concession.
SIBLING_VALUES = {1410, 1560, 1650, 1800, 2100, 2610, 2910}

# The admission number is looked for in a short window either side of the whole word
# "sib", rather than by a pattern that has to know the office's spelling. That is what
# copes with ``SIB N0`` (a zero, not the letter O), where a stray digit sits between the
# word and the number and defeats any "the number comes straight after" rule.
_MENTIONS_SIB = re.compile(r"\bsib\b", re.I)
_NUMBER = re.compile(r"(?<!\d)(\d{4,7})(?!\d)")
_WINDOW_AFTER = 22
_WINDOW_BEFORE = 12

COL_ADMISSION, COL_NAME, COL_FATHER, COL_CLASS = 1, 2, 3, 5
COL_DISCOUNT, COL_REMARK = 10, 21


def read_ledger(root: str) -> list[tuple]:
    import openpyxl

    path = os.path.join(root, LEDGER)
    book = openpyxl.load_workbook(path, read_only=True)
    return list(book.active.iter_rows(values_only=True))[2:]


def analyse(rows: list[tuple]) -> dict:
    known = {str(r[COL_ADMISSION]).strip() for r in rows if r[COL_ADMISSION]}
    who = {}
    links: dict[str, set[str]] = collections.defaultdict(set)
    discounted: set[str] = set()
    unreadable: list[dict] = []

    for row in rows:
        adm = str(row[COL_ADMISSION]).strip() if row[COL_ADMISSION] else ""
        if not adm:
            continue
        who.setdefault(adm, {
            "admission_number": adm,
            "name": str(row[COL_NAME] or "").strip(),
            "father": str(row[COL_FATHER] or "").strip(),
            "class": str(row[COL_CLASS] or "").strip(),
        })
        try:
            amount = float(row[COL_DISCOUNT] or 0)
        except (TypeError, ValueError):
            amount = 0
        if amount in SIBLING_VALUES:
            discounted.add(adm)

        remark = str(row[COL_REMARK] or "").strip()
        if not remark or not _MENTIONS_SIB.search(remark):
            continue
        found = set()
        for mention in _MENTIONS_SIB.finditer(remark):
            window = remark[mention.end():mention.end() + _WINDOW_AFTER]
            found |= {m.group(1) for m in _NUMBER.finditer(window)}
            behind = remark[max(0, mention.start() - _WINDOW_BEFORE):mention.start()]
            found |= {m.group(1) for m in _NUMBER.finditer(behind)}
        found = {n for n in found if n in known and n != adm}
        if found:
            links[adm] |= found
        else:
            unreadable.append({"admission_number": adm, "remark": remark})

    # Join the links up into families. The office usually writes the link on one child's
    # line only, so a family of three can arrive as two separate statements.
    parent: dict[str, str] = {}

    def root_of(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for child, partners in links.items():
        for partner in partners:
            parent[root_of(child)] = root_of(partner)

    grouped: dict[str, set[str]] = collections.defaultdict(set)
    for node in list(parent):
        grouped[root_of(node)].add(node)

    families = []
    odd = []
    for members in grouped.values():
        members = sorted(members)
        paying_full = [m for m in members if m not in discounted]
        family = {
            "members": members,
            "discounted": [m for m in members if m in discounted],
            "paying_full": paying_full,
        }
        families.append(family)
        # The school's rule is that exactly one child in a family pays full.
        if len(paying_full) != 1:
            odd.append(family)

    in_a_family = set().union(*grouped.values()) if grouped else set()
    return {
        "who": who,
        "families": sorted(families, key=lambda f: f["members"]),
        "odd_families": odd,
        "unreadable": unreadable,
        "discounted": sorted(discounted),
        "discounted_with_no_stated_family": sorted(discounted - in_a_family),
        "to_mark": sorted(discounted & in_a_family),
        "children_in_a_stated_family": len(in_a_family),
    }


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = analyse(read_ledger(root))

    print(f"  stated families                         {len(out['families']):>5}")
    print(f"  children in one                         {out['children_in_a_stated_family']:>5}")
    print(f"  children the school discounted          {len(out['discounted']):>5}")
    print(f"  -> to mark (discounted AND stated)      {len(out['to_mark']):>5}")
    print(f"  -> discounted but no sibling named      {len(out['discounted_with_no_stated_family']):>5}")
    print(f"  families where one child does not pay full {len(out['odd_families']):>4}")
    print(f"  remarks mentioning a sibling, unreadable {len(out['unreadable']):>4}")

    sizes = collections.Counter(len(f["members"]) for f in out["families"])
    print("\n  family sizes: " + ", ".join(f"{n} children x{c}" for n, c in sorted(sizes.items())))

    path = os.path.join(root, "aaryans_database", "_sibling_links.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({k: v for k, v in out.items() if k != "who"}, handle, indent=2)
    print(f"\n  written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
