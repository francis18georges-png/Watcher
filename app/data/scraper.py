"""Concurrent web scraper with simple filesystem caching.

The :func:`scrape_all` coroutine downloads a collection of URLs, stores the
responses on disk and returns a mapping of source URL to cached file path.  The
implementation purposely relies on :mod:`urllib` only so it remains easy to
monkeypatch in tests and works in constrained offline environments.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib import request as urllib_request
from urllib.error import URLError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

RATE_PER_DOMAIN = 1.0  # seconds between two requests to the same domain
_CACHE_SUFFIX = ".html"
_DEFAULT_CACHE_DIR = Path("datasets/raw")


class DomainRateLimiter:
    """Co-ordinate access to individual domains."""

    def __init__(self, delay: float = RATE_PER_DOMAIN):
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


def _fetch_sync(url: str) -> bytes:
    """Blocking helper executed in a thread to download *url*."""

    with urllib_request.urlopen(url) as response:  # type: ignore[arg-type]
        return response.read()


async def _download(
    url: str,
    cache_dir: Path,
    limiter: DomainRateLimiter,
) -> Tuple[str, str | None]:
    """Download *url* if necessary and return the cached path."""

    cache_file = _cache_path(cache_dir, url)
    if cache_file.exists():
        logger.debug("cache hit for %s -> %s", url, cache_file)
        return url, str(cache_file)

    domain = urlparse(url).netloc
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
    logger.info("fetched %s -> %s", url, cache_file)
    return url, str(cache_file)


async def scrape_all(
    urls: Iterable[str],
    cache_dir: Path,
    *,
    concurrency: int = 5,
) -> Dict[str, str]:
    """Fetch *urls* concurrently and return a mapping to cached files."""

    if concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    limiter = DomainRateLimiter()
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(url: str) -> Tuple[str, str | None]:
        async with semaphore:
            return await _download(url, cache_dir, limiter)

    tasks = [asyncio.create_task(_run(url)) for url in urls]
    results = await asyncio.gather(*tasks)
    return {url: path for url, path in results if path is not None}


async def scrape(
    urls: Iterable[str],
    concurrency: int = 5,
    *,
    cache_dir: str | Path | None = None,
) -> List[str | None]:
    """Compatibility wrapper returning cached file paths in input order."""

    selected_cache_dir = Path(cache_dir) if cache_dir is not None else _DEFAULT_CACHE_DIR
    mapping = await scrape_all(urls, selected_cache_dir, concurrency=concurrency)
    return [mapping.get(url) for url in urls]


__all__ = ["scrape_all", "scrape", "DomainRateLimiter"]
