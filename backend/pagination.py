from __future__ import annotations
"""One page-size rule for every list endpoint on the platform.

WHY THIS EXISTS (Release 3, 2026-08-12)
---------------------------------------
Before this module, every list route invented its own answer to "how many rows
may one request return?", and the answers disagreed with each other:

    students, staff, message logs   500
    chats, maintenance, audit       100
    file list                       100, and rejected anything else outright
    notifications                    50
    facility requests, tech requests, leave requests, incidents,
    announcements, platform messages   NO LIMIT AT ALL

Two distinct faults lived in that table.

1. **The disagreement itself.** A screen cannot know what it is allowed to ask
   for, so "show me everything" had to be hand-tuned per screen and was wrong
   wherever nobody remembered to tune it.

2. **The silent short answer.** The clamped routes used `max(1, min(limit, CAP))`.
   `max(1, -1)` is 1, so a caller asking for everything with the `ALL_ROWS`
   sentinel (-1) got exactly ONE ROW and no error. The unclamped routes passed
   the value to Mongo's `.limit(-1)`, which returns a single batch and closes the
   cursor - also a short answer, also silent. That defect was live on the School
   Directory, the staff list and the notification list.

THE RULE
--------
* One ceiling, `MAX_PAGE_SIZE`, for every list. A caller that asks for more gets
  the ceiling, which is a long-standing behaviour two tests already pin
  (`limit=9999` on students, `limit=100000` on chats).
* A page size below 1 is a **mistake, not a request**, so it is refused with a
  400 that says what was wrong. Never quietly turned into 1. This is the whole
  lesson of the 11-12 August faults: a query that returns less than it should
  must say so.
* Asking for everything is done by WALKING THE PAGES, not by defeating the
  ceiling. The frontend half of that is `frontend/src/lib/fetchAllRows.js`.

The ceiling protects the server from holding and serialising a whole collection
for one request. Raising it is a measurement, not a preference.
"""

from fastapi import HTTPException

#: The most rows any list endpoint will return in one request.
#:
#: 500 is the figure the two busiest lists (students, staff) already used and are
#: tested against, and it comfortably covers a class, a department or a day's
#: attendance in a single page. The school's longest list is the payment ledger
#: at roughly 10,700 rows, which is 22 pages - cheap to walk, expensive to serve
#: whole.
MAX_PAGE_SIZE = 500

#: What a list returns when the caller says nothing. Kept small on purpose: the
#: common case is a screen showing one page to one person on a phone.
DEFAULT_PAGE_SIZE = 20


def clamp_page_size(limit: int, maximum: int = MAX_PAGE_SIZE) -> int:
    """Return a safe page size, or refuse a nonsensical one.

    Args:
        limit: what the caller asked for.
        maximum: the ceiling for this endpoint. Pass a lower one only where the
            rows are genuinely expensive (a wide document, an aggregation);
            never pass a lower one merely because the list is short today.

    Returns:
        `limit` when it is sane, otherwise `maximum`.

    Raises:
        HTTPException: 400, when `limit` is below 1. Includes the ALL_ROWS
            sentinel (-1). A caller wanting everything walks the pages; a
            caller sending -1 has a bug, and being told is the point.
    """
    if limit is None:
        return DEFAULT_PAGE_SIZE
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        raise HTTPException(400, "limit must be a whole number")
    if limit < 1:
        raise HTTPException(
            400,
            f"limit must be 1 or more (got {limit}). To fetch every row, request "
            f"successive pages of up to {maximum}; there is no 'all' page size.",
        )
    return min(limit, maximum)


def clamp_page(page: int) -> int:
    """Return a safe page number, or refuse a nonsensical one.

    Page 0 and negative pages used to be silently treated as page 1 in some
    routes and produced a negative `skip` in others (which Mongo rejects at
    query time, surfacing as a 500). Both are refused here for the same reason
    page sizes are: it is a caller bug and hiding it helps nobody.
    """
    if page is None:
        return 1
    try:
        page = int(page)
    except (TypeError, ValueError):
        raise HTTPException(400, "page must be a whole number")
    if page < 1:
        raise HTTPException(400, f"page must be 1 or more (got {page})")
    return page


def page_meta(page: int, per_page: int, total: int) -> dict:
    """The `meta` block every list response carries.

    Exists so that `total` is never omitted. A screen offering an "All" view has
    to be able to say "showing 500 of 1,876" rather than presenting the rows it
    happens to hold as the whole set.
    """
    return {"page": page, "per_page": per_page, "total": total}
