"""No response may ever hand a browser the previous vendor's photo link.

Every photograph the school brought over from Vedmarg, its previous software vendor, is
stored as an absolute `https://cdn.vedmarg.com/...` address that needs no login: anyone
holding one can open a picture of a child. Copies of all 1,692 images sit in the school's
own bucket and every record carries the key, and `photo_url_service` answers reads with a
short-lived signed link instead.

Two reads skipped it, found 2026-08-15:

* `GET /api/guardian/wards` and the ward detail behind it. **The parent portal**, of all
  places, returned the child's whole record untouched, so a parent's own browser was
  handed the public vendor address for their child and both parents.
* `PATCH` on a guardian returned the freshly updated guardian document untouched.

The rule these pin is the one in `photo_url_service.resolve_one`: a vendor address is
never returned, even when it still works, and even when our own copy is missing. A
missing photograph is a face that does not load. A vendor address is a photograph of a
child on the open internet.
"""

from __future__ import annotations

import pytest

from services import photo_url_service

VENDOR = "https://cdn.vedmarg.com/uploads/student/9999.jpg"


def test_a_vendor_link_is_never_returned_even_with_no_copy_of_our_own():
    doc = {"photo_url": VENDOR}
    assert photo_url_service.resolve_one(doc) is None


def test_apply_replaces_the_vendor_link_and_keeps_it_only_as_history():
    doc = {"photo_url": VENDOR}
    photo_url_service.apply(doc, fields=("photo_url",))
    assert doc["photo_url"] is None
    # The record still says where the picture came from. It simply stops being the thing
    # handed to a browser.
    assert doc["photo_url_source"] == VENDOR


def test_apply_many_covers_every_parent_field_on_a_student():
    doc = {
        "photo_url": VENDOR,
        "mother_photo": VENDOR,
        "father_photo": VENDOR,
        "guardian_photo": VENDOR,
    }
    photo_url_service.apply_many([doc])
    for field in ("photo_url", "mother_photo", "father_photo", "guardian_photo"):
        assert doc[field] is None, f"{field} still carries a vendor address"


@pytest.mark.parametrize(
    "module, symbol",
    [
        ("routes.guardian", "photo_url_service"),
        ("routes.students", "photo_url_service"),
        ("routes.staff", "photo_url_service"),
    ],
)
def test_every_route_that_returns_a_person_imports_the_photo_service(module, symbol):
    """A route that returns a person and never imports this cannot be applying it.

    Crude on purpose. It is the cheap alarm that catches a NEW route being written
    without the rule, which is exactly how the parent portal came to skip it."""
    import importlib

    assert hasattr(importlib.import_module(module), symbol)
