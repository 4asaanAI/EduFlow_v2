"""R4-1 - one shape for a recorded change.

--------------------------------------------------------------------------------
Why this module exists
--------------------------------------------------------------------------------

A change to the school's records is written down in at least eight different shapes
across the platform. `undo_service` found this the hard way and documented it, and it is
the reason undo refuses far more than it should:

    {field: {"previous": …, "new": …}}          reversible - this is the one
    {"before": {…}, "after": {…}}               reversible, different words
    {"deleted": {…the whole document…}}          a restore, not an edit
    {"created": {…the whole document…}}          undoing it means deleting
    {"count_marked": 41, "date": …}              a summary. No before-value exists.
    {…the update dict as it was applied…}        NEW VALUES ONLY, no previous
    {"applied": {…}} / {"import_batch": …}       neither shape
    {"previous_state": {"previous": …}}          nested one level deeper

The most common of those, by a wide margin, is the sixth: **the update dict as applied,
carrying new values and nothing else.** So for most changes the platform records what a
value became and not what it was.

--------------------------------------------------------------------------------
The one distinction everything here exists to protect
--------------------------------------------------------------------------------

**"The value used to be empty" and "we never wrote down what the value was" must never
look the same.**

They look identical in every legacy shape, and that single ambiguity is what makes an
undo dishonest. An undo reading a missing previous value as an empty one will cheerfully
blank a field that had a name in it. An undo reading an empty one as missing will refuse
a change it could perfectly well reverse and send a person to the principal for nothing.

So in the canonical shape every field carries **three** keys, always:

    {"previous": …, "new": …, "previous_known": True|False}

`previous_known=False` means nobody recorded it. `previous_known=True` with
`previous=None` means it really was empty. A reader can finally tell.

--------------------------------------------------------------------------------
The shape
--------------------------------------------------------------------------------

Every canonical `changes` value is a dict with a `kind`, and the kind decides the rest:

    {"kind": "edit",   "fields": {name: {"previous", "new", "previous_known"}}}
    {"kind": "create", "snapshot": {…the document as created…}}
    {"kind": "delete", "snapshot": {…the document as it was…}}
    {"kind": "bulk",   "summary": {…}, "affected": N}
    {"kind": "none",   "why": "…a sentence a person can act on…"}

`kind` is always present, so a reader never has to guess by sniffing keys - which is what
every reader does today, and why adding a ninth shape silently broke them.

`none` is deliberately a real kind rather than an absence. A change that genuinely cannot
be described (a summary with no before-state, a legacy row too vague to interpret) SAYS
so, carrying the reason. Nothing is left blank and hoped over: a blank reads as "nothing
happened", which is the exact failure this release exists to end.

--------------------------------------------------------------------------------
Nothing old is orphaned
--------------------------------------------------------------------------------

`normalise()` takes any of the eight legacy shapes and returns the canonical one, so the
audit screen and undo read ONE thing while the school's existing history stays readable.
Old rows are not rewritten. They are translated on the way out, and where a legacy row
cannot honestly be translated it becomes `kind="none"` with a reason, never a guess.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional

# Keys that carry the platform's own bookkeeping rather than anything a person changed.
# Recording them would triple the size of every audit row (decision 13, cost) and tell a
# reader nothing: nobody has ever wanted to know that `updated_at` changed during an edit.
NOISE_FIELDS = frozenset({
    "_id", "updated_at", "modified_at", "last_modified", "schoolId", "school_id",
})

KIND_EDIT = "edit"
KIND_CREATE = "create"
KIND_DELETE = "delete"
KIND_BULK = "bulk"
KIND_NONE = "none"

VALID_KINDS = frozenset({KIND_EDIT, KIND_CREATE, KIND_DELETE, KIND_BULK, KIND_NONE})


def _clean(doc: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """A document with the platform's bookkeeping keys dropped."""
    if not isinstance(doc, Mapping):
        return {}
    return {k: v for k, v in doc.items() if k not in NOISE_FIELDS}


# ---------------------------------------------------------------------------
# Building a canonical change. These are what call sites use.
# ---------------------------------------------------------------------------

def edit(
    before: Optional[Mapping[str, Any]],
    after: Mapping[str, Any],
    *,
    fields: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """A field-by-field edit.

    `before` is the document as it stood; pass None ONLY when it genuinely was not read,
    which marks every field `previous_known=False` rather than pretending it was empty.

    `after` is the update as applied - the `$set` dict, not the whole document. Passing
    the whole document would record every unchanged field as a change.

    Fields whose value did not actually change are dropped. An audit row saying a value
    changed from "Sharma" to "Sharma" is noise that costs storage and, worse, makes a
    real change harder to find in a list.
    """
    after_clean = _clean(after)
    if fields is not None:
        wanted = set(fields)
        after_clean = {k: v for k, v in after_clean.items() if k in wanted}

    before_known = before is not None
    before_clean = _clean(before)

    out: Dict[str, Any] = {}
    for key, new_value in after_clean.items():
        previous = before_clean.get(key) if before_known else None
        # Only skip when we KNOW it is unchanged. Without a before-document every field
        # has to be kept: "probably the same" is a guess, and a guess is what this
        # module exists to stop.
        if before_known and key in before_clean and previous == new_value:
            continue
        out[key] = {
            "previous": previous,
            "new": new_value,
            "previous_known": bool(before_known and key in before_clean),
        }

    if not out:
        return none("Nothing changed: every field submitted already held that value.")
    return {"kind": KIND_EDIT, "fields": out}


def created(doc: Mapping[str, Any]) -> Dict[str, Any]:
    """A record was created. There is no before-state, and that is a fact, not a gap."""
    return {"kind": KIND_CREATE, "snapshot": _clean(doc)}


def removed(doc: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """A record was removed. The snapshot is what makes a restore possible later."""
    if not doc:
        return none("The record was removed before a copy of it could be taken.")
    return {"kind": KIND_DELETE, "snapshot": _clean(doc)}


def bulk(summary: Mapping[str, Any], *, affected: Optional[int] = None) -> Dict[str, Any]:
    """Many records at once: an attendance sweep, an import, a fee run.

    `affected` is the count, and it is separate from the summary on purpose. The count is
    the one number a person always wants and it must never be buried inside a free-form
    blob where a reader has to know its key to find it.
    """
    body: Dict[str, Any] = {"kind": KIND_BULK, "summary": dict(summary or {})}
    if affected is not None:
        body["affected"] = int(affected)
    return body


def none(why: str) -> Dict[str, Any]:
    """This change cannot be described, and here is the reason in a usable sentence.

    Never call this with a vague reason. The sentence is shown to a person who is trying
    to understand what happened to a child's record, and "unknown" tells them nothing
    that an empty row would not have told them already.
    """
    return {"kind": KIND_NONE, "why": (why or "").strip() or "No reason was recorded."}


# ---------------------------------------------------------------------------
# Reading a change: one shape out, whatever went in.
# ---------------------------------------------------------------------------

def is_canonical(changes: Any) -> bool:
    """Is this already in the one shape? Cheap enough to call on every row."""
    return isinstance(changes, Mapping) and changes.get("kind") in VALID_KINDS


def _fields_from_previous_new(changes: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    """Legacy shape 1: {field: {"previous": …, "new": …}} - the reversible one.

    Handled PER FIELD, not all-or-nothing. A row can carry a real before-value for some
    fields and only a new value for others, because different code paths wrote different
    halves of the same edit. Rejecting the whole row on one incomplete field threw away
    every good before-value beside it, so a change that was half reversible became
    entirely irreversible, and the person was told nothing could be put back when most of
    it could.

    Returns None only when NO field carries a before-value, which is the plain
    new-values-only shape and belongs to the catch-all branch instead.
    """
    out: Dict[str, Any] = {}
    any_known = False
    for key, value in changes.items():
        if not isinstance(value, Mapping):
            return None
        if "previous" in value and "new" in value:
            any_known = True
            out[key] = {
                "previous": value.get("previous"),
                "new": value.get("new"),
                "previous_known": True,
            }
        elif "new" in value:
            out[key] = {"previous": None, "new": value.get("new"), "previous_known": False}
        else:
            return None
    return out if any_known else None


def normalise(changes: Any) -> Dict[str, Any]:
    """Translate any recorded change, old or new, into the one shape.

    Order matters here. The checks run from most specific to least, because the last
    branch - "a plain dict of new values" - matches almost anything, and letting it run
    early would swallow the shapes that carry a real before-value and quietly downgrade
    them to `previous_known=False`. That would turn reversible history into
    irreversible history at read time, which is worse than the problem being fixed.
    """
    if is_canonical(changes):
        return dict(changes)

    if not isinstance(changes, Mapping) or not changes:
        return none("This change was recorded before the platform kept details of what changed.")

    # Shape 3 / 2: a whole-document create or delete.
    if "created" in changes and isinstance(changes.get("created"), Mapping):
        return created(changes["created"])
    if "deleted" in changes and isinstance(changes.get("deleted"), Mapping):
        return removed(changes["deleted"])

    # Shape 8: {"before": {...}, "after": {...}} - custom forms use this wording.
    before = changes.get("before")
    after = changes.get("after")
    if isinstance(after, Mapping) and (isinstance(before, Mapping) or before is None):
        return edit(before if isinstance(before, Mapping) else None, after)

    # Shape 7: {"previous_state": {...}} nested one level deeper.
    nested = changes.get("previous_state")
    if isinstance(nested, Mapping):
        inner = _fields_from_previous_new(nested)
        if inner:
            return {"kind": KIND_EDIT, "fields": inner}

    # Shape 6: an import or an applied batch. A summary, not an edit.
    for key in ("applied", "import_batch"):
        if key in changes:
            return bulk(changes)

    # Shape 4: a count-style summary. Recognised by carrying a number and no nested
    # field records - an attendance sweep, a fee run.
    if any(k.startswith("count") or k in ("affected", "total", "rows") for k in changes):
        affected = None
        for k in ("affected", "count", "count_marked", "total", "rows"):
            if isinstance(changes.get(k), int):
                affected = changes[k]
                break
        return bulk(changes, affected=affected)

    # Shape 1: the reversible one.
    fields = _fields_from_previous_new(changes)
    if fields:
        return {"kind": KIND_EDIT, "fields": fields}

    # Shape 5, and the most common by far: the update dict as it was applied. New values
    # only. This is an edit, and every field is honestly marked as having no recorded
    # before-value rather than being given a fabricated empty one.
    applied = _clean(changes)
    if not applied:
        return none("This change recorded no details beyond the platform's own bookkeeping.")
    return {
        "kind": KIND_EDIT,
        "fields": {
            key: {"previous": None, "new": value, "previous_known": False}
            for key, value in applied.items()
        },
    }


def reversible_fields(changes: Any) -> Dict[str, Any]:
    """The fields that can honestly be put back, and the value each returns to.

    Empty means "nothing here can be reversed", and callers must treat it as a refusal
    rather than as a successful undo of nothing. A field whose before-value was never
    recorded is NOT included: writing None into it would erase a value rather than
    restore one, which is the single most damaging thing an undo could do.
    """
    canonical = normalise(changes)
    if canonical.get("kind") != KIND_EDIT:
        return {}
    return {
        name: entry.get("previous")
        for name, entry in (canonical.get("fields") or {}).items()
        if isinstance(entry, Mapping) and entry.get("previous_known")
    }


def describe(changes: Any) -> str:
    """One plain sentence about a recorded change, for a person reading the audit log."""
    canonical = normalise(changes)
    kind = canonical.get("kind")
    if kind == KIND_CREATE:
        return "Created this record."
    if kind == KIND_DELETE:
        return "Removed this record."
    if kind == KIND_BULK:
        affected = canonical.get("affected")
        if isinstance(affected, int):
            return f"Changed {affected} records at once."
        return "Changed many records at once."
    if kind == KIND_NONE:
        return canonical.get("why") or "No details were recorded."
    fields = canonical.get("fields") or {}
    names = ", ".join(sorted(fields))
    unknown = sum(1 for e in fields.values() if isinstance(e, Mapping) and not e.get("previous_known"))
    if not names:
        return "No details were recorded."
    base = f"Changed {names}."
    if unknown:
        # Said out loud rather than left as an empty column. A reader who is not told
        # this will read a blank previous-value as "it was empty before".
        base += f" The earlier value was not recorded for {unknown} of them."
    return base
