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

from config import get_settings


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

    # Copy the memory configuration to avoid mutating the cached config
    settings = get_settings()
    memory_cfg = settings.memory

    model = model or memory_cfg.embed_model
    host = host or memory_cfg.embed_host

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
        logger = logging.getLogger(__name__)
        if getattr(logger, "disabled", False):
            try:
                logger.disabled = False
            except Exception:
                pass
        logger.warning("Embedding backend unreachable: %s", exc)
        root_logger = logging.getLogger()
        if getattr(root_logger, "disabled", False):
            try:
                root_logger.disabled = False
            except Exception:
                pass
        root_logger.warning("Embedding backend unreachable: %s", exc)
        return [np.zeros(1, dtype=np.float32) for _ in texts]
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
