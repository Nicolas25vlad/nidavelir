from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from nidavelir_core.database import get_session

from .domain import InvalidTaskTransition, TaskState, allowed_transitions
from .repository import TaskNotFound, TaskRepository
from .schemas import TaskCreate, TaskRead, TaskTransitionRequest, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDep = Annotated[Session, Depends(get_session)]


def repository(session: SessionDep) -> TaskRepository:
    return TaskRepository(session)


RepoDep = Annotated[TaskRepository, Depends(repository)]


def _not_found(task_id: UUID) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"task {task_id} not found")


def _invalid_transition(error: InvalidTaskTransition) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "message": str(error),
            "current_state": error.current,
            "requested_state": error.requested,
            "allowed_states": allowed_transitions(error.current),
        },
    )


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, repo: RepoDep) -> TaskRead:
    return TaskRead.model_validate(repo.create(payload))


@router.get("", response_model=list[TaskRead])
def list_tasks(repo: RepoDep) -> list[TaskRead]:
    return [TaskRead.model_validate(task) for task in repo.list()]


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: UUID, repo: RepoDep) -> TaskRead:
    try:
        task = repo.get(task_id)
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    return TaskRead.model_validate(task)


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, payload: TaskUpdate, repo: RepoDep) -> TaskRead:
    try:
        task = repo.update(task_id, payload)
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    return TaskRead.model_validate(task)


@router.post("/{task_id}/transitions", response_model=TaskRead)
def transition_task(
    task_id: UUID,
    payload: TaskTransitionRequest,
    repo: RepoDep,
) -> TaskRead:
    try:
        task = repo.transition(task_id, payload.state, reason=payload.reason)
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except InvalidTaskTransition as error:
        raise _invalid_transition(error) from error
    return TaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(task_id: UUID, repo: RepoDep) -> Response:
    try:
        repo.transition(task_id, TaskState.CANCELLED, reason="cancelled through API")
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except InvalidTaskTransition as error:
        raise _invalid_transition(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
