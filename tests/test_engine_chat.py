import numpy as np
import sqlite3

from app.core.memory import Memory
from app.core.engine import Engine


def test_chat_saves_distinct_kinds(tmp_path, monkeypatch):
    # Avoid heavy embedding and network calls
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def generate(self, prompt: str) -> str:
            return "pong"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()

    answer = eng.chat("ping")
    assert answer.startswith("pong")
    assert "Merci." in answer

    with sqlite3.connect(tmp_path / "mem.db") as con:
        rows = con.execute("SELECT kind,text FROM items ORDER BY id").fetchall()

    assert rows[0] == ("chat_user", "ping")
    assert rows[1][0] == "chat_ai"
    assert "pong" in rows[1][1]
    assert "Merci." in rows[1][1]


def test_chat_includes_retrieved_terms(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")

    def fake_search(self, query: str, top_k: int = 8):
        return [(0.9, 1, "ctx", "alpha beta")]

    monkeypatch.setattr(Memory, "search", fake_search)

    class DummyClient:
        def __init__(self):
            self.prompt = None

        def generate(self, prompt: str) -> str:
            self.prompt = prompt
            return "pong"

    eng.client = DummyClient()

    answer = eng.chat("ping")

    assert answer.startswith("pong")
    assert "Merci." in answer
    assert "alpha beta" in eng.client.prompt
    assert "ping" in eng.client.prompt
