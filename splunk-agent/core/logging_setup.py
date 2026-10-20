"""Logging configuration with secret redaction and optional JSON output."""

from __future__ import annotations

import json
import logging
import logging.handlers
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.config import LoggingSettings

_REDACTIONS = [
    (re.compile(r"(?i)(password|passwd|token|splunkToken|secret|authorization)(\s*[=:]\s*|['\"]\s*:\s*['\"])([^\s'\",]+)"), r"\1\2***"),
    (re.compile(r"(?i)\b(Bearer|Splunk)\s+[A-Za-z0-9._\-]{12,}"), r"\1 ***"),
]


class RedactingFilter(logging.Filter):
    """Masks credentials that might end up in log messages or exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        redacted = msg
        for pattern, repl in _REDACTIONS:
            redacted = pattern.sub(repl, redacted)
        if redacted != msg:
            record.msg, record.args = redacted, ()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line - friendly for Splunk/ELK ingestion of the agent's own logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: LoggingSettings, *, level_override: str | None = None) -> None:
    level = (level_override or settings.level).upper()
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    formatter: logging.Formatter = (
        JsonFormatter() if settings.json
        else logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    console = logging.StreamHandler(sys.stderr)
    handlers: list[logging.Handler] = [console]
    if settings.file:
        path = Path(settings.file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(
            path, maxBytes=settings.max_bytes, backupCount=settings.backup_count, encoding="utf-8"))
    redactor = RedactingFilter()
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(redactor)
        root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("urllib3", "splunklib"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))
