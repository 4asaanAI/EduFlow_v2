"""Teacher teaching-scope resolver — the single source of truth for "what classes
and subjects is this teacher assigned to".

Assignments come from the **Academic Structure** (Owner/Principal/Management edit
these in the panel), NOT the legacy seed-only staff fields:

  * Class teacher  →  ``classes.class_teacher_id == teacher.user_id``
  * Subject teacher →  ``subjects.teacher_id == teacher.user_id`` (each subject
    carries the ``class_id`` it belongs to)

A teacher's "assigned classes" is the union of the classes they are class teacher
of and the classes they teach a subject in. Attendance is intentionally narrower
(class-teacher only) — callers pick the field they need.

This module is shared by ``routes/academics.py``, ``routes/attendance.py`` and
``routes/students.py`` so every surface enforces the same, current definition.
"""

from __future__ import annotations

from tenant import scoped_filter, scoped_query


async def compute_teacher_scope(db, user: dict, school_id: str) -> dict:
    """Resolve a teacher's assigned classes & subjects from the Academic Structure.

    Returns a dict with:
      * ``class_teacher_class_ids`` — classes where the user is the class teacher
      * ``subject_class_ids``       — classes where the user teaches a subject
      * ``all_class_ids``           — union of the two above
      * ``subject_ids``             — subjects the user teaches
      * ``classes``                 — full docs for ``all_class_ids`` (for dropdowns)
      * ``subjects``                — full docs for the subjects the user teaches
    """
    uid = user.get("id")
    branch_id = user.get("branch_id")

    class_teacher_classes = await db.classes.find(
        scoped_query({"class_teacher_id": uid}, branch_id=branch_id), {"_id": 0},
    ).to_list(500)

    # Subjects are school-scoped (no branch_id field) and link to a class via class_id.
    my_subjects = await db.subjects.find(
        scoped_filter({"teacher_id": uid}, school_id), {"_id": 0},
    ).to_list(1000)

    class_teacher_ids = sorted({c["id"] for c in class_teacher_classes if c.get("id")})
    subject_class_ids = sorted({s["class_id"] for s in my_subjects if s.get("class_id")})
    all_class_ids = sorted(set(class_teacher_ids) | set(subject_class_ids))

    union_classes = (
        await db.classes.find(
            scoped_filter({"id": {"$in": all_class_ids}}, school_id), {"_id": 0},
        ).to_list(len(all_class_ids))
        if all_class_ids
        else []
    )

    return {
        "class_teacher_class_ids": class_teacher_ids,
        "subject_class_ids": subject_class_ids,
        "all_class_ids": all_class_ids,
        "subject_ids": [s["id"] for s in my_subjects if s.get("id")],
        "classes": union_classes,
        "subjects": my_subjects,
    }


def empty_scope() -> dict:
    """Scope payload for a user with no teaching assignments (or a non-teacher)."""
    return {
        "class_teacher_class_ids": [],
        "subject_class_ids": [],
        "all_class_ids": [],
        "subject_ids": [],
        "classes": [],
        "subjects": [],
    }
