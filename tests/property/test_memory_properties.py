"""Property-based tests for :mod:`app.core.memory`."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from app.core.memory import Memory
from app.utils import np


PRINTABLE_TEXT = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126, blacklist_characters=["\n"]),
    min_size=1,
    max_size=40,
)


def _fake_embedding(text: str) -> np.ndarray:
    """Return a deterministic embedding vector for ``text``."""

    length = (len(text) % 5) + 1
    return np.arange(length, dtype=np.float32)


@given(st.lists(PRINTABLE_TEXT, min_size=1, max_size=5))
@settings(max_examples=25, deadline=None)
def test_add_persists_embedding_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, texts: list[str]
) -> None:
    """Adding items should store embeddings with the expected dimensionality."""

    def fake_embed(texts_to_embed: list[str], model: str = "nomic-embed-text"):
        return [_fake_embedding(text) for text in texts_to_embed]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    db_path = tmp_path / "memory.db"
    memory = Memory(db_path)
    memory.set_offline(False)

    for text in texts:
        memory.add("note", text)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT text, vec FROM items WHERE kind=? ORDER BY ts ASC",
            ("note",),
        ).fetchall()

    assert len(rows) == len(texts)
    for stored_text, blob in rows:
        vector = np.frombuffer(blob, dtype=np.float32)
        expected = _fake_embedding(stored_text)
        assert vector.shape == expected.shape
        assert vector.dtype == np.float32


@given(
    st.lists(PRINTABLE_TEXT, min_size=1, max_size=10),
    st.integers(min_value=1, max_value=5),
)
@settings(max_examples=25, deadline=None)
def test_summarize_limits_history_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    texts: list[str],
    max_items: int,
) -> None:
    """Summaries keep history bounded and stable across repeated calls."""

    def fake_embed(texts_to_embed: list[str], model: str = "nomic-embed-text"):
        return [_fake_embedding(text) for text in texts_to_embed]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    db_path = tmp_path / "memory.db"
    memory = Memory(db_path)
    memory.set_offline(False)

    for text in texts:
        memory.add("kind", text)

    memory.summarize("kind", max_items)

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT text, ts FROM items WHERE kind=? ORDER BY ts ASC",
            ("kind",),
        ).fetchall()

    if len(texts) <= max_items:
        assert [text for text, _ in rows] == texts
    else:
        assert len(rows) == max_items
        oldest_count = len(texts) - max_items + 1
        expected_summary = " ".join(texts[:oldest_count])
        if len(expected_summary) > 200:
            expected_summary = expected_summary[:197] + "..."
        summary_text = rows[-1][0]
        assert summary_text == expected_summary

    memory.summarize("kind", max_items)

    with sqlite3.connect(db_path) as connection:
        rows_again = connection.execute(
            "SELECT text, ts FROM items WHERE kind=? ORDER BY ts ASC",
            ("kind",),
        ).fetchall()

    assert rows_again == rows
