from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .domain import TaskState


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    repository: str = Field(min_length=1, max_length=500)
    base_branch: str = Field(default="main", min_length=1, max_length=200)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=100)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    repository: str | None = Field(default=None, min_length=1, max_length=500)
    base_branch: str | None = Field(default=None, min_length=1, max_length=200)
    acceptance_criteria: list[str] | None = Field(default=None, max_length=100)


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


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    repository: str
    base_branch: str
    acceptance_criteria: list[str]
    state: TaskState
    created_at: datetime
    updated_at: datetime
    transitions: list[TaskTransitionRead]
