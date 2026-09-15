from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.merge import merge_approved_task
from nidavelir_core.execution.models import AttemptStatus, ValidationCheckStatus
from nidavelir_core.execution.queue import claim_next_attempt, enqueue_attempt
from nidavelir_core.execution.repository import AttemptRepository
from nidavelir_core.execution.review import approve_task
from nidavelir_core.execution.validation import ValidationRepository
from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.domain import TaskState
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate, ValidationCommand


@pytest.fixture
def session_factory(monkeypatch) -> Iterator[sessionmaker[Session]]:
    monkeypatch.setenv("NIDAVELIR_GITHUB_TOKEN", "dogfood-test-token")
    monkeypatch.setenv("NIDAVELIR_OPENAI_API_KEY", "dogfood-openai-key")
    monkeypatch.setenv("NIDAVELIR_INSTALLATION_ID", "dogfood-ci")
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


def test_full_durable_lifecycle_reaches_controlled_merge(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        tasks = TaskRepository(session)
        attempts = AttemptRepository(session)
        checks = ValidationRepository(session)

        task = tasks.create(
            TaskCreate(
                title="Dogfood lifecycle smoke",
                description="Exercise the durable orchestration contract.",
                repository="Nicolas25vlad/nidavelir",
                profile="backend",
                supervisor_client="pytest",
                supervisor_session_id="dogfood-smoke",
                project_id="nidavelir",
                acceptance_criteria=["The task reaches CLOSED through controlled merge."],
                validation_commands=[
                    ValidationCommand(
                        name="core-tests",
                        type="test",
                        command="pytest -q",
                        timeout_seconds=300,
                    )
                ],
            )
        )

        attempt = enqueue_attempt(session, task.id, harness="codex")
        assert tasks.get(task.id).state == TaskState.QUEUED
        assert attempt.status == AttemptStatus.PREPARING

        claimed = claim_next_attempt(
            session,
            owner="dogfood-executor",
            lease_seconds=45,
        )
        assert claimed is not None
        assert claimed.id == attempt.id
        assert claimed.lease_owner == "dogfood-executor"

        tasks.transition(task.id, TaskState.RUNNING, reason="dogfood worker started")
        attempts.mark_running(attempt.id, harness_version="codex-test")
        attempts.set_result(
            attempt.id,
            {
                "status": "success",
                "profile": "backend",
                "profile_schema_version": 2,
                "prompt_fingerprint": "a" * 64,
                "skills": ["ponytail", "fastapi"],
                "commit": "head123",
                "token_usage": {
                    "input_tokens": 120,
                    "cached_input_tokens": 80,
                    "output_tokens": 30,
                    "total_tokens": 150,
                },
                "validation_plan": {
                    "mode": "configured",
                    "reason": "validation commands configured on task",
                    "commands": [
                        {
                            "name": "core-tests",
                            "type": "test",
                            "command": "pytest -q",
                            "timeout_seconds": 300,
                        }
                    ],
                },
            },
        )
        attempts.set_diff(
            attempt.id,
            base_commit_sha="base123",
            commit_sha="head123",
            diff_stat="1 file changed, 1 insertion(+)",
            diff_patch="diff --git a/smoke.txt b/smoke.txt",
        )

        tasks.transition(task.id, TaskState.AGENT_DONE, reason="worker emitted durable result")
        tasks.transition(task.id, TaskState.VALIDATING, reason="running persisted checks")
        persisted_attempt = attempts.get(attempt.id)
        records = checks.create_checks(
            task_id=task.id,
            attempt_id=attempt.id,
            commands=persisted_attempt.resolved_validation_commands,
        )
        assert len(records) == 1
        checks.mark_running(records[0].id)
        checks.finish(
            records[0].id,
            status=ValidationCheckStatus.PASSED,
            exit_code=0,
            output="1 passed",
        )
        attempts.finish(attempt.id, status=AttemptStatus.SUCCEEDED, exit_code=0)

        decision = approve_task(
            session,
            task.id,
            actor="dogfood-reviewer",
            feedback="Validated smoke result.",
        )
        assert decision.decision == "APPROVED"
        assert tasks.get(task.id).state == TaskState.APPROVED

        def fake_github(method, path, *, token, payload=None, allow_no_content=False):
            assert token == "dogfood-test-token"
            if method == "GET" and "/git/ref/heads/" in path:
                return {"object": {"sha": "head123"}}
            if method == "POST" and path.endswith("/merges"):
                assert payload == {
                    "base": "main",
                    "head": "head123",
                    "commit_message": "Nidavelir task: Dogfood lifecycle smoke",
                }
                return {"sha": "merge456"}
            raise AssertionError((method, path, payload, allow_no_content))

        monkeypatch.setattr("nidavelir_core.execution.merge._github_json", fake_github)
        merge_sha = merge_approved_task(session, task.id)

        persisted_task = tasks.get(task.id)
        persisted_attempt = attempts.get(attempt.id)
        persisted_checks = checks.list_for_attempt(attempt.id)

        assert merge_sha == "merge456"
        assert persisted_task.state == TaskState.CLOSED
        assert persisted_task.merge_commit_sha == "merge456"
        assert persisted_attempt.status == AttemptStatus.SUCCEEDED
        assert persisted_attempt.profile if hasattr(persisted_attempt, "profile") else True
        assert persisted_attempt.total_tokens == 150
        assert persisted_attempt.validation_mode == "configured"
        assert persisted_attempt.diff_patch.startswith("diff --git")
        assert persisted_checks[0].status == ValidationCheckStatus.PASSED
        assert [transition.to_state for transition in persisted_task.transitions] == [
            TaskState.QUEUED,
            TaskState.RUNNING,
            TaskState.AGENT_DONE,
            TaskState.VALIDATING,
            TaskState.APPROVED,
            TaskState.MERGED,
            TaskState.CLOSED,
        ]
