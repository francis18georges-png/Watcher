from app.llm.client import Client


def test_client_fallback_echo() -> None:
    client = Client()
    assert client.generate("salut") == "Echo: salut"


def test_client_custom_fallback() -> None:
    client = Client(fallback_phrase="Offline")
    assert client.generate("hi") == "Offline: hi"
