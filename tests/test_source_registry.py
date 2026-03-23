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
        corroborating_sources=2,
        status_reason="corroborated by 2 distinct domains",
        observed_at=now,
    )
    registry.record(
        source="https://example.com/raw",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.85,
        freshness_at=now,
        licence="CC-BY-4.0",
        corroborating_sources=2,
        status_reason="promoted after evaluation: 2 corroborating domains and age 0 days",
        evaluation_status="promoted",
        evaluation_score=0.85,
        evaluation_reason="promoted after evaluation: 2 corroborating domains and age 0 days",
        observed_at=now,
    )

    entries = registry.entries()

    assert len(entries) == 1
    assert entries[0].status is KnowledgeStatus.PROMOTED
    assert entries[0].confidence == 0.85
    assert entries[0].source_type == "web"
    assert entries[0].freshness_at == "2024-01-01T00:00:00+00:00"
    assert entries[0].corroborating_sources == 2
    assert (
        entries[0].status_reason
        == "promoted after evaluation: 2 corroborating domains and age 0 days"
    )
    assert entries[0].evaluation_status == "promoted"
    assert entries[0].evaluation_score == 0.85
    assert (
        entries[0].evaluation_reason
        == "promoted after evaluation: 2 corroborating domains and age 0 days"
    )


def test_source_registry_does_not_downgrade_reason_or_evidence_on_raw_refresh(tmp_path) -> None:
    registry = SourceRegistry(tmp_path / "source-registry.json")
    first = datetime(2024, 1, 1, tzinfo=timezone.utc)
    second = datetime(2024, 1, 2, tzinfo=timezone.utc)

    registry.record(
        source="https://example.com/promoted",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.9,
        freshness_at=first,
        licence="CC-BY-4.0",
        corroborating_sources=3,
        status_reason="promoted after evaluation: 3 corroborating domains and age 0 days",
        evaluation_status="promoted",
        evaluation_score=0.9,
        evaluation_reason="promoted after evaluation: 3 corroborating domains and age 0 days",
        observed_at=first,
    )
    registry.record(
        source="https://example.com/promoted",
        source_type="web",
        status=KnowledgeStatus.RAW,
        confidence=0.1,
        freshness_at=second,
        licence="CC-BY-4.0",
        status_reason="discovered",
        observed_at=second,
    )

    entry = registry.entries()[0]
    assert entry.status is KnowledgeStatus.PROMOTED
    assert entry.corroborating_sources == 3
    assert (
        entry.status_reason
        == "promoted after evaluation: 3 corroborating domains and age 0 days"
    )
    assert entry.evaluation_status == "promoted"
    assert entry.evaluation_score == 0.9


def test_source_registry_tracks_evaluation_rejection_without_losing_validation(tmp_path) -> None:
    registry = SourceRegistry(tmp_path / "source-registry.json")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    registry.record(
        source="https://example.com/stale",
        source_type="web",
        status=KnowledgeStatus.VALIDATED,
        confidence=0.65,
        freshness_at=now,
        licence="CC-BY-4.0",
        corroborating_sources=2,
        status_reason="rejected by evaluator: content is 400 days old (max 30)",
        evaluation_status="rejected",
        evaluation_score=0.55,
        evaluation_reason="rejected by evaluator: content is 400 days old (max 30)",
        observed_at=now,
    )

    entry = registry.entries()[0]
    assert entry.status is KnowledgeStatus.VALIDATED
    assert entry.evaluation_status == "rejected"
    assert entry.evaluation_score == 0.55
    assert (
        entry.evaluation_reason
        == "rejected by evaluator: content is 400 days old (max 30)"
    )


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
    assert entry.status_reason == "rejected: incompatible licence"
    assert entry.status_note == "rejected: incompatible licence"


def test_source_registry_revokes_matching_domains(tmp_path) -> None:
    registry = SourceRegistry(tmp_path / "source-registry.json")
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)

    registry.record(
        source="https://revoked.test/doc",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.8,
        freshness_at=now,
        licence="CC-BY-4.0",
        evaluation_status="promoted",
        evaluation_score=0.8,
        evaluation_reason="promoted after evaluation",
        observed_at=now,
    )
    registry.record(
        source="https://allowed.test/doc",
        source_type="web",
        status=KnowledgeStatus.PROMOTED,
        confidence=0.8,
        freshness_at=now,
        licence="CC-BY-4.0",
        evaluation_status="promoted",
        evaluation_score=0.8,
        evaluation_reason="promoted after evaluation",
        observed_at=now,
    )

    changed = registry.revoke_domains(
        domains={"revoked.test"},
        reason="revoked by consent ledger",
        observed_at=now,
    )

    assert [entry.source for entry in changed] == ["https://revoked.test/doc"]
    entries = {entry.source: entry for entry in registry.entries()}
    assert entries["https://revoked.test/doc"].evaluation_status == "revoked"
    assert entries["https://revoked.test/doc"].evaluation_reason == "revoked by consent ledger"
    assert entries["https://allowed.test/doc"].evaluation_status == "promoted"
