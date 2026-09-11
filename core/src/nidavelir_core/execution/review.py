from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from nidavelir_core.tasks.domain import InvalidTaskTransition, TaskState
from nidavelir_core.tasks.repository import TaskRepository

from .models import AttemptStatus, ReviewDecision, ReviewDecisionRecord
from .repository import AttemptRepository

MAX_RETRY_CONTEXT_CHARS = 4000


class ReviewConflict(RuntimeError):
    pass


class ReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        task_id: UUID,
        attempt_id: UUID,
        decision: ReviewDecision,
        actor: str,
        feedback: str = "",
    ) -> ReviewDecisionRecord:
        record = ReviewDecisionRecord(
            task_id=task_id,
            attempt_id=attempt_id,
            decision=decision,
            actor=actor,
            feedback=feedback,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_for_task(self, task_id: UUID) -> list[ReviewDecisionRecord]:
        statement = (
            select(ReviewDecisionRecord)
            .where(ReviewDecisionRecord.task_id == task_id)
            .order_by(ReviewDecisionRecord.created_at.desc())
        )
        return list(self.session.scalars(statement).all())

    def latest_rejection(self, task_id: UUID) -> ReviewDecisionRecord | None:
        statement = (
            select(ReviewDecisionRecord)
            .where(
                ReviewDecisionRecord.task_id == task_id,
                ReviewDecisionRecord.decision == ReviewDecision.REJECTED,
            )
            .order_by(ReviewDecisionRecord.created_at.desc())
            .limit(1)
        )
        return self.session.scalar(statement)


def _reviewable_attempt(session: Session, task_id: UUID):
    task = TaskRepository(session).get(task_id)
    if task.state != TaskState.VALIDATING:
        raise ReviewConflict(f"task {task_id} cannot be reviewed from {task.state}")

    attempt = AttemptRepository(session).latest_for_task(task_id)
    if attempt is None or attempt.status != AttemptStatus.SUCCEEDED:
        raise ReviewConflict("latest attempt is not a successful validated revision")
    if not attempt.commit_sha:
        raise ReviewConflict("latest attempt has no persisted commit SHA")
    return task, attempt


def approve_task(
    session: Session,
    task_id: UUID,
    *,
    actor: str,
    feedback: str = "",
) -> ReviewDecisionRecord:
    task, attempt = _reviewable_attempt(session, task_id)
    decision = ReviewRepository(session).create(
        task_id=task.id,
        attempt_id=attempt.id,
        decision=ReviewDecision.APPROVED,
        actor=actor,
        feedback=feedback,
    )
    task.retry_context = ""
    task.retry_review_ids = []
    session.commit()
    try:
        TaskRepository(session).transition(
            task.id,
            TaskState.APPROVED,
            reason=f"attempt {attempt.number} approved by {actor}",
        )
    except InvalidTaskTransition as error:
        raise ReviewConflict(str(error)) from error
    return decision


def reject_task(
    session: Session,
    task_id: UUID,
    *,
    actor: str,
    feedback: str,
) -> ReviewDecisionRecord:
    task, attempt = _reviewable_attempt(session, task_id)
    feedback = feedback.strip()
    if not feedback:
        raise ReviewConflict("rejection feedback is required")

    decision = ReviewRepository(session).create(
        task_id=task.id,
        attempt_id=attempt.id,
        decision=ReviewDecision.REJECTED,
        actor=actor,
        feedback=feedback,
    )

    retry_context = (
        f"Review feedback for retry (attempt {attempt.number}, by {actor}):\n{feedback}"
    )
    task.retry_context = retry_context[:MAX_RETRY_CONTEXT_CHARS]
    task.retry_review_ids = [str(decision.id)]
    session.commit()

    try:
        TaskRepository(session).transition(
            task.id,
            TaskState.NEEDS_CHANGES,
            reason=f"attempt {attempt.number} rejected by {actor}: {feedback}",
        )
    except InvalidTaskTransition as error:
        raise ReviewConflict(str(error)) from error
    return decision
