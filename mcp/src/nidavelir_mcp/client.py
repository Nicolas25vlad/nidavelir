from __future__ import annotations

from typing import Any

import httpx


class CoreAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(f"Nidavelir Core returned HTTP {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": "core_api_error",
            "status_code": self.status_code,
            "detail": self.detail,
        }


class CoreClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            response = self._client.request(method, path, json=json)
        except httpx.HTTPError as error:
            raise CoreAPIError(
                503,
                {"message": "Core is unavailable", "cause": str(error)},
            ) from error

        if response.is_error:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
            raise CoreAPIError(response.status_code, detail)

        if response.status_code == 204:
            return None
        return response.json()

    def create_task(
        self,
        *,
        title: str,
        repository: str,
        description: str = "",
        base_branch: str = "main",
        acceptance_criteria: list[str] | None = None,
        validation_commands: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/tasks",
            json={
                "title": title,
                "description": description,
                "repository": repository,
                "base_branch": base_branch,
                "acceptance_criteria": acceptance_criteria or [],
                "validation_commands": validation_commands or [],
            },
        )

    def list_tasks(self) -> list[dict[str, Any]]:
        return self._request("GET", "/tasks")

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/tasks/{task_id}")

    def update_task(self, task_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        return self._request("PATCH", f"/tasks/{task_id}", json=changes)

    def start_task(self, task_id: str, *, harness: str = "codex") -> dict[str, Any]:
        return self._request("POST", f"/tasks/{task_id}/start", json={"harness": harness})

    def cancel_task(self, task_id: str) -> None:
        self._request("POST", f"/tasks/{task_id}/cancel")

    def list_attempts(self, task_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/tasks/{task_id}/attempts")

    def get_attempt(self, attempt_id: str) -> dict[str, Any]:
        return self._request("GET", f"/attempts/{attempt_id}")

    def get_attempt_logs(self, attempt_id: str) -> dict[str, Any]:
        return self._request("GET", f"/attempts/{attempt_id}/logs")

    def get_attempt_diff(self, attempt_id: str) -> dict[str, Any]:
        return self._request("GET", f"/attempts/{attempt_id}/diff")

    def get_attempt_checks(self, attempt_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/attempts/{attempt_id}/checks")

    def get_task_checks(self, task_id: str) -> list[dict[str, Any]]:
        return self._request("GET", f"/tasks/{task_id}/checks")
