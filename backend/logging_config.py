"""Structured logging setup.

Log level policy:
- debug: low-volume diagnostics such as slow query timing when enabled.
- info: normal lifecycle and security-success events.
- warning: expected degraded conditions and security failures.
- error: unexpected exceptions and data integrity failures.
- critical: unrecoverable startup or configuration failures.

For subtasks spawned during a request, use contextvars.copy_context().run(...)
around asyncio.create_task(...) so request_id_ctx follows the child task.
"""

from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime, timezone


request_id_ctx = contextvars.ContextVar("request_id", default=None)
method_ctx = contextvars.ContextVar("method", default=None)
path_ctx = contextvars.ContextVar("path", default=None)
status_code_ctx = contextvars.ContextVar("status_code", default=None)
duration_ms_ctx = contextvars.ContextVar("duration_ms", default=None)

FORBIDDEN_LOG_FIELDS = {"student_name", "phone", "address", "fee_amount", "biometric"}
STANDARD_LOG_RECORD_FIELDS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename", "module",
    "exc_info", "exc_text", "stack_info", "lineno", "funcName", "created", "msecs",
    "relativeCreated", "thread", "threadName", "processName", "process", "message",
    "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": "eduflow-api",
            "logger": record.name,
            "message": record.getMessage(),
            "method": getattr(record, "method", None) or method_ctx.get(),
            "path": getattr(record, "path", None) or path_ctx.get(),
            "status_code": getattr(record, "status_code", None) or status_code_ctx.get(),
            "duration_ms": getattr(record, "duration_ms", None) or duration_ms_ctx.get(),
            "request_id": getattr(record, "request_id", None) or request_id_ctx.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_FIELDS or key in payload or key in FORBIDDEN_LOG_FIELDS:
                continue
            payload[key] = value
        return json.dumps(
            {k: v for k, v in payload.items() if k not in FORBIDDEN_LOG_FIELDS},
            default=str,
            separators=(",", ":"),
        )


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
