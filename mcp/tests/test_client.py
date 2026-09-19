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
        assert payload["supervisor_client"] == "codex"
        assert payload["supervisor_session_id"] == "chat-a"
        assert payload["project_id"] == "nidavelir"
        assert payload["source_key"] == "github_issue:Nicolas25vlad/nidavelir#132"
        assert payload["source"]["type"] == "github_issue"
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
            supervisor_client="codex",
            supervisor_session_id="chat-a",
            project_id="nidavelir",
            source_key="github_issue:Nicolas25vlad/nidavelir#132",
            source={
                "type": "github_issue",
                "ref": "Nicolas25vlad/nidavelir#132",
                "url": "https://github.com/Nicolas25vlad/nidavelir/issues/132",
                "metadata": {"labels": ["dogfood"]},
            },
        )
    finally:
        client.close()

    assert task["id"] == "task-1"
    assert task["state"] == "BACKLOG"


def test_client_sends_core_service_bearer_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer internal-service-token"
        return httpx.Response(200, json=[])

    client = CoreClient(
        "http://core:8000",
        bearer_token="internal-service-token",
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.list_tasks() == []
    finally:
        client.close()


def test_list_tasks_sends_supervisor_filters() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/tasks"
        assert request.url.params["supervisor_client"] == "codex"
        assert request.url.params["supervisor_session_id"] == "chat-a"
        assert request.url.params["project_id"] == "nidavelir"
        assert request.url.params["source_key"] == "github_issue:Nicolas25vlad/nidavelir#132"
        return httpx.Response(200, json=[])

    client = CoreClient("http://core:8000", transport=httpx.MockTransport(handler))
    try:
        tasks = client.list_tasks(
            supervisor_client="codex",
            supervisor_session_id="chat-a",
            project_id="nidavelir",
            source_key="github_issue:Nicolas25vlad/nidavelir#132",
        )
    finally:
        client.close()

    assert tasks == []


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
