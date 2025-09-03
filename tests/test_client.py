import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.llm.client import Client


def test_client_fallback_echo() -> None:
    client = Client()
    assert client.generate("salut") == "Echo: salut"

