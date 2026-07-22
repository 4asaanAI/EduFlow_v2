from __future__ import annotations

"""Ordering for school classes — the server-side twin of ``lib/classOrder.js``.

Classes are stored in insertion order, which is effectively random
("11th-A, 1st-A, 2nd-C, 2nd-E, 3rd-A, ... LKG-A, NUR-D"). Sorting the
``class_id`` column, as ``GET /api/students?sort=class`` did before Epic 3,
orders by a random UUID and produces a list in no order at all.

A plain alphabetical sort is no better: it puts 10th, 11th and 12th ahead of
1st and scatters the pre-primary classes.

The Aaryans runs NUR -> LKG -> UKG -> 1st ... 12th, each with sections A-E.

This module and ``frontend/src/lib/classOrder.js`` implement the SAME rule and
must be changed together; ``tests/backend/unit/test_class_order.py`` pins the
cases that prove they agree.
"""

import re

# Pre-primary comes before class 1 and has no numeric form of its own.
_PRE_PRIMARY = {
    "PRE_NUR": -4, "PRENUR": -4,
    "NUR": -3, "NURSERY": -3,
    "LKG": -2,
    "UKG": -1,
}

_UNRANKED = 10 ** 9  # unknown names sort last rather than raising

_ROMAN = {"I": 1, "V": 5, "X": 10}
_ROMAN_RE = re.compile(r"^(X{0,3})(IX|IV|V?I{0,3})")
_ARABIC_RE = re.compile(r"(\d+)")


def class_rank(name: str | None) -> int:
    """A sortable rank for a class name like "NUR", "1st", "10th", "XII".

    Unknown values sort last rather than raising, so one stray record never
    breaks a whole listing.
    """
    if not name:
        return _UNRANKED
    key = re.sub(r"[\s.\-]+", "_", str(name).strip().upper())

    if key in _PRE_PRIMARY:
        return _PRE_PRIMARY[key]

    arabic = _ARABIC_RE.search(key)
    if arabic:
        return int(arabic.group(1))

    # Roman numerals, as used on the school's own paperwork ("III-A", "XII Sci")
    roman = _ROMAN_RE.match(key)
    if roman and (roman.group(1) or roman.group(2)):
        s = roman.group(1) + roman.group(2)
        total = 0
        for i, ch in enumerate(s):
            cur = _ROMAN[ch]
            nxt = _ROMAN.get(s[i + 1]) if i + 1 < len(s) else None
            total += -cur if (nxt and cur < nxt) else cur
        if total > 0:
            return total

    return _UNRANKED


def class_sort_key(cls: dict) -> tuple:
    """Sort key for a class record: school order, then section A->E."""
    return (
        class_rank(cls.get("name")),
        str(cls.get("section") or "").upper(),
        str(cls.get("name") or ""),
    )


def ordered_class_ids(classes: list) -> list:
    """Class ids in school order, for ``$indexOfArray`` ranking in a pipeline."""
    return [c["id"] for c in sorted(classes, key=class_sort_key) if c.get("id")]
