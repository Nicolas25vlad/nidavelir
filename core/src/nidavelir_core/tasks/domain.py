from __future__ import annotations

from enum import StrEnum


class TaskState(StrEnum):
    BACKLOG = "BACKLOG"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    AGENT_DONE = "AGENT_DONE"
    VALIDATING = "VALIDATING"
    NEEDS_CHANGES = "NEEDS_CHANGES"
    APPROVED = "APPROVED"
    MERGED = "MERGED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.BACKLOG: frozenset({TaskState.QUEUED, TaskState.CANCELLED}),
    TaskState.QUEUED: frozenset(
        {TaskState.RUNNING, TaskState.NEEDS_CHANGES, TaskState.CANCELLED}
    ),
    TaskState.RUNNING: frozenset(
        {TaskState.AGENT_DONE, TaskState.NEEDS_CHANGES, TaskState.CANCELLED}
    ),
    TaskState.AGENT_DONE: frozenset(
        {TaskState.VALIDATING, TaskState.NEEDS_CHANGES, TaskState.CANCELLED}
    ),
    TaskState.VALIDATING: frozenset(
        {TaskState.NEEDS_CHANGES, TaskState.APPROVED, TaskState.CANCELLED}
    ),
    TaskState.NEEDS_CHANGES: frozenset({TaskState.QUEUED, TaskState.CANCELLED}),
    TaskState.APPROVED: frozenset({TaskState.MERGED, TaskState.CANCELLED}),
    TaskState.MERGED: frozenset({TaskState.CLOSED}),
    TaskState.CLOSED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


class InvalidTaskTransition(ValueError):
    def __init__(self, current: TaskState, requested: TaskState) -> None:
        super().__init__(f"invalid task transition: {current} -> {requested}")
        self.current = current
        self.requested = requested


def ensure_transition_allowed(current: TaskState, requested: TaskState) -> None:
    if requested not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTaskTransition(current, requested)


def allowed_transitions(state: TaskState) -> tuple[TaskState, ...]:
    return tuple(sorted(_ALLOWED_TRANSITIONS[state], key=str))
