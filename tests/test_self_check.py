import numpy as np

from app.core.engine import Engine
from app.core.memory import Memory


def test_self_check_reports_arithmetic_error(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def generate(self, prompt: str) -> str:
            return "5"  # wrong on purpose

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()
    eng.last_check = ""

    answer = eng.chat("Combien font 2 + 2 ?")

    assert answer == "5"
    assert eng.last_check
    assert "4" in eng.last_check
