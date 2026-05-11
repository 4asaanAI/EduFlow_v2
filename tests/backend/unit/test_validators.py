"""
Unit Tests: Input Validators — EduFlow Backend

Tests for pure validation logic that doesn't require a database or server.
These tests run fast and have no external dependencies.
"""

import pytest


class TestLoginRequestValidation:
    """Pydantic validator tests for LoginRequest model."""

    def test_username_strips_whitespace(self):
        """Username validator should strip leading/trailing whitespace."""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            from routes.auth import LoginRequest
        except ImportError:
            pytest.skip("Backend not importable in this environment")

        req = LoginRequest(username="  admin  ", password="pass")
        assert req.username == "admin"

    def test_username_too_short_rejected(self):
        """Username shorter than 2 chars should raise ValueError."""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            from routes.auth import LoginRequest
            from pydantic import ValidationError
        except ImportError:
            pytest.skip("Backend not importable in this environment")

        with pytest.raises(ValidationError):
            LoginRequest(username="a", password="pass")

    def test_username_rejects_injection_chars(self):
        """Username with $ or {} chars should raise ValueError."""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            from routes.auth import LoginRequest
            from pydantic import ValidationError
        except ImportError:
            pytest.skip("Backend not importable in this environment")

        with pytest.raises(ValidationError):
            LoginRequest(username="admin${}attack", password="pass")

    @pytest.mark.parametrize("bad_char", ["$", "{", "}", "(", ")"])
    def test_username_rejects_each_forbidden_char(self, bad_char):
        """Each forbidden character should individually trigger validation error."""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            from routes.auth import LoginRequest
            from pydantic import ValidationError
        except ImportError:
            pytest.skip("Backend not importable in this environment")

        with pytest.raises(ValidationError):
            LoginRequest(username=f"user{bad_char}name", password="pass")


class TestPasswordValidation:
    """Password validation edge cases."""

    def test_password_strips_whitespace(self):
        """Password should strip surrounding whitespace."""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            from routes.auth import LoginRequest
        except ImportError:
            pytest.skip("Backend not importable in this environment")

        req = LoginRequest(username="admin", password="  mypass  ")
        assert req.password == "mypass"

    def test_empty_password_rejected(self):
        """Empty password should raise ValueError."""
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
            from routes.auth import LoginRequest
            from pydantic import ValidationError
        except ImportError:
            pytest.skip("Backend not importable in this environment")

        with pytest.raises(ValidationError):
            LoginRequest(username="admin", password="")
