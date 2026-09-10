from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .domain import InvalidTaskTransition, TaskState, ensure_transition_allowed
from .models import TaskRecord, TaskTransitionRecord, utcnow
from .schemas import TaskCreate, TaskUpdate


class TaskNotFound(LookupError):
    pass


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, payload: TaskCreate) -> TaskRecord:
        task = TaskRecord(
            title=payload.title,
            description=payload.description,
            repository=payload.repository,
            base_branch=payload.base_branch,
            acceptance_criteria=payload.acceptance_criteria,
            state=TaskState.BACKLOG,
        )
        self.session.add(task)
        self.session.commit()
        return self.get(task.id)

    def list(self) -> list[TaskRecord]:
        statement = (
            select(TaskRecord)
            .options(selectinload(TaskRecord.transitions))
            .order_by(TaskRecord.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def get(self, task_id: UUID) -> TaskRecord:
        statement = (
            select(TaskRecord)
            .where(TaskRecord.id == task_id)
            .options(selectinload(TaskRecord.transitions))
        )
        task = self.session.scalar(statement)
        if task is None:
            raise TaskNotFound(str(task_id))
        return task

    def update(self, task_id: UUID, payload: TaskUpdate) -> TaskRecord:
        task = self.get(task_id)
        if task.state in {TaskState.CLOSED, TaskState.CANCELLED}:
            raise InvalidTaskTransition(task.state, task.state)

        changes = payload.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)
        if changes:
            task.updated_at = utcnow()
            self.session.commit()
        return self.get(task_id)

    def transition(
        self,
        task_id: UUID,
        requested: TaskState,
        *,
        reason: str | None = None,
    ) -> TaskRecord:
        task = self.get(task_id)
        ensure_transition_allowed(task.state, requested)

        occurred_at = utcnow()
        transition = TaskTransitionRecord(
            task_id=task.id,
            from_state=task.state,
            to_state=requested,
            reason=reason,
            occurred_at=occurred_at,
        )
        task.state = requested
        task.updated_at = occurred_at
        self.session.add(transition)
        self.session.commit()
        return self.get(task_id)
