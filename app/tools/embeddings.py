"""Utilities for working with embeddings.

These helpers first try to contact an Ollama server. When unavailable, a local
SentenceTransformer model is used instead, ensuring the application keeps its
retrieval capabilities offline.
"""

from __future__ import annotations

import http.client
import json
import logging
import threading
from urllib.parse import urlparse

from app.utils import np

from config import get_settings

try:  # pragma: no cover - optional dependency
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional dependency
    SentenceTransformer = None  # type: ignore[assignment]


class _LocalEncoder:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._model: SentenceTransformer | None = None

    def _load(self) -> SentenceTransformer:
        if SentenceTransformer is None:  # pragma: no cover - dependency missing
            raise RuntimeError(
                "sentence-transformers est requis pour l'embedding local."
            )
        with self._lock:
            if self._model is None:
                settings = get_settings()
                mem_cfg = settings.memory
                model_path = settings.paths.resolve(mem_cfg.embed_model_path)
                if model_path.exists():
                    self._model = SentenceTransformer(
                        str(model_path), trust_remote_code=False
                    )
                else:
                    model_path.parent.mkdir(parents=True, exist_ok=True)
                    self._model = SentenceTransformer(
                        mem_cfg.embed_model,
                        cache_folder=str(model_path.parent),
                        trust_remote_code=False,
                    )
        return self._model

    def encode(self, texts: list[str]) -> list[np.ndarray]:
        model = self._load()
        vectors = model.encode(
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            device="cpu",
        )
        return [np.asarray(vec, dtype=np.float32) for vec in vectors]


_ENCODER = _LocalEncoder()


def embed_local(texts: list[str]) -> list[np.ndarray]:
    """Embed ``texts`` using the local SentenceTransformer model."""

    if not texts:
        return []
    return _ENCODER.encode(texts)


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
    scheme = (parsed.scheme or "http").lower()
    if scheme == "https":
        conn_cls = http.client.HTTPSConnection
        default_port = 443
    else:
        conn_cls = http.client.HTTPConnection
        default_port = 11434

    conn = None
    try:
        conn = conn_cls(
            parsed.hostname or "127.0.0.1",
            parsed.port or default_port,
            timeout=30,
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
        return embed_local(texts)
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
