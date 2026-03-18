"""Minimal source registry for the Phase 1 knowledge flow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

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
    status_note: str | None = None

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
            "status_note": self.status_note,
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
            status_note=_normalise_optional_text(data.get("status_note")),
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
        status_note: str | None = None,
        observed_at: datetime | None = None,
    ) -> SourceRegistryEntry:
        source_key = source.strip()
        if not source_key:
            raise ValueError("source must not be empty")
        current_time = observed_at or datetime.now(timezone.utc)
        now_iso = _timestamp(current_time)
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
                status_note=_normalise_optional_text(status_note),
            )
        else:
            entry.source_type = source_type.strip() or entry.source_type or "web"
            entry.confidence = max(entry.confidence, float(confidence))
            entry.freshness_at = _coerce_freshness(freshness_at) or entry.freshness_at
            entry.licence = _normalise_optional_text(licence) or entry.licence
            entry.status = _max_status(entry.status, status)
            entry.updated_at = now_iso
            entry.status_note = _normalise_optional_text(status_note)
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
        observed_at: datetime | None = None,
    ) -> SourceRegistryEntry:
        """Record a rejected item while keeping it out of validated/promoted states."""

        return self.record(
            source=source,
            source_type=source_type,
            status=KnowledgeStatus.RAW,
            confidence=confidence,
            freshness_at=freshness_at,
            licence=licence,
            status_note=f"rejected: {reason.strip()}",
            observed_at=observed_at,
        )

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


def _max_status(left: KnowledgeStatus, right: KnowledgeStatus) -> KnowledgeStatus:
    order = {
        KnowledgeStatus.RAW: 0,
        KnowledgeStatus.VALIDATED: 1,
        KnowledgeStatus.PROMOTED: 2,
    }
    return left if order[left] >= order[right] else right
