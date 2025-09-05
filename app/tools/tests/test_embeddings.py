import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.append(str(Path(__file__).resolve().parents[3]))
sys.modules.setdefault("numpy", SimpleNamespace(array=lambda *_, **__: None))
from app.tools.embeddings import embed_ollama


def test_embed_ollama_connection_failure():
    with mock.patch(
        "app.tools.embeddings.http.client.HTTPConnection",
        side_effect=OSError("fail"),
    ):
        with pytest.raises(RuntimeError):
            embed_ollama(["test"])
