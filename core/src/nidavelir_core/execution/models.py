from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nidavelir_core.database import Base


class AttemptStatus(StrEnum):
    PREPARING = "PREPARING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


def utcnow() -> datetime:
    return datetime.now(UTC)


attempt_status_type = Enum(
    AttemptStatus,
    name="attempt_status",
    native_enum=False,
    length=32,
)


class AttemptRecord(Base):
    __tablename__ = "attempts"
    __table_args__ = (UniqueConstraint("task_id", "number", name="uq_attempt_task_number"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_id: Mapped[UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AttemptStatus] = mapped_column(
        attempt_status_type, default=AttemptStatus.PREPARING, nullable=False
    )
    harness: Mapped[str] = mapped_column(String(80), default="codex", nullable=False)
    harness_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    container_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    volume_name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    branch_name: Mapped[str] = mapped_column(String(240), nullable=False)
    base_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    diff_stat: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs: Mapped[str] = mapped_column(Text, default="", nullable=False)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    task = relationship("TaskRecord")
