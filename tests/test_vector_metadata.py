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
    assert metadata["source"] == "https://example.net/b"
    assert metadata["url"] == "https://example.net/b"
    assert metadata["title"] == "Titre B"
    assert metadata["licence"] == "CC-BY-4.0"
    assert metadata["hash"] == digest
    assert metadata["score"] == 0.6
    assert metadata["confidence_score"] == 0.6
    assert metadata["corroborating_sources"] == 2
    assert metadata["language"] == "unknown"
    assert metadata["domain"] == "example.net"
    assert metadata["knowledge_state"] == "promoted"
    assert metadata["status"] == "promoted"
    assert metadata["source_type"] == "web"
    assert metadata["date"] == datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat()
    assert metadata["freshness_at"] == datetime(2024, 1, 2, tzinfo=timezone.utc).isoformat()


def test_metadata_includes_http_trace_fields_when_available() -> None:
    store = DummyStore()
    pipeline = IngestPipeline(store)
    fetched_at = datetime(2024, 1, 4, tzinfo=timezone.utc)

    docs = [
        RawDocument(
            url="https://example.org/a",
            title="Titre A",
            text="Corroboration multi source",
            licence="CC-BY-4.0",
            fetched_at=fetched_at,
            etag='"abc"',
            last_modified="Wed, 03 Jan 2024 10:00:00 GMT",
        ),
        RawDocument(
            url="https://example.net/b",
            title="Titre B",
            text="Corroboration multi source",
            licence="CC-BY-4.0",
            fetched_at=fetched_at,
            etag='"def"',
            last_modified="Thu, 04 Jan 2024 10:00:00 GMT",
        ),
    ]

    pipeline.ingest(docs)

    metadata = store.add_calls[0][1][0]
    assert metadata["fetched_at"] == fetched_at.isoformat()
    assert metadata["etag"] in {'"abc"', '"def"'}
    assert metadata["last_modified"] in {
        "Wed, 03 Jan 2024 10:00:00 GMT",
        "Thu, 04 Jan 2024 10:00:00 GMT",
    }
