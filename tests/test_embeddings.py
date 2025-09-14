import logging

from app.tools.embeddings import embed_ollama
from config import load_config


def test_embed_ollama_connection_error(monkeypatch):
    def bad_conn(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    vecs = embed_ollama(["hello"], host="1.2.3.4:5678")
    assert len(vecs) == 1
    assert len(vecs[0]) == 1
    assert vecs[0].shape == (1,)
    assert vecs[0][0] == 0.0


def test_embed_ollama_logs_warning(monkeypatch, caplog):
    def bad_conn(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    with caplog.at_level(logging.WARNING):
        embed_ollama(["hello"], host="1.2.3.4:5678")
    assert (
        "app.tools.embeddings",
        logging.WARNING,
        "Embedding backend unreachable: fail",
    ) in caplog.record_tuples


def test_embed_ollama_host_argument(monkeypatch):
    called = {}

    def bad_conn(host, port, *args, **kwargs):
        called["host"] = host
        called["port"] = port
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    embed_ollama(["hi"], host="example.com:1234")
    assert called == {"host": "example.com", "port": 1234}


def test_embed_ollama_host_from_config(monkeypatch):
    def fake_config():
        return {"memory": {"embed_host": "confighost:4242"}}

    called = {}

    def bad_conn(host, port, *args, **kwargs):
        called["host"] = host
        called["port"] = port
        raise OSError("fail")

    monkeypatch.setattr("app.tools.embeddings.load_config", fake_config)
    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    embed_ollama(["hi"])
    assert called == {"host": "confighost", "port": 4242}


def test_embed_ollama_warning_logged(monkeypatch):
    def bad_conn(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)

    class StubLogger:
        def __init__(self):
            self.messages = []

        def warning(self, msg, exc):
            self.messages.append(msg % exc)

    stub = StubLogger()
    original_get_logger = logging.getLogger

    def fake_get_logger(name=None, *args, **kwargs):
        if name == "app.tools.embeddings":
            return stub
        return original_get_logger(name, *args, **kwargs)

    monkeypatch.setattr("app.tools.embeddings.logging.getLogger", fake_get_logger)

    embed_ollama(["hello"], host="1.2.3.4:5678")

    assert stub.messages == ["Embedding backend unreachable: fail"]


def test_embed_ollama_does_not_mutate_config(monkeypatch):
    """Successive calls with overrides leave the cached config unchanged."""

    load_config.cache_clear()
    original_memory = load_config()["memory"].copy()

    def bad_conn(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)

    embed_ollama(["hi"], model="foo", host="example.com:1234")
    assert load_config()["memory"] == original_memory

    embed_ollama(["hi"], model="bar", host="another.com:5678")
    assert load_config()["memory"] == original_memory
