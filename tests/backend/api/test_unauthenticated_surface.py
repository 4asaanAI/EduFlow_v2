import pytest


PROTECTED_GET_ENDPOINTS = (
    "/api/fees/summary",
    "/api/staff",
    "/api/students",
    "/api/ops/visitors",
    "/api/issues/facility",
    "/api/queries",
    "/api/settings/branches",
    "/api/audit-log",
    "/api/health/system",
)


@pytest.mark.parametrize("path", PROTECTED_GET_ENDPOINTS)
def test_representative_surfaces_reject_unauthenticated_gets(client, path):
    response = client.get(path)

    assert response.status_code in (401, 403)
