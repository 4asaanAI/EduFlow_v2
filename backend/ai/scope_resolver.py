from __future__ import annotations

"""
Deterministic scope resolver for EduFlow.

Called before EVERY tool invocation or query to produce the exact MongoDB
filter that limits what data the requesting user can see or modify.

Design principles
-----------------
* **Deterministic**: same (user, staff-record) always yields the same scope.
* **Deny-by-default**: if a role or sub-category is unrecognised the scope
  restricts to "self only".
* **Single DB round-trip**: the staff lookup is cached for the lifetime of
  the request via the returned ``Scope`` object so callers never re-fetch.

Roles and sub-categories
-------------------------
owner
    Sees everything across all branches.

admin
    principal          -- all operational data
    accountant         -- financial data only
    transport_head     -- transport data only
    receptionist       -- enquiries only
    support_staff      -- self only

teacher
    hod                -- subject-wide across all classes
    coordinator        -- class range (1-5, 6-8, 9-12)
    class_teacher      -- own class-section
    subject_teacher    -- assigned classes only
    kg_incharge        -- own KG class

student
    Self only.

Usage
-----
    from ai.scope_resolver import resolve_scope

    scope = await resolve_scope(user)
    mongo_filter = scope.filter()           # dict you pass to Motor queries
    if scope.can_see_financial_data():
        ...
    if scope.can_see_personal_info(target_user):
        ...
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from database import get_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Coordinator class-range definitions: label -> list of class-name prefixes.
COORDINATOR_RANGES: Dict[str, List[str]] = {
    "1-5":  [f"Class {n}" for n in range(1, 6)],
    "6-8":  [f"Class {n}" for n in range(6, 9)],
    "9-12": [f"Class {n}" for n in range(9, 13)],
}

# Roles ordered from most to least privileged (lower number = higher rank).
_ROLE_RANK: Dict[str, int] = {
    "owner": 0,
    "admin": 1,
    "teacher": 2,
    "student": 3,
}

# Admin sub-categories that have full operational visibility.
_ADMIN_FULL_OPS: frozenset = frozenset({"principal"})

# Admin sub-categories mapped to their restricted domain.
_ADMIN_DOMAIN_MAP: Dict[str, str] = {
    "accountant": "financial",
    "transport_head": "transport",
    "receptionist": "enquiries",
}


# ---------------------------------------------------------------------------
# Scope dataclass
# ---------------------------------------------------------------------------

@dataclass
class Scope:
    """Data bag returned by :func:`resolve_scope`.

    Attributes
    ----------
    type : str
        One of ``"all"``, ``"branch"``, ``"class_list"``, ``"subject"``,
        ``"domain"``, ``"self_only"``.
    role : str
        Original role from the user dict (``owner | admin | teacher | student``).
    sub_category : str | None
        Staff sub-category looked up from MongoDB (e.g. ``"principal"``,
        ``"hod"``, ``"coordinator"``).
    user_id : str
        The requesting user's id.
    branch_id : str | None
        Populated when scope is branch-level (future multi-branch support).
    class_ids : list[str]
        Explicit list of class ``id`` values the user may access.
        Empty list means "no class restriction" when type is ``"all"`` or
        ``"domain"``; for ``"class_list"`` an empty list means no classes
        could be resolved (effectively self-only).
    student_id : str | None
        Set when the user is a student -- their own student record id.
    subject : str | None
        Set for HODs -- the subject they oversee school-wide.
    domain : str | None
        Set for domain-restricted admins (``"financial"``, ``"transport"``,
        ``"enquiries"``).
    staff_record : dict | None
        The raw staff document from MongoDB, cached for downstream use.
    """

    type: str
    role: str
    sub_category: Optional[str] = None
    user_id: str = ""
    branch_id: Optional[str] = None
    class_ids: List[str] = field(default_factory=list)
    student_id: Optional[str] = None
    subject: Optional[str] = None
    domain: Optional[str] = None
    staff_record: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        # Part 1.5 Patch E: an empty-string user_id silently turns Scope into
        # an oracle (can_see_personal_info matches "" == "" for any target
        # without an id; self-only filter becomes {"user_id": ""}). Fail
        # closed at construction so the issue surfaces at the call site.
        if not isinstance(self.user_id, str) or self.user_id == "":
            raise ValueError(
                "Scope.user_id must be a non-empty string; "
                "got %r (callers must propagate the authenticated user id)" % (self.user_id,)
            )

    # ------------------------------------------------------------------
    # MongoDB filter builder
    # ------------------------------------------------------------------

    def filter(self, *, collection: str = "students") -> Dict[str, Any]:
        """Return a MongoDB query filter dict for the given collection.

        Parameters
        ----------
        collection : str
            The target collection name.  The filter adjusts the key used for
            class membership (``class_id`` for students/attendance, ``id`` for
            classes, etc.).

        Returns
        -------
        dict
            A filter that can be spread into ``db.<col>.find(scope.filter())``.

        Part 2 Patch P1: when ``self.branch_id`` is set, a ``branch_id``
        clause is ALWAYS added to the returned filter (composed via ``$and``
        when other clauses already exist) — even for ``type="all"`` and
        ``type="domain"``. Previously only ``type="branch"`` consulted
        branch_id, and that type was never produced; ``_apply_branch_filter``
        in tool_functions_v2 was a permanent no-op.
        """

        base = self._raw_filter(collection)
        if not self.branch_id:
            return base
        # Compose with branch_id. Avoid double-clause if the inner filter
        # already pinned branch_id (defensive — shouldn't happen).
        if "branch_id" in base:
            return base
        if not base:
            return {"branch_id": self.branch_id}
        if "$and" in base:
            return {"$and": [*base["$and"], {"branch_id": self.branch_id}]}
        return {"$and": [base, {"branch_id": self.branch_id}]}

    def _raw_filter(self, collection: str) -> Dict[str, Any]:
        """Type-based filter, without the branch_id wrapper. See ``filter()``."""

        if self.type == "all":
            return {}

        if self.type == "branch" and self.branch_id:
            return {"branch_id": self.branch_id}

        if self.type == "domain":
            # Domain-restricted admins.  The caller must check
            # ``allowed_collections()`` to decide whether the query is even
            # permitted.  Within the allowed collection we return an empty
            # filter (unrestricted within that domain).
            return {}

        if self.type == "self_only":
            if self.student_id and collection in (
                "students",
                "student_attendance",
                "fee_transactions",
                "exam_results",
            ):
                id_key = "student_id" if collection != "students" else "id"
                return {id_key: self.student_id}
            # Staff self-only -- restrict by user_id.
            return {"user_id": self.user_id}

        if self.type == "subject" and self.subject:
            # HOD sees everything for their subject across all classes.
            if collection == "subjects":
                return {"name": self.subject}
            if collection in ("students", "student_attendance", "assignments"):
                if self.class_ids:
                    return {"class_id": {"$in": self.class_ids}}
                return {}
            return {}

        if self.type == "class_list" and self.class_ids:
            if collection in ("students", "student_attendance", "assignments"):
                return {"class_id": {"$in": self.class_ids}}
            if collection == "classes":
                return {"id": {"$in": self.class_ids}}
            # fee_transactions / exam_results don't carry class_id directly;
            # caller must join via student_ids.
            if collection in ("fee_transactions", "exam_results"):
                return {}
            return {"class_id": {"$in": self.class_ids}}

        # Fallback -- self only.
        logger.warning(
            "scope.filter() fell through to self-only fallback for "
            "user=%s type=%s",
            self.user_id,
            self.type,
        )
        return {"user_id": self.user_id}

    # ------------------------------------------------------------------
    # Authorisation helpers
    # ------------------------------------------------------------------

    def can_see_personal_info(self, target: Dict[str, Any]) -> bool:
        """Check whether this user may view *target*'s personal info.

        Personal info includes phone numbers, addresses, guardian details, and
        financial records tied to an individual.

        Parameters
        ----------
        target : dict
            A user dict with at least ``{"id": "...", "role": "..."}``.

        Returns
        -------
        bool
            Deterministic result for the same (self, target) pair.
        """

        target_role: str = target.get("role", "student")
        target_id: str = target.get("id", "")

        # Anyone can see their own info. Guard against empty target_id so
        # `target_id == self.user_id` is never an empty-string match. Scope
        # construction already forbids empty self.user_id; this is defense
        # in depth for malformed target dicts.
        if target_id and target_id == self.user_id:
            return True

        # Owner sees everything.
        if self.role == "owner":
            return True

        # Admin sub-categories.
        if self.role == "admin":
            if self.sub_category in _ADMIN_FULL_OPS:
                # Principal can see all operational personal info.
                return True
            if self.sub_category == "accountant":
                # Accountant can see student/guardian financial-adjacent info
                # but not fellow staff personal info.
                return target_role == "student"
            if self.sub_category == "receptionist":
                # Receptionist can see enquiry-related personal info only
                # (students and their guardians).
                return target_role == "student"
            # transport_head, support_staff, unrecognised -- self only.
            return False

        # Teachers can see personal info of students within their scope.
        if self.role == "teacher":
            if target_role == "student":
                if self.class_ids:
                    # Check whether the student's class is in our scope.
                    return target.get("class_id") in self.class_ids
                # HOD with subject scope -- allowed for all students in
                # subject classes.
                if self.type == "subject":
                    return True
            return False

        # Students can only see themselves (handled by the self-check above).
        return False

    def can_see_financial_data(self) -> bool:
        """Return whether this user may access financial data.

        Financial data includes fee transactions, salary details, revenue
        reports, and accounting ledgers.

        Returns
        -------
        bool
            Deterministic result for the same scope.
        """

        if self.role == "owner":
            return True

        if self.role == "admin":
            # Principal and accountant can see financial data. Legacy admin
            # rows with no sub_category are denied (Part 1 hardening) —
            # migration 016 backfills these to support_staff.
            return self.sub_category in (_ADMIN_FULL_OPS | {"accountant"})

        if self.role == "student":
            # Students can see their own fee data (self-only filter enforced).
            return True

        # Teachers cannot see financial data.
        return False

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def is_restricted_to_self(self) -> bool:
        """Return ``True`` when the user can only see their own records."""
        return self.type == "self_only"

    def allowed_collections(self) -> Optional[List[str]]:
        """Return the collection names the user may query, or ``None`` if
        unrestricted.

        Domain-restricted admins can only query specific collections.
        """

        if self.domain == "financial":
            return [
                "fee_transactions",
                "fee_structures",
                "students",  # needed for fee lookups by student name
            ]
        if self.domain == "transport":
            return [
                "students",        # transport-using students
                "bus_routes",
                "transport_logs",
            ]
        if self.domain == "enquiries":
            return ["enquiries"]
        return None

    def __repr__(self) -> str:
        parts = [f"type={self.type!r}", f"role={self.role!r}"]
        if self.sub_category:
            parts.append(f"sub_category={self.sub_category!r}")
        if self.class_ids:
            parts.append(f"class_ids=({len(self.class_ids)} classes)")
        if self.student_id:
            parts.append(f"student_id={self.student_id!r}")
        if self.subject:
            parts.append(f"subject={self.subject!r}")
        if self.domain:
            parts.append(f"domain={self.domain!r}")
        return f"Scope({', '.join(parts)})"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def resolve_scope(user: Dict[str, Any], db: Any = None) -> Scope:
    """Look up the user's staff/student record and return a deterministic Scope.

    Parameters
    ----------
    user : dict
        Must contain at minimum ``{"id": str, "role": str}``.
        The ``"name"`` key is expected but not required by this function.
    db : optional
        Motor database instance.  Defaults to ``get_db()`` if not provided.

    Returns
    -------
    Scope

    Raises
    ------
    ValueError
        If ``user`` is missing required keys.
    """

    if not user or "id" not in user or "role" not in user:
        raise ValueError(
            "user dict must contain 'id' and 'role' keys, got: "
            f"{list(user.keys()) if user else None}"
        )

    if db is None:
        db = get_db()

    user_id: str = user["id"]
    role: str = user["role"]
    # Part 2 Patch P1: propagate branch_id from the JWT into every Scope so
    # `_apply_branch_filter` (and any other consumer) is no longer a no-op.
    # Owner intentionally stays None (cross-branch read is part of the role).
    user_branch_id: Optional[str] = user.get("branch_id") if role != "owner" else None

    logger.debug("resolve_scope: user_id=%s role=%s branch_id=%s",
                 user_id, role, user_branch_id)

    # ------------------------------------------------------------------
    # Owner -- unrestricted
    # ------------------------------------------------------------------
    if role == "owner":
        logger.debug("resolve_scope: owner -> scope type='all'")
        return Scope(type="all", role="owner", user_id=user_id, branch_id=None)

    # ------------------------------------------------------------------
    # Student -- self only
    # ------------------------------------------------------------------
    if role == "student":
        student = await db.students.find_one(
            {"user_id": user_id, "is_active": True}
        )
        student_id: Optional[str] = student["id"] if student else None

        if not student:
            logger.warning(
                "resolve_scope: no active student record for user_id=%s",
                user_id,
            )

        return Scope(
            type="self_only",
            role="student",
            user_id=user_id,
            student_id=student_id,
            branch_id=user_branch_id,
        )

    # ------------------------------------------------------------------
    # Admin & Teacher -- require a staff record
    # ------------------------------------------------------------------
    staff = await db.staff.find_one({"user_id": user_id, "is_active": True})

    if not staff:
        logger.warning(
            "resolve_scope: no active staff record for user_id=%s role=%s "
            "-- falling back to self-only",
            user_id,
            role,
        )
        return Scope(type="self_only", role=role, user_id=user_id,
                     branch_id=user_branch_id)

    sub_category: Optional[str] = staff.get("sub_category")

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------
    if role == "admin":
        # Part 1.5 Patch J: designation is NO LONGER honored as a fallback.
        # Previously a legacy admin row with designation="Principal" silently
        # got type=all even without sub_category. Migration 016 promotes known
        # designation values to sub_category before this resolver runs.
        return _resolve_admin_scope(user_id, staff, sub_category,
                                    branch_id=user_branch_id)

    # ------------------------------------------------------------------
    # Teacher
    # ------------------------------------------------------------------
    if role == "teacher":
        return await _resolve_teacher_scope(user_id, staff, sub_category, db,
                                            branch_id=user_branch_id)

    # ------------------------------------------------------------------
    # Unrecognised role -- self only
    # ------------------------------------------------------------------
    logger.warning("resolve_scope: unrecognised role=%r -> self-only", role)
    return Scope(type="self_only", role=role, user_id=user_id,
                 staff_record=staff, branch_id=user_branch_id)


# ---------------------------------------------------------------------------
# Admin resolution (synchronous -- no additional DB calls needed)
# ---------------------------------------------------------------------------

def _resolve_admin_scope(
    user_id: str,
    staff: Dict[str, Any],
    sub_category: Optional[str],
    branch_id: Optional[str] = None,
) -> Scope:
    """Produce scope for an admin user based on sub_category ONLY.

    Part 1.5 Patch J (strict mode): the `designation` field is no longer
    consulted. Legacy rows where designation carried the privilege intent
    (e.g. designation="Principal", sub_category=None) are promoted to
    sub_category at migration time (016). Any admin row that reaches this
    function without sub_category gets self-only (deny by default).

    Part 2 Patch P1: `branch_id` is now threaded through every returned Scope
    so consumers can enforce branch isolation. Principal staying type="all"
    is intentional (operational visibility across branches within the school).
    """

    effective: str = (sub_category or "").strip().lower()

    if effective in ("principal",):
        logger.debug("resolve_scope: admin/principal -> scope type='all'")
        return Scope(
            type="all",
            role="admin",
            sub_category="principal",
            user_id=user_id,
            staff_record=staff,
            branch_id=branch_id,
        )

    if effective in ("accountant", "accounts"):
        logger.debug("resolve_scope: admin/accountant -> domain='financial'")
        return Scope(
            type="domain",
            role="admin",
            sub_category="accountant",
            user_id=user_id,
            domain="financial",
            staff_record=staff,
            branch_id=branch_id,
        )

    if effective in ("transport_head", "transport"):
        logger.debug("resolve_scope: admin/transport_head -> domain='transport'")
        return Scope(
            type="domain",
            role="admin",
            sub_category="transport_head",
            user_id=user_id,
            domain="transport",
            staff_record=staff,
            branch_id=branch_id,
        )

    if effective in ("receptionist", "front_desk"):
        logger.debug("resolve_scope: admin/receptionist -> domain='enquiries'")
        return Scope(
            type="domain",
            role="admin",
            sub_category="receptionist",
            user_id=user_id,
            domain="enquiries",
            staff_record=staff,
            branch_id=branch_id,
        )

    if effective in ("support_staff", "support", "peon", "helper"):
        logger.debug("resolve_scope: admin/support_staff -> self_only")
        return Scope(
            type="self_only",
            role="admin",
            sub_category="support_staff",
            user_id=user_id,
            staff_record=staff,
            branch_id=branch_id,
        )

    # No sub_category at all -- DENY BY DEFAULT (Part 1 hardening).
    # Previously this fell through to type='all', which silently granted
    # full access to legacy admin rows. Migration 016 backfills support_staff
    # for any admin row without sub_category; if anything still arrives here
    # it's an unrecognised configuration and gets self_only.
    if not effective:
        logger.warning(
            "resolve_scope: admin with no sub_category and no designation -> "
            "self_only (deny-by-default). Run migration 016 to backfill legacy rows."
        )
        return Scope(
            type="self_only",
            role="admin",
            sub_category=None,
            user_id=user_id,
            staff_record=staff,
            branch_id=branch_id,
        )

    # Unrecognised sub_category -- deny-by-default.
    logger.warning(
        "resolve_scope: unrecognised admin sub_category=%r -> self-only",
        effective,
    )
    return Scope(
        type="self_only",
        role="admin",
        sub_category=effective,
        user_id=user_id,
        staff_record=staff,
        branch_id=branch_id,
    )


# ---------------------------------------------------------------------------
# Teacher resolution (async -- may query classes/subjects collections)
# ---------------------------------------------------------------------------

async def _resolve_teacher_scope(
    user_id: str,
    staff: Dict[str, Any],
    sub_category: Optional[str],
    db: Any,
    branch_id: Optional[str] = None,
) -> Scope:
    """Produce scope for a teacher based on sub_category and staff fields.

    Staff document fields consumed (all optional):
        sub_category       : hod | coordinator | class_teacher | subject_teacher
                             | kg_incharge
        wing               : primary | middle | senior  (informational only)
        subject            : str -- the subject name (for HODs)
        coordinator_range  : str -- e.g. "1-5", "6-8", "9-12"
        class_teacher_of   : str -- class id this teacher is class-teacher of
        assigned_class_ids : list[str] -- classes explicitly assigned
        is_incharge        : bool
        incharge_of        : str -- class id for KG in-charge
    """

    effective: str = (sub_category or "").strip().lower()

    # --- HOD (subject-wide) -------------------------------------------
    if effective == "hod":
        subject_name: Optional[str] = staff.get("subject")
        class_ids: List[str] = []

        if subject_name:
            # Resolve all classes that carry this subject.
            subject_docs = await db.subjects.find(
                {"name": {"$regex": f"^{subject_name}$", "$options": "i"}}
            ).to_list(100)
            class_ids = list(
                {doc["class_id"] for doc in subject_docs if doc.get("class_id")}
            )

        logger.debug(
            "resolve_scope: teacher/hod subject=%s classes=%d",
            subject_name,
            len(class_ids),
        )
        return Scope(
            type="subject",
            role="teacher",
            sub_category="hod",
            user_id=user_id,
            class_ids=class_ids,
            subject=subject_name,
            staff_record=staff,
            branch_id=branch_id,
        )

    # --- Coordinator (class range) ------------------------------------
    if effective == "coordinator":
        coordinator_range: Optional[str] = staff.get("coordinator_range")
        class_ids = []

        if coordinator_range and coordinator_range in COORDINATOR_RANGES:
            prefixes = COORDINATOR_RANGES[coordinator_range]
            regex_pattern = "^(" + "|".join(prefixes) + ")"
            class_docs = await db.classes.find(
                {"name": {"$regex": regex_pattern}}
            ).to_list(200)
            class_ids = [doc["id"] for doc in class_docs if doc.get("id")]
        elif coordinator_range:
            # Non-standard range string -- try to parse "N-M" dynamically.
            class_ids = await _parse_custom_range(coordinator_range, db)

        logger.debug(
            "resolve_scope: teacher/coordinator range=%s classes=%d",
            coordinator_range,
            len(class_ids),
        )
        return Scope(
            type="class_list",
            role="teacher",
            sub_category="coordinator",
            user_id=user_id,
            class_ids=class_ids,
            staff_record=staff,
            branch_id=branch_id,
        )

    # --- Class teacher (single class-section) -------------------------
    if effective == "class_teacher":
        class_teacher_of: Optional[str] = staff.get("class_teacher_of")
        class_ids = []

        if class_teacher_of:
            class_ids = [class_teacher_of]
        else:
            # Fallback: look up classes where class_teacher_id matches.
            class_docs = await db.classes.find(
                {"class_teacher_id": user_id}
            ).to_list(10)
            class_ids = [doc["id"] for doc in class_docs if doc.get("id")]

        logger.debug(
            "resolve_scope: teacher/class_teacher classes=%d", len(class_ids)
        )
        return Scope(
            type="class_list",
            role="teacher",
            sub_category="class_teacher",
            user_id=user_id,
            class_ids=class_ids,
            staff_record=staff,
            branch_id=branch_id,
        )

    # --- Subject teacher (assigned classes) ---------------------------
    if effective == "subject_teacher":
        assigned: Optional[List[str]] = staff.get("assigned_class_ids")
        class_ids = []

        if assigned and isinstance(assigned, list):
            class_ids = list(assigned)
        else:
            # Fallback: look up subjects where teacher_id matches.
            subject_docs = await db.subjects.find(
                {"teacher_id": user_id}
            ).to_list(100)
            class_ids = list(
                {doc["class_id"] for doc in subject_docs if doc.get("class_id")}
            )

        logger.debug(
            "resolve_scope: teacher/subject_teacher classes=%d", len(class_ids)
        )
        return Scope(
            type="class_list",
            role="teacher",
            sub_category="subject_teacher",
            user_id=user_id,
            class_ids=class_ids,
            staff_record=staff,
            branch_id=branch_id,
        )

    # --- KG in-charge -------------------------------------------------
    if effective == "kg_incharge":
        incharge_of: Optional[str] = staff.get("incharge_of")
        class_ids = [incharge_of] if incharge_of else []

        if not class_ids and staff.get("is_incharge"):
            # Fallback: find KG/Nursery classes this teacher is linked to.
            kg_classes = await db.classes.find(
                {
                    "name": {"$regex": "^(KG|Nursery|LKG|UKG)", "$options": "i"},
                    "class_teacher_id": user_id,
                }
            ).to_list(10)
            class_ids = [doc["id"] for doc in kg_classes if doc.get("id")]

        logger.debug(
            "resolve_scope: teacher/kg_incharge classes=%d", len(class_ids)
        )
        return Scope(
            type="class_list",
            role="teacher",
            sub_category="kg_incharge",
            user_id=user_id,
            class_ids=class_ids,
            staff_record=staff,
            branch_id=branch_id,
        )

    # --- No sub_category (legacy teacher records) ---------------------
    if not effective:
        class_ids = await _resolve_legacy_teacher_classes(user_id, db)
        scope_type = "class_list" if class_ids else "self_only"

        logger.debug(
            "resolve_scope: teacher with no sub_category -> %s (%d classes)",
            scope_type,
            len(class_ids),
        )
        return Scope(
            type=scope_type,
            role="teacher",
            sub_category=None,
            user_id=user_id,
            class_ids=class_ids,
            staff_record=staff,
            branch_id=branch_id,
        )

    # --- Unrecognised teacher sub_category ----------------------------
    logger.warning(
        "resolve_scope: unrecognised teacher sub_category=%r -> self-only",
        effective,
    )
    return Scope(
        type="self_only",
        role="teacher",
        sub_category=effective,
        user_id=user_id,
        staff_record=staff,
        branch_id=branch_id,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _parse_custom_range(range_str: str, db: Any) -> List[str]:
    """Parse a coordinator range like ``"1-5"`` into class ids.

    Returns an empty list if the string is unparseable.
    """

    try:
        parts = range_str.split("-")
        if len(parts) != 2:
            return []
        low, high = int(parts[0].strip()), int(parts[1].strip())
        prefixes = [f"Class {n}" for n in range(low, high + 1)]
        regex_pattern = "^(" + "|".join(prefixes) + ")"
        class_docs = await db.classes.find(
            {"name": {"$regex": regex_pattern}}
        ).to_list(200)
        return [doc["id"] for doc in class_docs if doc.get("id")]
    except (ValueError, TypeError):
        logger.warning("_parse_custom_range: could not parse %r", range_str)
        return []


async def _resolve_legacy_teacher_classes(
    user_id: str, db: Any
) -> List[str]:
    """For teachers without a sub_category, gather all classes they are linked
    to -- either as class teacher or as subject teacher.

    Returns
    -------
    list[str]
        Deduplicated list of class ids.
    """

    class_ids: set = set()

    # Classes where this teacher is the class teacher.
    ct_docs = await db.classes.find({"class_teacher_id": user_id}).to_list(20)
    for doc in ct_docs:
        if doc.get("id"):
            class_ids.add(doc["id"])

    # Classes where this teacher teaches a subject.
    subj_docs = await db.subjects.find({"teacher_id": user_id}).to_list(100)
    for doc in subj_docs:
        if doc.get("class_id"):
            class_ids.add(doc["class_id"])

    return sorted(class_ids)
