"""R3-2, 2026-08-15: the transport head sees children who are on a bus, and no others.

Abhimanyu's decision of 2026-08-15, and it restates the staff profiles draft of
2026-08-10: Chaman gets the addresses and guardian numbers of *the families on his
routes*, because he has to ring a parent when a bus is late. Roughly 1,500 of The
Aaryans' children never board a bus, and he has no reason to hold where they live.

**Why this is a module and not four `if` statements.** The R3-1 survey of 2026-08-14
counted about a dozen separate hand-written statements of who may do what, none of which
read the permission table and none of which moved when another one did. That is the habit
this release is trying to stop, so the narrowing is written once and every path asks it.

**The filter is the SERVER's, not the screen's.** It is applied to the database query
rather than to the answer, so there is no request Chaman can shape - no page size, no
search term, no id typed directly - that returns a child who is not on a route. Filtering
the response instead would leave the record fetched and one careless change away from
being returned.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

# The profile this applies to. Named here rather than passed in, because "which profiles
# are scoped to the bus" is a permission fact and belongs beside the rule, not with each
# caller. R3-3 adds drivers and conductors to this set.
BUS_SCOPED_PROFILES = frozenset({"transport_head"})

# A child counts as being on a bus when the school has put them on a route. Both fields
# are checked because the platform records the same fact two ways: `route_zone_id` is set
# by the transport screens and by the optimisation tools, while `uses_transport` came off
# the Vedmarg migration (036). A child carrying either one is somebody Chaman drives.
_ON_A_BUS = {
    "$or": [
        {"route_zone_id": {"$nin": [None, ""]}},
        {"uses_transport": True},
    ]
}


def is_bus_scoped(user: Optional[Dict[str, Any]]) -> bool:
    """Is this profile limited to children who are on a route?"""
    user = user or {}
    return (
        user.get("role") == "admin"
        and user.get("sub_category") in BUS_SCOPED_PROFILES
    )


def scope_students_to_the_bus(query: Dict[str, Any], user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Add the on-a-route condition to a student query, for the profiles it applies to.

    Returns the query unchanged for everybody else, so this is safe to call on any
    student query without first asking whose it is. That matters: a helper somebody has
    to remember to guard is a helper somebody will forget to guard.

    The condition is combined with `$and` rather than merged into the top level, because
    the caller's query may already carry its own `$or` (a name search does), and merging
    would silently replace it and widen the answer.
    """
    if not is_bus_scoped(user):
        return query
    existing = dict(query or {})
    if "$and" in existing:
        return {**existing, "$and": [*existing["$and"], _ON_A_BUS]}
    return {"$and": [existing, _ON_A_BUS]} if existing else dict(_ON_A_BUS)


def student_is_in_scope(student: Optional[Dict[str, Any]], user: Optional[Dict[str, Any]]) -> bool:
    """Is this one child inside the caller's student scope?

    For the single-record paths, where a query filter cannot be applied because the
    record was fetched by id. A refusal here must read the same as a record that does not
    exist, so callers return 404 rather than 403: telling somebody "that child exists but
    is not yours" still tells them the child exists.
    """
    if not is_bus_scoped(user):
        return True
    student = student or {}
    route = student.get("route_zone_id")
    return bool((route not in (None, "")) or student.get("uses_transport"))
