import numpy as np

from app.core.critic import suggest
from app.core.engine import Engine
from app.core.memory import Memory


def test_suggest_returns_plan_for_short_impolite_answer():
    plan = suggest("question", "ok")
    assert "politesse" in plan.lower()
    assert "détail" in plan.lower()


def test_engine_applies_suggestions(tmp_path, monkeypatch):
    # Avoid heavy embedding calls
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def generate(self, prompt: str) -> str:
            return "ok"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()

    answer = eng.chat("ping")
    assert "Merci." in answer
    assert "détails" in answer
