from app.utils import np
import sqlite3

from app.core.memory import Memory
from app.core.engine import Engine
from types import SimpleNamespace


class _StubCritic:
    def __init__(self, response=None):
        self._response = response

    def suggest(self, prompt: str):
        if callable(self._response):
            return list(self._response(prompt))
        if self._response is None:
            return []
        return list(self._response)


def _configure_engine(eng):
    eng.settings = SimpleNamespace(memory=SimpleNamespace(cache_size=128))

def test_chat_saves_distinct_kinds(tmp_path, monkeypatch):
    # Avoid heavy embedding and network calls
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def generate(self, prompt: str) -> tuple[str, str]:
            return "pong", "dummy-trace"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    _configure_engine(eng)
    eng.client = DummyClient()
    eng.critic = _StubCritic()

    prompt = "please " + "word " * 60 + "thank you"
    answer = eng.chat(prompt)
    assert answer == "pong"

    with sqlite3.connect(tmp_path / "mem.db") as con:
        rows = con.execute("SELECT kind,text FROM items ORDER BY id").fetchall()

    assert rows == [
        ("chat_user", prompt),
        ("chat_ai", "pong"),
        ("trace", "dummy-trace"),
    ]


def test_chat_includes_retrieved_terms(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    _configure_engine(eng)
    eng.critic = _StubCritic()

    def fake_search(self, query: str, top_k: int = 8):
        return [(0.9, 1, "ctx", "alpha beta")]

    monkeypatch.setattr(Memory, "search", fake_search)

    class DummyClient:
        def __init__(self):
            self.prompt = None

        def generate(self, prompt: str) -> tuple[str, str]:
            self.prompt = prompt
            return "pong", "dummy-trace"

    eng.client = DummyClient()

    prompt = "please " + "word " * 60 + "thank you"
    answer = eng.chat(prompt)

    assert answer == "pong"
    assert "alpha beta" in eng.client.prompt
    assert "please" in eng.client.prompt


def test_chat_suggests_details_without_llm(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    class DummyClient:
        def generate(self, prompt: str) -> tuple[str, str]:
            raise AssertionError("LLM should not be called when suggestions exist")

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    _configure_engine(eng)
    eng.client = DummyClient()
    eng.critic = _StubCritic(["detail"])

    answer = eng.chat("ping")
    assert "Voici quelques détails supplémentaires." in answer

    with sqlite3.connect(tmp_path / "mem.db") as con:
        rows = con.execute("SELECT kind,text FROM items ORDER BY id").fetchall()

    assert rows == [
        ("chat_user", "ping"),
        ("chat_ai", answer),
    ]


def test_chat_uses_cache_for_identical_prompts(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt: str) -> tuple[str, str]:
            self.calls += 1
            return "pong", "dummy-trace"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    _configure_engine(eng)
    eng.client = DummyClient()
    eng.critic = _StubCritic()

    prompt = "please " + "word " * 60 + "thank you"

    first = eng.chat(prompt)
    second = eng.chat(prompt)

    assert first == second == "pong"
    assert eng.client.calls == 1


def test_chat_evicts_least_recent(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def __init__(self):
            self.calls = []

        def generate(self, prompt: str) -> tuple[str, str]:
            self.calls.append(prompt)
            return "pong", "dummy-trace"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    _configure_engine(eng)
    eng.client = DummyClient()
    eng.critic = _StubCritic()
    eng._cache_size = 2

    def make_prompt(tag: str) -> str:
        return "please " + "word " * 60 + f"{tag} thank you"

    p1, p2, p3 = make_prompt("one"), make_prompt("two"), make_prompt("three")

    eng.chat(p1)
    eng.chat(p2)
    eng.chat(p3)
    eng.chat(p2)
    eng.chat(p1)

    assert eng.client.calls.count(p1) == 2
    assert eng.client.calls.count(p2) == 1
    assert eng.client.calls.count(p3) == 1
    assert p3 not in eng._cache


def test_chat_respects_offline_mode(tmp_path, monkeypatch):
    def fake_embed(texts, model="nomic-embed-text"):
        return [np.array([1.0])]

    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)
    monkeypatch.setattr(Memory, "search", lambda self, q, top_k=8: [])

    class DummyClient:
        def __init__(self) -> None:
            self.calls = 0
            self.fallback_phrase = "Offline"

        def generate(self, prompt: str) -> tuple[str, str]:
            self.calls += 1
            return "pong", "dummy-trace"

    eng = Engine.__new__(Engine)
    eng.mem = Memory(tmp_path / "mem.db")
    _configure_engine(eng)
    eng.client = DummyClient()
    eng.critic = _StubCritic()
    eng.set_offline_mode(True)

    answer = eng.chat("hello there")

    assert eng.client.calls == 0
    assert answer.startswith("Offline: ")
