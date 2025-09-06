"""Helpers for scraping programming documentation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Dict, Iterable

from ..scraper import scrape_all

# Default documentation pages in English; chosen for permissive licences and
# short size. These URLs are placeholders and can be adjusted.
DEFAULT_URLS = {
    "https://docs.python.org/3/",  # Python documentation index
}


async def _async_fetch(urls: Iterable[str], cache_dir: Path) -> Dict[str, str]:
    return await scrape_all(urls, cache_dir)


def fetch_programming_docs(
    urls: Iterable[str] | None, cache_dir: Path
) -> Dict[str, str]:
    """Download programming documentation pages.

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
