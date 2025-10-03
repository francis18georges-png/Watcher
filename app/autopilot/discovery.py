"""Discovery helpers turning allowlist entries into crawl candidates."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

from app.autopilot.controller import DiscoveryResult
from app.policy.schema import DomainRule
from app.scrapers.github import GitHubScraper
from app.scrapers.http import HTTPScraper
from app.scrapers.sitemap import SitemapScraper

__all__ = ["DefaultDiscoveryCrawler"]


@dataclass(slots=True)
class _FeedEntry:
    url: str
    title: str
    summary: str
    published_at: datetime | None


class DefaultDiscoveryCrawler:
    """High level crawler combining sitemap, RSS and GitHub discovery."""

    def __init__(
        self,
        *,
        http: HTTPScraper | None = None,
        sitemap: SitemapScraper | None = None,
        github: GitHubScraper | None = None,
    ) -> None:
        self._http = http or HTTPScraper()
        self._sitemap = sitemap or SitemapScraper(self._http)
        self._github = github or GitHubScraper(self._http)

    # ------------------------------------------------------------------
    # Public API

    def discover(
        self,
        topics: Sequence[str],
        rules: Sequence[DomainRule],
    ) -> Iterable[DiscoveryResult]:
        seen: set[str] = set()
        lowered_topics = [item.lower() for item in topics if item]
        for rule in rules:
            for result in self._discover_for_rule(rule, lowered_topics):
                if result.url in seen:
                    continue
                seen.add(result.url)
                yield result

    # ------------------------------------------------------------------

    def _discover_for_rule(
        self, rule: DomainRule, topics: Sequence[str]
    ) -> Iterator[DiscoveryResult]:
        scope = (rule.scope or "web").lower()
        if scope == "git":
            yield from self._discover_git(rule, topics)
            return
        yield from self._discover_web(rule, topics)

    def _discover_web(
        self, rule: DomainRule, topics: Sequence[str]
    ) -> Iterator[DiscoveryResult]:
        for sitemap_url in self._candidate_sitemaps(rule.domain):
            for url in self._sitemap.fetch(sitemap_url):
                if not self._url_allowed(rule, url):
                    continue
                if not self._matches_topics(topics, url):
                    continue
                yield DiscoveryResult(url=url, title="", summary="")
        for feed_url in self._candidate_feeds(rule.domain):
            payload = self._http.fetch_raw(feed_url, respect_robots=False)
            if payload is None:
                continue
            raw, _headers = payload
            for entry in self._parse_feed(raw):
                if not self._url_allowed(rule, entry.url):
                    continue
                if not self._matches_topics(topics, entry.url, entry.title, entry.summary):
                    continue
                yield DiscoveryResult(
                    url=entry.url,
                    title=entry.title,
                    summary=entry.summary,
                    published_at=entry.published_at,
                )

    def _discover_git(
        self, rule: DomainRule, topics: Sequence[str]
    ) -> Iterator[DiscoveryResult]:
        repos = self._candidate_repositories(rule, topics)
        for repo in repos:
            info = self._github.fetch_repository(repo)
            if info is None:
                continue
            if not info.url:
                continue
            if not self._url_allowed(rule, info.url):
                continue
            if topics and not self._matches_topics(topics, info.repository):
                continue
            yield DiscoveryResult(
                url=info.url,
                title=info.repository,
                summary="Dépôt GitHub découvert via allowlist",
                licence=info.license,
            )

    # ------------------------------------------------------------------
    # Helpers

    @staticmethod
    def _candidate_sitemaps(domain: str) -> list[str]:
        bases = DefaultDiscoveryCrawler._candidate_bases(domain)
        return [f"{base}/sitemap.xml" for base in bases] + [
            f"{base}/sitemap_index.xml" for base in bases
        ]

    @staticmethod
    def _candidate_feeds(domain: str) -> list[str]:
        bases = DefaultDiscoveryCrawler._candidate_bases(domain)
        suffixes = ("/feed", "/rss.xml", "/rss", "/atom.xml")
        return [f"{base}{suffix}" for base in bases for suffix in suffixes]

    @staticmethod
    def _candidate_bases(domain: str) -> list[str]:
        parsed = urlparse(domain if "//" in domain else f"//{domain}", "https")
        host = parsed.netloc or parsed.path
        host = host.strip().strip("/")
        if not host:
            return []
        if parsed.scheme in {"http", "https"}:
            bases = [f"{parsed.scheme}://{host}"]
        else:
            bases = [f"https://{host}"]
        if not any(base.startswith("http://") for base in bases):
            bases.append(f"http://{host}")
        return list(dict.fromkeys(bases))

    @staticmethod
    def _url_allowed(rule: DomainRule, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        domain = DefaultDiscoveryCrawler._normalise_domain(rule.domain)
        if not host:
            return False
        if rule.allow_subdomains:
            return host == domain or host.endswith(f".{domain}")
        return host == domain

    @staticmethod
    def _normalise_domain(domain: str) -> str:
        value = domain.strip().lower()
        if "//" in value:
            parsed = urlparse(value)
            if parsed.netloc:
                value = parsed.netloc
        return value.strip("/")

    @staticmethod
    def _matches_topics(topics: Sequence[str], *values: str) -> bool:
        if not topics:
            return True
        haystack = " ".join(value.lower() for value in values if value)
        return any(topic in haystack for topic in topics)

    @staticmethod
    def _candidate_repositories(
        rule: DomainRule, topics: Sequence[str]
    ) -> list[str]:
        repos: list[str] = []
        domain_candidate = rule.domain.strip()
        if "/" in domain_candidate:
            repos.append(domain_candidate)
        repos.extend(item for item in rule.categories if "/" in item)
        repos.extend(topic for topic in topics if "/" in topic)
        ordered = []
        seen: set[str] = set()
        for repo in repos:
            normalised = repo.strip().strip("/")
            if not normalised or normalised in seen:
                continue
            seen.add(normalised)
            ordered.append(normalised)
        return ordered

    @staticmethod
    def _parse_feed(payload: bytes) -> Iterator[_FeedEntry]:
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return iter(())
        entries = list(root.findall(".//item"))
        if not entries:
            entries = list(root.findall(".//{*}entry"))
        parsed_entries: list[_FeedEntry] = []
        for item in entries:
            link = DefaultDiscoveryCrawler._extract_link(item)
            if not link:
                continue
            title = DefaultDiscoveryCrawler._extract_text(item, {"title"}) or ""
            summary = DefaultDiscoveryCrawler._extract_text(
                item, {"summary", "description"}
            ) or ""
            published = DefaultDiscoveryCrawler._extract_text(
                item, {"pubDate", "published", "updated"}
            )
            published_at = DefaultDiscoveryCrawler._parse_datetime(published)
            parsed_entries.append(
                _FeedEntry(
                    url=link,
                    title=title.strip(),
                    summary=summary.strip(),
                    published_at=published_at,
                )
            )
        return iter(parsed_entries)

    @staticmethod
    def _extract_text(element: ET.Element, names: set[str]) -> str | None:
        for child in element.iter():
            name = child.tag.rsplit("}", 1)[-1]
            if name not in names:
                continue
            if child.text and child.text.strip():
                return child.text.strip()
        return None

    @staticmethod
    def _extract_link(element: ET.Element) -> str | None:
        for child in element.iter():
            name = child.tag.rsplit("}", 1)[-1]
            if name != "link":
                continue
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text and child.text.strip():
                return child.text.strip()
        return None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError):
                return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

