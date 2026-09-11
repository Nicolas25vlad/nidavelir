from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.models import AttemptStatus
from nidavelir_core.execution.recovery import RESTART_REASON, recover_interrupted_attempts
from nidavelir_core.execution.repository import (
    LOG_TRUNCATION_MARKER,
    MAX_PERSISTED_LOG_CHARS,
    AttemptRepository,
)
from nidavelir_core.tasks.domain import TaskState
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate


def _session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _create_interrupted(factory, *, running: bool):
    with factory() as session:
        tasks = TaskRepository(session)
        attempts = AttemptRepository(session)
        task = tasks.create(
            TaskCreate(
                title="Interrupted dogfood task",
                repository="Nicolas25vlad/nidavelir",
            )
        )
        tasks.transition(task.id, TaskState.QUEUED, reason="test queued")
        attempt = attempts.create(
            task_id=task.id,
            number=1,
            container_name="nidavelir-test-a1",
            volume_name="nidavelir-test-volume",
            branch_name="task/test-interrupted",
            harness="codex",
        )
        if running:
            tasks.transition(task.id, TaskState.RUNNING, reason="test running")
            attempts.mark_running(attempt.id)
        return task.id, attempt.id


def test_recovery_marks_preparing_attempt_failed_and_task_retryable() -> None:
    engine, factory = _session_factory()
    task_id, attempt_id = _create_interrupted(factory, running=False)

    with factory() as session:
        recovered = recover_interrupted_attempts(session)
        attempt = AttemptRepository(session).get(attempt_id)
        task = TaskRepository(session).get(task_id)

        assert recovered == 1
        assert attempt.status is AttemptStatus.FAILED
        assert attempt.failure_reason == RESTART_REASON
        assert "[recovery]" in attempt.logs
        assert task.state is TaskState.NEEDS_CHANGES

    engine.dispose()


def test_recovery_marks_running_attempt_failed_and_task_retryable() -> None:
    engine, factory = _session_factory()
    task_id, attempt_id = _create_interrupted(factory, running=True)

    with factory() as session:
        recovered = recover_interrupted_attempts(session)
        attempt = AttemptRepository(session).get(attempt_id)
        task = TaskRepository(session).get(task_id)

        assert recovered == 1
        assert attempt.status is AttemptStatus.FAILED
        assert attempt.finished_at is not None
        assert task.state is TaskState.NEEDS_CHANGES
        assert "interrupted by Core restart" in (task.transitions[-1].reason or "")

    engine.dispose()


def test_worker_logs_keep_a_bounded_tail() -> None:
    engine, factory = _session_factory()
    task_id, attempt_id = _create_interrupted(factory, running=False)

    with factory() as session:
        attempts = AttemptRepository(session)
        attempts.append_logs(attempt_id, "A" * MAX_PERSISTED_LOG_CHARS)
        attempts.append_logs(attempt_id, "TAIL")
        persisted = attempts.get(attempt_id)

        assert len(persisted.logs) == MAX_PERSISTED_LOG_CHARS
        assert persisted.logs.startswith(LOG_TRUNCATION_MARKER)
        assert persisted.logs.endswith("TAIL")
        assert persisted.task_id == task_id

    engine.dispose()
