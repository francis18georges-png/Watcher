import sqlite3
import numpy as np

from app.core.memory import Memory
from app.core.engine import Engine
from app.core.critic import Critic
from app.core.reasoning import ReasoningChain


def test_chat_records_reasoning(tmp_path, monkeypatch):
    """Engine.chat should append reasoning steps and persist them when provided."""

    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])
    monkeypatch.setattr(Critic, "suggest", lambda self, prompt: [])

    class DummyClient:
        def generate(self, prompt: str) -> tuple[str, str]:
            return "pong", "dummy-trace"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()
    eng.critic = Critic()

    chain = ReasoningChain()
    answer = eng.chat("ping", reasoning=chain)

    assert answer == "pong"
    assert chain.steps[0].startswith("prompt: ping")
    assert chain.steps[-1].startswith("answer: pong")

    with sqlite3.connect(tmp_path / "mem.db") as con:
        rows = con.execute("SELECT kind,text FROM items ORDER BY id").fetchall()

    assert ("reasoning", chain.to_text()) in rows

    loaded = ReasoningChain.from_memory(eng.mem)
    assert loaded.steps == chain.steps
