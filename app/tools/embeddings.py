"""Utilities for working with embeddings.

If the embedding backend cannot be reached, the helper below returns a zero
vector (``np.zeros(1, dtype=np.float32)``) for each requested text. This
disables vector search but allows the application to continue running.
"""

import http.client
import json

import numpy as np


def embed_ollama(texts, model: str = "nomic-embed-text"):
    conn = None
    try:
        conn = http.client.HTTPConnection("127.0.0.1", 11434, timeout=30)
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
    except Exception:  # pragma: no cover - network
        return [np.zeros(1, dtype=np.float32) for _ in texts]
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # pragma: no cover - defensive
                pass
