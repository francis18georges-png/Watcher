"""Concurrent web scraper with configuration-aware defaults and caching.

The :func:`scrape_all` coroutine downloads a collection of URLs, stores the
responses on disk and returns a mapping of source URL to cached file path. The
implementation relies on :mod:`urllib` only so it remains easy to monkeypatch in
tests and works in constrained offline environments. Runtime defaults (cache
directory, rate limiting, concurrency, user agent) are pulled from the
configuration when available, falling back to sensible built-ins.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from urllib import request as urllib_request
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

_FALLBACK_CACHE_DIR = Path("datasets/raw")
_DEFAULT_RATE_LIMIT = 1.0  # seconds between two requests to the same domain
_DEFAULT_CONCURRENCY = 5
_DEFAULT_USER_AGENT = "WatcherBot/1.0 (+https://github.com/francis18georges-png/Watcher)"
_CACHE_SUFFIX = ".html"
_META_SUFFIX = ".meta.txt"

_DEFAULT_CACHE_DIR: Path = _FALLBACK_CACHE_DIR
RATE_PER_DOMAIN: float = _DEFAULT_RATE_LIMIT
DEFAULT_CONCURRENCY: int = _DEFAULT_CONCURRENCY
DEFAULT_USER_AGENT: str = _DEFAULT_USER_AGENT

try:  # pragma: no cover - optional during bootstrap
    from config import load_config as _load_config
except Exception:  # pragma: no cover - configuration not ready
    _load_config = None

try:  # pragma: no cover - optional dependency during bootstrap
    from bs4 import BeautifulSoup  # type: ignore
except Exception:  # pragma: no cover - BeautifulSoup not installed yet
    BeautifulSoup = None  # type: ignore


def _coerce_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 0 else default


def _coerce_int(value: Any, default: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result > 0 else default


@lru_cache(maxsize=1)
def _resolve_defaults() -> Tuple[Path, float, int, str]:
    """Load scraper defaults from configuration if possible."""

    cache_dir = _FALLBACK_CACHE_DIR
    rate_limit = _DEFAULT_RATE_LIMIT
    concurrency = _DEFAULT_CONCURRENCY
    user_agent = _DEFAULT_USER_AGENT

    if _load_config is None:
        return cache_dir, rate_limit, concurrency, user_agent

    try:
        cfg = _load_config()
    except Exception:  # pragma: no cover - configuration errors logged elsewhere
        logger.debug("Unable to load configuration for scraper defaults", exc_info=True)
        return cache_dir, rate_limit, concurrency, user_agent

    if isinstance(cfg, dict):
        scraper_section = cfg.get("scraper")
        if isinstance(scraper_section, dict):
            rate_limit = _coerce_float(scraper_section.get("rate_per_domain"), rate_limit)
            concurrency = _coerce_int(scraper_section.get("concurrency"), concurrency)
            cache_candidate = scraper_section.get("cache_dir")
            if isinstance(cache_candidate, str) and cache_candidate:
                cache_dir = Path(cache_candidate)
            ua_candidate = scraper_section.get("user_agent")
            if isinstance(ua_candidate, str) and ua_candidate.strip():
                user_agent = ua_candidate.strip()

        if cache_dir == _FALLBACK_CACHE_DIR:
            for section_name in ("data", "dataset"):
                section = cfg.get(section_name)
                if isinstance(section, dict):
                    candidate = section.get("raw_dir")
                    if isinstance(candidate, str) and candidate:
                        cache_dir = Path(candidate)
                        break

    return cache_dir, rate_limit, concurrency, user_agent


def _refresh_defaults() -> None:
    """Populate module-level defaults from configuration."""

    cache_dir, rate_limit, concurrency, user_agent = _resolve_defaults()

    globals()["_DEFAULT_CACHE_DIR"] = cache_dir
    globals()["RATE_PER_DOMAIN"] = rate_limit
    globals()["DEFAULT_CONCURRENCY"] = concurrency
    globals()["DEFAULT_USER_AGENT"] = user_agent


def _build_request(url: str) -> Any:
    """Return a request object honouring the configured user agent."""

    request_factory = getattr(urllib_request, "Request", None)
    if request_factory is None:
        return url
    _, _, _, user_agent = _resolve_defaults()
    return request_factory(url, headers={"User-Agent": user_agent})


_ROBOTS_CACHE: Dict[str, RobotFileParser | bool] = {}
_ROBOTS_LOCKS: Dict[str, asyncio.Lock] = {}


class DomainRateLimiter:
    """Co-ordinate access to individual domains."""

    def __init__(self, delay: float | None = None):
        if delay is None:
            delay = RATE_PER_DOMAIN
        self.delay = max(0.0, delay)
        self._locks: dict[str, asyncio.Lock] = {}
        self._last_seen: dict[str, float] = {}

    async def wait(self, domain: str) -> None:
        """Wait until the rate limit for *domain* allows another request."""

        if self.delay <= 0:
            return
        lock = self._locks.setdefault(domain, asyncio.Lock())
        async with lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            last = self._last_seen.get(domain, 0.0)
            sleep_for = self.delay - (now - last)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            self._last_seen[domain] = loop.time()


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{_cache_key(url)}{_CACHE_SUFFIX}"


def _metadata_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{_cache_key(url)}{_META_SUFFIX}"


def _summarise_html(url: str, html: bytes) -> str:
    """Return a short textual summary for *url* based on *html* content."""

    title = ""
    code_blocks = 0
    if BeautifulSoup is None:
        return f"url: {url}\ntitle: {title}\ncode_blocks: {code_blocks}\n"

    try:
        soup = BeautifulSoup(html, "html.parser")  # type: ignore[arg-type]
        for selector in ("nav", "footer", "aside", "header", "script", "style"):
            for element in soup.select(selector):
                element.decompose()
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        code_blocks = sum(
            1
            for node in soup.find_all(["pre", "code"])
            if node.get_text("\n", strip=True)
        )
    except Exception:  # pragma: no cover - defensive against HTML edge cases
        logger.debug("unable to build metadata summary for %s", url, exc_info=True)
        title = ""
        code_blocks = 0

    return f"url: {url}\ntitle: {title}\ncode_blocks: {code_blocks}\n"


def _write_metadata(cache_dir: Path, url: str, content: bytes) -> None:
    """Persist metadata sidecar for the cached HTML content."""

    try:
        summary = _summarise_html(url, content)
        _metadata_path(cache_dir, url).write_text(summary, encoding="utf-8")
    except Exception:  # pragma: no cover - metadata generation best-effort
        logger.debug("failed to write metadata for %s", url, exc_info=True)


def _ensure_metadata_from_cache(cache_dir: Path, url: str) -> None:
    """Regenerate metadata for cached files missing their sidecar."""

    meta_file = _metadata_path(cache_dir, url)
    if meta_file.exists():
        return

    cache_file = _cache_path(cache_dir, url)
    try:
        content = cache_file.read_bytes()
    except OSError:  # pragma: no cover - cache removed concurrently
        logger.debug("unable to read cached file for metadata regeneration: %s", cache_file)
        return

    _write_metadata(cache_dir, url, content)


async def _robots_allowed(url: str) -> bool:
    """Return ``True`` if scraping *url* is permitted by robots.txt."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return True

    domain = parsed.netloc
    cached = _ROBOTS_CACHE.get(domain)
    if isinstance(cached, RobotFileParser):
        return cached.can_fetch(DEFAULT_USER_AGENT, url)
    if cached is False:
        return True

    lock = _ROBOTS_LOCKS.setdefault(domain, asyncio.Lock())
    async with lock:
        cached = _ROBOTS_CACHE.get(domain)
        if isinstance(cached, RobotFileParser):
            return cached.can_fetch(DEFAULT_USER_AGENT, url)
        if cached is False:
            return True

        parser = RobotFileParser()
        parser.set_url(f"{parsed.scheme}://{domain}/robots.txt")
        try:
            await asyncio.to_thread(parser.read)
        except Exception:  # pragma: no cover - network hiccups tolerated
            _ROBOTS_CACHE[domain] = False
            return True

        _ROBOTS_CACHE[domain] = parser
        return parser.can_fetch(DEFAULT_USER_AGENT, url)


def _fetch_sync(url: str) -> bytes:
    """Blocking helper executed in a thread to download *url*."""

    request = _build_request(url)
    with urllib_request.urlopen(request) as response:  # type: ignore[arg-type]
        return response.read()


async def _download(
    url: str,
    cache_dir: Path,
    limiter: DomainRateLimiter,
) -> Tuple[str, str | None]:
    """Download *url* if necessary and return the cached path."""

    cache_file = _cache_path(cache_dir, url)
    if cache_file.exists():
        await asyncio.to_thread(_ensure_metadata_from_cache, cache_dir, url)
        logger.debug("cache hit for %s -> %s", url, cache_file)
        return url, str(cache_file)

    domain = urlparse(url).netloc
    if not await _robots_allowed(url):
        logger.info("robots.txt disallows scraping %s", url)
        return url, None

    await limiter.wait(domain)

    try:
        content = await asyncio.to_thread(_fetch_sync, url)
    except URLError as exc:
        logger.warning("failed to fetch %s: %s", url, exc.reason)
        return url, None
    except Exception as exc:  # pragma: no cover - unexpected network failure
        logger.warning("failed to fetch %s: %s", url, exc)
        return url, None

    cache_file.write_bytes(content)
    await asyncio.to_thread(_write_metadata, cache_dir, url, content)
    logger.info("fetched %s -> %s", url, cache_file)
    return url, str(cache_file)


async def scrape_all(
    urls: Iterable[str],
    cache_dir: str | Path | None = None,
    *,
    concurrency: int | None = None,
    rate_per_domain: float | None = None,
) -> Dict[str, str]:
    """Fetch *urls* concurrently and return a mapping to cached files.

    Parameters
    ----------
    urls:
        Iterable of URLs to download.
    cache_dir:
        Optional destination directory for cached responses. When omitted the
        cache directory declared in the configuration (``[scraper].cache_dir``)
        or its fallback (``datasets/raw``) is used. The directory is created
        automatically when missing.
    concurrency:
        Optional override for the number of parallel downloads. When omitted the
        value defined in the configuration (``[scraper].concurrency``) is used,
        falling back to ``5``.
    rate_per_domain:
        Optional override for the minimum delay (in seconds) between two
        requests to the same domain. Defaults to the configuration value or
        ``1.0`` seconds.
    """

    if concurrency is None:
        concurrency = DEFAULT_CONCURRENCY
    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    if rate_per_domain is None:
        rate_per_domain = RATE_PER_DOMAIN
    else:
        rate_per_domain = max(0.0, rate_per_domain)

    selected_cache_dir = Path(cache_dir) if cache_dir is not None else _DEFAULT_CACHE_DIR
    selected_cache_dir.mkdir(parents=True, exist_ok=True)

    limiter = DomainRateLimiter(delay=rate_per_domain)
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(url: str) -> Tuple[str, str | None]:
        async with semaphore:
            return await _download(url, selected_cache_dir, limiter)

    tasks = [asyncio.create_task(_run(url)) for url in urls]
    results = await asyncio.gather(*tasks)
    return {url: path for url, path in results if path is not None}


async def scrape(
    urls: Iterable[str],
    concurrency: int | None = None,
    *,
    cache_dir: str | Path | None = None,
    rate_per_domain: float | None = None,
) -> List[str | None]:
    """Compatibility wrapper returning cached file paths in input order.

    The helper mirrors the historic :func:`scrape` coroutine by yielding cached
    file paths in the same order as *urls*. It transparently picks up defaults
    from the configuration when explicit values are not provided.
    """

    selected_cache_dir = Path(cache_dir) if cache_dir is not None else _DEFAULT_CACHE_DIR
    mapping = await scrape_all(
        urls,
        selected_cache_dir,
        concurrency=concurrency,
        rate_per_domain=rate_per_domain,
    )
    return [mapping.get(url) for url in urls]


def refresh_defaults() -> None:
    """Re-read configuration so future calls use the latest defaults."""

    _resolve_defaults.cache_clear()
    _refresh_defaults()


_refresh_defaults()


__all__ = ["scrape_all", "scrape", "DomainRateLimiter", "refresh_defaults"]
