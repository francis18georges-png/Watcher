from app.llm.client import Client


def test_client_fallback_echo() -> None:
    client = Client()
    assert client.generate("salut") == "Echo: salut"
