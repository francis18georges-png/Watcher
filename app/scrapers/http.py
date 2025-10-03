"""HTTP scraping helpers with robots.txt, caching and content extraction."""

from __future__ import annotations

import hashlib
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Mapping, MutableMapping, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import time

try:  # pragma: no cover - optional dependency
    import trafilatura  # type: ignore
except Exception:  # pragma: no cover - fallback when unavailable
    trafilatura = None

try:  # pragma: no cover - optional dependency
    from readability import Document  # type: ignore
except Exception:  # pragma: no cover - fallback when unavailable
    Document = None

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "WatcherScraper/1.0"
DEFAULT_TIMEOUT = 10
DEFAULT_THROTTLE = 1.0


class CaseInsensitiveDict(MutableMapping[str, str]):
    """Minimal case-insensitive mapping for HTTP headers."""

    def __init__(self, data: Optional[Mapping[str, str]] = None) -> None:
        self._store: Dict[str, str] = {}
        if data:
            for key, value in data.items():
                self[key] = value

    def __getitem__(self, key: str) -> str:
        return self._store[key.lower()]

    def __setitem__(self, key: str, value: str) -> None:
        self._store[key.lower()] = value

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __iter__(self) -> Iterable[str]:
        return iter(self._store)

    def __len__(self) -> int:
        return len(self._store)

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        return self._store.get(key.lower(), default)

    def items(self):  # pragma: no cover - forwarding helper
        return self._store.items()

    def copy(self) -> "CaseInsensitiveDict":  # pragma: no cover - helper
        return CaseInsensitiveDict(self._store)


@dataclass
class ScrapeResult:
    """Container for a scraped HTTP document."""

    url: str
    content: Optional[str]
    raw_content: bytes
    content_hash: Optional[str]
    license: Optional[str]
    headers: Mapping[str, str]
    etag: Optional[str]
    last_modified: Optional[str]
    is_duplicate: bool = False


@dataclass
class CachedResponse:
    """Metadata stored for a cached HTTP response."""

    url: str
    raw_content: bytes
    headers: CaseInsensitiveDict
    etag: Optional[str]
    last_modified: Optional[str]
    content: Optional[str] = None
    content_hash: Optional[str] = None
    license: Optional[str] = None
    is_duplicate: bool = False

    def to_result(self) -> ScrapeResult:
        return ScrapeResult(
            url=self.url,
            content=self.content,
            raw_content=self.raw_content,
            content_hash=self.content_hash,
            license=self.license,
            headers=dict(self.headers.items()),
            etag=self.etag,
            last_modified=self.last_modified,
            is_duplicate=self.is_duplicate,
        )


class HTTPScraper:
    """High level HTTP scraper with caching and politeness controls."""

    def __init__(
        self,
        *,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = DEFAULT_TIMEOUT,
        throttle_delay: float = DEFAULT_THROTTLE,
        opener: Optional[Callable[..., object]] = None,
        time_func: Callable[[], float] | None = None,
        sleep_func: Callable[[float], None] | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.throttle_delay = max(0.0, throttle_delay)
        self._opener = opener or urllib_request.urlopen
        self._time = time_func or time.monotonic
        self._sleep = sleep_func or time.sleep
        self._robots: Dict[str, RobotFileParser] = {}
        self._cache: Dict[str, CachedResponse] = {}
        self._url_hash: Dict[str, str] = {}
        self._hash_urls: Dict[str, set[str]] = defaultdict(set)
        self._last_request: Dict[str, float] = {}

    def fetch(self, url: str, *, respect_robots: bool = True) -> Optional[ScrapeResult]:
        """Fetch *url* and return a :class:`ScrapeResult` when successful."""

        cached = self._get_cached(url)

        response = self._perform_request(url, respect_robots=respect_robots)
        if response is None:
            return cached.to_result() if cached else None

        if response.content is None:
            decoded = self._decode_content(response.raw_content, response.headers)
            response.content = self._extract_content(decoded)
            response.content_hash = self._store_hash(url, response.content)
            response.is_duplicate = self._hash_is_duplicate(response.content_hash)
            response.license = detect_license(response.headers, response.content)

        return response.to_result()

    def fetch_raw(
        self, url: str, *, respect_robots: bool = True
    ) -> Optional[tuple[bytes, Mapping[str, str]]]:
        """Fetch *url* and return the raw payload alongside headers."""

        response = self._perform_request(url, respect_robots=respect_robots)
        if response is None:
            return None
        return response.raw_content, dict(response.headers.items())

    def _perform_request(self, url: str, *, respect_robots: bool) -> Optional[CachedResponse]:
        if respect_robots and not self._is_allowed(url):
            logger.info("blocked by robots.txt: %s", url)
            return None

        cached = self._get_cached(url)

        domain = urlparse(url).netloc
        self._throttle(domain)

        headers = {"User-Agent": self.user_agent}
        if cached:
            if cached.etag:
                headers["If-None-Match"] = cached.etag
            if cached.last_modified:
                headers["If-Modified-Since"] = cached.last_modified

        request = urllib_request.Request(url, headers=headers)

        try:
            with self._opener(request, timeout=self.timeout) as response:  # type: ignore[arg-type]
                raw = response.read()
                header_map = CaseInsensitiveDict(dict(response.headers.items()))
                etag = header_map.get("etag")
                last_modified = header_map.get("last-modified")
        except HTTPError as error:
            if error.code == 304 and cached:
                logger.debug("not modified: %s", url)
                return cached
            logger.warning("failed to fetch %s: %s", url, error)
            return None
        except URLError as error:
            logger.warning("failed to fetch %s: %s", url, error.reason)
            return None

        response_cache = CachedResponse(
            url=url,
            raw_content=raw,
            headers=header_map,
            etag=etag,
            last_modified=last_modified,
        )
        self._cache[url] = response_cache
        return response_cache

    def _get_cached(self, url: str) -> Optional[CachedResponse]:
        cached = self._cache.get(url)
        if cached and cached.content_hash:
            cached.is_duplicate = self._hash_is_duplicate(cached.content_hash)
        return cached

    def _is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        key = parsed.netloc
        parser = self._robots.get(key)
        if parser is None:
            parser = self._fetch_robots(parsed.scheme, parsed.netloc)
            self._robots[key] = parser
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:  # pragma: no cover - defensive
            return True

    def _fetch_robots(self, scheme: str, netloc: str) -> RobotFileParser:
        robots_url = urljoin(f"{scheme}://{netloc}", "robots.txt")
        parser = RobotFileParser()
        request = urllib_request.Request(robots_url, headers={"User-Agent": self.user_agent})
        try:
            with self._opener(request, timeout=self.timeout) as response:  # type: ignore[arg-type]
                body = response.read().decode("utf-8", errors="ignore")
        except Exception:
            parser.parse([])
            return parser
        parser.parse(body.splitlines())
        return parser

    def _throttle(self, domain: str) -> None:
        if self.throttle_delay <= 0:
            return
        now = self._time()
        last = self._last_request.get(domain)
        if last is not None:
            wait_for = self.throttle_delay - (now - last)
            if wait_for > 0:
                self._sleep(wait_for)
                now = self._time()
        self._last_request[domain] = now

    def _decode_content(self, raw: bytes, headers: Mapping[str, str]) -> str:
        content_type = headers.get("content-type", "")
        match = re.search(r"charset=([\\w-]+)", content_type)
        encoding = match.group(1) if match else "utf-8"
        try:
            return raw.decode(encoding, errors="replace")
        except LookupError:  # pragma: no cover - rare codec issue
            return raw.decode("utf-8", errors="replace")

    def _extract_content(self, text: str) -> str:
        if trafilatura is not None:
            try:
                extracted = trafilatura.extract(text)
                if extracted:
                    return extracted.strip()
            except Exception:  # pragma: no cover - library failure
                logger.debug("trafilatura failed to extract content", exc_info=True)
        if Document is not None:
            try:
                document = Document(text)
                summary = document.summary()
                if summary:
                    return self._strip_tags(summary)
            except Exception:  # pragma: no cover - library failure
                logger.debug("Readability failed to extract content", exc_info=True)
        return text

    def _strip_tags(self, html: str) -> str:
        return re.sub(r"<[^>]+>", " ", html).strip()

    def _store_hash(self, url: str, content: str) -> str:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        previous = self._url_hash.get(url)
        if previous and previous in self._hash_urls:
            urls = self._hash_urls[previous]
            urls.discard(url)
            if not urls:
                del self._hash_urls[previous]
        self._url_hash[url] = digest
        self._hash_urls[digest].add(url)
        return digest

    def _hash_is_duplicate(self, digest: Optional[str]) -> bool:
        if not digest:
            return False
        urls = self._hash_urls.get(digest)
        return bool(urls and len(urls) > 1)


def detect_license(headers: Mapping[str, str], content: str) -> Optional[str]:
    """Attempt to infer a license from headers or page content."""

    header_keys = ["license", "x-license", "content-license"]
    for key in header_keys:
        value = headers.get(key)
        if value:
            return value.strip()

    text = content.lower()
    patterns = {
        "mit license": "MIT License",
        "apache license": "Apache License",
        "creative commons": "Creative Commons",
        "gpl": "GNU General Public License",
    }
    for needle, name in patterns.items():
        if needle in text:
            return name
    return None


__all__ = ["HTTPScraper", "ScrapeResult", "detect_license"]
