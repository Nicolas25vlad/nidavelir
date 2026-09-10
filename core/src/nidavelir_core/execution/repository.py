from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AttemptRecord, AttemptStatus, utcnow


class AttemptNotFound(LookupError):
    pass


class AttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def next_number(self, task_id: UUID) -> int:
        number = self.session.scalar(
            select(func.coalesce(func.max(AttemptRecord.number), 0)).where(
                AttemptRecord.task_id == task_id
            )
        )
        return int(number or 0) + 1

    def count_active(self) -> int:
        active = self.session.scalar(
            select(func.count())
            .select_from(AttemptRecord)
            .where(
                AttemptRecord.status.in_(
                    [AttemptStatus.PREPARING, AttemptStatus.RUNNING]
                )
            )
        )
        return int(active or 0)

    def list_active(self) -> list[AttemptRecord]:
        statement = (
            select(AttemptRecord)
            .where(
                AttemptRecord.status.in_(
                    [AttemptStatus.PREPARING, AttemptStatus.RUNNING]
                )
            )
            .order_by(AttemptRecord.created_at.asc())
        )
        return list(self.session.scalars(statement).all())

    def create(
        self,
        *,
        task_id: UUID,
        number: int,
        container_name: str,
        volume_name: str,
        branch_name: str,
        harness: str = "codex",
    ) -> AttemptRecord:
        attempt = AttemptRecord(
            task_id=task_id,
            number=number,
            container_name=container_name,
            volume_name=volume_name,
            branch_name=branch_name,
            harness=harness,
            status=AttemptStatus.PREPARING,
        )
        self.session.add(attempt)
        self.session.commit()
        self.session.refresh(attempt)
        return attempt

    def get(self, attempt_id: UUID) -> AttemptRecord:
        attempt = self.session.get(AttemptRecord, attempt_id)
        if attempt is None:
            raise AttemptNotFound(str(attempt_id))
        return attempt

    def list_for_task(self, task_id: UUID) -> list[AttemptRecord]:
        statement = (
            select(AttemptRecord)
            .where(AttemptRecord.task_id == task_id)
            .order_by(AttemptRecord.number.desc())
        )
        return list(self.session.scalars(statement).all())

    def latest_for_task(self, task_id: UUID) -> AttemptRecord | None:
        statement = (
            select(AttemptRecord)
            .where(AttemptRecord.task_id == task_id)
            .order_by(AttemptRecord.number.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

    def mark_running(self, attempt_id: UUID, *, harness_version: str | None = None) -> None:
        attempt = self.get(attempt_id)
        attempt.status = AttemptStatus.RUNNING
        attempt.started_at = utcnow()
        attempt.harness_version = harness_version
        self.session.commit()

    def set_harness_version(self, attempt_id: UUID, harness_version: str) -> None:
        attempt = self.get(attempt_id)
        attempt.harness_version = harness_version
        self.session.commit()

    def set_result(self, attempt_id: UUID, result: dict) -> None:
        attempt = self.get(attempt_id)
        attempt.result = result
        commit = result.get("commit")
        attempt.commit_sha = str(commit) if commit else None
        self.session.commit()

    def set_diff(
        self,
        attempt_id: UUID,
        *,
        base_commit_sha: str,
        commit_sha: str,
        diff_stat: str,
        diff_patch: str,
    ) -> None:
        attempt = self.get(attempt_id)
        attempt.base_commit_sha = base_commit_sha
        attempt.commit_sha = commit_sha
        attempt.diff_stat = diff_stat
        attempt.diff_patch = diff_patch
        self.session.commit()

    def append_logs(self, attempt_id: UUID, text: str) -> None:
        if not text:
            return
        attempt = self.get(attempt_id)
        attempt.logs = f"{attempt.logs}{text}"
        self.session.commit()

    def finish(
        self,
        attempt_id: UUID,
        *,
        status: AttemptStatus,
        exit_code: int | None,
        failure_reason: str | None = None,
    ) -> None:
        attempt = self.get(attempt_id)
        attempt.status = status
        attempt.exit_code = exit_code
        attempt.failure_reason = failure_reason
        attempt.finished_at = utcnow()
        self.session.commit()
