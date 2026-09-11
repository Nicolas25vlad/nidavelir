from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import AttemptStatus, ValidationCheckStatus


class StartTaskRequest(BaseModel):
    harness: str = Field(default="codex", min_length=1, max_length=80)


class HarnessRead(BaseModel):
    id: str
    display_name: str
    configured: bool
    credential_env: str
    capabilities: list[str]


class AttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    number: int
    status: AttemptStatus
    harness: str
    harness_version: str | None
    model: str | None
    container_name: str
    volume_name: str
    branch_name: str
    retry_context: str
    retry_review_ids: list[str]
    base_commit_sha: str | None
    commit_sha: str | None
    result: dict | None
    input_tokens: int | None
    cached_input_tokens: int | None
    cache_write_input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None
    cache_hit_ratio: float | None
    exit_code: int | None
    failure_reason: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class AttemptLogsRead(BaseModel):
    attempt_id: UUID
    status: AttemptStatus
    logs: str


class AttemptDiffRead(BaseModel):
    attempt_id: UUID
    branch_name: str
    base_commit_sha: str | None
    commit_sha: str | None
    stat: str
    patch: str


class ValidationCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    attempt_id: UUID
    position: int
    name: str
    check_type: str
    command: str
    status: ValidationCheckStatus
    exit_code: int | None
    output: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
