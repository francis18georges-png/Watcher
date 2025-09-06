import numpy as np

from app.core.engine import Engine
from app.core.memory import Memory


def test_chat_retries_on_low_score(tmp_path, monkeypatch):
    """Engine.chat should retry generation when critic gives low score."""

    # Avoid heavy embedding calls
    monkeypatch.setattr("app.core.memory.embed_ollama", lambda texts, model="": [np.array([1.0])])

    # Track generate calls and provide different answers per attempt
    calls = {"count": 0}

    class DummyClient:
        def generate(self, prompt: str) -> str:
            calls["count"] += 1
            return "bad" if calls["count"] == 1 else "good"

    # Critic returns low then high score
    def fake_review(prompt, answer):
        return 0.0 if answer == "bad" else 1.0

    monkeypatch.setattr("app.core.critic.review", fake_review)

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()

    ans = eng.chat("ping", threshold=0.5)

    assert ans == "good"
    assert calls["count"] == 2


def test_chat_accepts_high_score(tmp_path, monkeypatch):
    """When critic approves, only one generation should occur."""

    monkeypatch.setattr("app.core.memory.embed_ollama", lambda texts, model="": [np.array([1.0])])

    calls = {"count": 0}

    class DummyClient:
        def generate(self, prompt: str) -> str:
            calls["count"] += 1
            return "fine"

    def fake_review(prompt, answer):
        return 1.0

    monkeypatch.setattr("app.core.critic.review", fake_review)

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    eng.client = DummyClient()

    ans = eng.chat("ping")

    assert ans == "fine"
    assert calls["count"] == 1
