import json
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from nidavelir_core.database import Base
from nidavelir_core.execution.merge import MergeConflict, merge_approved_task
from nidavelir_core.execution.models import AttemptStatus
from nidavelir_core.execution.repository import AttemptRepository
from nidavelir_core.execution.review import ReviewRepository, approve_task, reject_task
from nidavelir_core.execution.service import _agent_environment, enqueue_attempt
from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.domain import TaskState
from nidavelir_core.tasks.repository import TaskRepository
from nidavelir_core.tasks.schemas import TaskCreate


@pytest.fixture
def session_factory(monkeypatch) -> Iterator[sessionmaker[Session]]:
    monkeypatch.setenv("NIDAVELIR_GITHUB_TOKEN", "test-token")
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


def _validated_attempt(session: Session):
    tasks = TaskRepository(session)
    task = tasks.create(
        TaskCreate(
            title="Finish the review gate",
            description="Implement the requested change.",
            repository="Nicolas25vlad/nidavelir",
        )
    )
    for state in [
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.AGENT_DONE,
        TaskState.VALIDATING,
    ]:
        task = tasks.transition(task.id, state)

    attempt = AttemptRepository(session).create(
        task_id=task.id,
        number=1,
        container_name="review-a1",
        volume_name="review-a1-volume",
        branch_name="task/review-gate",
    )
    attempts = AttemptRepository(session)
    attempts.set_diff(
        attempt.id,
        base_commit_sha="base123",
        commit_sha="head123",
        diff_stat="1 file changed",
        diff_patch="diff --git a/a b/a",
    )
    attempts.finish(attempt.id, status=AttemptStatus.SUCCEEDED, exit_code=0)
    return tasks, tasks.get(task.id), attempts.get(attempt.id)


def _make_retry_reviewable(session: Session, task_id, number: int):
    tasks = TaskRepository(session)
    for state in [
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.AGENT_DONE,
        TaskState.VALIDATING,
    ]:
        tasks.transition(task_id, state)

    attempt = AttemptRepository(session).create(
        task_id=task_id,
        number=number,
        container_name=f"review-a{number}",
        volume_name=f"review-a{number}-volume",
        branch_name="task/review-gate",
    )
    attempts = AttemptRepository(session)
    attempts.set_diff(
        attempt.id,
        base_commit_sha="base123",
        commit_sha=f"head{number}23",
        diff_stat="1 file changed",
        diff_patch="diff --git a/a b/a",
    )
    attempts.finish(attempt.id, status=AttemptStatus.SUCCEEDED, exit_code=0)
    return attempts.get(attempt.id)


def test_rejection_is_persisted_without_mutating_task_description(session_factory) -> None:
    with session_factory() as session:
        tasks, task, attempt = _validated_attempt(session)
        original_description = task.description

        decision = reject_task(
            session,
            task.id,
            actor="nicolas",
            feedback="Keep the API compatible and add the missing test.",
        )

        persisted = tasks.get(task.id)
        assert decision.attempt_id == attempt.id
        assert decision.decision == "REJECTED"
        assert persisted.state == TaskState.NEEDS_CHANGES
        assert persisted.description == original_description
        assert "Keep the API compatible" in persisted.retry_context
        assert persisted.retry_review_ids == [str(decision.id)]
        assert ReviewRepository(session).latest_rejection(task.id).id == decision.id


def test_retry_attempt_snapshots_review_context_and_worker_payload(session_factory) -> None:
    with session_factory() as session:
        tasks, task, _ = _validated_attempt(session)
        decision = reject_task(
            session,
            task.id,
            actor="reviewer",
            feedback="Only fix the failing API contract.",
        )

        attempt = enqueue_attempt(session, task.id)
        persisted_task = tasks.get(task.id)
        payload = json.loads(
            _agent_environment(get_settings(), attempt, persisted_task)["NIDAVELIR_TASK_JSON"]
        )

        assert attempt.retry_review_ids == [str(decision.id)]
        assert attempt.retry_context == persisted_task.retry_context
        assert payload["description"] == "Implement the requested change."
        assert payload["context"] == attempt.retry_context


def test_new_rejection_supersedes_old_retry_context(session_factory) -> None:
    with session_factory() as session:
        tasks, task, _ = _validated_attempt(session)
        first = reject_task(
            session,
            task.id,
            actor="reviewer-a",
            feedback="First feedback that should be superseded.",
        )
        _make_retry_reviewable(session, task.id, 2)
        second = reject_task(
            session,
            task.id,
            actor="reviewer-b",
            feedback="Second feedback is the only actionable retry context.",
        )

        persisted = tasks.get(task.id)
        assert persisted.description == "Implement the requested change."
        assert persisted.retry_review_ids == [str(second.id)]
        assert str(first.id) not in persisted.retry_review_ids
        assert "Second feedback" in persisted.retry_context
        assert "First feedback" not in persisted.retry_context


def test_approval_is_distinct_from_agent_completion(session_factory) -> None:
    with session_factory() as session:
        tasks, task, attempt = _validated_attempt(session)

        decision = approve_task(session, task.id, actor="orchestrator", feedback="Looks good")

        assert decision.attempt_id == attempt.id
        assert decision.decision == "APPROVED"
        persisted = tasks.get(task.id)
        assert persisted.state == TaskState.APPROVED
        assert persisted.retry_context == ""
        assert persisted.retry_review_ids == []


def test_controlled_merge_verifies_reviewed_head_and_closes_task(
    session_factory,
    monkeypatch,
) -> None:
    with session_factory() as session:
        tasks, task, _ = _validated_attempt(session)
        approve_task(session, task.id, actor="orchestrator")

        def fake_github(method, path, *, token, payload=None, allow_no_content=False):
            assert token == "test-token"
            if method == "GET" and "/git/ref/heads/task%2Freview-gate" in path:
                return {"object": {"sha": "head123"}}
            if method == "POST" and path.endswith("/merges"):
                assert payload["base"] == "main"
                assert payload["head"] == "head123"
                return {"sha": "merge456"}
            raise AssertionError((method, path, payload, allow_no_content))

        monkeypatch.setattr("nidavelir_core.execution.merge._github_json", fake_github)

        merge_sha = merge_approved_task(session, task.id)
        persisted = tasks.get(task.id)

        assert merge_sha == "merge456"
        assert persisted.merge_commit_sha == "merge456"
        assert persisted.state == TaskState.CLOSED
        assert [transition.to_state for transition in persisted.transitions[-2:]] == [
            TaskState.MERGED,
            TaskState.CLOSED,
        ]


def test_controlled_merge_rejects_moved_task_branch(session_factory, monkeypatch) -> None:
    with session_factory() as session:
        tasks, task, _ = _validated_attempt(session)
        approve_task(session, task.id, actor="orchestrator")

        monkeypatch.setattr(
            "nidavelir_core.execution.merge._github_json",
            lambda *args, **kwargs: {"object": {"sha": "someone-moved-the-branch"}},
        )

        with pytest.raises(MergeConflict, match="moved after review"):
            merge_approved_task(session, task.id)

        assert tasks.get(task.id).state == TaskState.APPROVED
        assert tasks.get(task.id).merge_commit_sha is None
