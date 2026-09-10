from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nidavelir_core.database import get_session
from nidavelir_core.tasks.domain import InvalidTaskTransition, TaskState
from nidavelir_core.tasks.repository import TaskNotFound, TaskRepository

from .models import AttemptStatus
from .repository import AttemptNotFound, AttemptRepository
from .schemas import AttemptLogsRead, AttemptRead, StartTaskRequest
from .service import (
    ExecutionConfigurationError,
    ExecutionConflict,
    cancel_attempt_resources,
    enqueue_attempt,
    execute_attempt,
)

router = APIRouter(tags=["execution"])
SessionDep = Annotated[Session, Depends(get_session)]


def _attempt_not_found(attempt_id: UUID) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"attempt {attempt_id} not found",
    )


@router.post(
    "/tasks/{task_id}/start",
    response_model=AttemptRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_task(
    task_id: UUID,
    payload: StartTaskRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> AttemptRead:
    try:
        attempt = enqueue_attempt(session, task_id, harness=payload.harness)
    except TaskNotFound as error:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found") from error
    except ExecutionConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ExecutionConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    background_tasks.add_task(execute_attempt, attempt.id)
    return AttemptRead.model_validate(attempt)


@router.get("/tasks/{task_id}/attempts", response_model=list[AttemptRead])
def list_task_attempts(task_id: UUID, session: SessionDep) -> list[AttemptRead]:
    tasks = TaskRepository(session)
    try:
        tasks.get(task_id)
    except TaskNotFound as error:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found") from error

    attempts = AttemptRepository(session).list_for_task(task_id)
    return [AttemptRead.model_validate(attempt) for attempt in attempts]


@router.get("/attempts/{attempt_id}", response_model=AttemptRead)
def get_attempt(attempt_id: UUID, session: SessionDep) -> AttemptRead:
    try:
        attempt = AttemptRepository(session).get(attempt_id)
    except AttemptNotFound as error:
        raise _attempt_not_found(attempt_id) from error
    return AttemptRead.model_validate(attempt)


@router.get("/attempts/{attempt_id}/logs", response_model=AttemptLogsRead)
def get_attempt_logs(attempt_id: UUID, session: SessionDep) -> AttemptLogsRead:
    try:
        attempt = AttemptRepository(session).get(attempt_id)
    except AttemptNotFound as error:
        raise _attempt_not_found(attempt_id) from error
    return AttemptLogsRead(attempt_id=attempt.id, status=attempt.status, logs=attempt.logs)


@router.post("/tasks/{task_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(task_id: UUID, session: SessionDep) -> None:
    tasks = TaskRepository(session)
    attempts = AttemptRepository(session)
    try:
        task = tasks.get(task_id)
    except TaskNotFound as error:
        raise HTTPException(status_code=404, detail=f"task {task_id} not found") from error

    if task.state == TaskState.CANCELLED:
        return

    try:
        tasks.transition(task_id, TaskState.CANCELLED, reason="execution cancelled through API")
    except InvalidTaskTransition as error:
        raise HTTPException(status_code=409, detail=str(error)) from error

    latest = attempts.latest_for_task(task_id)
    if latest is not None and latest.status in {AttemptStatus.PREPARING, AttemptStatus.RUNNING}:
        attempts.finish(
            latest.id,
            status=AttemptStatus.CANCELLED,
            exit_code=None,
            failure_reason="cancelled by operator",
        )
        cancel_attempt_resources(latest.id)
