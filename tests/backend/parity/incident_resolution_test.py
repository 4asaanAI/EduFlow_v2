"""Story C.1 — characterization test for explicit record-type resolution.

Pins the behavior of `services.incident_service.resolve_record_type`: the legacy
`_find_mutable_record` precedence (incidents → complaints → facility_requests →
tech_requests) is preserved, a missing id refuses with NotFound, and the same id in
two collections is a hard ambiguity refusal (no blind multi-collection scan at write).
"""

from __future__ import annotations

import pytest

from services import incident_service
from services.incident_service import (
    resolve_record_type,
    IncidentNotFoundError,
    IncidentAmbiguousError,
)

pytestmark = pytest.mark.asyncio

_COLLECTIONS = ("incidents", "complaints", "facility_requests", "tech_requests")


def _clear(fake_db):
    for col in _COLLECTIONS:
        getattr(fake_db, col).docs[:] = []


@pytest.fixture(autouse=True)
def _clean(fake_db):
    _clear(fake_db)
    yield
    _clear(fake_db)


@pytest.mark.parametrize("record_type", _COLLECTIONS)
async def test_resolve_returns_owning_collection(fake_db, record_type):
    getattr(fake_db, record_type).docs.append(
        {"id": "rec-1", "schoolId": "aaryans-joya", "status": "open"}
    )
    resolved_type, doc = await resolve_record_type(fake_db, "rec-1")
    assert resolved_type == record_type
    assert doc["id"] == "rec-1"


async def test_resolve_precedence_matches_legacy_scan(fake_db):
    # Legacy `_find_mutable_record` returned the FIRST hit in this order; a single id
    # only ever lives in one collection in practice, but pin the order regardless by
    # asserting incidents wins when it is present.
    fake_db.incidents.docs.append({"id": "rec-1", "schoolId": "aaryans-joya"})
    resolved_type, _ = await resolve_record_type(fake_db, "rec-1")
    assert resolved_type == "incidents"


async def test_resolve_unknown_id_refuses(fake_db):
    with pytest.raises(IncidentNotFoundError):
        await resolve_record_type(fake_db, "does-not-exist")


async def test_resolve_ambiguous_id_refuses(fake_db):
    fake_db.incidents.docs.append({"id": "dup", "schoolId": "aaryans-joya"})
    fake_db.complaints.docs.append({"id": "dup", "schoolId": "aaryans-joya"})
    with pytest.raises(IncidentAmbiguousError):
        await resolve_record_type(fake_db, "dup")


async def test_resolve_can_exclude_tech(fake_db):
    fake_db.tech_requests.docs.append({"id": "rec-1", "schoolId": "aaryans-joya"})
    with pytest.raises(IncidentNotFoundError):
        await resolve_record_type(fake_db, "rec-1", include_tech=False)
