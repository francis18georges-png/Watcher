"""Regression tests for the engine offline mode integration."""

import socket
from types import SimpleNamespace

import pytest
from pytest_socket import SocketBlockedError

from config import get_settings

from app.core.engine import Engine
from app.core.memory import Memory
from app.utils import np


def test_engine_offline_skips_embedding_calls(monkeypatch, tmp_path):
    calls = {"count": 0}

    def fake_embed(texts, model=None, host=None):  # noqa: ARG001
        calls["count"] += 1
        return [np.ones(1, dtype=np.float32)]

    monkeypatch.setattr("app.tools.embeddings.embed_ollama", fake_embed)
    monkeypatch.setattr("app.core.memory.embed_ollama", fake_embed)

    engine = Engine.__new__(Engine)
    engine.settings = get_settings()
    engine.mem = Memory(tmp_path / "mem.db")
    engine.client = SimpleNamespace(set_offline=lambda _offline: None)

    engine.set_offline(True)
    engine.mem.add("note", "bonjour")

    vec = engine.mem._embed("salut")

    assert calls["count"] == 0
    assert np.array_equal(vec, np.zeros(1, dtype=np.float32))


def test_engine_offline_blocks_network(tmp_path):
    engine = Engine.__new__(Engine)
    engine.settings = get_settings()
    engine.mem = Memory(tmp_path / "mem_offline_network.db")
    engine.client = SimpleNamespace(set_offline=lambda _offline: None)

    engine.set_offline(True)

    with pytest.raises(SocketBlockedError):
        socket.create_connection(("example.com", 80), timeout=0.1)
