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

    def fetch_raw(self, url: str, *, respect_robots: bool = True):  # noqa: D401
        payload = self.payloads.get(url)
        if payload is None:
            return None
        return payload, {}


def _rule(domain: str, *, scope: str = "web", allow_subdomains: bool = False) -> DomainRule:
    return DomainRule(
        domain=domain,
        categories=[],
        bandwidth_mb=10,
        time_budget_minutes=5,
        allow_subdomains=allow_subdomains,
        scope=scope,
        last_approved=datetime.now(timezone.utc),
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
    rule = _rule("news.test", allow_subdomains=False)

    results = list(crawler.discover(["ai"], [rule]))

    assert [item.url for item in results] == ["https://news.test/articles/ai-overview"]


def test_discover_rss_filters_topics_and_metadata() -> None:
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
          <title>Other topic</title>
          <link>https://feed.test/other</link>
          <description>General news.</description>
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
    rule = _rule("feed.test", allow_subdomains=True)

    results = list(crawler.discover(["AI"], [rule]))

    assert len(results) == 1
    item = results[0]
    assert item.url == "https://feed.test/ai-weekly"
    assert item.title == "AI Weekly"
    assert "trustworthy" in item.summary.lower()
    assert item.published_at is not None


def test_discover_github_scope_uses_categories() -> None:
    repo_data = json.dumps({
        "full_name": "octocat/Hello-World",
        "license": {"spdx_id": "MIT"},
    }).encode("utf-8")
    http = StubHTTP({
        "https://api.github.com/repos/octocat/Hello-World": repo_data,
    })
    crawler = DefaultDiscoveryCrawler(http=http)
    rule = DomainRule(
        domain="github.com",
        categories=["octocat/Hello-World"],
        bandwidth_mb=0,
        time_budget_minutes=0,
        allow_subdomains=True,
        scope="git",
        last_approved=datetime.now(timezone.utc),
    )

    results = list(crawler.discover([], [rule]))

    assert len(results) == 1
    result = results[0]
    assert result.url == "https://github.com/octocat/Hello-World"
    assert result.title == "octocat/Hello-World"
    assert result.licence == "MIT"

