"""Tests for the default discovery crawler."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Mapping

from app.autopilot.discovery import DefaultDiscoveryCrawler
from app.policy.schema import DomainRule


class StubHTTP:
    """Minimal stub emulating :class:`HTTPScraper`."""

    def __init__(self, payloads: Mapping[str, bytes]) -> None:
        self.payloads = dict(payloads)
        self.calls: list[tuple[str, bool]] = []

    def fetch_raw(self, url: str, *, respect_robots: bool = True):  # noqa: D401
        self.calls.append((url, respect_robots))
        payload = self.payloads.get(url)
        if payload is None:
            return None
        return payload, {}


def _rule(domain: str, *, scope: str = "web") -> DomainRule:
    return DomainRule(
        domain=domain,
        bandwidth_mb=10,
        time_budget_minutes=5,
        scope=scope,
    )


def test_discover_sitemap_respects_allowlist() -> None:
    sitemap = b"""<?xml version='1.0'?>
    <urlset>
      <url><loc>https://news.test/articles/ai-overview</loc></url>
      <url><loc>https://other.test/out-of-scope</loc></url>
    </urlset>
    """
    http = StubHTTP({"https://news.test/sitemap.xml": sitemap})
    crawler = DefaultDiscoveryCrawler(http=http)
    rule = _rule("news.test")

    results = list(crawler.discover(["ai"], [rule]))

    assert [item.url for item in results] == ["https://news.test/articles/ai-overview"]
    assert ("https://news.test/sitemap.xml", True) in http.calls


def test_discover_rss_filters_topics_and_respects_robots() -> None:
    rss = b"""<?xml version='1.0'?>
    <rss version='2.0'>
      <channel>
        <title>Feed</title>
        <item>
          <title>AI Weekly</title>
          <link>https://feed.test/ai-weekly</link>
          <description>Focus on trustworthy AI systems.</description>
          <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate>
        </item>
        <item>
          <title>External</title>
          <link>https://outside.test/news</link>
          <description>Should be ignored.</description>
        </item>
      </channel>
    </rss>
    """
    http = StubHTTP({"https://feed.test/feed": rss})
    crawler = DefaultDiscoveryCrawler(http=http)
    rule = _rule("feed.test")

    results = list(crawler.discover(["AI"], [rule]))

    assert len(results) == 1
    item = results[0]
    assert item.url == "https://feed.test/ai-weekly"
    assert item.title == "AI Weekly"
    assert "trustworthy" in item.summary.lower()
    assert item.published_at is not None
    assert ("https://feed.test/feed", True) in http.calls


def test_discover_github_scope_uses_topic_repo() -> None:
    repo_data = json.dumps(
        {
            "full_name": "octocat/Hello-World",
            "license": {"spdx_id": "MIT"},
        }
    ).encode("utf-8")
    http = StubHTTP(
        {
            "https://api.github.com/repos/octocat/Hello-World": repo_data,
        }
    )
    crawler = DefaultDiscoveryCrawler(http=http)
    rule = _rule("github.com", scope="git")

    results = list(crawler.discover(["octocat/Hello-World"], [rule]))

    assert len(results) == 1
    result = results[0]
    assert result.url == "https://github.com/octocat/Hello-World"
    assert result.title == "octocat/Hello-World"
    assert result.licence == "MIT"
    assert ("https://api.github.com/repos/octocat/Hello-World", False) in http.calls


def test_discover_github_scope_yields_targeted_content_items() -> None:
    release = json.dumps(
        {
            "tag_name": "v1.2.3",
            "name": "Release 1.2.3",
            "html_url": "https://github.com/octocat/Hello-World/releases/tag/v1.2.3",
            "published_at": "2024-01-01T10:00:00Z",
            "body": "Bug fixes and API updates.",
        }
    ).encode("utf-8")
    repo_data = json.dumps(
        {
            "full_name": "octocat/Hello-World",
            "default_branch": "main",
            "license": {"spdx_id": "MIT"},
        }
    ).encode("utf-8")
    readme = json.dumps(
        {
            "type": "file",
            "path": "README.md",
            "size": 32,
            "encoding": "base64",
            "content": "IyBIZWxsbyBXb3JsZAoKUHJvZ3JhbW1pbmcgZ3VpZGU=",
            "html_url": "https://github.com/octocat/Hello-World/blob/main/README.md",
        }
    ).encode("utf-8")
    http = StubHTTP(
        {
            "https://api.github.com/repos/octocat/Hello-World": repo_data,
            "https://api.github.com/repos/octocat/Hello-World/releases/latest": release,
            "https://api.github.com/repos/octocat/Hello-World/contents/README.md?ref=main": readme,
        }
    )
    crawler = DefaultDiscoveryCrawler(http=http)
    rule = _rule("github.com", scope="git")

    results = list(crawler.discover(["octocat/Hello-World"], [rule]))

    assert len(results) == 2
    assert {item.source_type for item in results} == {"git-release", "git-documentation"}
    assert all(item.content for item in results)


def test_discovery_tracks_payload_bytes_and_stops_when_budget_exhausted() -> None:
    rss = b"""<?xml version='1.0'?>
    <rss version='2.0'>
      <channel>
        <item>
          <title>AI Weekly</title>
          <link>https://feed.test/ai-weekly</link>
          <description>Focus on trustworthy AI systems.</description>
        </item>
      </channel>
    </rss>
    """
    http = StubHTTP(
        {
            "https://feed.test/feed": rss,
            "https://feed.test/rss.xml": rss,
        }
    )
    consumed: list[int] = []
    remaining = {"calls": 1}

    def can_fetch() -> bool:
        return remaining["calls"] > 0

    def register_payload_bytes(size: int) -> None:
        consumed.append(size)
        remaining["calls"] -= 1

    crawler = DefaultDiscoveryCrawler(
        http=http,
        can_fetch=can_fetch,
        register_payload_bytes=register_payload_bytes,
    )

    results = list(crawler.discover(["AI"], [_rule("feed.test")]))

    assert len(results) == 1
    assert consumed == [len(rss)]
    assert http.calls == [
        ("https://feed.test/sitemap.xml", True),
        ("https://feed.test/feed", True),
    ]


def test_candidate_bases_only_allow_https_except_localhost() -> None:
    assert DefaultDiscoveryCrawler._candidate_bases("example.com") == ["https://example.com"]
    assert DefaultDiscoveryCrawler._candidate_bases("https://example.com") == [
        "https://example.com"
    ]
    assert DefaultDiscoveryCrawler._candidate_bases("localhost") == [
        "https://localhost",
        "http://localhost",
    ]
