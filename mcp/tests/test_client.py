import json

import httpx
import pytest

from nidavelir_mcp.client import CoreAPIError, CoreClient


def test_create_task_sends_normalized_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/tasks"
        payload = json.loads(request.read())
        assert payload["acceptance_criteria"] == ["CI passes"]
        assert payload["validation_commands"] == [
            {
                "name": "tests",
                "type": "test",
                "command": "pytest -q",
                "timeout_seconds": 300,
            }
        ]
        return httpx.Response(
            201,
            json={"id": "task-1", "title": "Ship MVP", "state": "BACKLOG"},
        )

    client = CoreClient("http://core:8000", transport=httpx.MockTransport(handler))
    try:
        task = client.create_task(
            title="Ship MVP",
            repository="Nicolas25vlad/nidavelir",
            acceptance_criteria=["CI passes"],
            validation_commands=[
                {
                    "name": "tests",
                    "type": "test",
                    "command": "pytest -q",
                    "timeout_seconds": 300,
                }
            ],
        )
    finally:
        client.close()

    assert task["id"] == "task-1"
    assert task["state"] == "BACKLOG"


def test_diff_and_check_requests_use_attempt_endpoints() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path.endswith("/diff"):
            return httpx.Response(200, json={"attempt_id": "attempt-1", "patch": "+forge"})
        return httpx.Response(200, json=[{"id": "check-1", "status": "PASSED"}])

    client = CoreClient("http://core:8000", transport=httpx.MockTransport(handler))
    try:
        diff = client.get_attempt_diff("attempt-1")
        checks = client.get_attempt_checks("attempt-1")
    finally:
        client.close()

    assert diff["patch"] == "+forge"
    assert checks[0]["status"] == "PASSED"
    assert paths == ["/attempts/attempt-1/diff", "/attempts/attempt-1/checks"]


def test_core_error_keeps_status_and_detail() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"detail": "task cannot start from RUNNING"})

    client = CoreClient("http://core:8000", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(CoreAPIError) as captured:
            client.start_task("task-1")
    finally:
        client.close()

    assert captured.value.status_code == 409
    assert captured.value.detail == "task cannot start from RUNNING"


def test_cancel_accepts_no_content_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/tasks/task-1/cancel"
        return httpx.Response(204)

    client = CoreClient("http://core:8000", transport=httpx.MockTransport(handler))
    try:
        client.cancel_task("task-1")
    finally:
        client.close()
