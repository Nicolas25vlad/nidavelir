from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

_ISSUE_REF = re.compile(
    r"^(?:https://github\.com/)?(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)"
    r"(?:/issues/|#)(?P<number>[1-9][0-9]*)/?$"
)


class GitHubIssueError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitHubIssue:
    owner: str
    repository: str
    number: int
    title: str
    body: str
    url: str

    @property
    def repository_full_name(self) -> str:
        return f"{self.owner}/{self.repository}"


def parse_issue_reference(reference: str) -> tuple[str, str, int]:
    normalized = reference.strip()
    match = _ISSUE_REF.fullmatch(normalized)
    if match is None:
        raise GitHubIssueError(
            "GitHub issue must look like owner/repo#123 or "
            "https://github.com/owner/repo/issues/123"
        )
    return match.group("owner"), match.group("repo"), int(match.group("number"))


def fetch_github_issue(
    reference: str,
    *,
    token: str | None = None,
    timeout_seconds: float = 20.0,
) -> GitHubIssue:
    owner, repository, number = parse_issue_reference(reference)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "nidavelir-mcp",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{repository}/issues/{number}"
    try:
        response = httpx.get(url, headers=headers, timeout=timeout_seconds)
    except httpx.HTTPError as error:
        raise GitHubIssueError(f"GitHub issue request failed: {error}") from error

    if response.status_code == 404:
        raise GitHubIssueError("GitHub issue was not found or is not accessible")
    if response.status_code >= 400:
        raise GitHubIssueError(f"GitHub issue request failed with HTTP {response.status_code}")

    payload = response.json()
    if "pull_request" in payload:
        raise GitHubIssueError("reference points to a pull request, not a GitHub issue")

    title = payload.get("title")
    html_url = payload.get("html_url")
    if not isinstance(title, str) or not title.strip() or not isinstance(html_url, str):
        raise GitHubIssueError("GitHub returned an invalid issue payload")

    body = payload.get("body")
    return GitHubIssue(
        owner=owner,
        repository=repository,
        number=number,
        title=title.strip(),
        body=body if isinstance(body, str) else "",
        url=html_url,
    )
