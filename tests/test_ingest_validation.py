from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.ingest import IngestPipeline, IngestValidationError, RawDocument


class DummyStore:
    def __init__(self) -> None:
        self.add_calls: list[tuple[list[str], list[dict[str, object]]]] = []

    def add(self, texts, metas) -> None:  # pragma: no cover - exercised in tests
        self.add_calls.append((list(texts), list(metas)))


def test_pipeline_requires_multiple_sources() -> None:
    store = DummyStore()
    pipeline = IngestPipeline(store)
    doc = RawDocument(
        url="https://example.com/a",
        title="A",
        text="Contenu singulier",
        licence="CC-BY-4.0",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(IngestValidationError):
        pipeline.ingest([doc])

    assert store.add_calls == []


def test_pipeline_skips_incompatible_licence_and_deduplicates() -> None:
    store = DummyStore()
    pipeline = IngestPipeline(store, allowed_licences={"CC-BY-4.0"})

    base_text = "  Information  corroborée\n\npar plusieurs sources.  "
    docs = [
        RawDocument(
            url="https://example.com/a",
            title="Source A",
            text=base_text,
            licence="CC-BY-4.0",
            published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
        RawDocument(
            url="https://example.com/b",
            title="Source B",
            text=base_text,
            licence="All Rights Reserved",
            published_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ),
        RawDocument(
            url="https://example.com/c",
            title="Source C",
            text=base_text,
            licence="CC-BY-4.0",
            published_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
        ),
    ]

    count = pipeline.ingest(docs)

    assert count == 1
    assert len(store.add_calls) == 1
    texts, metas = store.add_calls[0]
    assert len(texts) == 1
    assert len(metas) == 1
    assert metas[0]["language"] == "unknown"
    assert metas[0]["source_type"] == "web"
    assert metas[0]["source"] in {"https://example.com/a", "https://example.com/c"}
    assert metas[0]["corroborating_sources"] == 2
    assert metas[0]["confidence_score"] >= 0.6
    assert metas[0]["knowledge_state"] == "promoted"
    assert metas[0]["evaluation_basis"] == "multi_source_corroboration"
    assert metas[0]["evaluation_status"] == "promoted"
    assert metas[0]["evaluation_score"] >= 0.6
    assert (
        metas[0]["evaluation_reason"]
        == "promoted after ingesting corroborated content from 2 distinct sources"
    )
    assert metas[0]["validation_reason"] == "corroborated by 2 distinct sources"
    assert (
        metas[0]["promotion_reason"]
        == "promoted after ingesting corroborated content from 2 distinct sources"
    )
    assert metas[0]["status"] == "promoted"
    assert metas[0]["confidence"] >= 0.6
    assert "freshness_at" in metas[0]
    assert metas[0]["domain"] in {"example.com"}
    assert metas[0]["licence"] == "CC-BY-4.0"
    assert metas[0]["url"] in {"https://example.com/a", "https://example.com/c"}


def test_pipeline_uses_overlap_chunking() -> None:
    store = DummyStore()
    pipeline = IngestPipeline(store, chunk_size=4, chunk_overlap=1)
    text = "alpha beta gamma delta epsilon zeta eta"
    docs = [
        RawDocument(
            url="https://example.com/a",
            title="Source A",
            text=text,
            licence="CC-BY-4.0",
        ),
        RawDocument(
            url="https://example.com/b",
            title="Source B",
            text=text,
            licence="CC-BY-4.0",
        ),
    ]

    count = pipeline.ingest(docs)

    assert count == 2
    texts, metas = store.add_calls[0]
    assert texts == [
        "alpha beta gamma delta",
        "delta epsilon zeta eta",
    ]
    assert all(meta["corroborating_sources"] == 2 for meta in metas)


def test_pipeline_handles_mixed_timezone_metadata_when_selecting_source() -> None:
    store = DummyStore()
    pipeline = IngestPipeline(store, allowed_licences={"CC-BY-4.0", "MIT"})
    docs = [
        RawDocument(
            url="https://example.com/a",
            title="Aware source",
            text="Shared corroborated content",
            licence="MIT",
            published_at=datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc),
        ),
        RawDocument(
            url="https://example.com/b",
            title="Naive source",
            text="Shared corroborated content",
            licence="CC-BY-4.0",
            published_at=datetime(2024, 1, 2, 9, 0, 0),
        ),
    ]

    count = pipeline.ingest(docs)

    assert count == 1
    texts, metas = store.add_calls[0]
    assert texts == ["Shared corroborated content"]
    assert metas[0]["source"] == "https://example.com/a"
    assert metas[0]["freshness_at"] == "2024-01-01T09:00:00+00:00"
