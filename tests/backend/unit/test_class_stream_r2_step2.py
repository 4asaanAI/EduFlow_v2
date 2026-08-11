"""Release 2, step 2: a class record can carry a stream, and only a real one.

11th and 12th are charged 4,800 a year apart depending on Commerce or Science. Until this
work the platform had nowhere to record which was which, so it could not tell them apart.

The tests that matter here are the refusals. A stream nobody recognises would fall out of
the fee band lookup silently, and the family would be charged the wrong amount with
nothing on any screen looking wrong.
"""

from __future__ import annotations

import pytest

from services.academic_structure_service import (
    CLASS_UPDATABLE_FIELDS,
    VALID_STREAMS,
    AcademicStructureValidationError,
    _clean_stream,
)


def test_the_two_streams_the_school_uses():
    assert VALID_STREAMS == {"Commerce", "Science"}


def test_stream_can_be_edited_like_any_other_class_field():
    # Without this the office would need a developer to correct a stream, and a wrong
    # stream is 4,800 a year to a family.
    assert "stream" in CLASS_UPDATABLE_FIELDS


@pytest.mark.parametrize("given", ["Commerce", "commerce", "  SCIENCE  ", "science"])
def test_a_real_stream_is_accepted_however_it_is_typed(given):
    assert _clean_stream(given) in VALID_STREAMS


@pytest.mark.parametrize("given", [None, ""])
def test_no_stream_is_allowed_because_most_classes_have_none(given):
    # Every class below 11th has no stream. That is correct, not missing data.
    assert _clean_stream(given) == ""


@pytest.mark.parametrize("given", ["Arts", "Humanities", "PCM", "Sci", "Commerce/Science", "0"])
def test_a_stream_the_school_does_not_use_is_refused_out_loud(given):
    # Refused rather than stored. A stored-but-unrecognised stream is the dangerous case:
    # it looks fine on the record and quietly misses the fee band.
    with pytest.raises(AcademicStructureValidationError):
        _clean_stream(given)


def test_the_refusal_says_what_is_allowed():
    with pytest.raises(AcademicStructureValidationError) as caught:
        _clean_stream("Arts")
    message = str(caught.value)
    assert "Commerce" in message and "Science" in message
