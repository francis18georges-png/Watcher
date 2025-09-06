from app.llm.client import Client
import app.llm.client as llm_client


def test_long_prompt_is_chunked_and_concatenated(monkeypatch):
    client = Client(ctx=5)

    chunks: list[str] = []

    def fake_generate_ollama(chunk: str, *, host: str, model: str) -> str:
        chunks.append(chunk)
        return chunk.upper()

    monkeypatch.setattr(llm_client, "generate_ollama", fake_generate_ollama)

    prompt = "abcdefghij"  # 10 characters; ctx=5 -> two chunks
    result = client.generate(prompt)

    assert result == "ABCDE FGHIJ"
    assert chunks == ["abcde", "fghij"]
