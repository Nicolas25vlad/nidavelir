from types import SimpleNamespace

from nidavelir_mcp import server
from nidavelir_mcp.github_issues import GitHubIssue


def test_server_module_imports() -> None:
    assert server.mcp is not None


class FakeCoreClient:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.existing = existing or []
        self.created: dict | None = None

    def list_tasks(self, **filters):
        assert filters["source_key"] == "github_issue:Nicolas25vlad/nidavelir#132"
        return self.existing

    def create_task(self, **payload):
        self.created = payload
        return {"id": "task-132", **payload}


def issue() -> GitHubIssue:
    return GitHubIssue(
        owner="Nicolas25vlad",
        repository="nidavelir",
        number=132,
        title="Dogfood issue import",
        body="Keep the source durable.",
        url="https://github.com/Nicolas25vlad/nidavelir/issues/132",
        labels=("dogfood", "review"),
    )


def test_github_issue_import_persists_structured_source(monkeypatch) -> None:
    client = FakeCoreClient()
    monkeypatch.setattr(
        server,
        "get_settings",
        lambda: SimpleNamespace(github_token=None, request_timeout_seconds=20.0),
    )
    monkeypatch.setattr(server, "fetch_github_issue", lambda *args, **kwargs: issue())
    monkeypatch.setattr(server, "get_core_client", lambda: client)

    result = server.create_task_from_github_issue("Nicolas25vlad/nidavelir#132")

    assert result["ok"] is True
    assert client.created is not None
    assert client.created["source_key"] == "github_issue:Nicolas25vlad/nidavelir#132"
    assert client.created["source"] == {
        "type": "github_issue",
        "ref": "Nicolas25vlad/nidavelir#132",
        "url": "https://github.com/Nicolas25vlad/nidavelir/issues/132",
        "metadata": {"labels": ["dogfood", "review"]},
    }
    assert client.created["description"] == "Keep the source durable."


def test_github_issue_import_rejects_duplicate_by_default(monkeypatch) -> None:
    client = FakeCoreClient(existing=[{"id": "existing-task"}])
    monkeypatch.setattr(
        server,
        "get_settings",
        lambda: SimpleNamespace(github_token=None, request_timeout_seconds=20.0),
    )
    monkeypatch.setattr(server, "fetch_github_issue", lambda *args, **kwargs: issue())
    monkeypatch.setattr(server, "get_core_client", lambda: client)

    result = server.create_task_from_github_issue("Nicolas25vlad/nidavelir#132")

    assert result["ok"] is False
    assert result["error"]["status_code"] == 409
    assert result["error"]["detail"]["task_id"] == "existing-task"


def test_github_issue_import_allows_explicit_duplicate(monkeypatch) -> None:
    client = FakeCoreClient(existing=[{"id": "existing-task"}])
    monkeypatch.setattr(
        server,
        "get_settings",
        lambda: SimpleNamespace(github_token=None, request_timeout_seconds=20.0),
    )
    monkeypatch.setattr(server, "fetch_github_issue", lambda *args, **kwargs: issue())
    monkeypatch.setattr(server, "get_core_client", lambda: client)

    result = server.create_task_from_github_issue(
        "Nicolas25vlad/nidavelir#132",
        allow_duplicate=True,
    )

    assert result["ok"] is True
    assert client.created is not None
