from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar, Mapping
from uuid import UUID, uuid4


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


class TaskPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class InvalidTaskTransition(ValueError):
    def __init__(self, current: TaskState, target: TaskState) -> None:
        super().__init__(f"invalid task transition: {current.value} -> {target.value}")
        self.current = current
        self.target = target


@dataclass(frozen=True, slots=True)
class TaskTransition:
    from_state: TaskState | None
    to_state: TaskState
    occurred_at: datetime
    actor: str
    reason: str | None = None


@dataclass(slots=True)
class Task:
    id: UUID
    title: str
    description: str
    repository: str
    base_branch: str
    acceptance_criteria: tuple[str, ...]
    priority: TaskPriority
    state: TaskState
    created_at: datetime
    updated_at: datetime
    transitions: list[TaskTransition] = field(default_factory=list)

    _TRANSITIONS: ClassVar[Mapping[TaskState, frozenset[TaskState]]] = MappingProxyType(
        {
            TaskState.BACKLOG: frozenset({TaskState.QUEUED, TaskState.CANCELLED}),
            TaskState.QUEUED: frozenset({TaskState.RUNNING, TaskState.CANCELLED}),
            TaskState.RUNNING: frozenset({TaskState.AGENT_DONE, TaskState.CANCELLED}),
            TaskState.AGENT_DONE: frozenset({TaskState.VALIDATING, TaskState.CANCELLED}),
            TaskState.VALIDATING: frozenset(
                {TaskState.NEEDS_CHANGES, TaskState.APPROVED, TaskState.CANCELLED}
            ),
            TaskState.NEEDS_CHANGES: frozenset({TaskState.QUEUED, TaskState.CANCELLED}),
            TaskState.APPROVED: frozenset({TaskState.MERGED, TaskState.CANCELLED}),
            TaskState.MERGED: frozenset({TaskState.CLOSED}),
            TaskState.CLOSED: frozenset(),
            TaskState.CANCELLED: frozenset(),
        }
    )

    @classmethod
    def create(
        cls,
        *,
        title: str,
        description: str,
        repository: str,
        acceptance_criteria: tuple[str, ...] | list[str],
        base_branch: str = "main",
        priority: TaskPriority = TaskPriority.NORMAL,
        actor: str = "system",
        now: datetime | None = None,
        task_id: UUID | None = None,
    ) -> Task:
        created_at = now or datetime.now(UTC)
        normalized_title = title.strip()
        normalized_repository = repository.strip()
        normalized_branch = base_branch.strip()
        criteria = tuple(item.strip() for item in acceptance_criteria if item.strip())

        if not normalized_title:
            raise ValueError("task title cannot be empty")
        if not normalized_repository:
            raise ValueError("task repository cannot be empty")
        if not normalized_branch:
            raise ValueError("task base branch cannot be empty")
        if not criteria:
            raise ValueError("task requires at least one acceptance criterion")

        transition = TaskTransition(
            from_state=None,
            to_state=TaskState.BACKLOG,
            occurred_at=created_at,
            actor=actor,
            reason="task created",
        )

        return cls(
            id=task_id or uuid4(),
            title=normalized_title,
            description=description.strip(),
            repository=normalized_repository,
            base_branch=normalized_branch,
            acceptance_criteria=criteria,
            priority=priority,
            state=TaskState.BACKLOG,
            created_at=created_at,
            updated_at=created_at,
            transitions=[transition],
        )

    @classmethod
    def allowed_transitions(cls, state: TaskState) -> frozenset[TaskState]:
        return cls._TRANSITIONS[state]

    def can_transition_to(self, target: TaskState) -> bool:
        return target in self.allowed_transitions(self.state)

    def transition_to(
        self,
        target: TaskState,
        *,
        actor: str,
        reason: str | None = None,
        now: datetime | None = None,
    ) -> TaskTransition:
        if not self.can_transition_to(target):
            raise InvalidTaskTransition(self.state, target)

        occurred_at = now or datetime.now(UTC)
        transition = TaskTransition(
            from_state=self.state,
            to_state=target,
            occurred_at=occurred_at,
            actor=actor,
            reason=reason,
        )
        self.state = target
        self.updated_at = occurred_at
        self.transitions.append(transition)
        return transition
