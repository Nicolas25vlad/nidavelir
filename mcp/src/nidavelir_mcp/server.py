from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache
from typing import Any

from mcp.server import MCPServer

from .auth import server_auth_kwargs
from .client import CoreAPIError, CoreClient
from .settings import get_settings

_settings = get_settings()
mcp = MCPServer(
    "Nidavelir",
    instructions=(
        "Control durable coding tasks and inspect disposable worker attempts. "
        "Check available harnesses before execution when selecting an agent. "
        "Agent completion is not approval: validation must pass before review. "
        "Merge is always explicit."
    ),
    **server_auth_kwargs(_settings),
)


@lru_cache
def get_core_client() -> CoreClient:
    settings = get_settings()
    return CoreClient(
        settings.core_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _call(operation: str, fn: Callable[[], Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "data": fn()}
    except CoreAPIError as error:
        return {
            "ok": False,
            "error": {
                "operation": operation,
                **error.as_dict(),
            },
        }


@mcp.tool()
def list_harnesses() -> dict[str, Any]:
    """List installed coding harnesses, capabilities and credential readiness."""
    return _call("list_harnesses", get_core_client().list_harnesses)


@mcp.tool()
def create_task(
    title: str,
    repository: str,
    description: str = "",
    base_branch: str = "main",
    acceptance_criteria: list[str] | None = None,
    validation_commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a durable task with optional deterministic validation commands."""
    return _call(
        "create_task",
        lambda: get_core_client().create_task(
            title=title,
            repository=repository,
            description=description,
            base_branch=base_branch,
            acceptance_criteria=acceptance_criteria,
            validation_commands=validation_commands,
        ),
    )


@mcp.tool()
def list_tasks() -> dict[str, Any]:
    """List durable tasks, newest first."""
    return _call("list_tasks", get_core_client().list_tasks)


@mcp.tool()
def get_task(task_id: str) -> dict[str, Any]:
    """Read one durable task, including transition history."""
    return _call("get_task", lambda: get_core_client().get_task(task_id))


@mcp.tool()
def update_task(
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    repository: str | None = None,
    base_branch: str | None = None,
    acceptance_criteria: list[str] | None = None,
    validation_commands: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Update mutable task fields without bypassing lifecycle state."""
    changes = {
        key: value
        for key, value in {
            "title": title,
            "description": description,
            "repository": repository,
            "base_branch": base_branch,
            "acceptance_criteria": acceptance_criteria,
            "validation_commands": validation_commands,
        }.items()
        if value is not None
    }
    return _call("update_task", lambda: get_core_client().update_task(task_id, changes))


@mcp.tool()
def start_task(task_id: str, harness: str = "codex") -> dict[str, Any]:
    """Queue a disposable Codex or Cursor attempt, including retries after rejection."""
    return _call("start_task", lambda: get_core_client().start_task(task_id, harness=harness))


@mcp.tool()
def cancel_task(task_id: str) -> dict[str, Any]:
    """Cancel a task and terminate its active worker resources when present."""

    def cancel() -> dict[str, str]:
        get_core_client().cancel_task(task_id)
        return {"task_id": task_id, "status": "cancelled"}

    return _call("cancel_task", cancel)


@mcp.tool()
def get_agent_status(task_id: str) -> dict[str, Any]:
    """Get task state and the most recent worker attempt for a task."""

    def status() -> dict[str, Any]:
        client = get_core_client()
        task = client.get_task(task_id)
        attempts = client.list_attempts(task_id)
        return {
            "task": task,
            "latest_attempt": attempts[0] if attempts else None,
        }

    return _call("get_agent_status", status)


@mcp.tool()
def get_agent_logs(
    attempt_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Read persisted worker logs by attempt id, or from a task's latest attempt."""

    def logs() -> dict[str, Any]:
        client = get_core_client()
        resolved_attempt_id = attempt_id
        if resolved_attempt_id is None:
            if task_id is None:
                raise CoreAPIError(422, "attempt_id or task_id is required")
            attempts = client.list_attempts(task_id)
            if not attempts:
                return {
                    "task_id": task_id,
                    "attempt_id": None,
                    "status": "IDLE",
                    "logs": "",
                }
            resolved_attempt_id = attempts[0]["id"]
        return client.get_attempt_logs(resolved_attempt_id)

    return _call("get_agent_logs", logs)


@mcp.tool()
def get_task_diff(
    attempt_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Read the durable patch captured for an attempt or a task's latest attempt."""

    def diff() -> dict[str, Any]:
        client = get_core_client()
        resolved_attempt_id = attempt_id
        if resolved_attempt_id is None:
            if task_id is None:
                raise CoreAPIError(422, "attempt_id or task_id is required")
            attempts = client.list_attempts(task_id)
            if not attempts:
                return {"task_id": task_id, "attempt_id": None, "stat": "", "patch": ""}
            resolved_attempt_id = attempts[0]["id"]
        return client.get_attempt_diff(resolved_attempt_id)

    return _call("get_task_diff", diff)


@mcp.tool()
def get_validation_checks(
    attempt_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """Read persisted validation results for an attempt or task."""

    def checks() -> list[dict[str, Any]]:
        client = get_core_client()
        if attempt_id is not None:
            return client.get_attempt_checks(attempt_id)
        if task_id is not None:
            return client.get_task_checks(task_id)
        raise CoreAPIError(422, "attempt_id or task_id is required")

    return _call("get_validation_checks", checks)


@mcp.tool()
def get_reviews(task_id: str) -> dict[str, Any]:
    """Read durable approval/rejection history for a task."""
    return _call("get_reviews", lambda: get_core_client().get_reviews(task_id))


@mcp.tool()
def approve_task(
    task_id: str,
    actor: str = "mcp",
    feedback: str = "",
) -> dict[str, Any]:
    """Approve the latest successfully validated attempt. This does not merge it."""
    return _call(
        "approve_task",
        lambda: get_core_client().approve_task(task_id, actor=actor, feedback=feedback),
    )


@mcp.tool()
def reject_task(task_id: str, feedback: str, actor: str = "mcp") -> dict[str, Any]:
    """Reject the latest validated attempt and preserve feedback for the next retry."""
    return _call(
        "reject_task",
        lambda: get_core_client().reject_task(task_id, actor=actor, feedback=feedback),
    )


@mcp.tool()
def merge_task(task_id: str) -> dict[str, Any]:
    """Merge an explicitly approved task after verifying the reviewed branch SHA."""
    return _call("merge_task", lambda: get_core_client().merge_task(task_id))


def main() -> None:
    settings = get_settings()
    if settings.transport == "stdio":
        mcp.run()
        return

    if settings.auth_token is None:
        raise RuntimeError(
            "NIDAVELIR_MCP_AUTH_TOKEN is required for streamable-http transport"
        )

    mcp.run(
        transport="streamable-http",
        host=settings.host,
        port=settings.port,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
