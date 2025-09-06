from app.tools.embeddings import embed_ollama


def test_embed_ollama_connection_error(monkeypatch):
    def bad_conn(*args, **kwargs):
        raise OSError("fail")

    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    vecs = embed_ollama(["hello"], host="1.2.3.4:5678")
    assert len(vecs) == 1
    assert len(vecs[0]) == 1
    assert vecs[0].shape == (1,)
    assert vecs[0][0] == 0.0


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
    def fake_load(fh):
        return {"memory": {"embed_host": "confighost:4242"}}

    called = {}

    def bad_conn(host, port, *args, **kwargs):
        called["host"] = host
        called["port"] = port
        raise OSError("fail")

    monkeypatch.setattr("app.tools.embeddings.tomllib.load", fake_load)
    monkeypatch.setattr("http.client.HTTPConnection", bad_conn)
    embed_ollama(["hi"])
    assert called == {"host": "confighost", "port": 4242}
