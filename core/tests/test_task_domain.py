from datetime import UTC, datetime, timedelta

import pytest

from nidavelir_core.domain import (
    InvalidTaskTransition,
    Task,
    TaskPriority,
    TaskState,
)


def build_task() -> Task:
    return Task.create(
        title="Implement durable task model",
        description="Define Nidavelir's task lifecycle.",
        repository="Nicolas25vlad/nidavelir",
        acceptance_criteria=["invalid transitions are rejected", "history is recorded"],
    )


def test_task_starts_in_backlog_with_creation_history() -> None:
    task = build_task()

    assert task.state is TaskState.BACKLOG
    assert task.priority is TaskPriority.NORMAL
    assert len(task.transitions) == 1
    assert task.transitions[0].from_state is None
    assert task.transitions[0].to_state is TaskState.BACKLOG
    assert task.transitions[0].reason == "task created"


def test_happy_path_reaches_closed() -> None:
    task = build_task()
    path = [
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.AGENT_DONE,
        TaskState.VALIDATING,
        TaskState.APPROVED,
        TaskState.MERGED,
        TaskState.CLOSED,
    ]

    for state in path:
        task.transition_to(state, actor="test")

    assert task.state is TaskState.CLOSED
    assert [transition.to_state for transition in task.transitions] == [
        TaskState.BACKLOG,
        *path,
    ]


def test_rejected_task_can_be_requeued() -> None:
    task = build_task()

    for state in (
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.AGENT_DONE,
        TaskState.VALIDATING,
        TaskState.NEEDS_CHANGES,
        TaskState.QUEUED,
    ):
        task.transition_to(state, actor="test")

    assert task.state is TaskState.QUEUED


def test_invalid_transition_is_rejected_without_mutating_task() -> None:
    task = build_task()
    original_updated_at = task.updated_at

    with pytest.raises(InvalidTaskTransition) as exc_info:
        task.transition_to(TaskState.APPROVED, actor="test")

    assert str(exc_info.value) == "invalid task transition: BACKLOG -> APPROVED"
    assert task.state is TaskState.BACKLOG
    assert task.updated_at == original_updated_at
    assert len(task.transitions) == 1


def test_transition_updates_timestamp_and_audit_metadata() -> None:
    created_at = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
    transitioned_at = created_at + timedelta(minutes=5)
    task = Task.create(
        title="Queue task",
        description="",
        repository="owner/repo",
        acceptance_criteria=["queued"],
        now=created_at,
        actor="nicolas",
    )

    transition = task.transition_to(
        TaskState.QUEUED,
        actor="scheduler",
        reason="capacity available",
        now=transitioned_at,
    )

    assert task.updated_at == transitioned_at
    assert transition.actor == "scheduler"
    assert transition.reason == "capacity available"
    assert transition.occurred_at == transitioned_at


def test_cancelled_and_closed_tasks_are_terminal() -> None:
    cancelled = build_task()
    cancelled.transition_to(TaskState.CANCELLED, actor="test")

    assert cancelled.allowed_transitions(cancelled.state) == frozenset()

    closed = build_task()
    for state in (
        TaskState.QUEUED,
        TaskState.RUNNING,
        TaskState.AGENT_DONE,
        TaskState.VALIDATING,
        TaskState.APPROVED,
        TaskState.MERGED,
        TaskState.CLOSED,
    ):
        closed.transition_to(state, actor="test")

    assert closed.allowed_transitions(closed.state) == frozenset()


@pytest.mark.parametrize(
    ("title", "repository", "criteria", "message"),
    [
        ("   ", "owner/repo", ["ok"], "task title cannot be empty"),
        ("Task", "   ", ["ok"], "task repository cannot be empty"),
        ("Task", "owner/repo", ["  "], "task requires at least one acceptance criterion"),
    ],
)
def test_task_creation_validates_required_fields(
    title: str,
    repository: str,
    criteria: list[str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        Task.create(
            title=title,
            description="",
            repository=repository,
            acceptance_criteria=criteria,
        )
