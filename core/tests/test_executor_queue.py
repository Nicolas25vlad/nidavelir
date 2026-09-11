from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.models import AttemptStatus, utcnow
from nidavelir_core.execution.queue import (
    claim_next_attempt,
    release_attempt_lease,
    renew_attempt_lease,
)
from nidavelir_core.execution.repository import AttemptRepository
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate


def _session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def _queued_attempt(session: Session):
    task = TaskRepository(session).create(
        TaskCreate(title="durable executor", repository="Nicolas25vlad/nidavelir")
    )
    return AttemptRepository(session).create(
        task_id=task.id,
        number=1,
        container_name=f"executor-{task.id}",
        volume_name=f"executor-volume-{task.id}",
        branch_name=f"task/{task.id}",
    )


def test_claim_is_exclusive_until_lease_released() -> None:
    factory = _session_factory()
    with factory() as session:
        attempt = _queued_attempt(session)
        claimed = claim_next_attempt(session, owner="executor-a", lease_seconds=30)
        assert claimed is not None
        assert claimed.id == attempt.id
        assert claimed.lease_owner == "executor-a"

    with factory() as session:
        assert claim_next_attempt(session, owner="executor-b", lease_seconds=30) is None
        release_attempt_lease(session, attempt.id, owner="executor-a")
        claimed = claim_next_attempt(session, owner="executor-b", lease_seconds=30)
        assert claimed is not None
        assert claimed.lease_owner == "executor-b"


def test_expired_preparing_lease_can_be_reclaimed() -> None:
    factory = _session_factory()
    with factory() as session:
        attempt = _queued_attempt(session)
        attempt.lease_owner = "dead-executor"
        attempt.lease_expires_at = utcnow() - timedelta(seconds=1)
        session.commit()

    with factory() as session:
        claimed = claim_next_attempt(session, owner="replacement", lease_seconds=30)
        assert claimed is not None
        assert claimed.id == attempt.id
        assert claimed.lease_owner == "replacement"


def test_heartbeat_only_renews_current_owner() -> None:
    factory = _session_factory()
    with factory() as session:
        attempt = _queued_attempt(session)
        claim_next_attempt(session, owner="executor-a", lease_seconds=30)
        assert not renew_attempt_lease(
            session,
            attempt.id,
            owner="executor-b",
            lease_seconds=60,
        )
        assert renew_attempt_lease(
            session,
            attempt.id,
            owner="executor-a",
            lease_seconds=60,
        )


def test_finished_attempt_cannot_keep_lease_alive() -> None:
    factory = _session_factory()
    with factory() as session:
        attempt = _queued_attempt(session)
        claim_next_attempt(session, owner="executor-a", lease_seconds=30)
        AttemptRepository(session).finish(
            attempt.id,
            status=AttemptStatus.SUCCEEDED,
            exit_code=0,
        )
        assert not renew_attempt_lease(
            session,
            attempt.id,
            owner="executor-a",
            lease_seconds=60,
        )
