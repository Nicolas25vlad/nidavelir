from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.models import AttemptStatus
from nidavelir_core.execution.repository import AttemptRepository
from nidavelir_core.execution.service import (
    ExecutionConflict,
    _capture_agent_metadata,
    enqueue_attempt,
    task_branch_name,
)
from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate


@pytest.fixture
def session_factory(monkeypatch):
    monkeypatch.setenv("NIDAVELIR_GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("NIDAVELIR_OPENAI_API_KEY", "openai-key")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        get_settings.cache_clear()


def _create_task(session: Session, title: str):
    return TaskRepository(session).create(
        TaskCreate(
            title=title,
            repository="Nicolas25vlad/nidavelir",
        )
    )


def test_task_branch_name_is_stable_and_safe() -> None:
    task_id = uuid4()

    branch = task_branch_name(task_id, "Fix: CI / worker logs!!!")

    assert branch == f"task/{str(task_id)[:8]}-fix-ci-worker-logs"


def test_enqueue_creates_attempt_and_queues_task(session_factory) -> None:
    with session_factory() as session:
        task = TaskRepository(session).create(
            TaskCreate(
                title="Make Nidavelir execute itself",
                repository="Nicolas25vlad/nidavelir",
                acceptance_criteria=["worker attempt is persisted"],
            )
        )

        attempt = enqueue_attempt(session, task.id)
        persisted_task = TaskRepository(session).get(task.id)

        assert attempt.number == 1
        assert attempt.status is AttemptStatus.PREPARING
        assert attempt.harness == "codex"
        assert persisted_task.state == "QUEUED"
        assert persisted_task.transitions[-1].to_state == "QUEUED"


def test_second_active_attempt_is_rejected(session_factory) -> None:
    with session_factory() as session:
        task = _create_task(session, "Prevent duplicate workers")
        enqueue_attempt(session, task.id)

        with pytest.raises(ExecutionConflict):
            enqueue_attempt(session, task.id)


def test_global_worker_capacity_is_enforced(session_factory, monkeypatch) -> None:
    monkeypatch.setenv("NIDAVELIR_MAX_PARALLEL_WORKERS", "1")
    get_settings.cache_clear()

    with session_factory() as session:
        first = _create_task(session, "First worker")
        second = _create_task(session, "Second worker")
        enqueue_attempt(session, first.id)

        with pytest.raises(ExecutionConflict, match="worker capacity reached"):
            enqueue_attempt(session, second.id)


def test_agent_result_and_commit_are_persisted(session_factory) -> None:
    with session_factory() as session:
        task = _create_task(session, "Persist the worker result")
        attempt = enqueue_attempt(session, task.id)
        attempts = AttemptRepository(session)
        attempts.append_logs(
            attempt.id,
            "NIDAVELIR_HARNESS_VERSION=codex-cli 1.2.3\n"
            'NIDAVELIR_RESULT={"type":"nidavelir_result","status":"success",'
            '"branch":"task/test","commit":"abc123"}\n',
        )

        result = _capture_agent_metadata(attempts, attempt.id)
        persisted = attempts.get(attempt.id)

        assert result is not None
        assert result["status"] == "success"
        assert persisted.harness_version == "codex-cli 1.2.3"
        assert persisted.commit_sha == "abc123"
        assert persisted.result == result
