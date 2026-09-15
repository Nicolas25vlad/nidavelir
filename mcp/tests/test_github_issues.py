import httpx
import pytest

from nidavelir_mcp.github_issues import GitHubIssueError, fetch_github_issue, parse_issue_reference


def test_parse_issue_reference_supports_short_and_url_forms() -> None:
    assert parse_issue_reference("Nicolas25vlad/nidavelir#142") == (
        "Nicolas25vlad",
        "nidavelir",
        142,
    )
    assert parse_issue_reference(
        "https://github.com/Nicolas25vlad/nidavelir/issues/142"
    ) == ("Nicolas25vlad", "nidavelir", 142)


def test_parse_issue_reference_rejects_ambiguous_input() -> None:
    with pytest.raises(GitHubIssueError):
        parse_issue_reference("nidavelir issue 142")


def test_fetch_github_issue_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request(
        "GET", "https://api.github.com/repos/Nicolas25vlad/nidavelir/issues/142"
    )
    response = httpx.Response(
        200,
        request=request,
        json={
            "title": "Dogfood GitHub issue import",
            "body": "Create a durable task from this issue.",
            "html_url": "https://github.com/Nicolas25vlad/nidavelir/issues/142",
        },
    )

    def fake_get(*args, **kwargs):  # noqa: ANN002, ANN003
        return response

    monkeypatch.setattr(httpx, "get", fake_get)
    issue = fetch_github_issue("Nicolas25vlad/nidavelir#142", token="secret")

    assert issue.repository_full_name == "Nicolas25vlad/nidavelir"
    assert issue.number == 142
    assert issue.title == "Dogfood GitHub issue import"
    assert issue.body == "Create a durable task from this issue."


def test_fetch_github_issue_rejects_pull_request(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://api.github.com/repos/o/r/issues/7")
    response = httpx.Response(
        200,
        request=request,
        json={
            "title": "PR",
            "body": "",
            "html_url": "https://github.com/o/r/pull/7",
            "pull_request": {"url": "https://api.github.com/repos/o/r/pulls/7"},
        },
    )
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: response)

    with pytest.raises(GitHubIssueError, match="pull request"):
        fetch_github_issue("o/r#7")
