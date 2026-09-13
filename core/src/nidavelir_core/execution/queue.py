from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.domain import TaskState
from nidavelir_core.tasks.repository import TaskRepository

from .models import AttemptRecord, AttemptStatus, utcnow
from .repository import AttemptRepository
from .service import (
    ExecutionConflict,
    _installation_namespace,
    _validate_harness_configuration,
    task_branch_name,
)


def enqueue_attempt(
    session: Session,
    task_id: UUID,
    *,
    harness: str = "codex",
) -> AttemptRecord:
    """Persist work for the executor without applying active-worker admission limits."""
    settings = get_settings()
    _validate_harness_configuration(settings, harness)

    tasks = TaskRepository(session)
    attempts = AttemptRepository(session)
    task = tasks.get(task_id)

    latest = attempts.latest_for_task(task_id)
    if latest is not None and latest.status in {
        AttemptStatus.PREPARING,
        AttemptStatus.RUNNING,
    }:
        raise ExecutionConflict(f"task {task_id} already has an active attempt")

    if task.state in {TaskState.BACKLOG, TaskState.NEEDS_CHANGES}:
        task = tasks.transition(task_id, TaskState.QUEUED, reason="execution requested")
    elif task.state != TaskState.QUEUED:
        raise ExecutionConflict(f"task {task_id} cannot start from {task.state}")

    number = attempts.next_number(task_id)
    short_id = str(task.id)[:8]
    namespace = _installation_namespace(settings)
    runtime_name = f"nidavelir-{namespace}-{short_id}-a{number}"
    return attempts.create(
        task_id=task.id,
        number=number,
        container_name=runtime_name,
        volume_name=f"nidavelir-{namespace}-task-{short_id}-a{number}",
        branch_name=task_branch_name(task.id, task.title),
        harness=harness,
        retry_context=task.retry_context,
        retry_review_ids=task.retry_review_ids,
    )


def claim_next_attempt(
    session: Session,
    *,
    owner: str,
    lease_seconds: int,
) -> AttemptRecord | None:
    now = utcnow()
    statement = (
        select(AttemptRecord)
        .where(
            AttemptRecord.status == AttemptStatus.PREPARING,
            or_(
                AttemptRecord.lease_owner.is_(None),
                AttemptRecord.lease_expires_at.is_(None),
                AttemptRecord.lease_expires_at <= now,
            ),
        )
        .order_by(AttemptRecord.created_at, AttemptRecord.number)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    attempt = session.scalar(statement)
    if attempt is None:
        session.rollback()
        return None

    attempt.lease_owner = owner
    attempt.heartbeat_at = now
    attempt.lease_expires_at = now + timedelta(seconds=lease_seconds)
    session.commit()
    session.refresh(attempt)
    return attempt


def renew_attempt_lease(
    session: Session,
    attempt_id: UUID,
    *,
    owner: str,
    lease_seconds: int,
) -> bool:
    attempt = session.get(AttemptRecord, attempt_id)
    if attempt is None or attempt.lease_owner != owner:
        return False
    if attempt.status not in {AttemptStatus.PREPARING, AttemptStatus.RUNNING}:
        return False

    now = utcnow()
    attempt.heartbeat_at = now
    attempt.lease_expires_at = now + timedelta(seconds=lease_seconds)
    session.commit()
    return True


def release_attempt_lease(session: Session, attempt_id: UUID, *, owner: str) -> None:
    attempt = session.get(AttemptRecord, attempt_id)
    if attempt is None or attempt.lease_owner != owner:
        return
    attempt.lease_owner = None
    attempt.lease_expires_at = None
    session.commit()


def list_stale_running_attempts(session: Session) -> list[AttemptRecord]:
    now = utcnow()
    statement = select(AttemptRecord).where(
        AttemptRecord.status == AttemptStatus.RUNNING,
        AttemptRecord.lease_expires_at.is_not(None),
        AttemptRecord.lease_expires_at <= now,
    )
    return list(session.scalars(statement).all())
