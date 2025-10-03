"""Ingestion pipeline orchestrating validation and vector store writes."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from app.embeddings.store import SimpleVectorStore

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


class IngestPipeline:
    """Validate, normalise and persist documents into the vector store."""

    def __init__(
        self,
        store: SimpleVectorStore,
        *,
        chunk_size: int = 512,
        min_sources: int = 2,
        allowed_licences: Iterable[str] | None = None,
    ) -> None:
        if chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if min_sources < 2:
            raise ValueError("min_sources must be >= 2")
        self.store = store
        self.chunk_size = int(chunk_size)
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
            score = self._compute_confidence(len(sources))
            representative = self._select_representative(items)
            metadata: dict[str, object] = {
                "url": representative.url,
                "title": representative.title,
                "licence": representative.licence,
                "hash": digest,
                "score": score,
            }
            if representative.published_at is not None:
                metadata["date"] = representative.published_at.isoformat()
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
            language = _detect_language(normalised)
            for chunk in _chunk_text(normalised, self.chunk_size):
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


def _chunk_text(text: str, chunk_size: int) -> list[str]:
    words = text.split(" ")
    if not words:
        return []
    chunks: list[str] = []
    step = max(1, chunk_size)
    for start in range(0, len(words), step):
        segment = " ".join(words[start : start + step]).strip()
        if segment:
            chunks.append(segment)
    return chunks
