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


def test_client_cache_and_stream() -> None:
    client = Client()
    answer1, trace1 = client.generate("hi")
    answer2, trace2 = client.generate("hi")
    assert answer1 == answer2
    assert trace2 == "cache"
    tokens = list(client.generate_stream("hi"))
    assert "hi" in " ".join(tokens)
