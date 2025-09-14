"""Utilities for working with embeddings.

If the embedding backend cannot be reached, the helper below returns a zero
vector (``np.zeros(1, dtype=np.float32)``) for each requested text. This
disables vector search but allows the application to continue running.
"""

import http.client
import json
import logging
from urllib.parse import urlparse

from app.utils import np

from config import load_config


def embed_ollama(
    texts: list[str],
    model: str | None = None,
    host: str | None = None,
) -> list[np.ndarray]:
    """Generate embeddings for the given texts via an Ollama server.

    Parameters
    ----------
    texts:
        List of strings to embed.
    model:
        Name of the embedding model served by Ollama. If omitted, the value is
        read from ``config/settings.toml``.
    host:
        Hostname (and optional port) of the Ollama server. If omitted, the
        value is read from ``config/settings.toml``.

    Returns
    -------
    list[np.ndarray]
        A list of embedding vectors corresponding to ``texts``. Each vector is
        a ``numpy.ndarray`` of ``float32``. If the Ollama backend cannot be
        reached, a list of zero vectors of shape ``(1,)`` is returned instead.
    """

    cfg = load_config().get("memory", {})

    if model is not None:
        cfg["embed_model"] = model
    if host is not None:
        cfg["embed_host"] = host

    model = cfg.get("embed_model", "nomic-embed-text")
    host = cfg.get("embed_host", "127.0.0.1:11434")

    parsed = urlparse(host if "://" in host else f"http://{host}")

    conn = None
    try:
        conn = http.client.HTTPConnection(
            parsed.hostname or "127.0.0.1", parsed.port or 11434, timeout=30
        )
        payload = json.dumps({"model": model, "input": texts})
        conn.request(
            "POST",
            "/api/embeddings",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"Embedding request failed: {resp.status}")
        data = json.loads(resp.read())
        return [np.array(v, dtype=np.float32) for v in data["embeddings"]]
    except Exception as exc:  # pragma: no cover - network
        logging.getLogger(__name__).warning("Embedding backend unreachable: %s", exc)
        return [np.zeros(1, dtype=np.float32) for _ in texts]
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
