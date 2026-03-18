"""Targeted GitHub collection helpers for programming-oriented sources."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any, Dict, Optional, Sequence
from urllib.parse import urlparse

from .http import HTTPScraper

_STANDARD_CHANGELOG_PATHS: tuple[str, ...] = (
    "CHANGELOG.md",
    "CHANGES.md",
    "NEWS.md",
)
_STANDARD_DOC_PATHS: tuple[str, ...] = (
    "README.md",
    "docs/README.md",
    "docs/index.md",
)
_ALLOWED_REFERENCE_SUFFIXES: tuple[str, ...] = (
    ".md",
    ".rst",
    ".txt",
    ".adoc",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".go",
    ".rs",
)
_MAX_CONTENT_BYTES = 200_000


@dataclass(frozen=True, slots=True)
class RepositorySpec:
    """Normalised repository target plus explicit file allowlist."""

    owner: str
    name: str
    explicit_paths: tuple[str, ...] = ()

    @property
    def repository(self) -> str:
        return f"{self.owner}/{self.name}"


@dataclass(slots=True)
class RepositoryInfo:
    """Summary of a GitHub repository."""

    repository: str
    url: str
    license: Optional[str]
    default_branch: str
    description: str | None
    metadata: Dict[str, object]
    payload_bytes: int = 0


@dataclass(slots=True)
class GitHubContentItem:
    """Targeted GitHub content eligible for ingestion."""

    repository: str
    kind: str
    path: str
    url: str
    title: str
    summary: str
    content: str
    license: Optional[str]
    published_at: datetime | None
    fetched_at: datetime
    etag: str | None
    last_modified: str | None
    payload_bytes: int

    @property
    def source_type(self) -> str:
        return f"git-{self.kind}"


@dataclass(slots=True)
class GitHubProgrammingBundle:
    """Repository metadata plus targeted programming corpus."""

    repository: RepositoryInfo
    documents: list[GitHubContentItem]
    payload_bytes: int


class GitHubScraper:
    """Fetch targeted GitHub programming sources from the REST API."""

    def __init__(self, http: HTTPScraper, *, api_base: str = "https://api.github.com") -> None:
        self.http = http
        self.api_base = api_base.rstrip("/")

    def fetch_repository(self, repo: str) -> Optional[RepositoryInfo]:
        """Return metadata for *repo* (``owner/name`` or ``owner/name:path``)."""

        spec = self._parse_repository_spec(repo)
        if spec is None:
            return None
        api_url = f"{self.api_base}/repos/{spec.owner}/{spec.name}"
        payload = self._fetch_json(api_url)
        if payload is None:
            return None
        data, _headers, payload_bytes = payload

        license_name: Optional[str] = None
        license_info = data.get("license") if isinstance(data, dict) else None
        if isinstance(license_info, dict):
            license_name = (
                license_info.get("spdx_id")
                or license_info.get("name")
                or license_info.get("key")
            )
        default_branch = str(data.get("default_branch", "HEAD") or "HEAD")
        description = data.get("description")
        return RepositoryInfo(
            repository=spec.repository,
            url=f"https://github.com/{spec.repository}",
            license=license_name,
            default_branch=default_branch,
            description=str(description).strip() if description else None,
            metadata=data if isinstance(data, dict) else {},
            payload_bytes=payload_bytes,
        )

    def fetch_programming_bundle(self, repo: str) -> Optional[GitHubProgrammingBundle]:
        """Return a targeted programming corpus for an explicitly allowed repository."""

        spec = self._parse_repository_spec(repo)
        if spec is None:
            return None
        repository = self.fetch_repository(repo)
        if repository is None:
            return None

        payload_total = repository.payload_bytes
        documents: list[GitHubContentItem] = []

        release = self._fetch_latest_release(spec, repository)
        if release is not None:
            documents.append(release)
            payload_total += release.payload_bytes

        for path in self._candidate_paths(spec):
            item = self._fetch_repository_file(spec, repository, path)
            if item is None:
                continue
            documents.append(item)
            payload_total += item.payload_bytes

        return GitHubProgrammingBundle(
            repository=repository,
            documents=documents,
            payload_bytes=payload_total,
        )

    def _fetch_latest_release(
        self,
        spec: RepositorySpec,
        repository: RepositoryInfo,
    ) -> GitHubContentItem | None:
        api_url = f"{self.api_base}/repos/{spec.owner}/{spec.name}/releases/latest"
        payload = self._fetch_json(api_url)
        if payload is None:
            return None
        data, headers, payload_bytes = payload
        body = str(data.get("body", "") or "").strip()
        if not body:
            return None
        tag = str(data.get("tag_name", "") or "").strip()
        html_url = str(data.get("html_url", "") or repository.url)
        title = str(data.get("name", "") or tag or f"{repository.repository} latest release").strip()
        published_at = _parse_datetime(data.get("published_at"))
        return GitHubContentItem(
            repository=repository.repository,
            kind="release",
            path=f"release:{tag or 'latest'}",
            url=html_url,
            title=title,
            summary=_summarise_text(body),
            content=body,
            license=repository.license,
            published_at=published_at,
            fetched_at=datetime.now(timezone.utc),
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
            payload_bytes=payload_bytes,
        )

    def _fetch_repository_file(
        self,
        spec: RepositorySpec,
        repository: RepositoryInfo,
        path: str,
    ) -> GitHubContentItem | None:
        if not self._is_supported_path(path):
            return None
        api_url = (
            f"{self.api_base}/repos/{spec.owner}/{spec.name}/contents/{path}"
            f"?ref={repository.default_branch}"
        )
        payload = self._fetch_json(api_url)
        if payload is None:
            return None
        data, headers, payload_bytes = payload
        size = int(data.get("size", 0) or 0)
        if size <= 0 or size > _MAX_CONTENT_BYTES:
            return None
        if str(data.get("type", "") or "") != "file":
            return None
        encoding = str(data.get("encoding", "") or "")
        if encoding != "base64":
            return None
        content_blob = str(data.get("content", "") or "")
        try:
            decoded = base64.b64decode(content_blob, validate=False)
            text = decoded.decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None
        cleaned = text.strip()
        if not cleaned:
            return None
        html_url = str(data.get("html_url", "") or repository.url)
        kind = self._classify_path(path, explicit=path in spec.explicit_paths)
        return GitHubContentItem(
            repository=repository.repository,
            kind=kind,
            path=path,
            url=html_url,
            title=f"{repository.repository}:{path}",
            summary=_summarise_text(cleaned),
            content=cleaned,
            license=repository.license,
            published_at=None,
            fetched_at=datetime.now(timezone.utc),
            etag=headers.get("etag"),
            last_modified=headers.get("last-modified"),
            payload_bytes=payload_bytes,
        )

    def _fetch_json(
        self,
        url: str,
    ) -> tuple[dict[str, Any], dict[str, str], int] | None:
        # The GitHub REST API is used only for repository-level, explicitly
        # targeted resources under ``scope=git``.
        payload = self.http.fetch_raw(url, respect_robots=False)
        if payload is None:
            return None
        raw, headers = payload
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        return data, {str(k).lower(): str(v) for k, v in headers.items()}, len(raw)

    def _candidate_paths(self, spec: RepositorySpec) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        for path in (*_STANDARD_CHANGELOG_PATHS, *_STANDARD_DOC_PATHS, *spec.explicit_paths):
            normalised = _normalise_path(path)
            if normalised is None or normalised in seen:
                continue
            seen.add(normalised)
            ordered.append(normalised)
        return ordered

    def _parse_repository_spec(self, repo: str) -> RepositorySpec | None:
        text = repo.strip()
        explicit_paths: tuple[str, ...] = ()
        repo_candidate = text
        if "://" not in text and ":" in text:
            maybe_repo, maybe_paths = text.split(":", 1)
            if maybe_repo.count("/") >= 1:
                repo_candidate = maybe_repo.strip()
                explicit_paths = tuple(
                    path
                    for path in (
                        _normalise_path(item)
                        for item in maybe_paths.split(",")
                    )
                    if path is not None
                )
        owner, name = self._parse_repository(repo_candidate)
        if owner is None or name is None:
            return None
        return RepositorySpec(owner=owner, name=name, explicit_paths=explicit_paths)

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

    @staticmethod
    def _is_supported_path(path: str) -> bool:
        suffix = PurePosixPath(path).suffix.lower()
        return suffix in _ALLOWED_REFERENCE_SUFFIXES

    @staticmethod
    def _classify_path(path: str, *, explicit: bool) -> str:
        lowered = path.lower()
        if explicit:
            return "reference"
        if lowered in {item.lower() for item in _STANDARD_CHANGELOG_PATHS}:
            return "changelog"
        return "documentation"


def _normalise_path(path: str) -> str | None:
    text = path.strip().strip("/")
    if not text:
        return None
    pure = PurePosixPath(text)
    if pure.is_absolute():
        return None
    if ".." in pure.parts:
        return None
    return pure.as_posix()


def _summarise_text(text: str, *, limit: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = [
    "GitHubContentItem",
    "GitHubProgrammingBundle",
    "GitHubScraper",
    "RepositoryInfo",
    "RepositorySpec",
]
