from __future__ import annotations

import base64
import json
from typing import Mapping

from app.scrapers.github import GitHubScraper


class StubHTTP:
    def __init__(self, payloads: Mapping[str, tuple[bytes, dict[str, str]] | None]) -> None:
        self.payloads = dict(payloads)
        self.calls: list[tuple[str, bool]] = []

    def fetch_raw(self, url: str, *, respect_robots: bool = True):  # noqa: D401
        self.calls.append((url, respect_robots))
        return self.payloads.get(url)


def _content_payload(
    *,
    path: str,
    text: str,
    html_url: str,
) -> tuple[bytes, dict[str, str]]:
    data = {
        "type": "file",
        "path": path,
        "size": len(text.encode("utf-8")),
        "encoding": "base64",
        "content": base64.b64encode(text.encode("utf-8")).decode("utf-8"),
        "html_url": html_url,
    }
    return json.dumps(data).encode("utf-8"), {
        "etag": f'"{path}"',
        "last-modified": "Wed, 03 Jan 2024 10:00:00 GMT",
    }


def test_github_scraper_fetches_targeted_programming_bundle() -> None:
    repo_url = "https://api.github.com/repos/octocat/Hello-World"
    release_url = "https://api.github.com/repos/octocat/Hello-World/releases/latest"
    changelog_url = (
        "https://api.github.com/repos/octocat/Hello-World/contents/CHANGELOG.md?ref=main"
    )
    readme_url = (
        "https://api.github.com/repos/octocat/Hello-World/contents/README.md?ref=main"
    )
    reference_url = (
        "https://api.github.com/repos/octocat/Hello-World/contents/docs/reference.md?ref=main"
    )
    http = StubHTTP(
        {
            repo_url: (
                json.dumps(
                    {
                        "full_name": "octocat/Hello-World",
                        "default_branch": "main",
                        "description": "Repository description",
                        "license": {"spdx_id": "MIT"},
                    }
                ).encode("utf-8"),
                {"etag": '"repo"'},
            ),
            release_url: (
                json.dumps(
                    {
                        "tag_name": "v1.2.3",
                        "name": "Release 1.2.3",
                        "html_url": "https://github.com/octocat/Hello-World/releases/tag/v1.2.3",
                        "published_at": "2024-01-01T10:00:00Z",
                        "body": "Bug fixes and API updates.",
                    }
                ).encode("utf-8"),
                {"etag": '"release"'},
            ),
            changelog_url: _content_payload(
                path="CHANGELOG.md",
                text="# Changelog\n\n- Added feature",
                html_url="https://github.com/octocat/Hello-World/blob/main/CHANGELOG.md",
            ),
            readme_url: _content_payload(
                path="README.md",
                text="# Hello World\n\nProgramming guide",
                html_url="https://github.com/octocat/Hello-World/blob/main/README.md",
            ),
            reference_url: _content_payload(
                path="docs/reference.md",
                text="# Reference\n\nStable API surface",
                html_url="https://github.com/octocat/Hello-World/blob/main/docs/reference.md",
            ),
        }
    )
    scraper = GitHubScraper(http)

    bundle = scraper.fetch_programming_bundle("octocat/Hello-World:docs/reference.md")

    assert bundle is not None
    assert bundle.repository.repository == "octocat/Hello-World"
    assert bundle.repository.license == "MIT"
    assert len(bundle.documents) == 4
    assert {item.kind for item in bundle.documents} == {
        "release",
        "changelog",
        "documentation",
        "reference",
    }
    assert {item.source_type for item in bundle.documents} == {
        "git-release",
        "git-changelog",
        "git-documentation",
        "git-reference",
    }
    assert all(call[1] is False for call in http.calls)


def test_github_scraper_limits_reference_files_to_supported_paths() -> None:
    repo_url = "https://api.github.com/repos/octocat/Hello-World"
    http = StubHTTP(
        {
            repo_url: (
                json.dumps(
                    {
                        "full_name": "octocat/Hello-World",
                        "default_branch": "main",
                        "license": {"spdx_id": "MIT"},
                    }
                ).encode("utf-8"),
                {},
            ),
        }
    )
    scraper = GitHubScraper(http)

    bundle = scraper.fetch_programming_bundle("octocat/Hello-World:dist/archive.zip")

    assert bundle is not None
    assert bundle.documents == []
    assert all("archive.zip" not in call[0] for call in http.calls)
