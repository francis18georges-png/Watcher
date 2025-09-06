from app.llm.client import Client


def test_generate_joins_chunks_without_extra_whitespace_trailing(monkeypatch):
    chunks = ["Hello ", "world"]

    def fake_generate_ollama(prompt, *, host, model):
        return chunks

    monkeypatch.setattr("app.llm.client.generate_ollama", fake_generate_ollama)
    client = Client()
    answer, _ = client.generate("greet")
    assert answer == "".join(chunks)


def test_generate_joins_chunks_without_extra_whitespace_leading(monkeypatch):
    chunks = ["Hello", " world"]

    def fake_generate_ollama(prompt, *, host, model):
        return chunks

    monkeypatch.setattr("app.llm.client.generate_ollama", fake_generate_ollama)
    client = Client()
    answer, _ = client.generate("greet")
    assert answer == "".join(chunks)
