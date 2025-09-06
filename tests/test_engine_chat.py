import numpy as np
import sqlite3
import pytest

from app.core.memory import Memory
from app.core.engine import Engine


def test_chat_saves_distinct_kinds(tmp_path, monkeypatch):
    # Avoid heavy embedding and network calls
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    class DummyClient:
        def generate(self, prompt: str) -> str:
            return "pong"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()

    answer = eng.chat("ping")
    assert answer == "pong"

    with sqlite3.connect(tmp_path / "mem.db") as con:
        rows = con.execute("SELECT kind,text FROM items ORDER BY id").fetchall()

    assert rows == [("chat_user", "ping"), ("chat_ai", "pong")]


def test_chat_rejects_empty_prompt(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    class DummyClient:
        def generate(self, prompt: str) -> str:  # pragma: no cover - should not run
            raise AssertionError("generate should not be called")

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()

    with pytest.raises(ValueError):
        eng.chat("   ")
