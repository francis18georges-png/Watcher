"""Asynchronous web scraping utilities with caching.

This module provides a minimal asynchronous scraper that fetches content
from URLs concurrently and caches results on disk.  It avoids re-downloading
previously seen URLs and offers simple error handling via the standard
:mod:`logging` package.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Dict, Iterable
from urllib import request as urllib_request


def _hash_url(url: str) -> str:
    """Return a filename-safe hash for *url*."""

    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _download_sync(url: str) -> str:
    """Synchronously download *url* and return decoded text.

    The function is executed in a thread pool via
    :func:`asyncio.get_running_loop().run_in_executor` allowing multiple
    downloads to proceed concurrently without requiring external
    dependencies.
    """

    with urllib_request.urlopen(url) as resp:  # pragma: no cover - network
        return resp.read().decode("utf-8")


async def fetch(url: str, cache_dir: Path) -> str:
    """Fetch *url* asynchronously with a simple on-disk cache.

    Parameters
    ----------
    url:
        The URL to retrieve.
    cache_dir:
        Directory where cached responses are stored.  Files are named using
        the SHA256 hash of the URL.
    """

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / _hash_url(url)
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    loop = asyncio.get_running_loop()
    try:
        text = await loop.run_in_executor(None, _download_sync, url)
    except Exception:  # pragma: no cover - network errors
        logging.exception("scrape failed for %s", url)
        raise
    cache_file.write_text(text, encoding="utf-8")
    return text


async def scrape_all(
    urls: Iterable[str], cache_dir: Path, *, concurrency: int = 5
) -> Dict[str, str]:
    """Concurrently scrape *urls* and return a mapping of URL to content.

    Downloads are limited by *concurrency* using an :class:`asyncio.Semaphore`.
    Results are cached via :func:`fetch` and returned as a dictionary.
    """

    sem = asyncio.Semaphore(concurrency)
    results: Dict[str, str] = {}

    async def _scrape(url: str) -> None:
        async with sem:
            results[url] = await fetch(url, cache_dir)

    await asyncio.gather(*(_scrape(u) for u in urls))
    return results
