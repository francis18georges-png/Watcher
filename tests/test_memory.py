import math
import sqlite3

from app.utils import np
import pytest

from app.core.memory import Memory


def test_add_and_search(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.add("note", "salut")

    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT kind,text,vec FROM items").fetchone()
    assert row[0] == "note"
    assert row[1] == "salut"
    vec = np.frombuffer(row[2], dtype=np.float32)
    assert vec.tolist() == [1.0]
    assert len(vec) == 1

    results = mem.search("salut")
    assert len(results) == 1
    assert results[0][2] == "note"
    assert results[0][3] == "salut"


def test_search_embedding_error(tmp_path, monkeypatch):
    def good_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", good_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.add("note", "bonjour")

    def bad_embed(texts, model="nomic-embed-text"):
        return [np.array([], dtype=np.float32)]

    monkeypatch.setattr("app.core.memory.embed_ollama", bad_embed)
    assert mem.search("bonjour") == []


def test_search_respects_threshold(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        if fake_embed.calls == 0:
            fake_embed.calls += 1
            return [np.array([1.0, 0.0])]
        return [np.array([0.0, 1.0])]

    fake_embed.calls = 0
    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    mem = Memory(tmp_path / "mem.db")
    mem.add("note", "salut")
    with pytest.raises(ValueError):
        mem.search("salut", threshold=0.5)


def test_search_threshold_checks_top_score(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        mapping = {
            "good": np.array([1.0, 0.0]),
            "bad": np.array([0.1, 1.0]),
        }
        return [mapping[text] for text in texts]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    mem = Memory(tmp_path / "mem.db")
    mem.add("note", "good")
    mem.add("note", "bad")

    results = mem.search("good", top_k=2, threshold=0.5)
    assert len(results) == 2
    assert results[0][0] >= 0.5
    assert results[1][0] < 0.5


def test_cosine_similarity_handles_tiny_denominator():
    tiny = np.array([1e-12], dtype=np.float32)
    blob = tiny.astype("float32").tobytes()
    assert Memory._cosine_similarity(blob, blob) == 0.0


def test_cosine_similarity_regular():
    vec = np.array([1.0], dtype=np.float32)
    blob = vec.tobytes()
    assert math.isclose(Memory._cosine_similarity(blob, blob), 1.0, rel_tol=1e-6)
