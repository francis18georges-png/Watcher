"""Utilities to work with XML sitemaps."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import List

from .http import HTTPScraper


class SitemapScraper:
    """Parse sitemap XML documents into URL lists."""

    def __init__(self, http: HTTPScraper) -> None:
        self.http = http

    def fetch(self, sitemap_url: str) -> List[str]:
        """Download *sitemap_url* and return contained URLs."""

        payload = self.http.fetch_raw(sitemap_url, respect_robots=False)
        if payload is None:
            return []
        raw, _ = payload
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []

        urls: List[str] = []
        for loc in root.findall(".//{*}loc"):
            if loc.text:
                candidate = loc.text.strip()
                if candidate:
                    urls.append(candidate)
        return urls


__all__ = ["SitemapScraper"]
