import numpy as np
import pytest

from app.core.validation import validate_prompt
from app.core.engine import Engine
from app.core.memory import Memory


def test_validate_prompt_rejects_script() -> None:
    with pytest.raises(ValueError):
        validate_prompt("<script>alert('x')</script>")


def test_engine_chat_rejects_command(tmp_path, monkeypatch) -> None:
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

    with pytest.raises(ValueError):
        eng.chat("rm -rf /")
