from __future__ import annotations

from datetime import datetime, timezone

from app.ingest import KnowledgeStatus, SourceRegistry


def test_source_registry_tracks_progressive_statuses(tmp_path) -> None:
    registry = SourceRegistry(tmp_path / "source-registry.json")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    registry.record(
        source="https://example.com/raw",
        source_type="web",
        status=KnowledgeStatus.RAW,
        confidence=0.1,
        freshness_at=now,
        licence="CC-BY-4.0",
        observed_at=now,
    )
    registry.record(
        source="https://example.com/raw",
        source_type="web",
        status=KnowledgeStatus.VALIDATED,
        confidence=0.8,
        freshness_at=now,
        licence="CC-BY-4.0",
        observed_at=now,
    )
    registry.record(
        source="https://example.com/raw",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.9,
        freshness_at=now,
        licence="CC-BY-4.0",
        observed_at=now,
    )

    entries = registry.entries()

    assert len(entries) == 1
    assert entries[0].status is KnowledgeStatus.PROMOTED
    assert entries[0].confidence == 0.9
    assert entries[0].source_type == "web"
    assert entries[0].freshness_at == "2024-01-01T00:00:00+00:00"


def test_source_registry_rejection_keeps_item_in_raw_state(tmp_path) -> None:
    registry = SourceRegistry(tmp_path / "source-registry.json")

    registry.reject(
        source="https://example.com/rejected",
        source_type="web",
        reason="incompatible licence",
        licence="ARR",
    )

    entry = registry.entries()[0]
    assert entry.status is KnowledgeStatus.RAW
    assert entry.status_note == "rejected: incompatible licence"
