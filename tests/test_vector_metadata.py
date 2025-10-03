from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.ingest import IngestPipeline, RawDocument


class DummyStore:
    def __init__(self) -> None:
        self.add_calls: list[tuple[list[str], list[dict[str, object]]]] = []

    def add(self, texts, metas) -> None:  # pragma: no cover - exercised in tests
        self.add_calls.append((list(texts), list(metas)))


def test_metadata_contains_required_fields_with_score() -> None:
    store = DummyStore()
    pipeline = IngestPipeline(store)

    docs = [
        RawDocument(
            url="https://example.org/a",
            title="Titre A",
            text="Corroboration\n\n multi source",
            licence="CC-BY-4.0",
            published_at=datetime(2024, 1, 3, tzinfo=timezone.utc),
        ),
        RawDocument(
            url="https://example.net/b",
            title="Titre B",
            text="Corroboration   multi    source",
            licence="CC-BY-4.0",
            published_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        ),
    ]

    count = pipeline.ingest(docs)

    assert count == 1
    assert len(store.add_calls) == 1
    texts, metas = store.add_calls[0]
    assert texts == ["Corroboration multi source"]
    assert len(metas) == 1
    metadata = metas[0]
    digest = hashlib.sha256("Corroboration multi source".encode("utf-8")).hexdigest()
    assert metadata == {
        "url": "https://example.net/b",
        "title": "Titre B",
        "licence": "CC-BY-4.0",
        "hash": digest,
        "score": 0.6,
        "date": datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat(),
    }
