"""Minimal source registry for the Phase 1 knowledge flow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

__all__ = [
    "KnowledgeStatus",
    "SourceRegistry",
    "SourceRegistryEntry",
]


class KnowledgeStatus(str, Enum):
    """Knowledge states used by the first controlled learning slice."""

    RAW = "raw"
    VALIDATED = "validated"
    PROMOTED = "promoted"


@dataclass(slots=True)
class SourceRegistryEntry:
    """Persisted source record used to track knowledge promotion."""

    source: str
    source_type: str
    confidence: float
    freshness_at: str | None
    licence: str | None
    status: KnowledgeStatus
    first_seen_at: str
    updated_at: str
    corroborating_sources: int | None = None
    status_reason: str | None = None
    evaluation_status: str | None = None
    evaluation_score: float | None = None
    evaluation_reason: str | None = None

    @property
    def status_note(self) -> str | None:
        """Backward-compatible alias for older callers/tests."""

        return self.status_reason

    @status_note.setter
    def status_note(self, value: str | None) -> None:
        self.status_reason = _normalise_optional_text(value)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "freshness_at": self.freshness_at,
            "licence": self.licence,
            "status": self.status.value,
            "first_seen_at": self.first_seen_at,
            "updated_at": self.updated_at,
            "corroborating_sources": self.corroborating_sources,
            "status_reason": self.status_reason,
            "status_note": self.status_reason,
            "evaluation_status": self.evaluation_status,
            "evaluation_score": self.evaluation_score,
            "evaluation_reason": self.evaluation_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceRegistryEntry":
        status_value = str(data.get("status", KnowledgeStatus.RAW.value))
        try:
            status = KnowledgeStatus(status_value)
        except ValueError:
            status = KnowledgeStatus.RAW
        return cls(
            source=str(data.get("source", "")),
            source_type=str(data.get("source_type", "web")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            freshness_at=_normalise_optional_text(data.get("freshness_at")),
            licence=_normalise_optional_text(data.get("licence")),
            status=status,
            first_seen_at=str(data.get("first_seen_at", _timestamp(datetime.now(timezone.utc)))),
            updated_at=str(data.get("updated_at", _timestamp(datetime.now(timezone.utc)))),
            corroborating_sources=_normalise_optional_int(data.get("corroborating_sources")),
            status_reason=_normalise_optional_text(
                data.get("status_reason", data.get("status_note"))
            ),
            evaluation_status=_normalise_optional_text(data.get("evaluation_status")),
            evaluation_score=_normalise_optional_float(data.get("evaluation_score")),
            evaluation_reason=_normalise_optional_text(data.get("evaluation_reason")),
        )


class SourceRegistry:
    """JSON-backed registry of authorised sources and knowledge states."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries = self._load()

    def record(
        self,
        *,
        source: str,
        source_type: str,
        status: KnowledgeStatus,
        confidence: float = 0.0,
        freshness_at: datetime | str | None = None,
        licence: str | None = None,
        corroborating_sources: int | None = None,
        status_reason: str | None = None,
        status_note: str | None = None,
        evaluation_status: str | None = None,
        evaluation_score: float | None = None,
        evaluation_reason: str | None = None,
        observed_at: datetime | None = None,
    ) -> SourceRegistryEntry:
        source_key = source.strip()
        if not source_key:
            raise ValueError("source must not be empty")
        current_time = observed_at or datetime.now(timezone.utc)
        now_iso = _timestamp(current_time)
        resolved_reason = _normalise_optional_text(status_reason or status_note)
        resolved_corroboration = _normalise_optional_int(corroborating_sources)
        resolved_evaluation_status = _normalise_optional_text(evaluation_status)
        resolved_evaluation_score = _normalise_optional_float(evaluation_score)
        resolved_evaluation_reason = _normalise_optional_text(evaluation_reason)
        entry = self._entries.get(source_key)
        if entry is None:
            entry = SourceRegistryEntry(
                source=source_key,
                source_type=source_type.strip() or "web",
                confidence=max(0.0, float(confidence)),
                freshness_at=_coerce_freshness(freshness_at),
                licence=_normalise_optional_text(licence),
                status=status,
                first_seen_at=now_iso,
                updated_at=now_iso,
                corroborating_sources=resolved_corroboration,
                status_reason=resolved_reason,
                evaluation_status=resolved_evaluation_status,
                evaluation_score=resolved_evaluation_score,
                evaluation_reason=resolved_evaluation_reason,
            )
        else:
            current_rank = _status_rank(entry.status)
            incoming_rank = _status_rank(status)
            entry.source_type = source_type.strip() or entry.source_type or "web"
            entry.confidence = max(entry.confidence, float(confidence))
            entry.freshness_at = _coerce_freshness(freshness_at) or entry.freshness_at
            entry.licence = _normalise_optional_text(licence) or entry.licence
            entry.updated_at = now_iso
            entry.status = _max_status(entry.status, status)
            if incoming_rank >= current_rank:
                if incoming_rank > current_rank:
                    entry.status = status
                if resolved_reason is not None:
                    entry.status_reason = resolved_reason
                elif incoming_rank > current_rank:
                    entry.status_reason = None
                if resolved_corroboration is not None:
                    if entry.corroborating_sources is None or incoming_rank > current_rank:
                        entry.corroborating_sources = resolved_corroboration
                    else:
                        entry.corroborating_sources = max(
                            entry.corroborating_sources,
                            resolved_corroboration,
                        )
                elif incoming_rank > current_rank:
                    entry.corroborating_sources = None
                if resolved_evaluation_status is not None:
                    entry.evaluation_status = resolved_evaluation_status
                if resolved_evaluation_score is not None:
                    entry.evaluation_score = resolved_evaluation_score
                if resolved_evaluation_reason is not None:
                    entry.evaluation_reason = resolved_evaluation_reason
        self._entries[source_key] = entry
        self._save()
        return entry

    def reject(
        self,
        *,
        source: str,
        source_type: str,
        reason: str,
        confidence: float = 0.0,
        freshness_at: datetime | str | None = None,
        licence: str | None = None,
        corroborating_sources: int | None = None,
        observed_at: datetime | None = None,
    ) -> SourceRegistryEntry:
        """Record a rejected item while keeping it out of validated/promoted states."""

        reason_text = f"rejected: {reason.strip()}"
        return self.record(
            source=source,
            source_type=source_type,
            status=KnowledgeStatus.RAW,
            confidence=confidence,
            freshness_at=freshness_at,
            licence=licence,
            corroborating_sources=corroborating_sources,
            status_reason=reason_text,
            observed_at=observed_at,
        )

    def revoke_domains(
        self,
        *,
        domains: list[str] | tuple[str, ...] | set[str],
        reason: str,
        observed_at: datetime | None = None,
    ) -> list[SourceRegistryEntry]:
        """Mark tracked validated/promoted entries as revoked for *domains*."""

        revoked_domains = {
            domain.strip().lower()
            for domain in domains
            if isinstance(domain, str) and domain.strip()
        }
        if not revoked_domains:
            return []
        reason_text = _normalise_optional_text(reason) or "revoked"
        current_time = observed_at or datetime.now(timezone.utc)
        now_iso = _timestamp(current_time)
        changed: list[SourceRegistryEntry] = []
        for entry in self._entries.values():
            if entry.status is KnowledgeStatus.RAW:
                continue
            if _domain_from_source(entry.source) not in revoked_domains:
                continue
            entry.updated_at = now_iso
            entry.status_reason = reason_text
            entry.evaluation_status = "revoked"
            entry.evaluation_reason = reason_text
            changed.append(entry)
        if changed:
            self._save()
        return sorted(changed, key=lambda item: item.source)

    def entries(self) -> list[SourceRegistryEntry]:
        return sorted(self._entries.values(), key=lambda item: item.source)

    def to_dict(self) -> list[dict[str, object]]:
        return [entry.to_dict() for entry in self.entries()]

    def _load(self) -> dict[str, SourceRegistryEntry]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, list):
            return {}
        entries: dict[str, SourceRegistryEntry] = {}
        for item in data:
            if not isinstance(item, dict):
                continue
            entry = SourceRegistryEntry.from_dict(item)
            if entry.source:
                entries[entry.source] = entry
        return entries

    def _save(self) -> None:
        payload = self.to_dict()
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _coerce_freshness(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _timestamp(value)
    text = str(value).strip()
    return text or None


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _normalise_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalise_optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _normalise_optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _status_rank(status: KnowledgeStatus) -> int:
    return {
        KnowledgeStatus.RAW: 0,
        KnowledgeStatus.VALIDATED: 1,
        KnowledgeStatus.PROMOTED: 2,
    }[status]


def _max_status(left: KnowledgeStatus, right: KnowledgeStatus) -> KnowledgeStatus:
    return left if _status_rank(left) >= _status_rank(right) else right


def _domain_from_source(source: str) -> str | None:
    parsed = urlparse(source)
    hostname = (parsed.hostname or "").strip().lower()
    return hostname or None
