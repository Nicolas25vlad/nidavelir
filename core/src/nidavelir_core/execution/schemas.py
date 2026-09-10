from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import AttemptStatus


class StartTaskRequest(BaseModel):
    harness: str = Field(default="codex", min_length=1, max_length=80)


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    number: int
    status: AttemptStatus
    harness: str
    harness_version: str | None
    container_name: str
    volume_name: str
    branch_name: str
    exit_code: int | None
    failure_reason: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AttemptLogsRead(BaseModel):
    attempt_id: UUID
    status: AttemptStatus
    logs: str
