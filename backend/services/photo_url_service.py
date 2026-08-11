"""Serve profile photographs from the school's own S3, never from the vendor's CDN.

THE PROBLEM THIS SOLVES
-----------------------
Every photograph the school brought over from its previous software vendor is stored
as an absolute `https://cdn.vedmarg.com/...` URL. Those links need no login: anyone who
has one can open a photograph of a child. There are 1,423 children, 13 staff and 256
parents in that position. The exposure exists on the vendor's CDN whether or not EduFlow
points at it - but handing that link to a browser makes this platform a participant in
it, and it also means every photograph breaks the day the school stops paying that
vendor.

Copies of all 1,692 images already sit in the school's own bucket, and every record
already carries the key (`photo_url_s3_key`). What was missing was the serving half.

WHY NOT JUST REPOINT `photo_url` AT `/api/uploads/serve/...`
------------------------------------------------------------
That is the platform's own convention for uploaded photos, and it does not work in a
browser: the screens render photographs with a plain `<img src=...>`, and an `<img>` tag
cannot send an `Authorization` header. Repointing 1,423 children's photographs at an
authenticated route would have replaced a working photograph with a broken image for
every one of them. (The same latent fault already affects photos uploaded through the
product - see `resolve_many`, which repairs those too.)

WHAT THIS DOES INSTEAD
----------------------
The stored record keeps its own history, and the API answers with a freshly signed,
short-lived S3 link at read time. A signed link carries its own credential in the query
string, so `<img src=...>` works untouched - no frontend change - while the link expires
on its own and the public CDN address never leaves the server.

Failure is deliberately soft: if a key is missing or S3 cannot be reached, the caller
gets `None` for that one photograph and the rest of the record is unaffected. A profile
screen showing an initial instead of a face is a far better outcome than a 500.
"""

from __future__ import annotations

import logging

from services.s3_storage import create_presigned_get_url

logger = logging.getLogger(__name__)

#: Photo fields that may appear on a record, each paired with the field holding its key.
#: `photo_url` covers students, staff and guardians; the three parent fields sit on the
#: student record because the guardian collection had no photo field when they landed.
PHOTO_FIELDS = ("photo_url", "mother_photo", "father_photo", "guardian_photo")

#: Hosts we must never hand to a browser. These are the previous vendor's public CDN.
VENDOR_HOSTS = ("cdn.vedmarg.com",)


def _key_field(field: str) -> str:
    return f"{field}_s3_key"


def resolve_one(doc: dict | None, field: str = "photo_url") -> str | None:
    """Return a signed, short-lived URL for one photo field, or None.

    Order of preference:
      1. the copy in the school's own bucket, signed fresh;
      2. nothing - a vendor CDN link is never returned, even if it still works.
    """
    if not doc:
        return None
    key = doc.get(_key_field(field))
    if key:
        try:
            return create_presigned_get_url(key)
        except Exception:
            # Soft-fail: one unreachable photo must not take down the whole response.
            logger.warning("photo_presign_failed", extra={"field": field}, exc_info=True)
            return None
    url = doc.get(field)
    if not url:
        return None
    if any(h in url for h in VENDOR_HOSTS):
        # We hold our own copy for every one of these, so reaching here means the key
        # is missing on this record. Returning the public link is not an acceptable
        # fallback -- that is the exposure this module exists to close.
        return None
    if url.startswith("s3://"):
        # A raw bucket URI is not something a browser can open. Pre-existing rule.
        return None
    return url


def apply(doc: dict | None, fields: tuple[str, ...] = PHOTO_FIELDS) -> dict | None:
    """Rewrite a record's photo fields in place so the response carries signed links.

    The vendor address is preserved on the document under `<field>_source` so the
    record still says where the picture originally came from; it simply stops being
    the thing handed to a browser.
    """
    if not doc:
        return doc
    for f in fields:
        if f not in doc and _key_field(f) not in doc:
            continue
        original = doc.get(f)
        resolved = resolve_one(doc, f)
        if original and any(h in str(original) for h in VENDOR_HOSTS):
            doc[f"{f}_source"] = original
        doc[f] = resolved
    return doc


def apply_many(docs, fields: tuple[str, ...] = PHOTO_FIELDS):
    """`apply` over a list of records. Returns the same list, rewritten in place."""
    for d in docs or []:
        apply(d, fields)
    return docs
