import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "request_id"):
            log_entry["requestId"] = record.request_id
        if hasattr(record, "method"):
            log_entry["method"] = record.method
        if hasattr(record, "path"):
            log_entry["path"] = record.path
        if hasattr(record, "status_code"):
            log_entry["statusCode"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_entry["durationMs"] = record.duration_ms
        if hasattr(record, "client_ip"):
            log_entry["clientIp"] = record.client_ip
        if hasattr(record, "user_id"):
            log_entry["userId"] = record.user_id

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, default=str)


class DevFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        parts = [f"{color}{ts} [{record.levelname:7s}]{self.RESET}", f"{record.name}:", record.getMessage()]

        if hasattr(record, "request_id"):
            parts.append(f"[{record.request_id[:8]}]")
        if hasattr(record, "status_code"):
            parts.append(f"→ {record.status_code}")
        if hasattr(record, "duration_ms"):
            parts.append(f"({record.duration_ms:.0f}ms)")

        if record.exc_info and record.exc_info[1]:
            parts.append(f"\n{self.formatException(record.exc_info)}")

        return " ".join(parts)


def setup_logging(environment: str = "development") -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if environment == "production":
        handler.setFormatter(StructuredFormatter())
        handler.setLevel(logging.INFO)
    else:
        handler.setFormatter(DevFormatter())
        handler.setLevel(logging.DEBUG)

    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)


logger = logging.getLogger("pvc")
