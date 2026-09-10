from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .domain import TaskState


class ValidationCommand(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    type: Literal["test", "lint", "build"]
    command: str = Field(min_length=1, max_length=4000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    repository: str = Field(min_length=1, max_length=500)
    base_branch: str = Field(default="main", min_length=1, max_length=200)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=100)
    validation_commands: list[ValidationCommand] = Field(default_factory=list, max_length=50)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    repository: str | None = Field(default=None, min_length=1, max_length=500)
    base_branch: str | None = Field(default=None, min_length=1, max_length=200)
    acceptance_criteria: list[str] | None = Field(default=None, max_length=100)
    validation_commands: list[ValidationCommand] | None = Field(default=None, max_length=50)


class TaskTransitionRequest(BaseModel):
    state: TaskState
    reason: str | None = Field(default=None, max_length=4000)


class TaskTransitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_state: TaskState
    to_state: TaskState
    reason: str | None
    occurred_at: datetime


class ReviewRequest(BaseModel):
    actor: str = Field(default="operator", min_length=1, max_length=160)
    feedback: str = Field(default="", max_length=8000)


class RejectRequest(BaseModel):
    actor: str = Field(default="operator", min_length=1, max_length=160)
    feedback: str = Field(min_length=1, max_length=8000)


class ReviewDecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    attempt_id: UUID
    decision: Literal["APPROVED", "REJECTED"]
    actor: str
    feedback: str
    created_at: datetime


class MergeRead(BaseModel):
    task_id: UUID
    state: TaskState
    merge_commit_sha: str


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    repository: str
    base_branch: str
    acceptance_criteria: list[str]
    validation_commands: list[ValidationCommand]
    merge_commit_sha: str | None
    state: TaskState
    created_at: datetime
    updated_at: datetime
    transitions: list[TaskTransitionRead]
