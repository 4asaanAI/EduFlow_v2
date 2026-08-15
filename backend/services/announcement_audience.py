"""Who an announcement actually reaches.

Before this existed, an announcement aimed "By Class" saved the chosen classes and then
**nothing ever read them back**. Delivery was decided by role alone, so a notice meant for
one class was shown to every student in the school. The person sending it had no way to
tell: the screen accepted the classes and reported success.

This module is the single answer to "does this announcement reach this person", used by
every entrance that writes one and every surface that reads one. Adding a new screen or a
new Flo tool means calling these functions, not writing the rule again.

--------------------------------------------------------------------------------
Class targeting is by class ID, never by a printed label
--------------------------------------------------------------------------------

The two sending screens wrote the same class in different words: Announcements wrote
``10th A`` and the Circular sender wrote ``10th-A``. Any fix that compares labels has to
pick a winner and silently mis-targets whatever it did not pick.

So a class audience is stored as ``audience_class_ids``, resolved at write time against
the school's own class list. ``audience_classes`` is kept beside it for display only and
is never used to decide who receives anything. Whatever wording a caller sends is resolved
through ``normalise_class_label``, so both screens, Flo, and anything written later agree
without having to know about each other.

--------------------------------------------------------------------------------
Default deny
--------------------------------------------------------------------------------

A class-targeted announcement that resolved to no classes reaches **nobody**. It is not
treated as "no restriction", because that is the original fault pointing the other way:
a targeting mistake would quietly become a school-wide broadcast. The write paths refuse
to create one, so this is the belt beside the braces.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

CLASS_AUDIENCE = "class"
ALL_AUDIENCE = "all"

#: Roles a person can hold that make them a member of a class. Everyone else (teachers,
#: office staff, the owner) is never narrowed by a class audience; they are reached, or
#: not, by role exactly as before.
CLASS_BOUND_ROLES = ("student", "parent")

_NON_ALNUM = re.compile(r"[^0-9A-Z]+")


def normalise_class_label(value: Any) -> str:
    """Collapse any way of writing a class into one comparable key.

    ``10th A``, ``10th-A``, ``10TH  -  a`` and ``Class 10th A`` all become ``10TH|A``.
    Anything unusable becomes an empty string, which matches nothing.
    """
    if value is None:
        return ""
    text = _NON_ALNUM.sub(" ", str(value).upper()).strip()
    if not text:
        return ""
    parts = [p for p in text.split(" ") if p]
    if parts and parts[0] == "CLASS":
        parts = parts[1:]
    return "|".join(parts)


def class_row_key(cls: Dict[str, Any]) -> str:
    """The comparable key for a row from the ``classes`` collection."""
    name = cls.get("name") or ""
    section = cls.get("section") or ""
    return normalise_class_label(f"{name} {section}")


def class_row_label(cls: Dict[str, Any]) -> str:
    """The one way this platform prints a class, so both screens agree from now on."""
    name = str(cls.get("name") or "").strip()
    section = str(cls.get("section") or "").strip()
    return f"{name} {section}".strip() if section else name


async def resolve_audience_classes(
    db,
    class_ids: Optional[Sequence[str]] = None,
    class_labels: Optional[Sequence[str]] = None,
) -> Tuple[List[str], List[str], List[str]]:
    """Turn whatever a caller sent into real class ids.

    Accepts ids, printed labels, or both, in any of the wordings the screens use.
    Returns ``(resolved_ids, display_labels, unmatched)``. ``unmatched`` is never
    discarded silently: the write paths refuse the request and name what did not match,
    because a class quietly dropped is indistinguishable from one that was delivered.
    """
    rows = await db.classes.find({}, {"_id": 0, "id": 1, "name": 1, "section": 1}).to_list(1000)
    by_id = {str(row.get("id")): row for row in rows if row.get("id")}
    by_key: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = class_row_key(row)
        if key:
            by_key.setdefault(key, row)

    resolved: List[str] = []
    labels: List[str] = []
    unmatched: List[str] = []
    seen: Set[str] = set()

    def _take(row: Dict[str, Any]) -> None:
        cid = str(row.get("id"))
        if cid in seen:
            return
        seen.add(cid)
        resolved.append(cid)
        labels.append(class_row_label(row))

    for raw in list(class_ids or []):
        key = str(raw)
        if key in by_id:
            _take(by_id[key])
        else:
            unmatched.append(key)

    for raw in list(class_labels or []):
        key = str(raw)
        # A screen may send an id in the labels field; accept it rather than reject a
        # request that is perfectly clear about which class it means.
        if key in by_id:
            _take(by_id[key])
            continue
        row = by_key.get(normalise_class_label(raw))
        if row is not None:
            _take(row)
        else:
            unmatched.append(key)

    return resolved, labels, unmatched


async def reader_class_ids(db, user: Dict[str, Any]) -> Set[str]:
    """The classes this person belongs to, for deciding what reaches them.

    A student is in their own class. A parent stands in for every ward they are linked
    to. Everybody else belongs to no class, which is why a class audience never reaches
    them: it is not a demotion, it is what "by class" means.
    """
    role = str(user.get("role") or "")
    user_id = user.get("id")
    if not user_id:
        return set()

    if role == "student":
        own = await db.students.find_one({"user_id": user_id}, {"_id": 0, "class_id": 1})
        cid = (own or {}).get("class_id")
        return {str(cid)} if cid else set()

    if role == "parent":
        links = await db.guardians.find({"user_id": user_id}, {"_id": 0, "student_id": 1}).to_list(200)
        student_ids = [row["student_id"] for row in links if row.get("student_id")]
        if not student_ids:
            return set()
        wards = await db.students.find(
            {"id": {"$in": student_ids}}, {"_id": 0, "class_id": 1}
        ).to_list(len(student_ids))
        return {str(w["class_id"]) for w in wards if w.get("class_id")}

    return set()


def is_class_targeted(ann: Dict[str, Any]) -> bool:
    return str(ann.get("audience_type") or "") == CLASS_AUDIENCE


def class_visibility_clause(classes: Iterable[str]) -> Dict[str, Any]:
    """A Mongo clause the database can apply, so paging and counts stay honest.

    Filtering after the fact would make "showing 20 of 60" a lie, and the whole point of
    this work is that a partial answer must never look like a complete one.
    """
    ids = [str(c) for c in classes if c]
    return {
        "$or": [
            {"audience_type": {"$ne": CLASS_AUDIENCE}},
            {"audience_class_ids": {"$in": ids}},
        ]
    }


def reaches(ann: Dict[str, Any], user: Dict[str, Any], classes: Iterable[str]) -> bool:
    """Does this announcement reach this person? The same rule as the Mongo clause.

    Used where the rows are already in hand. Answers the class question only; whether the
    row is published, and whether the ROLE matches, stay with the caller, which is how
    each surface keeps its own existing rules about drafts and approvals.
    """
    if not is_class_targeted(ann):
        return True
    targeted = {str(c) for c in (ann.get("audience_class_ids") or []) if c}
    if not targeted:
        return False
    return bool(targeted & {str(c) for c in classes if c})
