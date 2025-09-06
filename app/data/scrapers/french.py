"""Helpers for scraping French text sources."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Iterable

from ..scraper import scrape_all

# Default small set of French pages under permissive licences. These are merely
# examples and can be replaced or extended by configuration.
DEFAULT_URLS = {
    "https://www.gutenberg.org/cache/epub/2000/pg2000.html",  # Les Misérables
}


async def _async_fetch(urls: Iterable[str], cache_dir: Path) -> Dict[str, str]:
    return await scrape_all(urls, cache_dir)


def fetch_french_corpus(urls: Iterable[str] | None, cache_dir: Path) -> Dict[str, str]:
    """Retrieve French texts from *urls*.

    Parameters
    ----------
    urls:
        Iterable of URLs to download. When ``None`` the :data:`DEFAULT_URLS`
        collection is used.
    cache_dir:
        Directory where responses are cached.
    """

    urls = urls or DEFAULT_URLS
    return asyncio.run(_async_fetch(urls, cache_dir))
