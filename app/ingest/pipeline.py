"""Ingestion pipeline orchestrating validation and vector store writes."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence
from urllib.parse import urlparse

from app.embeddings.store import SimpleVectorStore
from app.ingest.source_registry import KnowledgeStatus

__all__ = [
    "RawDocument",
    "IngestValidationError",
    "IngestPipeline",
]


_ALLOWED_LICENCES = {
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "MIT",
    "Apache-2.0",
}


@dataclass(slots=True)
class RawDocument:
    """Description of a document to ingest before processing."""

    url: str
    title: str
    text: str
    licence: str
    published_at: datetime | None = None
    source_type: str = "web"
    language: str | None = None
    fetched_at: datetime | None = None
    etag: str | None = None
    last_modified: str | None = None


@dataclass(frozen=True, slots=True)
class _ChunkingConfig:
    size: int
    overlap: int

    @classmethod
    def from_values(
        cls,
        *,
        chunk_size: int,
        chunk_overlap: int | None,
    ) -> "_ChunkingConfig":
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if chunk_size == 1:
            overlap = 0
        elif chunk_overlap is None:
            overlap = min(64, max(1, chunk_size // 5))
        else:
            overlap = int(chunk_overlap)
        if overlap < 0:
            raise ValueError("chunk_overlap must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("chunk_overlap must be < chunk_size")
        return cls(size=int(chunk_size), overlap=overlap)


class IngestValidationError(ValueError):
    """Raised when documents fail ingestion validation rules."""


@dataclass(slots=True)
class _ChunkCandidate:
    text: str
    url: str
    title: str
    licence: str
    published_at: datetime | None
    language: str
    digest: str
    source_type: str
    fetched_at: datetime | None
    etag: str | None
    last_modified: str | None


class IngestPipeline:
    """Validate, normalise and persist documents into the vector store."""

    def __init__(
        self,
        store: SimpleVectorStore,
        *,
        chunk_size: int = 512,
        chunk_overlap: int | None = None,
        min_sources: int = 2,
        allowed_licences: Iterable[str] | None = None,
    ) -> None:
        if min_sources < 2:
            raise ValueError("min_sources must be >= 2")
        self.store = store
        self._chunking = _ChunkingConfig.from_values(
            chunk_size=int(chunk_size),
            chunk_overlap=chunk_overlap,
        )
        self.chunk_size = self._chunking.size
        self.chunk_overlap = self._chunking.overlap
        self.min_sources = int(min_sources)
        self.allowed_licences = set(allowed_licences or _ALLOWED_LICENCES)

    # ------------------------------------------------------------------
    # Public API

    def ingest(
        self,
        documents: Sequence[RawDocument],
        *,
        seen_digests: set[str] | None = None,
    ) -> int:
        """Normalise *documents* and write unique chunks to the vector store."""

        if not documents:
            raise IngestValidationError("Aucun document fourni pour ingestion.")

        candidates = self._prepare_candidates(documents)
        if not candidates:
            raise IngestValidationError("Aucun extrait valide après normalisation.")

        grouped = defaultdict(list)
        for candidate in candidates:
            if candidate.licence not in self.allowed_licences:
                continue
            grouped[candidate.digest].append(candidate)

        prepared_texts: list[str] = []
        prepared_meta: list[dict[str, object]] = []

        seen = seen_digests if seen_digests is not None else set()

        for digest, items in grouped.items():
            sources = {item.url for item in items}
            if len(sources) < self.min_sources:
                continue
            if digest in seen:
                continue
            corroborating_sources = len(sources)
            score = self._compute_confidence(corroborating_sources)
            representative = self._select_representative(items)
            metadata = self._build_metadata(
                representative=representative,
                digest=digest,
                corroborating_sources=corroborating_sources,
                confidence_score=score,
            )
            prepared_texts.append(representative.text)
            prepared_meta.append(metadata)
            seen.add(digest)

        if not prepared_texts:
            raise IngestValidationError(
                "Aucune source corroborée avec une licence compatible n'a été trouvée."
            )

        self.store.add(prepared_texts, prepared_meta)
        return len(prepared_texts)

    # ------------------------------------------------------------------
    # Internal helpers

    def _prepare_candidates(
        self, documents: Sequence[RawDocument]
    ) -> list[_ChunkCandidate]:
        candidates: list[_ChunkCandidate] = []
        for document in documents:
            normalised = _normalise_text(document.text)
            if not normalised:
                continue
            language = document.language or _detect_language(normalised)
            for chunk in _chunk_text(normalised, self.chunk_size, self.chunk_overlap):
                digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
                candidates.append(
                    _ChunkCandidate(
                        text=chunk,
                        url=document.url,
                        title=document.title,
                        licence=document.licence,
                        published_at=document.published_at,
                        language=language,
                        digest=digest,
                        source_type=document.source_type,
                        fetched_at=document.fetched_at,
                        etag=document.etag,
                        last_modified=document.last_modified,
                    )
                )
        return candidates

    @staticmethod
    def _select_representative(items: Sequence[_ChunkCandidate]) -> _ChunkCandidate:
        return min(
            items,
            key=lambda item: (
                item.published_at or datetime.max,
                item.url,
            ),
        )

    def _compute_confidence(self, corroborating_sources: int) -> float:
        base = 0.6
        increment = 0.1
        score = base + (corroborating_sources - self.min_sources) * increment
        return round(min(1.0, score), 2)

    def _build_metadata(
        self,
        *,
        representative: _ChunkCandidate,
        digest: str,
        corroborating_sources: int,
        confidence_score: float,
    ) -> dict[str, object]:
        metadata: dict[str, object] = {
            "source": representative.url,
            "url": representative.url,
            "title": representative.title,
            "licence": representative.licence,
            "hash": digest,
            "language": representative.language,
            "source_type": representative.source_type,
            "corroborating_sources": corroborating_sources,
            "confidence_score": confidence_score,
            "knowledge_state": KnowledgeStatus.PROMOTED.value,
            # Compatibility aliases kept for existing callers/consumers.
            "confidence": confidence_score,
            "score": confidence_score,
            "status": KnowledgeStatus.PROMOTED.value,
        }
        domain = _domain_from_url(representative.url)
        if domain is not None:
            metadata["domain"] = domain
        if representative.published_at is not None:
            published_iso = representative.published_at.isoformat()
            metadata["date"] = published_iso
            metadata["freshness_at"] = published_iso
        if representative.fetched_at is not None:
            metadata["fetched_at"] = representative.fetched_at.isoformat()
        if representative.etag:
            metadata["etag"] = representative.etag
        if representative.last_modified:
            metadata["last_modified"] = representative.last_modified
        return metadata


def _normalise_text(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text


def _detect_language(text: str) -> str:
    if not text:
        return "unknown"
    lowered = text.lower()
    french_markers = {" le ", " la ", " les ", " une ", " des ", " et "}
    english_markers = {" the ", " and ", " of ", " to ", " with "}
    fr_hits = sum(marker in lowered for marker in french_markers)
    en_hits = sum(marker in lowered for marker in english_markers)
    if fr_hits > en_hits:
        return "fr"
    if en_hits > fr_hits:
        return "en"
    return "unknown"


def _chunk_text(text: str, chunk_size: int, chunk_overlap: int = 0) -> list[str]:
    words = text.split(" ")
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size - max(0, chunk_overlap))
    for start in range(0, len(words), step):
        segment = " ".join(words[start : start + chunk_size]).strip()
        if segment:
            chunks.append(segment)
        if start + chunk_size >= len(words):
            break
    return chunks


def _domain_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    return hostname or None
