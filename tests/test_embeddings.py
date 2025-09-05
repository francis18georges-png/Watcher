import numpy as np  # type: ignore

from app.tools.embeddings import embed_ollama


def test_embed_ollama_connection_error(monkeypatch):
    def bad_conn(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    vecs = embed_ollama(["hello"])
    assert len(vecs) == 1
    assert vecs[0].size == 0
