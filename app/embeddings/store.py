\"\"\"
Simple embeddings store abstraction (local FAISS-like example).
- wraps encoder function (can be OpenAI / local model)
- persists vector index + metadata
\"\"\"
from __future__ import annotations
import pickle
from pathlib import Path
from typing import Any

import numpy as np

# Placeholder: replace with real encoder (OpenAI, sentence-transformers, etc.)
def fake_encoder(texts: list[str]) -> np.ndarray:
    return np.vstack([[float(len(t) % 512)] * 64 for t in texts]).astype("float32")

class SimpleVectorStore:
    def __init__(self, path: str = "metrics/vecstore"):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.index_path = self.path / "index.npy"
        self.meta_path = self.path / "meta.pkl"
        if self.index_path.exists():
            self.vectors = np.load(self.index_path)
            with open(self.meta_path, "rb") as f:
                self.meta = pickle.load(f)
        else:
            self.vectors = np.zeros((0, 64), dtype="float32")
            self.meta = []

    def add(self, texts: list[str], metas: list[dict[str, Any]]):
        emb = fake_encoder(texts)
        self.vectors = np.vstack([self.vectors, emb])
        self.meta.extend(metas)
        np.save(self.index_path, self.vectors)
        with open(self.meta_path, "wb") as f:
            pickle.dump(self.meta, f)

    def search(self, query: str, k: int = 5):
        if self.vectors.shape[0] == 0:
            return []
        qv = fake_encoder([query])[0]
        dists = np.linalg.norm(self.vectors - qv, axis=1)
        idx = np.argsort(dists)[:k].tolist()
        return [(self.meta[i], float(dists[i])) for i in idx]
