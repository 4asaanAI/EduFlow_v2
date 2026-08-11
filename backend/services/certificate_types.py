"""R2-9 - one vocabulary for the school's official documents.

Before this file there were **three** different names for the same piece of paper, in
three places that all had to agree and never did:

===========================  ==================================================
`certificate_service.py:20`  bonafide, tc, transfer_certificate, character, merit
`routes/image_gen.py:34`     transfer, bonafide, character, sports, participation,
                             migration
Flo's tool schema            bonafide, tc, transfer_certificate, character, merit,
                             participation
===========================  ==================================================

Only ``bonafide`` and ``character`` appeared in all of them. The consequences were real,
not theoretical:

* The Certificate Generator screen's dropdown uses the **printer's** words, so a Transfer
  Certificate raised from that screen was stored as ``transfer`` - which is not in the
  approval list - and was therefore **auto-issued to anybody**, including the two people
  the school explicitly wanted to hold back. The single most sensitive document the
  school produces was the one the mismatch let through.
* ``migration``, ``sports`` and ``participation`` could be printed and had no approval
  rule of any kind.
* ``tc`` and ``merit`` could be approved but could never be printed.

This module is the one place that decides what a document is called, whether it needs
approving, and what it is called on the page. Everything else asks it.

**Default deny, on purpose.** A document type nobody has classified requires approval
(:func:`requires_approval` returns ``True`` for anything unknown). The safe direction for
an unrecognised official document is to ask a human, so a new type added carelessly
fails closed rather than printing itself.
"""

from __future__ import annotations

from typing import Dict, FrozenSet

# ── The documents, by canonical name ─────────────────────────────────────────
#
# `approval` answers Aman's decision 6 of 2026-08-10: the owner and the principal issue
# directly; everybody else creates a request and waits.
#
# The rule for which documents need it, agreed in plan §1.6: a document that asserts a
# FACT ABOUT A CHILD'S STANDING needs approving, because the school is vouching for it.
# An award for taking part does not - nobody is harmed by an unapproved certificate
# saying a child ran in the sports day.
#
# `printable` says whether `routes/image_gen.py` has a template for it. `merit` is a
# record-only type: it can be requested and approved, and there is no page to print,
# which is how it has always been.
_DOCUMENTS: Dict[str, Dict] = {
    "transfer_certificate": {
        "label": "Transfer Certificate",
        "approval": True,   # ends a child's enrolment at the school
        "printable": True,
        "aliases": ("transfer", "tc"),
    },
    "bonafide": {
        "label": "Bonafide Certificate",
        "approval": True,   # asserts the child is on the roll
        "printable": True,
        "aliases": (),
    },
    "character": {
        "label": "Character Certificate",
        "approval": True,   # the school vouches for the child's conduct
        "printable": True,
        "aliases": (),
    },
    "migration": {
        "label": "Migration Certificate",
        "approval": True,   # asserts dues and formalities are cleared
        "printable": True,
        "aliases": (),
    },
    "merit": {
        "label": "Merit Certificate",
        "approval": True,   # asserts an academic standing; record-only, no template
        "printable": False,
        "aliases": (),
    },
    "sports": {
        "label": "Sports Certificate",
        "approval": False,  # an award for taking part, not a claim about standing
        "printable": True,
        "aliases": (),
    },
    "participation": {
        "label": "Participation Certificate",
        "approval": False,  # likewise
        "printable": True,
        "aliases": (),
    },
    "id_card": {
        # Not a certificate, and it shares this table because decision 6 puts it under
        # exactly the same rule and the school runs one approval queue, not two. An ID
        # card carries the school's name and a child's identity, so the owner and the
        # principal issue it and everyone else asks.
        "label": "Student ID Cards",
        "approval": True,
        "printable": True,
        "aliases": ("id_cards", "idcard"),
    },
}

_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _entry in _DOCUMENTS.items():
    _ALIAS_TO_CANONICAL[_canonical] = _canonical
    for _alias in _entry["aliases"]:
        _ALIAS_TO_CANONICAL[_alias] = _canonical

CANONICAL_TYPES: FrozenSet[str] = frozenset(_DOCUMENTS)
PRINTABLE_TYPES: FrozenSet[str] = frozenset(
    name for name, entry in _DOCUMENTS.items() if entry["printable"]
)
APPROVAL_REQUIRED_TYPES: FrozenSet[str] = frozenset(
    name for name, entry in _DOCUMENTS.items() if entry["approval"]
)
ID_CARD_TYPE = "id_card"


def canonical_type(value) -> str:
    """The canonical name for whatever anybody called this document.

    ``transfer`` and ``tc`` both mean ``transfer_certificate``. An unrecognised name is
    returned tidied but unchanged, so it can still be stored, logged and refused by
    name rather than silently becoming something else.
    """
    tidy = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return _ALIAS_TO_CANONICAL.get(tidy, tidy)


def requires_approval(value) -> bool:
    """Does this document need the owner's or the principal's say-so before it exists?

    **An unknown type answers yes.** See the module docstring: failing closed is the
    only safe default for a document that carries the school's name.
    """
    canonical = canonical_type(value)
    entry = _DOCUMENTS.get(canonical)
    if entry is None:
        return True
    return bool(entry["approval"])


def is_printable(value) -> bool:
    return canonical_type(value) in PRINTABLE_TYPES


def document_label(value) -> str:
    """What the document is called on the page and in a message to a person."""
    canonical = canonical_type(value)
    entry = _DOCUMENTS.get(canonical)
    if entry is not None:
        return entry["label"]
    return canonical.replace("_", " ").title() or "Certificate"


def same_document(left, right) -> bool:
    """Are these two names for the same document? ``transfer`` == ``transfer_certificate``."""
    return canonical_type(left) == canonical_type(right)
