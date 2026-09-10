import httpx
import pytest

from nidavelir_mcp.client import CoreAPIError, CoreClient


def test_create_task_sends_normalized_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/tasks"
        assert request.read()
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
        )
    finally:
        client.close()

    assert task["id"] == "task-1"
    assert task["state"] == "BACKLOG"


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
