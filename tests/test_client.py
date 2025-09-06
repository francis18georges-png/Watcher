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
