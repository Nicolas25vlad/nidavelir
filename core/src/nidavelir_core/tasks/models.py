from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nidavelir_core.database import Base

from .domain import TaskState


def utcnow() -> datetime:
    return datetime.now(UTC)


task_state_type = Enum(TaskState, name="task_state", native_enum=False, length=32)


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    repository: Mapped[str] = mapped_column(String(500))
    base_branch: Mapped[str] = mapped_column(String(200), default="main")
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, default=list)
    validation_commands: Mapped[list[dict]] = mapped_column(JSON, default=list, nullable=False)
    supervisor_client: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    supervisor_session_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    project_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    retry_context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    retry_review_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    merge_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[TaskState] = mapped_column(
        task_state_type, default=TaskState.BACKLOG, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    transitions: Mapped[list[TaskTransitionRecord]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskTransitionRecord.id",
    )


class TaskTransitionRecord(Base):
    __tablename__ = "task_transitions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    from_state: Mapped[TaskState] = mapped_column(task_state_type, nullable=False)
    to_state: Mapped[TaskState] = mapped_column(task_state_type, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    task: Mapped[TaskRecord] = relationship(back_populates="transitions")
