import json
import logging

from nidavelir_core.logging import (
    JsonLogFormatter,
    NidavelirContextFilter,
    log_context,
)


def _record(message: str = "worker stage started") -> logging.LogRecord:
    return logging.LogRecord(
        name="nidavelir.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_log_formatter_includes_installation_and_execution_context() -> None:
    record = _record()
    filter_ = NidavelirContextFilter("install-abc")

    with log_context(task_id="task-1", attempt_id="attempt-2", stage="validation"):
        assert filter_.filter(record) is True
        payload = json.loads(JsonLogFormatter().format(record))

    assert payload["installation_id"] == "install-abc"
    assert payload["task_id"] == "task-1"
    assert payload["attempt_id"] == "attempt-2"
    assert payload["stage"] == "validation"
    assert payload["message"] == "worker stage started"


def test_log_context_does_not_leak_between_scopes() -> None:
    filter_ = NidavelirContextFilter("install-abc")

    with log_context(task_id="task-1"):
        scoped = _record()
        filter_.filter(scoped)
        assert scoped.task_id == "task-1"

    unscoped = _record()
    filter_.filter(unscoped)
    assert unscoped.task_id == ""


def test_explicit_record_context_wins_over_context_var() -> None:
    record = _record()
    record.attempt_id = "explicit-attempt"
    filter_ = NidavelirContextFilter("install-abc")

    with log_context(attempt_id="context-attempt"):
        filter_.filter(record)

    assert record.attempt_id == "explicit-attempt"
