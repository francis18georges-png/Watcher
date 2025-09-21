"""Property-style tests exercising the ``Memory`` storage engine."""

from __future__ import annotations

from typing import Iterable

import pytest

from app.core import memory as memory_module
from app.core.memory import Memory
from app.tools import embeddings
from app.utils import np


def _fake_embedding(texts: Iterable[str], model: str = "nomic-embed-text"):
    """Return deterministic vectors for each input string."""

    vectors = []
    for text in texts:
        seed = sum(ord(ch) for ch in text) or 1
        values = [((seed + offset) % 97) / 97.0 for offset in range(1, 9)]
        vectors.append(np.array(values, dtype=np.float32))
    return vectors


@pytest.fixture(autouse=True)
def patch_embeddings(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_ollama", _fake_embedding)
    monkeypatch.setattr(memory_module, "embed_ollama", _fake_embedding)


def _make_memory(tmp_path):
    mem = Memory(tmp_path / "mem.db")
    mem.set_offline(False)
    return mem


def test_add_and_search_returns_similarity_sorted_results(tmp_path):
    mem = _make_memory(tmp_path)
    mem.add("note", "alpha")
    mem.add("note", "beta")

    results = mem.search("alpha", top_k=2)
    assert [row[3] for row in results] == ["alpha", "beta"]
    assert results[0][0] >= results[1][0]


def test_threshold_enforced_when_no_result_meets_requirement(tmp_path):
    mem = _make_memory(tmp_path)
    mem.add("note", "alpha")

    with pytest.raises(ValueError):
        mem.search("beta", threshold=1.0)


def test_multiple_kinds_can_be_added_and_retrieved(tmp_path):
    mem = _make_memory(tmp_path)
    mem.add("note", "alpha")
    mem.add("memory", "gamma")

    results = mem.search("gamma", top_k=1)
    assert len(results) == 1
    assert results[0][2] == "memory"
    assert results[0][3] == "gamma"
