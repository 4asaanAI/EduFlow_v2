from __future__ import annotations
"""
Security surface test: every protected endpoint must return 401 when called
without an Authorization header. Fails CI if a new route is accidentally left open.
"""
import pytest
from fastapi.routing import APIRoute
from tests.backend.conftest import APP_AVAILABLE, client as _client_fixture

# Public routes that intentionally need no auth
PUBLIC_PATHS = {
    "/api/health",
    "/api/health/ready",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/seed-status",
    "/api/docs",
    "/openapi.json",
    # Razorpay webhook: authenticated via X-Razorpay-Signature header, not JWT
    "/api/tokens/webhook",
}

pytestmark = pytest.mark.skipif(not APP_AVAILABLE, reason="app not available")


def test_protected_get_routes_require_auth(client):
    """Every GET route not in PUBLIC_PATHS must return 401 without auth."""
    from server import app

    failures = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if path in PUBLIC_PATHS:
            continue
        # Skip internal test-harness routes registered by test files themselves
        if path.startswith("/__test__/"):
            continue
        if "GET" not in route.methods:
            continue
        # Skip parameterised paths that require IDs — use a dummy value
        test_path = path
        for param in route.param_convertors:
            test_path = test_path.replace("{" + param + "}", "test-id-123")

        try:
            resp = client.get(test_path)
            status = resp.status_code
        except Exception as exc:
            failures.append(f"GET {test_path} → crashed: {exc}")
            continue
        if status not in (401, 403, 405, 422):
            failures.append(f"GET {test_path} → {status} (expected 401/403)")

    assert not failures, "Unauthenticated routes detected:\n" + "\n".join(failures)


def test_protected_post_routes_require_auth(client):
    """Every POST route not in PUBLIC_PATHS must return 401 without auth."""
    from server import app

    failures = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if path in PUBLIC_PATHS:
            continue
        # Skip internal test-harness routes registered by test files themselves
        if path.startswith("/__test__/"):
            continue
        if "POST" not in route.methods:
            continue
        test_path = path
        for param in route.param_convertors:
            test_path = test_path.replace("{" + param + "}", "test-id-123")

        try:
            resp = client.post(test_path, json={})
            status = resp.status_code
        except Exception as exc:
            failures.append(f"POST {test_path} → crashed: {exc}")
            continue
        if status not in (401, 403, 405, 422):
            failures.append(f"POST {test_path} → {status} (expected 401/403)")

    assert not failures, "Unauthenticated routes detected:\n" + "\n".join(failures)
