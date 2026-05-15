from __future__ import annotations

import logging
import json

import routes.auth as auth_routes
from logging_config import JsonFormatter


def test_failed_login_wrong_password_logs_warning_without_password(client, caplog):
    caplog.set_level(logging.WARNING, logger=auth_routes.logger.name)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-secret"},
        headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.1"},
    )

    assert response.status_code == 401
    record = next(record for record in caplog.records if record.msg == "login_failed")
    assert record.event == "login_failed"
    assert record.username == "admin"
    assert record.reason == "invalid_password"
    assert record.ip == "1.2.3.4"
    assert "wrong-secret" not in caplog.text


def test_failed_login_unknown_user_logs_warning(client, caplog):
    caplog.set_level(logging.WARNING, logger=auth_routes.logger.name)

    response = client.post(
        "/api/auth/login",
        json={"username": "missing-user", "password": "wrong-secret"},
    )

    assert response.status_code == 401
    record = next(record for record in caplog.records if record.msg == "login_failed")
    assert record.reason == "user_not_found"
    assert record.username == "missing-user"
    assert "wrong-secret" not in caplog.text


def test_successful_login_logs_structured_info_without_password(client, caplog):
    caplog.set_level(logging.INFO, logger=auth_routes.logger.name)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )

    assert response.status_code == 200
    record = next(record for record in caplog.records if record.msg == "login_success")
    assert record.event == "login_success"
    assert record.username == "admin"
    assert record.role == "owner"
    assert "admin123" not in caplog.text


def test_json_formatter_renders_extra_fields():
    record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="login_failed",
        args=(),
        exc_info=None,
    )
    record.event = "login_failed"
    record.reason = "invalid_password"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "login_failed"
    assert payload["reason"] == "invalid_password"
