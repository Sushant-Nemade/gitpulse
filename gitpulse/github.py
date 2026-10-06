from time import monotonic
from typing import Literal

import httpx

from gitpulse.core import Person, Relation, Repository, validate_login


class GitHubClient:
    def __init__(self, username: str, token: str = "", client: httpx.Client | None = None) -> None:
        self.username = validate_login(username)
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = client or httpx.Client(headers=headers, timeout=15, follow_redirects=False)
        self.owns_client = client is None
        self.deadline = monotonic() + 90
        self.remaining_requests = 50

    def close(self) -> None:
        if self.owns_client:
            self.client.close()

    def pages(self, endpoint: Literal["followers", "following", "repos"]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        try:
            for page in range(1, 51):
                if self.remaining_requests <= 0 or monotonic() >= self.deadline:
                    raise ValueError("Sync request/time budget exhausted")
                self.remaining_requests -= 1
                response = self.client.get(
                    f"https://api.github.com/users/{self.username}/{endpoint}",
                    timeout=min(15, max(0.1, self.deadline - monotonic())),
                    follow_redirects=False,
                    params={"per_page": 100, "page": page, **({"type": "owner"} if endpoint == "repos" else {})},
                )
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ValueError("Response exceeds bound")
                payload: object = response.json()
                if not isinstance(payload, list) or len(payload) > 100:
                    raise ValueError("Invalid GitHub page")
                for item in payload:
                    if not isinstance(item, dict):
                        raise ValueError("Invalid GitHub record")
                    rows.append(item)
                if len(payload) < 100:
                    return rows
            raise ValueError("Incomplete pagination: account exceeds supported limit")
        except (httpx.HTTPError, ValueError):
            raise RuntimeError("GitHub fetch failed or exceeded limits; previous snapshot preserved") from None

    def people(self, relation: Relation) -> list[Person]:
        result: list[Person] = []
        for row in self.pages(relation):
            identifier, login = row.get("id"), row.get("login")
            if type(identifier) is not int or not isinstance(login, str):
                raise ValueError("Invalid GitHub identity")
            result.append(Person(identifier, login))
        return result

    def repositories(self) -> list[Repository]:
        result: list[Repository] = []
        for row in self.pages("repos"):
            identifier, name, language = row.get("id"), row.get("name"), row.get("language")
            stars, forks, issues = row.get("stargazers_count"), row.get("forks_count"), row.get("open_issues_count")
            if (
                type(identifier) is not int
                or not isinstance(name, str)
                or (language is not None and not isinstance(language, str))
                or type(stars) is not int
                or type(forks) is not int
                or type(issues) is not int
            ):
                raise ValueError("Invalid repository metadata")
            result.append(Repository(identifier, name, language, stars, forks, issues))
        return result
