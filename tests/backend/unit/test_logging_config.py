import json
import logging

from backend import logging_config


def test_json_formatter_contains_required_request_fields():
    formatter = logging_config.JsonFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request completed",
        args=(),
        exc_info=None,
    )
    record.method = "GET"
    record.path = "/api/example"
    record.status_code = 200
    record.duration_ms = 12.3
    record.request_id = "req-1"

    payload = json.loads(formatter.format(record))

    for field in ["timestamp", "level", "service", "method", "path", "status_code", "duration_ms", "request_id"]:
        assert field in payload
    assert not (set(payload) & logging_config.FORBIDDEN_LOG_FIELDS)
