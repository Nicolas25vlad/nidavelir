from __future__ import annotations

import logging
import re
from threading import Event, Timer

from docker.errors import APIError, NotFound

from nidavelir_core.settings import Settings
from nidavelir_core.tasks.domain import TaskState
from nidavelir_core.tasks.repository import TaskRepository

from .models import AttemptRecord, ValidationCheckStatus
from .validation import ValidationRepository

logger = logging.getLogger(__name__)

MANAGED_LABEL = "io.nidavelir.managed"
INSTALLATION_LABEL = "io.nidavelir.installation"
ATTEMPT_LABEL = "io.nidavelir.attempt_id"


def _installation_namespace(settings: Settings) -> str:
    namespace = re.sub(r"[^a-z0-9]+", "-", settings.installation_id.lower()).strip("-")
    return (namespace or "development")[:24].rstrip("-")


def _run_check_container(
    client,
    *,
    settings: Settings,
    attempt: AttemptRecord,
    position: int,
    command: str,
    timeout_seconds: int,
) -> tuple[int, str, bool]:
    container = client.containers.run(
        settings.worker_image,
        command=["/usr/local/bin/nidavelir-run-check"],
        name=f"{attempt.container_name}-check-{position}",
        detach=True,
        labels={
            MANAGED_LABEL: "true",
            INSTALLATION_LABEL: _installation_namespace(settings),
            ATTEMPT_LABEL: str(attempt.id),
        },
        environment={"NIDAVELIR_VALIDATION_COMMAND": command},
        volumes={attempt.volume_name: {"bind": "/workspace/repo", "mode": "rw"}},
        mem_limit=settings.worker_memory,
        nano_cpus=int(settings.worker_cpus * 1_000_000_000),
    )
    timed_out = Event()

    def kill_for_timeout() -> None:
        timed_out.set()
        try:
            container.kill()
        except (APIError, NotFound):
            logger.debug("validation container finished before timeout kill", exc_info=True)

    timer = Timer(timeout_seconds, kill_for_timeout)
    timer.daemon = True
    timer.start()
    try:
        result = container.wait()
        output = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        return int(result.get("StatusCode", 1)), output, timed_out.is_set()
    finally:
        timer.cancel()
        try:
            container.remove(force=True)
        except (APIError, NotFound):
            logger.debug("validation container already removed", exc_info=True)


def run_validation_checks(
    client,
    *,
    settings: Settings,
    attempt: AttemptRecord,
    task,
    tasks: TaskRepository,
    checks: ValidationRepository,
) -> bool:
    if attempt.validation_mode in {"configured", "auto", "skipped"}:
        commands = list(attempt.resolved_validation_commands or [])
        mode = attempt.validation_mode
        reason = attempt.validation_reason
    else:
        commands = list(task.validation_commands or [])
        mode = "configured" if commands else "skipped"
        reason = "legacy attempt validation configuration"

    transition_reason = (
        f"running {len(commands)} {mode} validation checks for attempt {attempt.number}"
        if commands
        else f"UNVALIDATED attempt {attempt.number}: {reason or 'no validation checks configured'}"
    )
    tasks.transition(task.id, TaskState.VALIDATING, reason=transition_reason)
    if not commands:
        return True

    records = checks.create_checks(
        task_id=task.id,
        attempt_id=attempt.id,
        commands=commands,
    )

    for record, command in zip(records, commands, strict=True):
        checks.mark_running(record.id)
        exit_code, output, timed_out = _run_check_container(
            client,
            settings=settings,
            attempt=attempt,
            position=record.position,
            command=command["command"],
            timeout_seconds=int(command.get("timeout_seconds", 300)),
        )

        if timed_out:
            checks.finish(
                record.id,
                status=ValidationCheckStatus.TIMED_OUT,
                exit_code=exit_code,
                output=output,
            )
            tasks.transition(
                task.id,
                TaskState.NEEDS_CHANGES,
                reason=f"validation check {record.name!r} timed out",
            )
            return False

        if exit_code != 0:
            checks.finish(
                record.id,
                status=ValidationCheckStatus.FAILED,
                exit_code=exit_code,
                output=output,
            )
            tasks.transition(
                task.id,
                TaskState.NEEDS_CHANGES,
                reason=f"validation check {record.name!r} failed",
            )
            return False

        checks.finish(
            record.id,
            status=ValidationCheckStatus.PASSED,
            exit_code=0,
            output=output,
        )

    return True
