"""Data collection utilities for the Watcher project.

This module provides a minimal framework for gathering new training
examples from open datasets or by scraping the web. Actual download and
scraping logic is intentionally simple and offline to comply with the
execution environment. The design ensures that any real network access is
performed under human supervision and with proper licence checks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable
import urllib.parse


class DataCollector:
    """Prepare dataset directories and keep a record of sources.

    The collector only creates local folders for each known dataset. The
    user is expected to download the data manually in order to respect
    licences and robots.txt rules. The available sources correspond to
    popular open datasets useful for code-oriented assistants.
    """

    SOURCES: Dict[str, str] = {
        "the_stack": "https://huggingface.co/datasets/bigcode/the-stack",
        "codesearchnet": "https://github.com/github/CodeSearchNet",
        "stack_overflow": "https://archive.org/details/stackexchange",
        "common_crawl": "https://commoncrawl.org/",
        "kaggle": "https://www.kaggle.com/datasets",
    }

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def prepare(self) -> Dict[str, str]:
        """Create folders for each dataset source and return their paths."""
        mapping: Dict[str, str] = {}
        for name in self.SOURCES:
            path = self.root / name
            path.mkdir(parents=True, exist_ok=True)
            mapping[name] = str(path)
        return mapping

    def scrape(self, urls: Iterable[str]) -> Path:
        """Placeholder web scraping routine.

        For each URL the caller must ensure that scraping is permitted by
        the site's robots.txt and licence. This function simply logs the
        intent to scrape and returns the log file path.
        """

        log = self.root / "scrape.log"
        lines = []
        for u in urls:
            parsed = urllib.parse.urlparse(u)
            lines.append(f"SKIP {parsed.geturl()}\n")
        log.write_text("".join(lines), encoding="utf-8")
        return log
