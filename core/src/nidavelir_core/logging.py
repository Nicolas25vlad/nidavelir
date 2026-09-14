from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_log_context: ContextVar[dict[str, str]] = ContextVar("nidavelir_log_context", default={})
_CONTEXT_FIELDS = ("task_id", "attempt_id", "stage", "event")


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    current = _log_context.get()
    normalized = {
        key: str(value)
        for key, value in fields.items()
        if key in _CONTEXT_FIELDS and value is not None
    }
    token = _log_context.set({**current, **normalized})
    try:
        yield
    finally:
        _log_context.reset(token)


class NidavelirContextFilter(logging.Filter):
    def __init__(self, installation_id: str) -> None:
        super().__init__()
        self.installation_id = installation_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.installation_id = self.installation_id
        context = _log_context.get()
        for field in _CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, context.get(field, ""))
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "installation_id": getattr(record, "installation_id", ""),
        }
        for field in _CONTEXT_FIELDS:
            value = getattr(record, field, "")
            if value:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def configure_logging(
    level: str,
    *,
    installation_id: str = "development",
    structured: bool = False,
) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(NidavelirContextFilter(installation_id))
    if structured:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s "
                "[installation=%(installation_id)s task=%(task_id)s "
                "attempt=%(attempt_id)s stage=%(stage)s] %(message)s"
            )
        )

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[handler],
        force=True,
    )
