from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.models import AttemptStatus
from nidavelir_core.execution.service import (
    ExecutionConflict,
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
        task = TaskRepository(session).create(
            TaskCreate(
                title="Prevent duplicate workers",
                repository="Nicolas25vlad/nidavelir",
            )
        )
        enqueue_attempt(session, task.id)

        with pytest.raises(ExecutionConflict):
            enqueue_attempt(session, task.id)
