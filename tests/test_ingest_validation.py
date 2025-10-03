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
    assert metas[0]["licence"] == "CC-BY-4.0"
    assert metas[0]["url"] in {"https://example.com/a", "https://example.com/c"}
