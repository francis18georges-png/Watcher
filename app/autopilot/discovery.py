"""Discovery helpers turning allowlist entries into crawl candidates."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable
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
        can_fetch: Callable[[], bool] | None = None,
        register_payload_bytes: Callable[[int], None] | None = None,
    ) -> None:
        self._http = http or HTTPScraper()
        self._sitemap = sitemap or SitemapScraper(self._http)
        self._github = github or GitHubScraper(self._http)
        self._can_fetch = can_fetch
        self._register_payload_bytes = register_payload_bytes

    def discover(
        self,
        topics: Sequence[str],
        rules: Sequence[DomainRule],
    ) -> Iterable[DiscoveryResult]:
        seen: set[str] = set()
        filtered_topics = [item.strip() for item in topics if item and item.strip()]
        for rule in rules:
            for result in self._discover_for_rule(rule, filtered_topics):
                if result.url in seen:
                    continue
                seen.add(result.url)
                yield result

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
            if not self._budget_available():
                return
            payload = self._http.fetch_raw(sitemap_url, respect_robots=True)
            if payload is None:
                continue
            raw, _headers = payload
            self._record_payload(raw)
            for url in self._sitemap.parse(raw):
                if not self._url_allowed(rule, url):
                    continue
                if not self._matches_topics(topics, url):
                    continue
                yield DiscoveryResult(url=url, title="", summary="")

        for feed_url in self._candidate_feeds(rule.domain):
            if not self._budget_available():
                return
            payload = self._http.fetch_raw(feed_url, respect_robots=True)
            if payload is None:
                continue
            raw, _headers = payload
            self._record_payload(raw)
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
        for repo in self._candidate_repositories(rule, topics):
            if not self._budget_available():
                return
            bundle = self._github.fetch_programming_bundle(repo)
            if bundle is None or not bundle.repository.url:
                continue
            self._record_payload_bytes(bundle.payload_bytes)
            if bundle.documents:
                for document in bundle.documents:
                    yield DiscoveryResult(
                        url=document.url,
                        title=document.title,
                        summary=document.summary,
                        licence=document.license,
                        published_at=document.published_at,
                        content=document.content,
                        fetched_at=document.fetched_at,
                        etag=document.etag,
                        last_modified=document.last_modified,
                        source_type=document.source_type,
                    )
                continue
            yield DiscoveryResult(
                url=bundle.repository.url,
                title=bundle.repository.repository,
                summary=(
                    bundle.repository.description
                    or "Dépôt GitHub ciblé sans artefact textuel collecté"
                ),
                licence=bundle.repository.license,
                source_type="git-repository",
            )

    @staticmethod
    def _candidate_sitemaps(domain: str) -> list[str]:
        bases = DefaultDiscoveryCrawler._candidate_bases(domain)
        return [f"{base}/sitemap.xml" for base in bases]

    @staticmethod
    def _candidate_feeds(domain: str) -> list[str]:
        bases = DefaultDiscoveryCrawler._candidate_bases(domain)
        return [f"{base}/feed" for base in bases] + [f"{base}/rss.xml" for base in bases]

    @staticmethod
    def _candidate_bases(domain: str) -> list[str]:
        parsed = urlparse(domain if "://" in domain else f"https://{domain}")
        host = (parsed.netloc or parsed.path).strip().strip("/")
        if not host:
            return []
        scheme = parsed.scheme if parsed.scheme in {"http", "https"} else "https"
        bases = [f"{scheme}://{host}"]
        if scheme == "https" and DefaultDiscoveryCrawler._allow_insecure_http(host):
            bases.append(f"http://{host}")
        return bases

    @staticmethod
    def _allow_insecure_http(host: str) -> bool:
        return host in {"localhost", "127.0.0.1", "::1"}

    @staticmethod
    def _url_allowed(rule: DomainRule, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        domain = DefaultDiscoveryCrawler._normalise_domain(rule.domain)
        if not host:
            return False
        return host == domain

    @staticmethod
    def _normalise_domain(domain: str) -> str:
        value = domain.strip().lower()
        if "://" in value:
            parsed = urlparse(value)
            if parsed.hostname:
                return parsed.hostname.strip("/")
        return value.strip("/")

    @staticmethod
    def _matches_topics(topics: Sequence[str], *values: str) -> bool:
        if not topics:
            return True
        haystack = " ".join(value.lower() for value in values if value)
        return any(topic.lower() in haystack for topic in topics)

    @staticmethod
    def _candidate_repositories(
        rule: DomainRule, topics: Sequence[str]
    ) -> list[str]:
        repos: list[str] = []
        domain_candidate = rule.domain.strip().strip("/")
        if "/" in domain_candidate:
            repos.append(domain_candidate)
        repos.extend(topic for topic in topics if "/" in topic)
        ordered: list[str] = []
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

    def _budget_available(self) -> bool:
        if self._can_fetch is None:
            return True
        return bool(self._can_fetch())

    def _record_payload(self, raw: bytes) -> None:
        self._record_payload_bytes(len(raw))

    def _record_payload_bytes(self, payload_size: int) -> None:
        if self._register_payload_bytes is None:
            return
        self._register_payload_bytes(max(0, int(payload_size)))
