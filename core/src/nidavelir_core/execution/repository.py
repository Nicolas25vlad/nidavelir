from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AttemptRecord, AttemptStatus, utcnow


class AttemptNotFound(LookupError):
    pass


def _optional_non_negative_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _apply_token_usage(attempt: AttemptRecord, usage: dict, *, model: str | None = None) -> None:
    input_tokens = _optional_non_negative_int(usage.get("input_tokens"))
    cached_tokens = _optional_non_negative_int(usage.get("cached_input_tokens"))
    cache_write_tokens = _optional_non_negative_int(usage.get("cache_write_input_tokens"))
    output_tokens = _optional_non_negative_int(usage.get("output_tokens"))
    reasoning_tokens = _optional_non_negative_int(
        usage.get("reasoning_output_tokens", usage.get("reasoning_tokens"))
    )
    total_tokens = _optional_non_negative_int(usage.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    attempt.input_tokens = input_tokens
    attempt.cached_input_tokens = cached_tokens
    attempt.cache_write_input_tokens = cache_write_tokens
    attempt.output_tokens = output_tokens
    attempt.reasoning_tokens = reasoning_tokens
    attempt.total_tokens = total_tokens
    if input_tokens and cached_tokens is not None:
        attempt.cache_hit_ratio = min(cached_tokens / input_tokens, 1.0)
    else:
        attempt.cache_hit_ratio = None
    if model:
        attempt.model = model


def _apply_validation_plan(attempt: AttemptRecord, plan: dict) -> None:
    mode = str(plan.get("mode", "skipped"))
    if mode not in {"configured", "auto", "skipped"}:
        mode = "skipped"
    commands = plan.get("commands")
    attempt.validation_mode = mode
    attempt.validation_reason = str(plan.get("reason", ""))
    attempt.resolved_validation_commands = list(commands) if isinstance(commands, list) else []


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

    def create(
        self,
        *,
        task_id: UUID,
        number: int,
        container_name: str,
        volume_name: str,
        branch_name: str,
        harness: str = "codex",
        retry_context: str = "",
        retry_review_ids: list[str] | None = None,
    ) -> AttemptRecord:
        attempt = AttemptRecord(
            task_id=task_id,
            number=number,
            container_name=container_name,
            volume_name=volume_name,
            branch_name=branch_name,
            harness=harness,
            retry_context=retry_context,
            retry_review_ids=list(retry_review_ids or []),
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
        model = result.get("model")
        attempt.model = str(model) if model else attempt.model
        usage = result.get("token_usage")
        if isinstance(usage, dict):
            _apply_token_usage(attempt, usage, model=attempt.model)
        validation_plan = result.get("validation_plan")
        if isinstance(validation_plan, dict):
            _apply_validation_plan(attempt, validation_plan)
        self.session.commit()

    def set_token_usage(self, attempt_id: UUID, usage: dict, *, model: str | None = None) -> None:
        attempt = self.get(attempt_id)
        _apply_token_usage(attempt, usage, model=model)
        self.session.commit()

    def set_validation_plan(
        self,
        attempt_id: UUID,
        *,
        mode: str,
        reason: str,
        commands: list[dict],
    ) -> None:
        if mode not in {"configured", "auto", "skipped"}:
            raise ValueError(f"unsupported validation mode: {mode}")
        attempt = self.get(attempt_id)
        attempt.validation_mode = mode
        attempt.validation_reason = reason
        attempt.resolved_validation_commands = list(commands)
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
