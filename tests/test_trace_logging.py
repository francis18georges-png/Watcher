from app.utils import np
import sqlite3

from app.core.memory import Memory
from app.core.engine import Engine
from app.core.critic import Critic


def test_trace_stored_in_memory(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def generate(self, prompt: str):
            return "pong", "trace-steps"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.mem.set_offline(False)
    eng.client = DummyClient()
    eng.critic = Critic()

    prompt = "please " + "word " * 60 + "thank you"
    answer = eng.chat(prompt)
    assert answer == "pong"

    with sqlite3.connect(tmp_path / "mem.db") as con:
        rows = con.execute("SELECT kind,text FROM items ORDER BY id").fetchall()

    assert rows == [
        ("chat_user", prompt),
        ("chat_ai", "pong"),
        ("trace", "trace-steps"),
    ]
