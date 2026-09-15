import json
import logging
import sys
from contextvars import ContextVar
from typing import Any

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        if hasattr(record, "host"):
            log_data["host"] = record.host
        if hasattr(record, "group_id"):
            log_data["group_id"] = record.group_id
        if hasattr(record, "operation"):
            log_data["operation"] = record.operation
        if hasattr(record, "attempt"):
            log_data["attempt"] = record.attempt
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = [handler]

    logging.getLogger("httpx").setLevel(logging.WARNING)


def set_correlation_id(correlation_id: str) -> None:
    correlation_id_var.set(correlation_id)


def clear_correlation_id() -> None:
    correlation_id_var.set(None)
