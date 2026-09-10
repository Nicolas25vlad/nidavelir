from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import UUID

from sqlalchemy.orm import Session

from nidavelir_core.settings import get_settings
from nidavelir_core.tasks.domain import InvalidTaskTransition, TaskState
from nidavelir_core.tasks.repository import TaskRepository

from .repository import AttemptRepository


class MergeConflict(RuntimeError):
    pass


class MergeProviderError(RuntimeError):
    pass


def _repository_parts(repository: str) -> tuple[str, str]:
    parts = repository.strip().strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise MergeConflict("repository must use owner/name format")
    return parts[0], parts[1]


def _github_json(
    method: str,
    path: str,
    *,
    token: str,
    payload: dict | None = None,
    allow_no_content: bool = False,
) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"https://api.github.com{path}",
        data=body,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "nidavelir-core",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            raw = response.read()
            if not raw and allow_no_content:
                return {}
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise MergeProviderError(f"GitHub returned HTTP {error.code}: {detail[:1000]}") from error
    except URLError as error:
        raise MergeProviderError(f"GitHub is unavailable: {error.reason}") from error


def merge_approved_task(session: Session, task_id: UUID) -> str:
    settings = get_settings()
    if settings.github_token is None:
        raise MergeConflict("NIDAVELIR_GITHUB_TOKEN is required for controlled merge")
    token = settings.github_token.get_secret_value()

    tasks = TaskRepository(session)
    attempts = AttemptRepository(session)
    task = tasks.get(task_id)
    if task.state != TaskState.APPROVED:
        raise MergeConflict(f"task {task_id} cannot merge from {task.state}")

    attempt = attempts.latest_for_task(task_id)
    if attempt is None or not attempt.commit_sha:
        raise MergeConflict("approved task has no persisted attempt commit SHA")

    owner, repo = _repository_parts(task.repository)
    encoded_branch = quote(attempt.branch_name, safe="")
    branch = _github_json(
        "GET",
        f"/repos/{owner}/{repo}/git/ref/heads/{encoded_branch}",
        token=token,
    )
    remote_sha = str(branch.get("object", {}).get("sha", ""))
    if remote_sha != attempt.commit_sha:
        raise MergeConflict(
            "task branch moved after review; expected "
            f"{attempt.commit_sha}, found {remote_sha or 'unknown'}"
        )

    result = _github_json(
        "POST",
        f"/repos/{owner}/{repo}/merges",
        token=token,
        payload={
            "base": task.base_branch,
            "head": attempt.commit_sha,
            "commit_message": f"Nidavelir task {task.id}: {task.title}",
        },
        allow_no_content=True,
    )

    merge_sha = str(result.get("sha", ""))
    if not merge_sha:
        base_branch = quote(task.base_branch, safe="")
        base_ref = _github_json(
            "GET",
            f"/repos/{owner}/{repo}/git/ref/heads/{base_branch}",
            token=token,
        )
        merge_sha = str(base_ref.get("object", {}).get("sha", ""))
    if not merge_sha:
        raise MergeProviderError("GitHub merge completed without a resolvable resulting SHA")

    tasks.set_merge_commit(task.id, merge_sha)
    try:
        tasks.transition(
            task.id,
            TaskState.MERGED,
            reason=f"approved attempt {attempt.number} merged as {merge_sha}",
        )
        tasks.transition(
            task.id,
            TaskState.CLOSED,
            reason=f"merge {merge_sha} completed",
        )
    except InvalidTaskTransition as error:
        raise MergeConflict(str(error)) from error
    return merge_sha
