"""One place that turns a spoken class label into the class record it means.

Why this exists (owner report, 2026-08-07). Every AI tool used to resolve a class by
regex-matching the `name` field alone::

    db.classes.find_one({"name": {"$regex": re.escape(params["class_name"])}})

Class records store the grade and the section in **separate fields** - ``name="4th"``,
``section="C"`` - while every screen in the product *displays* them joined: "4th-C",
"1st-B", "UKG-C". So the label a person reads off the screen and types into chat was the
one form that could never match. Asked "who is in 4-C", the assistant reported nobody,
and the school was told a class was empty when a child was sitting in it.

The failure was silent in a second way: when the lookup found nothing, the caller
dropped the class filter and answered about the *whole school* instead of saying it
could not find the class. Callers now get ``None`` and are expected to say so.

Matching is done in Python over the class list rather than in the query, because the
school has 48 classes and the normalisation below (ordinals, roman numerals, "Class"
prefixes, punctuation) is not expressible as a Mongo regex.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# "class 4", "grade 4", "std 4", "standard 4" - noise words before the grade.
_LEADING_NOISE = re.compile(r"^(?:in\s+)?(?:the\s+)?(?:class|grade|std|standard|section)\s+", re.I)
# The ordinal tail on a numeral: 1st, 2nd, 3rd, 4th. Dropped so "4" and "4th" agree.
# Deliberately not anchored to a word boundary: people type "4thc" with no separator,
# and a digit followed by st/nd/rd/th is an ordinal in every class label there is.
_ORDINAL_TAIL = re.compile(r"(?<=\d)(?:st|nd|rd|th)", re.I)
_NON_ALNUM = re.compile(r"[^a-z0-9]")

# Roman numerals appear on printed CBSE lists ("IV-C"). Only the grades a school can
# actually have, so a section letter "I" or "V" is never mistaken for a numeral.
_ROMAN_GRADES = {
    "i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6",
    "vii": "7", "viii": "8", "ix": "9", "x": "10", "xi": "11", "xii": "12",
}

# Pre-primary grades under the names the school uses, plus what people call them.
_GRADE_ALIASES = {
    "nursery": "nur",
    "nsy": "nur",
    "prenursery": "prenur",
    "kg1": "lkg",
    "kg2": "ukg",
    "lowerkg": "lkg",
    "upperkg": "ukg",
}


def _normalise(text: str) -> str:
    """Reduce any way of writing a class to one comparable token.

    ``"4-C"``, ``"4th C"``, ``"Class IV-C"`` and ``"4thc"`` all become ``"4c"``.
    """
    s = (text or "").strip()
    # Strip repeated lead-ins: "in the class 4-C".
    for _ in range(3):
        stripped = _LEADING_NOISE.sub("", s)
        if stripped == s:
            break
        s = stripped
    s = _ORDINAL_TAIL.sub("", s)
    s = _NON_ALNUM.sub("", s.lower())

    # A leading roman numeral, where what follows is a single section letter or nothing.
    for length in (4, 3, 2, 1):
        head, tail = s[:length], s[length:]
        if head in _ROMAN_GRADES and (tail == "" or (len(tail) == 1 and tail.isalpha())):
            s = _ROMAN_GRADES[head] + tail
            break

    for alias, canonical in _GRADE_ALIASES.items():
        if s.startswith(alias):
            s = canonical + s[len(alias):]
            break
    return s


def _class_tokens(cls: Dict[str, Any]) -> tuple:
    """The (grade+section, grade) pair a class record can be matched on."""
    grade = _normalise(str(cls.get("name") or ""))
    section = _normalise(str(cls.get("section") or ""))
    return grade + section, grade


def match_classes(classes: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    """Every class the label could mean, most specific first.

    A label naming a section ("4-C") matches exactly that class. A label naming only a
    grade ("4th") matches every section of it, which is a real and useful answer -
    "how many in class 4" spans 4-A, 4-B and 4-C. Callers decide whether more than one
    match is acceptable; :func:`resolve_class` does not.
    """
    wanted = _normalise(label)
    if not wanted:
        return []
    exact, grade_wide = [], []
    for cls in classes:
        full, grade = _class_tokens(cls)
        if full == wanted:
            exact.append(cls)
        elif grade == wanted:
            grade_wide.append(cls)
    return exact + grade_wide


async def find_classes(db, label: str, base_query: Optional[dict] = None) -> List[Dict[str, Any]]:
    """Load the caller's visible classes and match `label` against them.

    `base_query` is the caller's own scoping - pass the result of ``scoped_query`` or
    ``scoped_filter`` so branch and school isolation is preserved. The previous
    per-tool lookups queried `db.classes` with **no** scoping at all, which is how a
    class name could be resolved across tenants; passing the scope here closes that.
    """
    classes = await db.classes.find(dict(base_query or {}), {"_id": 0}).to_list(200)
    return match_classes(classes, label)


async def resolve_class(db, label: str, base_query: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    """The one class this label means, or ``None`` if it names none or several.

    ``None`` means "say you could not find it" - never "carry on without a filter".
    """
    matches = await find_classes(db, label, base_query)
    return matches[0] if len(matches) == 1 else None


def describe_no_match(label: str, classes: List[Dict[str, Any]]) -> str:
    """A message that tells the reader what they could have asked for instead."""
    available = sorted(
        f"{c.get('name', '')}-{c.get('section', '')}".strip("-")
        for c in classes
    )
    if not available:
        return f"I could not find a class called {label}."
    shown = ", ".join(available[:12])
    more = f" and {len(available) - 12} more" if len(available) > 12 else ""
    return f"I could not find a class called {label}. The classes are: {shown}{more}."
