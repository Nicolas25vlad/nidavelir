from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.service import (
    ATTEMPT_LABEL,
    INSTALLATION_LABEL,
    MANAGED_LABEL,
    _labels,
    _scoped_filters,
    enqueue_attempt,
)
from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate


def test_worker_labels_include_installation_scope(monkeypatch) -> None:
    monkeypatch.setenv("NIDAVELIR_INSTALLATION_ID", "server-a")
    get_settings.cache_clear()
    attempt_id = uuid4()

    labels = _labels(attempt_id)

    assert labels == {
        MANAGED_LABEL: "true",
        INSTALLATION_LABEL: "server-a",
        ATTEMPT_LABEL: str(attempt_id),
    }
    get_settings.cache_clear()


def test_destructive_filters_require_installation_scope(monkeypatch) -> None:
    monkeypatch.setenv("NIDAVELIR_INSTALLATION_ID", "server-b")
    get_settings.cache_clear()
    attempt_id = uuid4()

    filters = _scoped_filters(attempt_id)

    assert filters["label"] == [
        f"{MANAGED_LABEL}=true",
        f"{INSTALLATION_LABEL}=server-b",
        f"{ATTEMPT_LABEL}={attempt_id}",
    ]
    get_settings.cache_clear()


def test_attempt_runtime_names_are_namespaced(monkeypatch) -> None:
    monkeypatch.setenv("NIDAVELIR_INSTALLATION_ID", "Home Server #1")
    monkeypatch.setenv("NIDAVELIR_GITHUB_TOKEN", "github-token")
    monkeypatch.setenv("NIDAVELIR_OPENAI_API_KEY", "openai-key")
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    try:
        with sessions() as session:
            task = TaskRepository(session).create(
                TaskCreate(
                    title="Shared Docker host isolation",
                    repository="Nicolas25vlad/nidavelir",
                )
            )
            attempt = enqueue_attempt(session, task.id)

            assert attempt.container_name.startswith("nidavelir-home-server-1-")
            assert attempt.volume_name.startswith("nidavelir-home-server-1-task-")
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
        get_settings.cache_clear()
