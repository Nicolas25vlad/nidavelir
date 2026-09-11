from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ValidationCheckRecord, ValidationCheckStatus, utcnow


class ValidationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_checks(
        self,
        *,
        task_id: UUID,
        attempt_id: UUID,
        commands: list[dict],
    ) -> list[ValidationCheckRecord]:
        checks = [
            ValidationCheckRecord(
                task_id=task_id,
                attempt_id=attempt_id,
                position=position,
                name=command["name"],
                check_type=command["type"],
                command=command["command"],
                status=ValidationCheckStatus.PENDING,
            )
            for position, command in enumerate(commands)
        ]
        self.session.add_all(checks)
        self.session.commit()
        return self.list_for_attempt(attempt_id)

    def create_skipped(
        self,
        *,
        task_id: UUID,
        attempt_id: UUID,
        reason: str,
    ) -> ValidationCheckRecord:
        check = ValidationCheckRecord(
            task_id=task_id,
            attempt_id=attempt_id,
            position=0,
            name="UNVALIDATED",
            check_type="validation",
            command="",
            status=ValidationCheckStatus.SKIPPED,
            output=reason,
            started_at=utcnow(),
            finished_at=utcnow(),
        )
        self.session.add(check)
        self.session.commit()
        self.session.refresh(check)
        return check

    def list_for_attempt(self, attempt_id: UUID) -> list[ValidationCheckRecord]:
        statement = (
            select(ValidationCheckRecord)
            .where(ValidationCheckRecord.attempt_id == attempt_id)
            .order_by(ValidationCheckRecord.position)
        )
        return list(self.session.scalars(statement).all())

    def list_for_task(self, task_id: UUID) -> list[ValidationCheckRecord]:
        statement = (
            select(ValidationCheckRecord)
            .where(ValidationCheckRecord.task_id == task_id)
            .order_by(ValidationCheckRecord.created_at.desc(), ValidationCheckRecord.position)
        )
        return list(self.session.scalars(statement).all())

    def mark_running(self, check_id: UUID) -> None:
        check = self.session.get(ValidationCheckRecord, check_id)
        if check is None:
            return
        check.status = ValidationCheckStatus.RUNNING
        check.started_at = utcnow()
        self.session.commit()

    def finish(
        self,
        check_id: UUID,
        *,
        status: ValidationCheckStatus,
        exit_code: int | None,
        output: str,
    ) -> None:
        check = self.session.get(ValidationCheckRecord, check_id)
        if check is None:
            return
        check.status = status
        check.exit_code = exit_code
        check.output = output
        check.finished_at = utcnow()
        self.session.commit()
