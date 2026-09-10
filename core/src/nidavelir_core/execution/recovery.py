from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from nidavelir_core.database import SessionLocal
from nidavelir_core.tasks.domain import InvalidTaskTransition, TaskState
from nidavelir_core.tasks.repository import TaskNotFound, TaskRepository

from .models import AttemptStatus
from .repository import AttemptRepository

logger = logging.getLogger(__name__)

RESTART_REASON = "Core restarted while this attempt was active"


def recover_interrupted_attempts(session: Session) -> int:
    attempts = AttemptRepository(session)
    tasks = TaskRepository(session)
    recovered = 0

    for attempt in attempts.list_active():
        attempts.append_logs(
            attempt.id,
            "\n[recovery]\nCore restarted before this attempt reached a terminal state.\n",
        )
        attempts.finish(
            attempt.id,
            status=AttemptStatus.FAILED,
            exit_code=None,
            failure_reason=RESTART_REASON,
        )

        try:
            task = tasks.get(attempt.task_id)
            if task.state in {TaskState.QUEUED, TaskState.RUNNING}:
                tasks.transition(
                    task.id,
                    TaskState.NEEDS_CHANGES,
                    reason=f"attempt {attempt.number} interrupted by Core restart",
                )
        except (TaskNotFound, InvalidTaskTransition):
            logger.warning(
                "could not reconcile task for interrupted attempt %s",
                attempt.id,
                exc_info=True,
            )

        recovered += 1

    return recovered


def recover_interrupted_execution() -> int:
    with SessionLocal() as session:
        recovered = recover_interrupted_attempts(session)
    if recovered:
        logger.warning("recovered %s interrupted attempt(s) after startup", recovered)
    return recovered
