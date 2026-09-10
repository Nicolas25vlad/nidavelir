from __future__ import annotations

import json
import logging
import re
from threading import Event, Timer
from uuid import UUID

import docker
from docker.errors import APIError, DockerException, NotFound
from sqlalchemy.orm import Session

from nidavelir_core.database import SessionLocal
from nidavelir_core.settings import Settings, get_settings
from nidavelir_core.tasks.domain import InvalidTaskTransition, TaskState
from nidavelir_core.tasks.repository import TaskNotFound, TaskRepository

from .models import AttemptRecord, AttemptStatus
from .repository import AttemptNotFound, AttemptRepository
from .validation import ValidationRepository
from .validation_runner import run_validation_checks

logger = logging.getLogger(__name__)

MANAGED_LABEL = "io.nidavelir.managed"
ATTEMPT_LABEL = "io.nidavelir.attempt_id"


class ExecutionConfigurationError(RuntimeError):
    pass


class ExecutionConflict(RuntimeError):
    pass


class WorkerStageError(RuntimeError):
    def __init__(self, stage: str, exit_code: int, logs: str) -> None:
        super().__init__(f"worker stage {stage!r} failed with exit code {exit_code}")
        self.stage = stage
        self.exit_code = exit_code
        self.logs = logs


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug or "task")[:48].rstrip("-")


def task_branch_name(task_id: UUID, title: str) -> str:
    return f"task/{str(task_id)[:8]}-{_slugify(title)}"


def enqueue_attempt(
    session: Session,
    task_id: UUID,
    *,
    harness: str = "codex",
) -> AttemptRecord:
    settings = get_settings()
    if harness != "codex":
        raise ExecutionConfigurationError(
            f"harness {harness!r} is not installed yet; the MVP currently provides 'codex'"
        )
    if settings.github_token is None:
        raise ExecutionConfigurationError(
            "NIDAVELIR_GITHUB_TOKEN is required to push task branches"
        )
    if settings.openai_api_key is None:
        raise ExecutionConfigurationError(
            "NIDAVELIR_OPENAI_API_KEY is required for the Codex harness"
        )

    tasks = TaskRepository(session)
    attempts = AttemptRepository(session)
    task = tasks.get(task_id)

    latest = attempts.latest_for_task(task_id)
    if latest is not None and latest.status in {
        AttemptStatus.PREPARING,
        AttemptStatus.RUNNING,
    }:
        raise ExecutionConflict(f"task {task_id} already has an active attempt")

    if attempts.count_active() >= settings.max_parallel_workers:
        raise ExecutionConflict(
            f"worker capacity reached ({settings.max_parallel_workers} active)"
        )

    if task.state in {TaskState.BACKLOG, TaskState.NEEDS_CHANGES}:
        task = tasks.transition(task_id, TaskState.QUEUED, reason="execution requested")
    elif task.state != TaskState.QUEUED:
        raise ExecutionConflict(f"task {task_id} cannot start from {task.state}")

    number = attempts.next_number(task_id)
    short_id = str(task.id)[:8]
    runtime_name = f"nidavelir-{short_id}-a{number}"
    return attempts.create(
        task_id=task.id,
        number=number,
        container_name=runtime_name,
        volume_name=f"nidavelir-task-{short_id}-a{number}",
        branch_name=task_branch_name(task.id, task.title),
        harness=harness,
    )


def _labels(attempt_id: UUID) -> dict[str, str]:
    return {MANAGED_LABEL: "true", ATTEMPT_LABEL: str(attempt_id)}


def _secret_value(value) -> str:
    return value.get_secret_value() if value is not None else ""


def _append_stage_logs(
    attempts: AttemptRepository,
    attempt_id: UUID,
    stage: str,
    logs: str,
) -> None:
    if logs:
        attempts.append_logs(attempt_id, f"\n[{stage}]\n{logs}")


def _runtime_limits(settings: Settings) -> dict[str, object]:
    return {
        "mem_limit": settings.worker_memory,
        "nano_cpus": int(settings.worker_cpus * 1_000_000_000),
    }


def _run_helper(
    client,
    *,
    settings: Settings,
    attempt: AttemptRecord,
    suffix: str,
    command: str,
    environment: dict[str, str],
    user: str | None = None,
) -> tuple[int, str]:
    container = client.containers.run(
        settings.worker_image,
        command=[command],
        name=f"{attempt.container_name}-{suffix}",
        detach=True,
        labels=_labels(attempt.id),
        environment=environment,
        user=user,
        volumes={attempt.volume_name: {"bind": "/workspace/repo", "mode": "rw"}},
        **_runtime_limits(settings),
    )
    try:
        result = container.wait()
        logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
        return int(result.get("StatusCode", 1)), logs
    finally:
        try:
            container.remove(force=True)
        except (APIError, NotFound):
            logger.debug("helper container already removed", exc_info=True)


def _stream_agent(
    client,
    *,
    settings: Settings,
    attempt: AttemptRecord,
    environment: dict[str, str],
    attempts: AttemptRepository,
) -> tuple[int, bool]:
    container = client.containers.run(
        settings.worker_image,
        command=["/usr/local/bin/nidavelir-run-task"],
        name=attempt.container_name,
        detach=True,
        labels=_labels(attempt.id),
        environment=environment,
        volumes={attempt.volume_name: {"bind": "/workspace/repo", "mode": "rw"}},
        **_runtime_limits(settings),
    )
    attempts.mark_running(attempt.id)

    timed_out = Event()

    def kill_for_timeout() -> None:
        timed_out.set()
        try:
            container.kill()
        except (APIError, NotFound):
            logger.debug("worker finished before timeout kill", exc_info=True)

    timer = Timer(settings.worker_timeout_seconds, kill_for_timeout)
    timer.daemon = True
    timer.start()
    buffer = ""

    try:
        for chunk in container.logs(stream=True, follow=True, stdout=True, stderr=True):
            buffer += chunk.decode("utf-8", errors="replace")
            if len(buffer) >= 1024:
                attempts.append_logs(attempt.id, buffer)
                buffer = ""
        if buffer:
            attempts.append_logs(attempt.id, buffer)
        result = container.wait()
        return int(result.get("StatusCode", 1)), timed_out.is_set()
    finally:
        timer.cancel()
        try:
            container.remove(force=True)
        except (APIError, NotFound):
            logger.debug("worker container already removed", exc_info=True)


def _task_payload(task) -> str:
    return json.dumps(
        {
            "id": str(task.id),
            "title": task.title,
            "description": task.description,
            "repository": task.repository,
            "base_branch": task.base_branch,
            "acceptance_criteria": task.acceptance_criteria,
            "validation_commands": task.validation_commands,
            "context": "",
        }
    )


def _capture_agent_metadata(
    attempts: AttemptRepository,
    attempt_id: UUID,
) -> dict | None:
    logs = attempts.get(attempt_id).logs

    version_match = re.search(
        r"^NIDAVELIR_HARNESS_VERSION=(.+)$",
        logs,
        re.MULTILINE,
    )
    if version_match:
        attempts.set_harness_version(
            attempt_id,
            version_match.group(1).strip(),
        )

    result_matches = re.findall(
        r"^NIDAVELIR_RESULT=(\{.*\})$",
        logs,
        re.MULTILINE,
    )
    if not result_matches:
        return None

    try:
        result = json.loads(result_matches[-1])
    except json.JSONDecodeError:
        logger.warning("attempt %s emitted an invalid result payload", attempt_id)
        return None

    if isinstance(result, dict):
        attempts.set_result(attempt_id, result)
        return result
    return None


def _capture_git_diff(
    client,
    *,
    settings: Settings,
    attempt: AttemptRecord,
    attempts: AttemptRepository,
    environment: dict[str, str],
) -> None:
    diff_code, diff_output = _run_helper(
        client,
        settings=settings,
        attempt=attempt,
        suffix="diff",
        command="/usr/local/bin/nidavelir-capture-diff",
        environment=environment,
    )
    if diff_code != 0:
        raise WorkerStageError("diff", diff_code, diff_output)

    try:
        payload = json.loads(diff_output)
        base_commit = str(payload["base_commit"])
        commit = str(payload["commit"])
        stat = str(payload.get("stat", ""))
        patch = str(payload.get("patch", ""))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise WorkerStageError("diff", 65, "diff helper emitted invalid JSON") from error

    attempts.set_diff(
        attempt.id,
        base_commit_sha=base_commit,
        commit_sha=commit,
        diff_stat=stat,
        diff_patch=patch,
    )


def _transition_failure(tasks: TaskRepository, task_id: UUID, reason: str) -> None:
    try:
        task = tasks.get(task_id)
        if task.state in {TaskState.RUNNING, TaskState.AGENT_DONE, TaskState.VALIDATING}:
            tasks.transition(task_id, TaskState.NEEDS_CHANGES, reason=reason)
    except (TaskNotFound, InvalidTaskTransition):
        logger.warning("could not move failed task to NEEDS_CHANGES", exc_info=True)


def execute_attempt(attempt_id: UUID) -> None:
    settings = get_settings()
    client = None
    volume = None

    with SessionLocal() as session:
        attempts = AttemptRepository(session)
        tasks = TaskRepository(session)
        try:
            attempt = attempts.get(attempt_id)
            task = tasks.get(attempt.task_id)
            if task.state == TaskState.CANCELLED:
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.CANCELLED,
                    exit_code=None,
                )
                return

            tasks.transition(
                task.id,
                TaskState.RUNNING,
                reason=f"attempt {attempt.number} started",
            )
            client = docker.from_env()
            client.ping()
            volume = client.volumes.create(
                name=attempt.volume_name,
                labels=_labels(attempt.id),
            )

            common_environment = {
                "NIDAVELIR_REPOSITORY": task.repository,
                "NIDAVELIR_BASE_BRANCH": task.base_branch,
                "NIDAVELIR_TASK_BRANCH": attempt.branch_name,
            }
            prepare_environment = {
                **common_environment,
                "NIDAVELIR_GITHUB_TOKEN": _secret_value(settings.github_token),
            }
            prepare_code, prepare_logs = _run_helper(
                client,
                settings=settings,
                attempt=attempt,
                suffix="prepare",
                command="/usr/local/bin/nidavelir-prepare",
                environment=prepare_environment,
                user="0:0",
            )
            _append_stage_logs(attempts, attempt.id, "prepare", prepare_logs)
            if prepare_code != 0:
                raise WorkerStageError("prepare", prepare_code, prepare_logs)

            if tasks.get(task.id).state == TaskState.CANCELLED:
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.CANCELLED,
                    exit_code=None,
                )
                return

            agent_environment = {
                "NIDAVELIR_TASK_JSON": _task_payload(task),
                "NIDAVELIR_TASK_BRANCH": attempt.branch_name,
                "NIDAVELIR_HARNESS": attempt.harness,
                "OPENAI_API_KEY": _secret_value(settings.openai_api_key),
            }
            exit_code, timed_out = _stream_agent(
                client,
                settings=settings,
                attempt=attempt,
                environment=agent_environment,
                attempts=attempts,
            )
            result = _capture_agent_metadata(attempts, attempt.id)

            current_task = tasks.get(task.id)
            if current_task.state == TaskState.CANCELLED:
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.CANCELLED,
                    exit_code=exit_code,
                )
                return
            if timed_out:
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.TIMED_OUT,
                    exit_code=exit_code,
                    failure_reason=(
                        f"worker exceeded {settings.worker_timeout_seconds}s timeout"
                    ),
                )
                _transition_failure(tasks, task.id, "worker timed out")
                return
            if exit_code != 0:
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.FAILED,
                    exit_code=exit_code,
                    failure_reason="coding harness exited with a non-zero status",
                )
                _transition_failure(tasks, task.id, "coding harness failed")
                return
            if result is None or result.get("status") != "success":
                raise WorkerStageError(
                    "result",
                    65,
                    "worker did not emit a valid successful NIDAVELIR_RESULT payload",
                )

            _capture_git_diff(
                client,
                settings=settings,
                attempt=attempt,
                attempts=attempts,
                environment=common_environment,
            )

            push_environment = {
                **common_environment,
                "NIDAVELIR_GITHUB_TOKEN": _secret_value(settings.github_token),
            }
            push_code, push_logs = _run_helper(
                client,
                settings=settings,
                attempt=attempt,
                suffix="push",
                command="/usr/local/bin/nidavelir-push",
                environment=push_environment,
            )
            _append_stage_logs(attempts, attempt.id, "push", push_logs)
            if push_code != 0:
                raise WorkerStageError("push", push_code, push_logs)

            tasks.transition(
                task.id,
                TaskState.AGENT_DONE,
                reason=(
                    f"attempt {attempt.number} completed and pushed {attempt.branch_name}"
                ),
            )

            validation_passed = run_validation_checks(
                client,
                settings=settings,
                attempt=attempt,
                task=tasks.get(task.id),
                tasks=tasks,
                checks=ValidationRepository(session),
            )
            if not validation_passed:
                attempts.finish(
                    attempt.id,
                    status=AttemptStatus.FAILED,
                    exit_code=1,
                    failure_reason="one or more validation checks failed",
                )
                return

            attempts.finish(
                attempt.id,
                status=AttemptStatus.SUCCEEDED,
                exit_code=0,
            )
        except AttemptNotFound:
            logger.exception("attempt disappeared before execution")
        except Exception as error:
            logger.exception("attempt %s failed", attempt_id)
            try:
                attempt = attempts.get(attempt_id)
                if attempt.status != AttemptStatus.CANCELLED:
                    exit_code = (
                        error.exit_code if isinstance(error, WorkerStageError) else None
                    )
                    attempts.append_logs(attempt.id, f"\n[error]\n{error}\n")
                    attempts.finish(
                        attempt.id,
                        status=AttemptStatus.FAILED,
                        exit_code=exit_code,
                        failure_reason=str(error),
                    )
                    _transition_failure(tasks, attempt.task_id, str(error))
            except AttemptNotFound:
                logger.exception("could not persist execution failure")
        finally:
            if client is not None:
                _cleanup_attempt_resources(
                    client,
                    attempt_id,
                    volume_name=getattr(volume, "name", None),
                )
                try:
                    client.close()
                except DockerException:
                    logger.debug("failed to close Docker client", exc_info=True)


def cancel_attempt_resources(attempt_id: UUID) -> None:
    client = None
    try:
        client = docker.from_env()
        containers = client.containers.list(
            all=True,
            filters={"label": f"{ATTEMPT_LABEL}={attempt_id}"},
        )
        for container in containers:
            try:
                container.kill()
            except (APIError, NotFound):
                pass
            try:
                container.remove(force=True)
            except (APIError, NotFound):
                pass
    except DockerException:
        logger.warning(
            "could not cancel Docker resources for attempt %s",
            attempt_id,
            exc_info=True,
        )
    finally:
        if client is not None:
            try:
                client.close()
            except DockerException:
                logger.debug("failed to close Docker client", exc_info=True)


def _cleanup_attempt_resources(
    client,
    attempt_id: UUID,
    *,
    volume_name: str | None,
) -> None:
    containers = client.containers.list(
        all=True,
        filters={"label": f"{ATTEMPT_LABEL}={attempt_id}"},
    )
    for container in containers:
        try:
            container.remove(force=True)
        except (APIError, NotFound):
            logger.debug("container cleanup raced with removal", exc_info=True)

    if volume_name:
        try:
            client.volumes.get(volume_name).remove(force=True)
        except (APIError, NotFound):
            logger.debug("volume already removed or still in use", exc_info=True)


def cleanup_orphaned_resources() -> None:
    client = None
    try:
        client = docker.from_env()
        containers = client.containers.list(
            all=True,
            filters={"label": f"{MANAGED_LABEL}=true"},
        )
        for container in containers:
            if container.status != "running":
                try:
                    container.remove(force=True)
                except (APIError, NotFound):
                    pass

        for volume in client.volumes.list(
            filters={"label": f"{MANAGED_LABEL}=true"}
        ):
            try:
                volume.remove()
            except APIError:
                pass
    except DockerException:
        logger.debug("Docker is unavailable; skipping orphan cleanup", exc_info=True)
    finally:
        if client is not None:
            try:
                client.close()
            except DockerException:
                logger.debug("failed to close Docker client", exc_info=True)
