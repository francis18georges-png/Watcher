"""Lightweight helpers to gather GitHub repository metadata."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse

from .http import HTTPScraper


@dataclass
class RepositoryInfo:
    """Summary of a GitHub repository."""

    repository: str
    url: str
    license: Optional[str]
    metadata: Dict[str, object]


class GitHubScraper:
    """Fetch metadata from the GitHub REST API."""

    def __init__(self, http: HTTPScraper, *, api_base: str = "https://api.github.com") -> None:
        self.http = http
        self.api_base = api_base.rstrip("/")

    def fetch_repository(self, repo: str) -> Optional[RepositoryInfo]:
        """Return metadata for *repo* (``owner/name`` or URL)."""

        owner, name = self._parse_repository(repo)
        if owner is None or name is None:
            return None
        api_url = f"{self.api_base}/repos/{owner}/{name}"
        payload = self.http.fetch_raw(api_url, respect_robots=False)
        if payload is None:
            return None
        raw, _ = payload
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

        license_name: Optional[str] = None
        license_info = data.get("license") if isinstance(data, dict) else None
        if isinstance(license_info, dict):
            license_name = (
                license_info.get("spdx_id")
                or license_info.get("name")
                or license_info.get("key")
            )
        return RepositoryInfo(
            repository=f"{owner}/{name}",
            url=f"https://github.com/{owner}/{name}",
            license=license_name,
            metadata=data if isinstance(data, dict) else {},
        )

    def _parse_repository(self, repo: str) -> tuple[Optional[str], Optional[str]]:
        if "/" not in repo or repo.endswith("/"):
            parsed = urlparse(repo)
            if not parsed.netloc:
                return None, None
            parts = parsed.path.strip("/").split("/")
        else:
            parts = repo.strip("/").split("/")
        if len(parts) < 2:
            return None, None
        owner, name = parts[0], parts[1]
        if not owner or not name:
            return None, None
        return owner, name


__all__ = ["GitHubScraper", "RepositoryInfo"]
