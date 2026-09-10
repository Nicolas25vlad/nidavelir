from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from nidavelir_core.database import get_session
from nidavelir_core.execution.merge import MergeConflict, MergeProviderError, merge_approved_task
from nidavelir_core.execution.review import (
    ReviewConflict,
    ReviewRepository,
    approve_task as approve_review,
    reject_task as reject_review,
)

from .domain import InvalidTaskTransition, TaskState, allowed_transitions
from .repository import TaskNotFound, TaskRepository
from .schemas import (
    MergeRead,
    RejectRequest,
    ReviewDecisionRead,
    ReviewRequest,
    TaskCreate,
    TaskRead,
    TaskTransitionRequest,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])
SessionDep = Annotated[Session, Depends(get_session)]

_PROTECTED_TRANSITIONS = {
    TaskState.AGENT_DONE,
    TaskState.VALIDATING,
    TaskState.APPROVED,
    TaskState.MERGED,
    TaskState.CLOSED,
}


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
    if payload.state in _PROTECTED_TRANSITIONS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"state {payload.state} is controlled by execution, validation, review, "
                "or merge endpoints"
            ),
        )
    try:
        task = repo.transition(task_id, payload.state, reason=payload.reason)
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except InvalidTaskTransition as error:
        raise _invalid_transition(error) from error
    return TaskRead.model_validate(task)


@router.get("/{task_id}/reviews", response_model=list[ReviewDecisionRead])
def list_reviews(task_id: UUID, session: SessionDep) -> list[ReviewDecisionRead]:
    try:
        TaskRepository(session).get(task_id)
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    return [
        ReviewDecisionRead.model_validate(decision)
        for decision in ReviewRepository(session).list_for_task(task_id)
    ]


@router.post("/{task_id}/approve", response_model=ReviewDecisionRead)
def approve_task(task_id: UUID, payload: ReviewRequest, session: SessionDep) -> ReviewDecisionRead:
    try:
        decision = approve_review(
            session,
            task_id,
            actor=payload.actor,
            feedback=payload.feedback,
        )
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except ReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ReviewDecisionRead.model_validate(decision)


@router.post("/{task_id}/reject", response_model=ReviewDecisionRead)
def reject_task(task_id: UUID, payload: RejectRequest, session: SessionDep) -> ReviewDecisionRead:
    try:
        decision = reject_review(
            session,
            task_id,
            actor=payload.actor,
            feedback=payload.feedback,
        )
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except ReviewConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return ReviewDecisionRead.model_validate(decision)


@router.post("/{task_id}/merge", response_model=MergeRead)
def merge_task(task_id: UUID, session: SessionDep) -> MergeRead:
    try:
        merge_sha = merge_approved_task(session, task_id)
        task = TaskRepository(session).get(task_id)
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except MergeConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except MergeProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return MergeRead(task_id=task.id, state=task.state, merge_commit_sha=merge_sha)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_task(task_id: UUID, repo: RepoDep) -> Response:
    try:
        repo.transition(task_id, TaskState.CANCELLED, reason="cancelled through API")
    except TaskNotFound as error:
        raise _not_found(task_id) from error
    except InvalidTaskTransition as error:
        raise _invalid_transition(error) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
