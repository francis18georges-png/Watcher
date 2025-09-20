from types import SimpleNamespace

from app.core.engine import Engine
from app.llm.client import Client


def test_client_fallback_echo() -> None:
    client = Client()
    answer, trace = client.generate("salut")
    assert answer == "Echo: salut"
    assert "fallback" in trace


def test_client_custom_fallback() -> None:
    client = Client(fallback_phrase="Offline")
    answer, trace = client.generate("hi")
    assert answer == "Offline: hi"
    assert "fallback" in trace


def test_engine_set_offline_toggles_client(monkeypatch) -> None:
    calls: list[str] = []

    def fake_generate_ollama(prompt: str, *, host: str, model: str) -> str:
        calls.append(prompt)
        return f"generated:{prompt}"

    monkeypatch.setattr(
        "app.llm.client.generate_ollama", fake_generate_ollama, raising=True
    )

    class DummyMem:
        def __init__(self) -> None:
            self.offline: bool | None = None

        def set_offline(self, offline: bool) -> None:
            self.offline = bool(offline)

    engine = object.__new__(Engine)
    engine.client = Client()
    engine.mem = DummyMem()
    engine.settings = SimpleNamespace(intelligence=SimpleNamespace(mode="online"))
    engine._offline = False

    offline_prompt = "bonjour"
    engine.set_offline(True)
    assert engine.settings.intelligence.mode == "offline"
    assert engine.client._offline is True
    assert engine.mem.offline is True

    offline_answer, offline_trace = engine.client.generate(offline_prompt)
    assert offline_answer == f"Echo: {offline_prompt}"
    assert offline_trace.split(" -> ") == ["offline", "fallback"]
    assert calls == []

    online_prompt = "hola"
    engine.set_offline(False)
    assert engine.settings.intelligence.mode == "online"
    assert engine.client._offline is False
    assert engine.mem.offline is False

    online_answer, online_trace = engine.client.generate(online_prompt)
    assert online_answer == f"generated:{online_prompt}"
    assert "ollama:0" in online_trace.split(" -> ")
    assert online_trace.split(" -> ")[-1] == "success"
    assert calls == [online_prompt]
