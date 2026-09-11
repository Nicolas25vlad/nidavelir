from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.repository import AttemptRepository
from nidavelir_core.execution.validation import ValidationRepository
from nidavelir_core.execution.validation_runner import run_validation_checks
from nidavelir_core.settings import Settings
from nidavelir_core.tasks.domain import TaskState
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate, ValidationCommand


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
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


def _ready_attempt(session: Session, *, with_checks: bool = True):
    tasks = TaskRepository(session)
    commands = (
        [
            ValidationCommand(name="tests", type="test", command="pytest -q"),
            ValidationCommand(name="lint", type="lint", command="ruff check ."),
        ]
        if with_checks
        else []
    )
    task = tasks.create(
        TaskCreate(
            title="Validate Nidavelir",
            repository="Nicolas25vlad/nidavelir",
            validation_commands=commands,
        )
    )
    task = tasks.transition(task.id, TaskState.QUEUED)
    task = tasks.transition(task.id, TaskState.RUNNING)
    task = tasks.transition(task.id, TaskState.AGENT_DONE)
    attempt = AttemptRepository(session).create(
        task_id=task.id,
        number=1,
        container_name=f"validation-test-{task.id}-a1",
        volume_name=f"validation-test-{task.id}-volume-a1",
        branch_name=f"task/{task.id}",
    )
    return tasks, task, attempt


def test_successful_checks_leave_task_ready_for_review(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        tasks, task, attempt = _ready_attempt(session)
        monkeypatch.setattr(
            "nidavelir_core.execution.validation_runner._run_check_container",
            lambda *args, **kwargs: (0, "all good", False),
        )
        checks = ValidationRepository(session)

        passed = run_validation_checks(
            None,
            settings=Settings(),
            attempt=attempt,
            task=task,
            tasks=tasks,
            checks=checks,
        )

        assert passed is True
        assert tasks.get(task.id).state == TaskState.VALIDATING
        persisted = checks.list_for_attempt(attempt.id)
        assert [check.status for check in persisted] == ["PASSED", "PASSED"]
        assert all(check.output == "all good" for check in persisted)


def test_no_checks_still_moves_task_to_review_gate(session_factory) -> None:
    with session_factory() as session:
        tasks, task, attempt = _ready_attempt(session, with_checks=False)
        checks = ValidationRepository(session)

        passed = run_validation_checks(
            None,
            settings=Settings(),
            attempt=attempt,
            task=task,
            tasks=tasks,
            checks=checks,
        )

        assert passed is True
        persisted_task = tasks.get(task.id)
        assert persisted_task.state == TaskState.VALIDATING
        assert "UNVALIDATED" in (persisted_task.transitions[-1].reason or "")
        persisted = checks.list_for_attempt(attempt.id)
        assert len(persisted) == 1
        assert persisted[0].name == "UNVALIDATED"
        assert persisted[0].status == "SKIPPED"


def test_auto_resolved_plan_is_persisted_and_executed(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        tasks, task, attempt = _ready_attempt(session, with_checks=False)
        attempts = AttemptRepository(session)
        attempts.set_result(
            attempt.id,
            {
                "status": "success",
                "validation_plan": {
                    "mode": "auto",
                    "reason": "Node build detected",
                    "commands": [
                        {
                            "name": "node build",
                            "type": "build",
                            "command": "npm run build",
                            "timeout_seconds": 300,
                        }
                    ],
                },
            },
        )
        attempt = attempts.get(attempt.id)
        monkeypatch.setattr(
            "nidavelir_core.execution.validation_runner._run_check_container",
            lambda *args, **kwargs: (0, "built", False),
        )
        checks = ValidationRepository(session)

        passed = run_validation_checks(
            None,
            settings=Settings(),
            attempt=attempt,
            task=task,
            tasks=tasks,
            checks=checks,
        )

        assert passed is True
        assert attempt.validation_mode == "auto"
        assert attempt.resolved_validation_commands[0]["command"] == "npm run build"
        assert checks.list_for_attempt(attempt.id)[0].status == "PASSED"


def test_skipped_plan_is_visible_as_unvalidated(session_factory) -> None:
    with session_factory() as session:
        tasks, task, attempt = _ready_attempt(session, with_checks=False)
        attempts = AttemptRepository(session)
        attempts.set_result(
            attempt.id,
            {
                "status": "success",
                "validation_plan": {
                    "mode": "skipped",
                    "reason": "no supported safe validation checks detected",
                    "commands": [],
                },
            },
        )
        attempt = attempts.get(attempt.id)
        checks = ValidationRepository(session)

        passed = run_validation_checks(
            None,
            settings=Settings(),
            attempt=attempt,
            task=task,
            tasks=tasks,
            checks=checks,
        )

        assert passed is True
        assert attempt.validation_mode == "skipped"
        assert "no supported" in attempt.validation_reason
        assert "UNVALIDATED" in (tasks.get(task.id).transitions[-1].reason or "")
        persisted = checks.list_for_attempt(attempt.id)
        assert persisted[0].status == "SKIPPED"
        assert "no supported" in persisted[0].output


def test_failed_check_moves_task_to_needs_changes(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        tasks, task, attempt = _ready_attempt(session)
        results = iter([(0, "tests pass", False), (2, "lint error", False)])
        monkeypatch.setattr(
            "nidavelir_core.execution.validation_runner._run_check_container",
            lambda *args, **kwargs: next(results),
        )
        checks = ValidationRepository(session)

        passed = run_validation_checks(
            None,
            settings=Settings(),
            attempt=attempt,
            task=task,
            tasks=tasks,
            checks=checks,
        )

        assert passed is False
        assert tasks.get(task.id).state == TaskState.NEEDS_CHANGES
        persisted = checks.list_for_attempt(attempt.id)
        assert [check.status for check in persisted] == ["PASSED", "FAILED"]
        assert persisted[-1].exit_code == 2
        assert persisted[-1].output == "lint error"


def test_timed_out_check_is_persisted(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        tasks, task, attempt = _ready_attempt(session)
        monkeypatch.setattr(
            "nidavelir_core.execution.validation_runner._run_check_container",
            lambda *args, **kwargs: (137, "timeout", True),
        )
        checks = ValidationRepository(session)

        passed = run_validation_checks(
            None,
            settings=Settings(),
            attempt=attempt,
            task=task,
            tasks=tasks,
            checks=checks,
        )

        assert passed is False
        assert tasks.get(task.id).state == TaskState.NEEDS_CHANGES
        persisted = checks.list_for_attempt(attempt.id)
        assert persisted[0].status == "TIMED_OUT"
        assert persisted[1].status == "PENDING"
