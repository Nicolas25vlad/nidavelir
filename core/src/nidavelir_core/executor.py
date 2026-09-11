from __future__ import annotations

import logging
import os
import socket
import time
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Thread
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from nidavelir_core.database import SessionLocal
from nidavelir_core.execution.models import AttemptStatus
from nidavelir_core.execution.queue import (
    claim_next_attempt,
    list_stale_running_attempts,
    release_attempt_lease,
    renew_attempt_lease,
)
from nidavelir_core.execution.repository import AttemptRepository
from nidavelir_core.execution.service import cancel_attempt_resources, execute_attempt
from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.domain import InvalidTaskTransition, TaskState
from nidavelir_core.tasks.repository import TaskRepository

logger = logging.getLogger(__name__)


def _executor_id() -> str:
    configured = os.getenv("NIDAVELIR_EXECUTOR_ID", "").strip()
    return configured or f"{socket.gethostname()}-{os.getpid()}"


def _heartbeat(attempt_id: UUID, owner: str, stopped: Event) -> None:
    settings = get_settings()
    interval = max(1, settings.executor_heartbeat_seconds)
    while not stopped.wait(interval):
        try:
            with SessionLocal() as session:
                if not renew_attempt_lease(
                    session,
                    attempt_id,
                    owner=owner,
                    lease_seconds=settings.executor_lease_seconds,
                ):
                    return
        except SQLAlchemyError:
            logger.warning("failed to renew executor lease for %s", attempt_id, exc_info=True)


def _run_claimed_attempt(attempt_id: UUID, owner: str) -> None:
    stopped = Event()
    heartbeat = Thread(target=_heartbeat, args=(attempt_id, owner, stopped), daemon=True)
    heartbeat.start()
    try:
        execute_attempt(attempt_id)
    finally:
        stopped.set()
        heartbeat.join(timeout=2)
        try:
            with SessionLocal() as session:
                release_attempt_lease(session, attempt_id, owner=owner)
        except SQLAlchemyError:
            logger.warning("failed to release executor lease for %s", attempt_id, exc_info=True)


def _recover_stale_attempts() -> None:
    try:
        with SessionLocal() as session:
            attempts = AttemptRepository(session)
            tasks = TaskRepository(session)
            for attempt in list_stale_running_attempts(session):
                logger.warning("recovering stale running attempt %s", attempt.id)
                cancel_attempt_resources(attempt.id)
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.FAILED,
                    exit_code=None,
                    failure_reason="executor lease expired; safe retry required",
                )
                try:
                    task = tasks.get(attempt.task_id)
                    if task.state in {TaskState.RUNNING, TaskState.AGENT_DONE, TaskState.VALIDATING}:
                        tasks.transition(
                            task.id,
                            TaskState.NEEDS_CHANGES,
                            reason="executor lease expired; previous attempt was interrupted",
                        )
                except InvalidTaskTransition:
                    logger.warning("could not recover task for stale attempt %s", attempt.id)
    except SQLAlchemyError:
        logger.warning("stale attempt recovery deferred until database is ready", exc_info=True)


def run() -> None:
    settings = get_settings()
    owner = _executor_id()
    active: dict[Future[None], UUID] = {}
    logger.info("starting Nidavelir executor %s", owner)
    _recover_stale_attempts()

    with ThreadPoolExecutor(
        max_workers=settings.max_parallel_workers,
        thread_name_prefix="nidavelir-attempt",
    ) as pool:
        while True:
            for future, attempt_id in list(active.items()):
                if future.done():
                    active.pop(future, None)
                    try:
                        future.result()
                    except Exception:
                        logger.exception("executor future failed for attempt %s", attempt_id)

            available = settings.max_parallel_workers - len(active)
            for _ in range(max(0, available)):
                try:
                    with SessionLocal() as session:
                        attempt = claim_next_attempt(
                            session,
                            owner=owner,
                            lease_seconds=settings.executor_lease_seconds,
                        )
                except SQLAlchemyError:
                    logger.warning("executor queue unavailable; retrying", exc_info=True)
                    attempt = None

                if attempt is None:
                    break
                future = pool.submit(_run_claimed_attempt, attempt.id, owner)
                active[future] = attempt.id

            time.sleep(settings.executor_poll_seconds)


if __name__ == "__main__":
    run()
