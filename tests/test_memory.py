import types
import sys
import math
import struct
import pathlib
import sqlite3

# Create a minimal numpy stub to avoid dependency
class _Vector:
    def __init__(self, values):
        self.values = [float(v) for v in values]
    def astype(self, dtype):
        return self
    def tobytes(self):
        return struct.pack(f"{len(self.values)}f", *self.values)
    def __matmul__(self, other):
        return sum(a * b for a, b in zip(self.values, other.values))
    @property
    def size(self):
        return len(self.values)
    def __iter__(self):
        return iter(self.values)
    def tolist(self):
        return list(self.values)


def _array(values, dtype=None):
    return _Vector(values)


def _frombuffer(buf, dtype=None):
    n = len(buf) // 4
    return _Vector(struct.unpack(f"{n}f", buf))


def _norm(vec):
    return math.sqrt(sum(v * v for v in vec))


np_stub = types.SimpleNamespace(
    array=_array,
    frombuffer=_frombuffer,
    float32="float32",
    linalg=types.SimpleNamespace(norm=_norm),
)

sys.modules.setdefault("numpy", np_stub)
import numpy as np  # type: ignore

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.core.memory import Memory


def test_add_and_search(tmp_path, monkeypatch):
    def fake_embed(texts):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.add("note", "salut")

    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT kind,text,vec FROM items").fetchone()
    assert row[0] == "note"
    assert row[1] == "salut"
    assert np.frombuffer(row[2], dtype=np.float32).tolist() == [1.0]

    results = mem.search("salut")
    assert len(results) == 1
    assert results[0][2] == "note"
    assert results[0][3] == "salut"


def test_search_embedding_error(tmp_path, monkeypatch):
    def good_embed(texts):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", good_embed)
    db_path = tmp_path / "mem.db"
    mem = Memory(db_path)
    mem.add("note", "bonjour")

    def bad_embed(texts):
        raise RuntimeError("fail")

    monkeypatch.setattr("app.core.memory.embed_ollama", bad_embed)
    assert mem.search("bonjour") == []
