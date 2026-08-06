"""Photographs must be served from the school's own bucket, never the vendor's CDN.

The school's previous software vendor hosts every imported photograph on
`cdn.vedmarg.com`, with no login of any kind. 1,423 children, 13 staff and 256 parents
are on it. Copies live in the school's own S3 bucket and every record carries the key,
so the rule these tests hold in place is simple: the API answers with a signed link to
our copy, and the public vendor address never reaches a browser.
"""

from __future__ import annotations

import pytest

from services import photo_url_service as svc

VENDOR = "https://cdn.vedmarg.com/uploads/media/profile/1/x.jpg"


@pytest.fixture
def fake_presign(monkeypatch):
    monkeypatch.setattr(svc, "create_presigned_get_url", lambda key: f"https://s3.example/{key}?sig=abc")


def test_record_with_a_key_is_served_signed_from_our_bucket(fake_presign):
    doc = {"photo_url": VENDOR, "photo_url_s3_key": "aaryans-joya/uploads/a/photo.jpg"}
    svc.apply(doc)
    assert doc["photo_url"] == "https://s3.example/aaryans-joya/uploads/a/photo.jpg?sig=abc"


def test_the_vendor_address_is_kept_as_provenance_but_not_served(fake_presign):
    doc = {"photo_url": VENDOR, "photo_url_s3_key": "k"}
    svc.apply(doc)
    assert doc["photo_url_source"] == VENDOR
    assert "cdn.vedmarg.com" not in doc["photo_url"]


def test_vendor_url_with_no_key_yields_no_photo_rather_than_the_public_link(fake_presign):
    """The whole point: a missing key must NOT fall back to the unauthenticated CDN."""
    doc = {"photo_url": VENDOR}
    svc.apply(doc)
    assert doc["photo_url"] is None
    assert doc["photo_url_source"] == VENDOR


def test_parent_photo_fields_on_the_student_record_are_resolved_too(fake_presign):
    doc = {
        "mother_photo": VENDOR, "mother_photo_s3_key": "mk",
        "father_photo": VENDOR, "father_photo_s3_key": "fk",
    }
    svc.apply(doc)
    assert doc["mother_photo"] == "https://s3.example/mk?sig=abc"
    assert doc["father_photo"] == "https://s3.example/fk?sig=abc"


def test_a_raw_bucket_uri_is_never_handed_to_a_browser(fake_presign):
    doc = {"photo_url": "s3://bucket/key.jpg"}
    svc.apply(doc)
    assert doc["photo_url"] is None


def test_an_unrelated_absolute_url_is_left_alone(fake_presign):
    doc = {"photo_url": "https://example.org/pic.jpg"}
    svc.apply(doc)
    assert doc["photo_url"] == "https://example.org/pic.jpg"


def test_a_record_with_no_photo_at_all_is_untouched(fake_presign):
    doc = {"name": "someone"}
    svc.apply(doc)
    assert "photo_url" not in doc


def test_one_unreachable_photo_does_not_break_the_whole_response(monkeypatch):
    """Soft-fail: an initial on screen beats a 500 for the entire student list."""
    def boom(key):
        raise RuntimeError("s3 unreachable")
    monkeypatch.setattr(svc, "create_presigned_get_url", boom)
    docs = [{"photo_url": VENDOR, "photo_url_s3_key": "k"}, {"name": "no photo"}]
    svc.apply_many(docs)
    assert docs[0]["photo_url"] is None
    assert docs[1] == {"name": "no photo"}


def test_apply_many_returns_the_same_list_it_was_given(fake_presign):
    docs = [{"photo_url": VENDOR, "photo_url_s3_key": "k"}]
    assert svc.apply_many(docs) is docs
